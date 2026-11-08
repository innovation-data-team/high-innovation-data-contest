"""
f3 —— 独立产出 01_数据治理/dedup_groups.csv（重复组与保留代表）。

自包含：不依赖 governance.py。默认读取 jd_keep_ids.csv 取得保留集；
若该文件不存在，则用与 f1 完全相同的规则从 data/raw_data.xlsx 现算保留集，
因此单独运行本文件也能产出结果表。

运行：python 05_代码/src/governance/dedup_groups.py
"""
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
GOV_DIR = ROOT / "01_数据治理"

RAW_XLSX = DATA_DIR / "raw_data.xlsx"
KEEP_CSV = GOV_DIR / "jd_keep_ids.csv"
OUTPUT_CSV = GOV_DIR / "dedup_groups.csv"

# ---- 可调阈值（与 governance.py 保持一致）----
TOO_SHORT_CHAR_THRESHOLD = 30
LANGUAGE_CN_RATIO_THRESHOLD = 0.5
NON_JOB_AD_KEYWORDS = ("招生", "加盟", "课程招生")


def _clean_text(val):
    return "" if pd.isna(val) else str(val).strip()


def _chinese_ratio(text):
    """中文占(中文+拉丁字母)比例，忽略数字/标点/空白。"""
    if not text:
        return 1.0
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    denom = cjk + latin
    return 1.0 if denom == 0 else cjk / denom


def _is_non_job_ad(name, body):
    return any(k in name + " " + body for k in NON_JOB_AD_KEYWORDS)


def _is_low_quality(name, body):
    return name == "" or "\ufffd" in body


def _classify_drop(row):
    """丢弃原因（不丢弃返回 None）。优先级：文本质量→重复→非招聘→低质。"""
    body = row["_body"]
    if body == "":
        return "EMPTY_TEXT"
    if _chinese_ratio(body) < LANGUAGE_CN_RATIO_THRESHOLD:
        return "LANGUAGE"
    if len(body) < TOO_SHORT_CHAR_THRESHOLD:
        return "TOO_SHORT"
    if row["_is_dup"]:
        return "DUPLICATE"
    if _is_non_job_ad(row["_name"], body):
        return "NON_JOB_AD"
    if _is_low_quality(row["_name"], body):
        return "LOW_QUALITY"
    return None


def _build_text_df():
    df = pd.read_excel(RAW_XLSX)
    df["_jd_id"] = df["id"].apply(_clean_text)
    df["_name"] = df["name"].apply(_clean_text)
    df["_resp"] = df["responsibility"].apply(_clean_text)
    df["_req"] = df["requirement"].apply(_clean_text)
    df["_body"] = df["_resp"] + df["_req"]
    df["_dupkey"] = (df["_name"] + " " + df["_body"]).str.replace(r"\s+", " ", regex=True).str.strip()
    df["_is_dup"] = df["_dupkey"].duplicated(keep="first")
    df["drop_reason"] = df.apply(_classify_drop, axis=1)
    return df


def _get_keep_set(df):
    """保留集：优先读 jd_keep_ids.csv；缺失时按 f1 同规则自算，保证独立运行。"""
    if KEEP_CSV.exists():
        return set(pd.read_csv(KEEP_CSV, usecols=["jd_id"])["jd_id"].astype(str))
    valid = df[(df["_jd_id"] != "") & (df["_jd_id"].str.lower() != "nan") & (df["drop_reason"].isna())]
    print("[f3] 未找到 jd_keep_ids.csv，已按 f1 规则现算保留集")
    return set(valid["_jd_id"].astype(str))


def f3():
    """EXACT 完全匹配去重分组，输出 dedup_groups.csv。

    同一组首条（存在于保留集）为 kept_jd_id，其余为 dropped_jd_ids；
    dedup_method=EXACT、similarity=1.0。近重复（MinHash/向量）为后续扩展点。
    """
    df = _build_text_df()
    keep_set = _get_keep_set(df)

    groups = []
    gid = 0
    for _, g in df.groupby("_dupkey", sort=False):
        if len(g) < 2:
            continue
        ids = g["_jd_id"].tolist()
        kept = [i for i in ids if i in keep_set]
        dropped = [i for i in ids if i not in keep_set]
        if not kept:
            # 组内无保留代表（首条也因更高优先级原因被丢弃）：
            # kept_jd_id 必须存在于 jd_keep_ids，故跳过该组（孤儿）。
            continue
        gid += 1
        groups.append({
            "dedup_group_id": f"DUP_{gid:06d}",
            "kept_jd_id": kept[0],
            "dropped_jd_ids": "|".join(dropped),
            "dedup_method": "EXACT",
            "similarity": 1.0,
        })

    out = pd.DataFrame(groups, columns=[
        "dedup_group_id", "kept_jd_id", "dropped_jd_ids", "dedup_method", "similarity"])
    GOV_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"[f3] 去重分组 {len(out)} 组 -> {OUTPUT_CSV}")
    return out


if __name__ == "__main__":
    f3()
