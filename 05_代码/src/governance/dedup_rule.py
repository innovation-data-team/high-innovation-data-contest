import numpy as np
import pandas as pd
from simhash import Simhash


def is_missing_text(value):
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def calc_simhash(text):
    """计算文本simhash值（返回64位整数），NaN/None按空串处理。"""
    if is_missing_text(text):
        text = ""
    return Simhash(str(text)).value


# numpy>=2.0 自带按位计数；旧版本用查表兜底
if hasattr(np, "bitwise_count"):
    def _bit_count(arr):
        return np.bitwise_count(arr)
else:
    _LUT = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)

    def _bit_count(arr):
        return _LUT[arr.view(np.uint8)].reshape(-1, 8).sum(axis=1).astype(np.int32)


def run_deduplicate(df_input, threshold=3):
    """
    对过滤后的岗位做simhash近重复分组（只输出真正的重复组，组内保留最长的一条）

    threshold：海明距离阈值，越小越严格
    要求 df_input 已含 simhash 整数列、jd_id 列、jd_content 列
    返回：标记好的DataFrame（group_id / temp_keep）、分组列表
    """
    df_input = df_input.reset_index(drop=True).copy()
    n = len(df_input)
    df_input["group_id"] = ""
    df_input["temp_keep"] = 1
    if n == 0:
        return df_input, []

    values = np.array([int(v) for v in df_input["simhash"].tolist()], dtype=np.uint64)
    lengths = df_input["jd_content"].astype(str).str.len().to_numpy()
    ids = df_input["jd_id"].astype(str).to_numpy()

    used = np.zeros(n, dtype=bool)
    group_ids = [""] * n
    temp_keep = [1] * n
    group_list = []
    group_idx = 0

    for i in range(n):
        if used[i]:
            continue

        # 只向后比较：i 之前的记录要么已被占用，要么距离已超过阈值
        tail_used = used[i + 1:]
        dist = _bit_count(values[i + 1:] ^ values[i])
        cand = np.nonzero((dist <= threshold) & (~tail_used))[0] + i + 1
        if cand.size == 0:
            continue  # 单条记录不成"重复组"

        group_idx += 1
        members = np.concatenate(([i], cand))
        min_dist = int(dist[cand - (i + 1)].min())

        # 组内保留内容最长的那条作为主记录，其余标记丢弃 D06
        order = np.argsort(-lengths[members], kind="stable")
        members = members[order]

        group_no = f"G{group_idx:04d}"
        for j in members:
            group_ids[j] = group_no
        for j in members[1:]:
            temp_keep[j] = 0
        used[members] = True

        member_ids = [ids[j] for j in members]
        group_list.append({
            "group_id": group_no,
            "represent_jd_id": member_ids[0],
            "all_jd_ids": ",".join(member_ids),
            "min_hamming_distance": min_dist,
            "similarity_score": round(1 - min_dist / 64, 4),
            "group_size": len(member_ids),
        })

    df_input["group_id"] = group_ids
    df_input["temp_keep"] = temp_keep
    return df_input, group_list
