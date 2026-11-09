import pandas as pd
import re
import hashlib
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')

# ==================== 1. 基础映射表 ====================
CITY_MAP = {
    "广州": "440100", "深圳": "440300", "珠海": "440400", "汕头": "440500", "佛山": "440600",
    "韶关": "440200", "湛江": "440800", "肇庆": "441200", "江门": "440700", "茂名": "440900",
    "惠州": "441300", "梅州": "441400", "汕尾": "441500", "河源": "441600", "阳江": "441700",
    "清远": "441800", "东莞": "441900", "中山": "442000", "潮州": "445100", "揭阳": "445200",
    "云浮": "445300"
}

EDU_MAP = {
    "不限": "不限", "初中及以下": "初中及以下", "高中/中技/中专": "高中",
    "大专": "大专", "本科": "本科", "硕士及以上": "硕士", "博士": "博士"
}

IND_MAP = {
    "互联网/电子商务": "I64", "计算机服务(系统、数据服务、维修)": "I65", "电子技术/半导体/集成电路": "C39",
    "机械/设备/重工": "C34/C35", "建筑/建材/工程": "E47/E48", "医疗/护理/卫生": "Q84",
    "教育/科研/培训": "P82/P83", "交通/运输/物流": "G54/G56", "房地产/物业管理/商业中心": "K70",
    "批发/零售": "F51/F52", "贸易/进出口": "F51", "汽车及零配件": "C36",
    "能源（电力/水利/矿产）": "D44/B06", "石油/化工/矿产/地质": "C25/B07",
    "快速消费品（食品、饮料、化妆品）": "C14/C15/C26", "美容/保健/生活服务": "O80/Q82",
    "中介/专业服务（咨询、人力资源、财会）": "L72/M75", "娱乐休闲/餐饮/体育": "H61/R88",
    "公关/市场推广/会展": "L72/M74", "服装/纺织/皮革": "C17/C18/C19", "制药/生物工程": "C27",
    "原材料和加工": "C29/C30", "仪器仪表/工业自动化": "C40", "家具/家电/玩具/礼品": "C21/C24/C38",
    "保险": "J68", "新能源": "C38/D44"
}

# ==================== 2. 辅助工具函数 ====================
def get_text_hash(text):
    return hashlib.md5(str(text).encode('utf-8')).hexdigest()

def parse_experience(exp_str):
    if pd.isna(exp_str) or str(exp_str).strip() in ["不限", "无经验", "nan"]:
        return 0, 0
    if "10年以上" in str(exp_str):
        return 10, -1
    match = re.search(r'(\d+)-(\d+)', str(exp_str))
    if match:
        return int(match.group(1)), int(match.group(2))
    match_single = re.search(r'(\d+)', str(exp_str))
    if match_single:
        return int(match_single.group(1)), int(match_single.group(1))
    return 0, 0

def clean_salary(val):
    if pd.isna(val) or val == "" or str(val).strip() == "":
        return ""
    try:
        return int(float(val) * 1000)
    except:
        return ""

def get_city_code(city_str):
    if pd.isna(city_str): return ""
    for city_name, code in CITY_MAP.items():
        if city_name in str(city_str):
            return code
    return ""

def map_industry(ind_str):
    if pd.isna(ind_str): return ""
    for k, v in IND_MAP.items():
        if k in str(ind_str): return v
    return ""

def format_date(date_str):
    """强制格式化日期为 YYYY-MM-DD"""
    if pd.isna(date_str) or str(date_str).strip() == "":
        return ""
    try:
        dt = pd.to_datetime(date_str)
        return dt.strftime('%Y-%m-%d')
    except:
        return ""

# ==================== 3. 主流程 ====================
def main():
    print("开始读取 raw_data.xlsx...")
    df = pd.read_excel('raw_data.xlsx', dtype=str)
    total_rows = len(df)
    
    # --- Step 1: 数据清洗与过滤 ---
    print("正在执行数据过滤...")
    
    # 只保留官方规定的枚举值
    drop_stats = {
        "EMPTY_TEXT": {"count": 0, "ids": [], "desc": "responsibility和requirement均为空或纯空格"},
        "TOO_SHORT": {"count": 0, "ids": [], "desc": "正文长度（responsibility+requirement）< 20个字符"},
        "NON_JOB_AD": {"count": 0, "ids": [], "desc": "包含纯广告话术如“请勿重复投递”等"}
    }
    
    valid_rows = []
    
    for index, row in df.iterrows():
        jd_id = str(row['id'])
        res = str(row['responsibility']) if pd.notna(row['responsibility']) else ""
        req = str(row['requirement']) if pd.notna(row['requirement']) else ""
        full_text = res + req
        
        # 1. 正文为空
        if len(full_text.strip()) == 0:
            drop_stats["EMPTY_TEXT"]["count"] += 1
            if len(drop_stats["EMPTY_TEXT"]["ids"]) < 20: drop_stats["EMPTY_TEXT"]["ids"].append(jd_id)
            continue
            
        # 2. 文本过短
        if len(full_text.strip()) < 20:
            drop_stats["TOO_SHORT"]["count"] += 1
            if len(drop_stats["TOO_SHORT"]["ids"]) < 20: drop_stats["TOO_SHORT"]["ids"].append(jd_id)
            continue
            
        # 3. 纯广告
        if "请勿重复投递" in full_text or ("温馨提示：" in full_text and len(full_text) < 100):
            drop_stats["NON_JOB_AD"]["count"] += 1
            if len(drop_stats["NON_JOB_AD"]["ids"]) < 20: drop_stats["NON_JOB_AD"]["ids"].append(jd_id)
            continue
            
        # 注意：不再过滤薪资异常，保留并后续打标签
        valid_rows.append(row)
        
    # 生成 jd_drop_summary.csv (无 BOM)
    drop_summary_data = []
    for reason, data in drop_stats.items():
        if data["count"] > 0:
            drop_summary_data.append({
                "drop_reason": reason,
                "record_count": data["count"],
                "rule_description": data["desc"],
                "sample_jd_ids": "|".join(data["ids"])
            })
    df_drop = pd.DataFrame(drop_summary_data)
    df_drop.to_csv("jd_drop_summary.csv", index=False, encoding='utf-8')
    print(f"--> 过滤完成，丢弃 {total_rows - len(valid_rows)} 条。")

    # --- Step 2: 文本去重 ---
    print("正在执行文本精确去重...")
    df_valid = pd.DataFrame(valid_rows).copy()
    
    dedup_groups = []
    kept_ids = set()
    dropped_ids = set()
    
    df_valid['text_hash'] = (df_valid['responsibility'].fillna("") + df_valid['requirement'].fillna("")).apply(get_text_hash)
    duplicated_hashes = df_valid[df_valid.duplicated(subset=['text_hash'], keep=False)]
    
    group_id_counter = 1
    for hash_val, group in duplicated_hashes.groupby('text_hash'):
        group_ids = group['id'].astype(str).tolist()
        if any(uid in kept_ids for uid in group_ids): continue
            
        group['text_len'] = group['responsibility'].str.len() + group['requirement'].str.len()
        group = group.sort_values(by='text_len', ascending=False)
        
        kept_id = str(group.iloc[0]['id'])
        dropped_list = [str(uid) for uid in group.iloc[1:]['id'].tolist()]
        
        kept_ids.add(kept_id)
        dropped_ids.update(dropped_list)
        
        dedup_groups.append({
            "dedup_group_id": f"DEDUP_{group_id_counter:06d}",
            "kept_jd_id": kept_id,
            "dropped_jd_ids": "|".join(dropped_list),
            "dedup_method": "EXACT",
            "similarity": 1.0
        })
        group_id_counter += 1
        
    for index, row in df_valid.iterrows():
        jd_id = str(row['id'])
        if jd_id not in dropped_ids and jd_id not in kept_ids:
            kept_ids.add(jd_id)
            
    df_dedup = pd.DataFrame(dedup_groups)
    if df_dedup.empty:
        df_dedup = pd.DataFrame(columns=["dedup_group_id", "kept_jd_id", "dropped_jd_ids", "dedup_method", "similarity"])
    df_dedup.to_csv("dedup_groups.csv", index=False, encoding='utf-8')
    print(f"--> 去重完成，剔除 {len(dropped_ids)} 条重复JD。")

    # --- Step 3: 字段映射与格式化 ---
    print("正在生成 jd_keep_ids.csv...")
    final_df = df_valid[df_valid['id'].astype(str).isin(kept_ids)].copy()
    
    keep_df = pd.DataFrame()
    keep_df['jd_id'] = final_df['id'].astype(str)
    keep_df['std_job_id'] = "STJ_000000"
    keep_df['job_title_raw'] = final_df['name']
    
    # 城市代码和有效标识联动 (附录A规定非广东/空值，is_valid可标0)
    keep_df['city_code'] = final_df['city'].apply(get_city_code)
    keep_df['is_valid'] = keep_df['city_code'].apply(lambda x: 1 if x != "" else 0)
    
    keep_df['industry_code'] = final_df['business'].apply(map_industry)
    keep_df['education'] = final_df['education'].astype(str).map(EDU_MAP).fillna("")
    
    exp_data = final_df['experience'].apply(parse_experience)
    keep_df['experience_min'] = [x[0] for x in exp_data]
    keep_df['experience_max'] = [x[1] for x in exp_data]
    
    keep_df['salary_min'] = final_df['starting_salary'].apply(clean_salary)
    keep_df['salary_max'] = final_df['salary'].apply(clean_salary)
    
    keep_df['publish_date'] = final_df['time'].apply(format_date)
    
    # 质量标记
    def get_flags(row):
        flags = []
        text_len = len(str(row['responsibility'])) + len(str(row['requirement']))
        if text_len < 30:
            flags.append("TOO_SHORT")
        if clean_salary(row['starting_salary']) == "":
            flags.append("SALARY_ANOMALY")
        return "|".join(flags)
    keep_df['quality_flags'] = final_df.apply(get_flags, axis=1)
    
    keep_df = keep_df.fillna("")
    keep_df.to_csv("jd_keep_ids.csv", index=False, encoding='utf-8')
    print(f"--> 完成！共保留 {len(keep_df)} 条有效JD。")

if __name__ == "__main__":
    main()