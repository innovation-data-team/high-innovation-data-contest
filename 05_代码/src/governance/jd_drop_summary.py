"""
f2 —— 独立产出 01_数据治理/jd_drop_summary.csv（丢弃原因统计）。

自包含：不依赖 governance.py，也不依赖任何产出文件，直接读取
data/raw_data.xlsx 即完成判定与汇总。每个 JD 按优先级归入单一 drop_reason。

运行：python 05_代码/src/governance/jd_drop_summary.py
"""
from pathlib import Path
from collections import defaultdict
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
GOV_DIR = ROOT / "01_数据治理"

RAW_XLSX = DATA_DIR / "raw_data.xlsx"
OUTPUT_CSV = GOV_DIR / "jd_drop_summary.csv"

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


def f2():
    """统计各丢弃原因，输出 jd_drop_summary.csv。

    注意：city 非广东/为空、salary 异常 不是 drop_reason，分别由
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
    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"[f2] 丢弃汇总 {len(out)} 行 -> {OUTPUT_CSV}")
    for r in order:
        print(f"[f2]   {r}: {cnt.get(r, 0)}")
    return out


if __name__ == "__main__":
    f2()
