"""
数据治理模块：将原始 JD 数据治理为标准化输出 (jd_keep_ids.csv)。

取数映射（依据 04_说明文档/data_dictionary.md）：
  jd_id          <- id
  std_job_id     <- 全部先置 STJ_000000（归一化由 normalization 模块回填）
  job_title_raw  <- name
  city_code      <- city 查附录 A
  industry_code  <- business 查附录 C
  education      <- education 查附录 B
  experience_*/ salary_* / publish_date / is_valid / quality_flags 见下方说明

技能抽取正文来自 responsibility 与 requirement（本模块仅据此计算质量标记，
原始正文不参与输出，下游按 jd_id 关联 raw_data.xlsx 取正文）。
"""

from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
GOV_DIR = ROOT / "01_数据治理"

RAW_XLSX = DATA_DIR / "raw_data.xlsx"
APPENDIX_A = DATA_DIR / "appendix_a_city_code.csv"   # city_name -> city_code
APPENDIX_B = DATA_DIR / "appendix_b_education.csv"   # education_raw -> education_std
APPENDIX_C = DATA_DIR / "appendix_c_industry.csv"    # business_raw -> industry_code
OUTPUT_CSV = GOV_DIR / "jd_keep_ids.csv"
DROP_CSV = GOV_DIR / "jd_drop.csv"          # 被丢弃的 JD 明细（含 drop_reason）

UNKNOWN_STD_JOB = "STJ_000000"

# ---- 可调阈值 ----
TOO_SHORT_CHAR_THRESHOLD = 30      # 正文(responsibility+requirement)合并字符数 < 此值 -> TOO_SHORT
# 薪资异常判定（单位：元/月）。None 表示不启用上限异常，仅检非法/倒置。
SALARY_MAX_MONTHLY_UPPER = None
# ---- 丢弃判定阈值（与 f2 共用）----
LANGUAGE_CN_RATIO_THRESHOLD = 0.5   # 正文中文字符占比低于此值 -> LANGUAGE
# 非招聘广告关键词（招生/加盟等机会类信息，而非招聘）
NON_JOB_AD_KEYWORDS = ("招生", "加盟", "课程招生")

DROP_SUMMARY_CSV = GOV_DIR / "jd_drop_summary.csv"
DEDUP_GROUPS_CSV = GOV_DIR / "dedup_groups.csv"


def _load_mapping(path, key_col, val_col):
    """读取附录 CSV，返回 {key: value}（去空格）。"""
    df = pd.read_csv(path, dtype=str)
    return dict(zip(
        df[key_col].astype(str).str.strip(),
        df[val_col].astype(str).str.strip(),
    ))


def parse_experience(val):
    """解析经验字段 -> (experience_min, experience_max)。

    规则：无经验/不限/空 -> (0, 0)；1-3年->(1,3)；3-5年->(3,5)；
    5-10年->(5,10)；10年以上->(10, -1，上限开放用 -1 哨兵)。
    """
    s = "" if pd.isna(val) else str(val).strip()
    if s in ("", "nan", "NaT", "不限"):
        return 0, 0
    if s == "无经验":
        return 0, 0
    if s == "1-3年":
        return 1, 3
    if s == "3-5年":
        return 3, 5
    if s == "5-10年":
        return 5, 10
    if s == "10年以上":
        return 10, -1
    nums = re.findall(r"\d+", s)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    if len(nums) == 1:
        return int(nums[0]), int(nums[0])
    return 0, 0


def parse_salary_to_yuan(val):
    """千元/月 -> 元/月 整数；缺失/非正返回 None（缺失留空）。"""
    if pd.isna(val):
        return None
    try:
        x = float(val)
    except (TypeError, ValueError):
        return None
    if x <= 0:
        return None
    return int(round(x * 1000))


def _clean_text(val):
    return "" if pd.isna(val) else str(val).strip()


def _classify_drop(row):
    """返回该 JD 的丢弃原因；不丢弃返回 None。优先级：文本质量→重复→非招聘→低质。"""
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
    """读取原始数据，附清洗后的文本列与 drop_reason 列（供 f1/f2 共用）。"""
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


def f1():
    """执行治理：读取原始数据 + 附录，剔除被丢弃的 JD，输出保留集与丢弃集。

    保留集 jd_keep_ids.csv 只含「未丢弃」的行；被丢弃行（依据 f2 同名规则）
    写入 jd_drop.csv 留痕。city 非广东/为空 -> city_code 留空且 is_valid=0。
    """
    city_map = _load_mapping(APPENDIX_A, "city_name", "city_code")
    edu_map = _load_mapping(APPENDIX_B, "education_raw", "education_std")
    ind_map = _load_mapping(APPENDIX_C, "business_raw", "industry_code")

    df = _build_text_df()

    # 薪资先换算为元/月，并保留用于异常判定
    df["_smin"] = df["starting_salary"].apply(parse_salary_to_yuan)
    df["_smax"] = df["salary"].apply(parse_salary_to_yuan)

    records, drops = [], []
    for _, r in df.iterrows():
        jd_id = r["_jd_id"]
        if jd_id == "" or jd_id.lower() == "nan":
            continue  # jd_id 必填，缺失跳过（不入保留集）

        smin, smax = r["_smin"], r["_smax"]

        # 质量标记（保留集中仅可能剩 SALARY_ANOMALY；文本类已判丢弃）
        flags = []
        if (smin is not None and smax is not None and smin > smax) or \
           (smin is not None and smin <= 0) or (smax is not None and smax <= 0) or \
           (SALARY_MAX_MONTHLY_UPPER is not None and (
               (smin is not None and smin > SALARY_MAX_MONTHLY_UPPER) or
               (smax is not None and smax > SALARY_MAX_MONTHLY_UPPER))):
            flags.append("SALARY_ANOMALY")
        quality_flags = "|".join(flags)

        # 字段映射
        city_raw = _clean_text(r.get("city"))
        bus_raw = _clean_text(r.get("business"))
        edu_raw = _clean_text(r.get("education"))
        emin, emax = parse_experience(r.get("experience"))
        pub = _clean_text(r.get("time"))
        city_code = city_map.get(city_raw, "")
        # is_valid：city 非广东/为空 -> 0（文档规定）；保留行其余有效=1
        is_valid = 0 if city_code == "" else 1

        if r["drop_reason"] is not None:
            # 被丢弃：仅入丢弃集，不进保留集
            drops.append({
                "jd_id": jd_id,
                "job_title_raw": _clean_text(r.get("name")),
                "drop_reason": r["drop_reason"],
            })
            continue

        records.append({
            "jd_id": jd_id,
            "std_job_id": UNKNOWN_STD_JOB,
            "job_title_raw": _clean_text(r.get("name")),
            "city_code": city_code,
            "industry_code": ind_map.get(bus_raw, ""),
            "education": edu_map.get(edu_raw, ""),
            "experience_min": emin,
            "experience_max": emax,
            "salary_min": smin,   # 缺失为 None -> 空
            "salary_max": smax,
            "publish_date": pub,
            "is_valid": is_valid,
            "quality_flags": quality_flags,
        })

    out = pd.DataFrame.from_records(records)

    # 整型列转为可空 Int64：缺失写空、有值写整数（不带小数）
    for col in ("experience_min", "experience_max", "salary_min", "salary_max"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    # 防御性去重：jd_id 必为唯一主键（官方清单）
    dup = out["jd_id"].duplicated().sum()
    if dup:
        out = out.drop_duplicates(subset="jd_id", keep="first")

    GOV_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    drop_df = pd.DataFrame(drops, columns=["jd_id", "job_title_raw", "drop_reason"])
    drop_df.to_csv(DROP_CSV, index=False, encoding="utf-8-sig")

    # 诊断信息
    n, nd = len(out), len(drop_df)
    print(f"治理完成：保留 {n} 条 -> {OUTPUT_CSV}；丢弃 {nd} 条 -> {DROP_CSV}")
    print(f"  保留集中 is_valid=0（city 空/非广东）: {(out['is_valid'] == 0).sum()}")
    print(f"  保留集中含 SALARY_ANOMALY: {out['quality_flags'].str.contains('SALARY_ANOMALY', regex=False).sum()}")
    print(f"  丢弃原因分布: {drop_df['drop_reason'].value_counts().to_dict()}")
    print(f"  未映射 industry（留空）: {(out['industry_code'] == '').sum()}")
    print(f"  重复 jd_id 已去重: {dup}")
    return out


def _chinese_ratio(text):
    """正文中文字符占比（CJK / (CJK + 拉丁字母)），忽略数字/标点/空白。

    仅比较“文字脚本”，避免数字、标点稀释占比导致中文正文被误判。
    无任何字母/汉字时返回 1.0（视为无语言问题）。
    """
    if not text:
        return 1.0
    cjk = len(re.findall(r"[一-鿿]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    denom = cjk + latin
    if denom == 0:
        return 1.0
    return cjk / denom


def _is_non_job_ad(name, body):
    text = name + " " + body
    return any(k in text for k in NON_JOB_AD_KEYWORDS)


def _is_low_quality(name, body):
    # 关键字段缺失 / 乱码：岗位名为空，或正文含替换符（mojibake）
    if name == "":
        return True
    if "�" in body:
        return True
    return False


def f2():
    """统计各丢弃原因，输出 jd_drop_summary.csv。

    每个 JD 按优先级归入单一 drop_reason（先判文本质量，再判重复/非招聘/低质）。
    注意：city 非广东或为空、salary 异常 不属于 drop_reason，分别由
    city_code 留空/is_valid=0 与 quality_flags=SALARY_ANOMALY 处理，不在此丢弃。
    """
    df = _build_text_df()

    rule_desc = {
        "EMPTY_TEXT": "responsibility 与 requirement 去空白后均为空（无正文）。",
        "LANGUAGE": f"正文中文(CJK)占(中文+拉丁字母)比例 < {LANGUAGE_CN_RATIO_THRESHOLD}（非中文/中文占比过低，忽略数字标点）。",
        "TOO_SHORT": f"responsibility+requirement 去空白后合并字符数 < {TOO_SHORT_CHAR_THRESHOLD}。",
        "DUPLICATE": "name+正文 归一化（去空白、合并）后完全一致；保留首条，其余判重复。",
        "NON_JOB_AD": f"name 或正文含非招聘关键词（{','.join(NON_JOB_AD_KEYWORDS)}）如招生/加盟，判定为非招聘广告。",
        "LOW_QUALITY": "岗位名 name 为空，或正文含替换符（乱码 mojibake）等明显低质。",
        "OTHER": "其他自定义规则；当前未定义，命中即记 OTHER（本实现暂无）。",
    }
    order = ["EMPTY_TEXT", "LANGUAGE", "TOO_SHORT", "DUPLICATE", "NON_JOB_AD", "LOW_QUALITY", "OTHER"]

    from collections import defaultdict
    cnt = defaultdict(int)
    samp = defaultdict(list)
    for _, r in df.iterrows():
        jd_id = r["_jd_id"]
        if jd_id == "" or jd_id.lower() == "nan":
            continue
        reason = r["drop_reason"]
        if reason is None:
            continue
        cnt[reason] += 1
        if len(samp[reason]) < 20:
            samp[reason].append(jd_id)

    rows = [{
        "drop_reason": r,
        "record_count": cnt.get(r, 0),
        "rule_description": rule_desc[r],
        "sample_jd_ids": "|".join(samp.get(r, [])),
    } for r in order]

    out = pd.DataFrame(rows, columns=["drop_reason", "record_count", "rule_description", "sample_jd_ids"])
    GOV_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(DROP_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    print(f"丢弃汇总：输出 -> {DROP_SUMMARY_CSV}")
    for r in order:
        print(f"  {r}: {cnt.get(r, 0)}")
    return out


def f3():
    """生成去重分组 dedup_groups.csv。

    与 f1/f2 的 DUPLICATE 判定一致，采用 EXACT（name+正文 归一化后完全一致）
    分组：同一组首条（存在于 jd_keep_ids.csv）为 kept_jd_id，其余为被丢弃项。
    dedup_method=EXACT，similarity=1.0。近重复（MinHash/向量）可作为后续扩展。
    """
    df = _build_text_df()
    keep_set = set(pd.read_csv(OUTPUT_CSV, usecols=["jd_id"])["jd_id"].astype(str))

    groups = []
    gid = 0
    for _, g in df.groupby("_dupkey", sort=False):
        if len(g) < 2:
            continue
        ids = g["_jd_id"].tolist()
        kept = [i for i in ids if i in keep_set]
        dropped = [i for i in ids if i not in keep_set]
        if not kept:
            # 组内无保留代表（如首条也因其他更高优先级原因被丢弃），
            # 无法构成合法去重组（kept_jd_id 必须存在于 jd_keep_ids），跳过。
            # 此情况会使去重组丢弃总数略少于 DUPLICATE 丢弃总数（孤儿）。
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
    out.to_csv(DEDUP_GROUPS_CSV, index=False, encoding="utf-8-sig")

    print(f"去重分组：输出 {len(out)} 组 -> {DEDUP_GROUPS_CSV}")
    if len(out):
        print("  示例:", out.iloc[0].to_dict())
    return out


if __name__ == "__main__":
    f1()
    f2()
    f3()
