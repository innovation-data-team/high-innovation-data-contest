from pathlib import Path
from collections import Counter

import pandas as pd

try:
    from .filter_rule import single_filter
    from .dedup_rule import run_deduplicate, calc_simhash
except ImportError:
    from filter_rule import single_filter
    from dedup_rule import run_deduplicate, calc_simhash

# ROOT 路径 完全沿用你写的
ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"

# 原始数据候选文件
RAW_CANDIDATES = [
    DATA_DIR / "raw_data.xlsx",
    DATA_DIR / "raw_data.xls",
    DATA_DIR / "raw_data.csv",
]

# ========== 运行配置（基线调试用，不影响业务逻辑） ==========
RUN_NAME = "base"      # 本次运行标识，决定输出子目录：output_run_base / output_run1 / ...
SAMPLE_ROWS = None     # None=跑全量；设为数字（如 5000）= 只取前N行做小样本调试

# 输出目录：01_数据治理/output_run_<RUN_NAME>，不同运行互不覆盖
OUT_DIR = ROOT / "01_数据治理" / f"output_run_{RUN_NAME}"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 列别名映射：原始列名 → 标准列名
COLUMN_ALIASES = {
    "jd_id": ["jd_id", "id", "job_id", "岗位id"],
    "job_title_raw": ["job_title_raw", "name", "job_name", "title", "岗位名称"],
    "jd_content": ["jd_content", "content", "jd", "job_content", "description", "正文", "岗位描述"],
    "city_name": ["city_name", "city", "work_city", "城市", "工作城市"],
}

# 丢弃原因字典
DROP_MAPPING = {
    "D01": "JD正文内容为空",
    "D02": "岗位不属于广东省21地市",
    "D03": "低质量文本（福利占比过高/灌水乱码）",
    "D04": "非招聘垃圾广告",
    "D05": "岗位名称/地点核心字段缺失",
    "D06": "重复JD，去重剔除",
}


def rename_columns(df: pd.DataFrame, alias_map: dict) -> pd.DataFrame:
    """根据别名字典，把原始列重命名为标准列名"""
    df = df.copy()
    col_map = {}
    std_cols = set()
    for std_name, alias_list in alias_map.items():
        for raw_col in alias_list:
            if raw_col in df.columns and std_name not in std_cols:
                col_map[raw_col] = std_name
                std_cols.add(std_name)
                break
    df = df.rename(columns=col_map)
    need_cols = list(alias_map.keys())
    for c in need_cols:
        if c not in df.columns:
            df[c] = None
    return df


def merge_jd_content(df: pd.DataFrame) -> pd.DataFrame:
    """原始表正文拆在 responsibility / requirement 两列，这里拼成 jd_content"""
    if "jd_content" in df.columns and df["jd_content"].notna().any():
        return df
    parts = [c for c in ("responsibility", "requirement") if c in df.columns]
    if not parts:
        return df
    df["jd_content"] = (
        df[parts].fillna("").astype(str).agg("".join, axis=1).str.strip()
    )
    return df


def load_raw_df() -> pd.DataFrame:
    """遍历候选文件，找到存在的原始数据并读取"""
    for fp in RAW_CANDIDATES:
        if fp.exists():
            suffix = fp.suffix.lower()
            if suffix in [".xlsx", ".xls"]:
                df = pd.read_excel(fp)
            elif suffix == ".csv":
                df = pd.read_csv(fp, dtype=str).fillna("")
            else:
                continue
            df = rename_columns(df, COLUMN_ALIASES)
            df = merge_jd_content(df)
            # 小样本调试开关：只取前N行，其余逻辑完全不变
            if SAMPLE_ROWS is not None:
                df = df.head(int(SAMPLE_ROWS)).copy()
                print(f"[调试模式] 仅取前 {SAMPLE_ROWS} 行样本（sample_rows={SAMPLE_ROWS}）")
            return df
    raise FileNotFoundError("data目录下没有找到 raw_data.xlsx / raw_data.xls / raw_data.csv")


def load_city_dict() -> dict:
    """从附录A加载 城市名 -> 区划码，'深圳'/'深圳市' 两种写法都命中"""
    city_dict = {}
    path = DATA_DIR / "appendix_a_city_code.csv"
    if not path.exists():
        print("⚠️  缺少 data/appendix_a_city_code.csv，城市字典为空，所有记录会判 D02")
        return city_dict
    table = pd.read_csv(path, dtype=str)
    for _, row in table.iterrows():
        code = str(row.get("city_code") or "").strip()
        for key in ("city_name", "city_full_name"):
            name = row.get(key)
            if pd.isna(name):
                continue
            name = str(name).strip()
            if not name:
                continue
            city_dict[name] = code
            if name.endswith("市"):
                city_dict[name[:-1]] = code
    return city_dict


def load_word_list(filename: str) -> list:
    """读取 data/ 下的词表文件（每行一个词），不存在则返回空表"""
    path = DATA_DIR / filename
    if not path.exists():
        return []
    return [
        w.strip()
        for w in path.read_text(encoding="utf-8").splitlines()
        if w.strip()
    ]


def city_code_of(city_name, city_dict) -> str:
    """查城市区划码，查不到返回空字符串"""
    if city_name is None or pd.isna(city_name):
        return ""
    name = str(city_name).strip()
    if name in city_dict:
        return city_dict[name]
    if name.endswith("市") and name[:-1] in city_dict:
        return city_dict[name[:-1]]
    return ""


class DataGovernance:
    def __init__(self):
        self.raw_df = load_raw_df()
        # 城市字典来自附录A；词表可在 data/ban_words.txt、data/welfare_words.txt 补充
        self.city_dict = load_city_dict()
        self.ban_words = load_word_list("ban_words.txt")
        self.welfare_words = load_word_list("welfare_words.txt")
        self.keep_data = []
        self.drop_data = []

    def execute(self):
        # 1. 逐条过滤 D01~D05
        for _, row in self.raw_df.iterrows():
            keep_flag, code = single_filter(row, self.ban_words, self.welfare_words, self.city_dict)
            if keep_flag:
                self.keep_data.append(row)
            else:
                self.drop_data.append({"jd_id": row["jd_id"], "drop_code": code})

        keep_df = pd.DataFrame(self.keep_data).reset_index(drop=True)
        dedup_list = []
        # 2. 过滤完成后，计算simhash，送入去重
        if len(keep_df) > 0:
            keep_df["city_code"] = keep_df["city_name"].apply(
                lambda c: city_code_of(c, self.city_dict)
            )
            keep_df["simhash"] = keep_df["jd_content"].apply(calc_simhash)
            keep_df, dedup_list = run_deduplicate(keep_df)

            # 去重剔除的记录补记为 D06，保证丢弃统计与原始条数对得上
            for jd_id in keep_df.loc[keep_df["temp_keep"] == 0, "jd_id"]:
                self.drop_data.append({"jd_id": jd_id, "drop_code": "D06"})

            final_keep = keep_df[keep_df["temp_keep"] == 1].drop(
                columns=["simhash", "temp_keep"], errors="ignore"
            )
        else:
            final_keep = keep_df  # 空表也照写，保证下游文件不缺

        # 去掉 Excel 自带的 Unnamed: 0 索引列
        final_keep = final_keep.drop(
            columns=[c for c in final_keep.columns if str(c).startswith("Unnamed")],
            errors="ignore",
        )

        final_keep.to_csv(OUT_DIR / "jd_keep_ids.csv", index=False, encoding="utf-8-sig")

        dedup_cols = [
            "group_id", "represent_jd_id", "all_jd_ids",
            "min_hamming_distance", "similarity_score", "group_size",
        ]
        pd.DataFrame(dedup_list, columns=dedup_cols).to_csv(
            OUT_DIR / "dedup_groups.csv", index=False, encoding="utf-8-sig"
        )

        # 3. 丢弃汇总表，对接 DROP_MAPPING（含 D06）
        drop_df = pd.DataFrame(self.drop_data)
        if len(drop_df) > 0:
            drop_summary = drop_df["drop_code"].value_counts().reset_index()
            drop_summary.columns = ["drop_code", "count"]
            drop_summary["drop_reason"] = drop_summary["drop_code"].map(DROP_MAPPING)
            total = drop_summary["count"].sum()
            drop_summary["proportion"] = (
                (drop_summary["count"] / total).round(4) if total > 0 else 0
            )
        else:
            drop_summary = pd.DataFrame(
                columns=["drop_code", "count", "drop_reason", "proportion"]
            )
        drop_summary.to_csv(OUT_DIR / "jd_drop_summary.csv", index=False, encoding="utf-8-sig")

        # ===== 关键统计指标 =====
        drop_counter = Counter(d["drop_code"] for d in self.drop_data)
        print("\n========== 运行统计 ==========")
        print(f"运行标识     : {RUN_NAME}")
        print(f"调试样本     : {'全量' if SAMPLE_ROWS is None else f'前 {SAMPLE_ROWS} 行'}")
        print(f"输入条数     : {len(self.raw_df)}")
        print(f"保留JD数量   : {len(final_keep)}")
        for code in ["D01", "D02", "D03", "D04", "D05", "D06"]:
            print(f"  {code} 剔除   : {drop_counter.get(code, 0)}  ({DROP_MAPPING[code]})")
        print(f"去重重复组数 : {len(dedup_list)}")
        print(f"输出目录     : {OUT_DIR}")
        print("==============================")


if __name__ == "__main__":
    dg = DataGovernance()
    dg.execute()
