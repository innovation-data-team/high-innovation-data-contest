# -*- coding: utf-8 -*-
"""
一键复现入口：读阶段数据 → 跑完整流程 → 产出 01~03 各表。

运行方式（先准备数据，再一键复现）：
    python 05_代码/prepare_data.py     # 把 data/ 下官方原始 xlsx 切分为三阶段输入
    python 05_代码/main.py             # 指导文件要求的固定入口

产出：
    01_数据治理/jd_keep_ids.csv
    01_数据治理/jd_drop_summary.csv
    01_数据治理/dedup_groups.csv
    02_岗位归一化/std_job.csv
    02_岗位归一化/jd_job_map.csv
    02_岗位归一化/synonym_pairs.csv
    03_技能抽取/skill.csv

注意：
    - 官方原始数据与阶段中间数据都在 data/，严禁上传到 GitHub，也不打进提交包。
    - 所有输出 CSV 必须为 UTF-8 无 BOM，遵循 RFC 4180。
    - 表头名照抄指导文档，不可改名。
    - 多值字段用竖线 | 分隔；空值留空；布尔用 1/0。
"""

from pathlib import Path

# 项目根目录（05_代码/main.py 的上一级）
ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = Path(__file__).resolve().parent

# 官方原始数据（本地放置，不入库、不打包；由 prepare_data.py 切分为阶段数据）
RAW_DATA_DIR = ROOT / "data"
RAW_JD_FILE = RAW_DATA_DIR / "团队预览_5万条.xlsx"

# 各阶段本地输入数据（prepare_data.py 生成；data/ 不入库、不打包）
DATA_01 = RAW_DATA_DIR / "01_数据治理"
DATA_02 = RAW_DATA_DIR / "02_岗位归一化"
DATA_03 = RAW_DATA_DIR / "03_技能抽取"
RAW_JD_FULL = DATA_01 / "raw_jd_full.csv"
FIELD_DICTIONARY = DATA_01 / "field_dictionary.csv"
JD_JOB_FIELDS = DATA_02 / "jd_job_fields.csv"
JD_TEXT_CORPUS = DATA_03 / "jd_text_corpus.csv"

# 指导文件 Word 附录 A/B/C 提取的映射表（随提交包分发，复现必需）
APPENDIX_A_CITY_CODE = CODE_DIR / "appendix_a_city_code.csv"   # city → city_code
APPENDIX_B_EDUCATION = CODE_DIR / "appendix_b_education.csv"   # education 原始值 → 规范枚举
APPENDIX_C_INDUSTRY = CODE_DIR / "appendix_c_industry.csv"     # business → industry_code

# 产出目录（提交包内容）
OUT_01 = ROOT / "01_数据治理"
OUT_02 = ROOT / "02_岗位归一化"
OUT_03 = ROOT / "03_技能抽取"


def run_governance() -> None:
    """阶段一：数据治理 —— 清洗、去重，产出 jd_keep_ids / jd_drop_summary / dedup_groups。

    输入：RAW_JD_FULL（全量 19 列）；字段转换查 APPENDIX_A/B/C；
          正文为空 / 过短判定与去重依赖 responsibility、requirement。
    """
    raise NotImplementedError("待实现：数据清洗 + 去重，输出 01_数据治理/ 三张表")


def run_job_normalization() -> None:
    """阶段二：岗位归一化 —— 聚类归纳，产出 std_job / jd_job_map / synonym_pairs。

    输入：JD_JOB_FIELDS（结构化岗位字段）+ OUT_01/jd_keep_ids.csv；
          大典代码表等官方资产发布后放入 DATA_02 再查表。
    """
    raise NotImplementedError("待实现：岗位聚类归一化，输出 02_岗位归一化/ 三张表")


def run_skill_extraction() -> None:
    """阶段三：技能抽取 —— 从 responsibility/requirement 抽取技能点，产出 skill.csv。

    输入：JD_TEXT_CORPUS（保留正文原文，确保 evidence_span 能在对应 jd_id 原文中定位）。
    """
    raise NotImplementedError("待实现：技能抽取，输出 03_技能抽取/skill.csv")


def main() -> None:
    print(f"[main] 项目根目录: {ROOT}")
    required = [RAW_JD_FULL, JD_JOB_FIELDS, JD_TEXT_CORPUS]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "缺少阶段输入数据，请先运行 python 05_代码/prepare_data.py\n"
            + "\n".join(missing)
        )
    run_governance()
    run_job_normalization()
    run_skill_extraction()
    print("[main] 全流程完成。请运行 validate.py 校验后，将 validate_report.json 放入 06_校验/。")


if __name__ == "__main__":
    main()
