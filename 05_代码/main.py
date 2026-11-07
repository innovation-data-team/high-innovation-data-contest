# -*- coding: utf-8 -*-
"""
一键复现入口：读官方数据 → 跑完整流程 → 产出 01~03 各表。

运行方式（指导文件要求）：
    python 05_代码/main.py

产出：
    01_数据治理/jd_keep_ids.csv
    01_数据治理/jd_drop_summary.csv
    01_数据治理/dedup_groups.csv
    02_岗位归一化/std_job.csv
    02_岗位归一化/jd_job_map.csv
    02_岗位归一化/synonym_pairs.csv
    03_技能抽取/skill.csv

注意：
    - 所有输出 CSV 必须为 UTF-8 无 BOM，遵循 RFC 4180。
    - 表头名照抄指导文档，不可改名。
    - 多值字段用竖线 | 分隔；空值留空；布尔用 1/0。
"""

from pathlib import Path

# 项目根目录（05_代码/main.py 的上一级）
ROOT = Path(__file__).resolve().parent.parent

# 官方原始数据路径（按实际放置调整，原始数据不随提交包分发）
RAW_DATA_DIR = ROOT / "data"
RAW_JD_CSV = RAW_DATA_DIR / "团队预览_5万条.xlsx"

# 输出目录
OUT_01 = ROOT / "01_数据治理"
OUT_02 = ROOT / "02_岗位归一化"
OUT_03 = ROOT / "03_技能抽取"


def run_governance() -> None:
    """阶段一：数据治理 —— 清洗、去重，产出 jd_keep_ids / jd_drop_summary / dedup_groups。"""
    raise NotImplementedError("待实现：数据清洗 + 去重，输出 01_数据治理/ 三张表")


def run_job_normalization() -> None:
    """阶段二：岗位归一化 —— 聚类归纳，产出 std_job / jd_job_map / synonym_pairs。"""
    raise NotImplementedError("待实现：岗位聚类归一化，输出 02_岗位归一化/ 三张表")


def run_skill_extraction() -> None:
    """阶段三：技能抽取 —— 从 responsibility/requirement 抽取技能点，产出 skill.csv。"""
    raise NotImplementedError("待实现：技能抽取，输出 03_技能抽取/skill.csv")


def main() -> None:
    print(f"[main] 项目根目录: {ROOT}")
    run_governance()
    run_job_normalization()
    run_skill_extraction()
    print("[main] 全流程完成。请运行 validate.py 校验后，将 validate_report.json 放入 06_校验/。")


if __name__ == "__main__":
    main()
