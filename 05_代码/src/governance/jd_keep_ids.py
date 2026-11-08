"""
f1 —— 独立产出 01_数据治理/jd_keep_ids.csv（保留 JD 清单）。

自包含：不依赖 governance.py，也不依赖其他产出文件，直接读取
data/raw_data.xlsx 与附录 A/B/C 即可完成治理；额外产出 jd_drop.csv
（被丢弃明细，留痕）。被判定丢弃的行不会进入保留集。

运行：python 05_代码/src/governance/jd_keep_ids.py
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
DROP_CSV = GOV_DIR / "jd_drop.csv"

UNKNOWN_STD_JOB = "STJ_000000"

# ---- 可调阈值（与 governance.py 保持一致）----
TOO_SHORT_CHAR_THRESHOLD = 30
SALARY_MAX_MONTHLY_UPPER = None
LANGUAGE_CN_RATIO_THRESHOLD = 0.5
NON_JOB_AD_KEYWORDS = ("招生", "加盟", "课程招生")


def _load_mapping(path, key_col, val_col):
    df = pd.read_csv(path, dtype=str)
    return dict(zip(
        df[key_col].astype(str).str.strip(),
        df[val_col].astype(str).str.strip(),
    ))


def _clean_text(val):
    return "" if pd.isna(val) else str(val).strip()


def parse_experience(val):
    """经验 -> (min, max)；无经验/不限->(0,0)，10年以上->(10,-1)。"""
    s = "" if pd.isna(val) else str(val).strip()
    if s in ("", "nan", "NaT", "不限", "无经验"):
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


def f1():
    """治理：剔除被丢弃 JD，输出保留集 jd_keep_ids.csv 与丢弃明细 jd_drop.csv。"""
    city_map = _load_mapping(APPENDIX_A, "city_name", "city_code")
    edu_map = _load_mapping(APPENDIX_B, "education_raw", "education_std")
    ind_map = _load_mapping(APPENDIX_C, "business_raw", "industry_code")

    df = _build_text_df()
    df["_smin"] = df["starting_salary"].apply(parse_salary_to_yuan)
    df["_smax"] = df["salary"].apply(parse_salary_to_yuan)

    records, drops = [], []
    for _, r in df.iterrows():
        jd_id = r["_jd_id"]
        if jd_id == "" or jd_id.lower() == "nan":
            continue

        smin, smax = r["_smin"], r["_smax"]
        flags = []
        if (smin is not None and smax is not None and smin > smax) or \
           (smin is not None and smin <= 0) or (smax is not None and smax <= 0) or \
           (SALARY_MAX_MONTHLY_UPPER is not None and (
               (smin is not None and smin > SALARY_MAX_MONTHLY_UPPER) or
               (smax is not None and smax > SALARY_MAX_MONTHLY_UPPER))):
            flags.append("SALARY_ANOMALY")
        quality_flags = "|".join(flags)

        city_raw = _clean_text(r.get("city"))
        bus_raw = _clean_text(r.get("business"))
        edu_raw = _clean_text(r.get("education"))
        emin, emax = parse_experience(r.get("experience"))
        pub = _clean_text(r.get("time"))
        city_code = city_map.get(city_raw, "")
        is_valid = 0 if city_code == "" else 1  # city 非广东/为空 -> is_valid=0

        if r["drop_reason"] is not None:
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
            "salary_min": smin,
            "salary_max": smax,
            "publish_date": pub,
            "is_valid": is_valid,
            "quality_flags": quality_flags,
        })

    out = pd.DataFrame.from_records(records)
    for col in ("experience_min", "experience_max", "salary_min", "salary_max"):
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")

    dup = out["jd_id"].duplicated().sum()
    if dup:
        out = out.drop_duplicates(subset="jd_id", keep="first")

    GOV_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    drop_df = pd.DataFrame(drops, columns=["jd_id", "job_title_raw", "drop_reason"])
    drop_df.to_csv(DROP_CSV, index=False, encoding="utf-8-sig")

    print(f"[f1] 保留 {len(out)} 条 -> {OUTPUT_CSV}")
    print(f"[f1] 丢弃 {len(drop_df)} 条 -> {DROP_CSV}")
    print(f"[f1] is_valid=0（city 空/非广东）: {(out['is_valid'] == 0).sum()}")
    print(f"[f1] 丢弃原因分布: {drop_df['drop_reason'].value_counts().to_dict()}")
    return out


if __name__ == "__main__":
    f1()
