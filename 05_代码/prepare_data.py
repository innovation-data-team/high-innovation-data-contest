# -*- coding: utf-8 -*-
"""
本地数据准备：把官方原始 xlsx 按 01/02/03 三个阶段的用途切分到 data/ 子目录。

运行方式：
    python 05_代码/prepare_data.py

前置条件：官方原始文件放在 data/ 根目录（不入库、不打包）：
    data/团队预览_5万条.xlsx
    data/数据集字段解释.xlsx

产物（全部在 data/ 下，被 .gitignore 排除，仅供本地复现使用）：
    data/01_数据治理/raw_jd_full.csv        全量 19 列，清洗/去重/字段转换用
    data/01_数据治理/field_dictionary.csv   原始字段解释
    data/02_岗位归一化/jd_job_fields.csv    岗位聚类所需的结构化字段（不含长正文）
    data/03_技能抽取/jd_text_corpus.csv     id + 原始岗位名 + 双正文（技能抽取与证据定位）

注意：所有产物为 UTF-8 无 BOM、RFC 4180；正文含逗号/换行/引号时由 csv 模块自动加引号。
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_JD_FILE = DATA / "团队预览_5万条.xlsx"
FIELD_DICT_FILE = DATA / "数据集字段解释.xlsx"

DIR_01 = DATA / "01_数据治理"
DIR_02 = DATA / "02_岗位归一化"
DIR_03 = DATA / "03_技能抽取"

# 02 阶段：岗位归一化所需的结构化字段（刻意排除 responsibility/requirement 长文本）
COLS_02 = [
    "source_row_index", "id", "name", "address", "province", "city",
    "business", "keyword", "education", "experience",
    "starting_salary", "salary", "time", "count",
    "company", "nature", "scale",
]

# 03 阶段：技能抽取语料，正文必须保留原文以便 evidence_span 能定位
COLS_03 = ["id", "name", "responsibility", "requirement"]


def _require_columns(df: pd.DataFrame, cols: list[str], where: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{where}: 官方原始表缺少字段 {missing}")


def main() -> None:
    if not RAW_JD_FILE.exists():
        raise FileNotFoundError(
            f"Missing raw file: {RAW_JD_FILE}\n"
            "Put the official xlsx into data/ first (data/ is gitignored, never upload it)."
        )

    for d in (DIR_01, DIR_02, DIR_03):
        d.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(RAW_JD_FILE)
    # pandas 把无表头的首列命名为 "Unnamed: 0"，重命名为可读的源行标识
    first_col = df.columns[0]
    if str(first_col).startswith("Unnamed"):
        df = df.rename(columns={first_col: "source_row_index"})

    _require_columns(df, ["id", "name", "responsibility", "requirement"], "raw_jd_full")

    # 01：全量原始字段
    p_full = DIR_01 / "raw_jd_full.csv"
    df.to_csv(p_full, index=False, encoding="utf-8")
    print(f"[prepare_data] 01 raw_jd_full.csv     rows={len(df)} cols={len(df.columns)}")

    # 01：字段字典
    if FIELD_DICT_FILE.exists():
        dct = pd.read_excel(FIELD_DICT_FILE)
        p_dict = DIR_01 / "field_dictionary.csv"
        dct.to_csv(p_dict, index=False, encoding="utf-8")
        print(f"[prepare_data] 01 field_dictionary.csv rows={len(dct)}")
    else:
        print("[prepare_data] 01 field_dictionary.csv SKIPPED (optional xlsx missing)")

    # 02：结构化岗位字段
    _require_columns(df, COLS_02, "jd_job_fields")
    p_job = DIR_02 / "jd_job_fields.csv"
    df[COLS_02].to_csv(p_job, index=False, encoding="utf-8")
    print(f"[prepare_data] 02 jd_job_fields.csv    rows={len(df)} cols={len(COLS_02)}")

    # 03：正文语料
    _require_columns(df, COLS_03, "jd_text_corpus")
    p_text = DIR_03 / "jd_text_corpus.csv"
    df[COLS_03].to_csv(p_text, index=False, encoding="utf-8")
    print(f"[prepare_data] 03 jd_text_corpus.csv   rows={len(df)} cols={len(COLS_03)}")

    print("[prepare_data] done. Next: python 05_代码/main.py")


if __name__ == "__main__":
    main()
