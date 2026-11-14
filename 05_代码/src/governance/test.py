import pandas as pd
import re
import hashlib
import warnings
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

warnings.filterwarnings('ignore')


# ==================== 0. GPU 设备检测 ====================
def get_device():
    if torch.cuda.is_available():
        print(f"--> 检测到 GPU: {torch.cuda.get_device_name(0)}，启用 CUDA 加速")
        return torch.device("cuda")
    print("--> 未检测到可用 GPU，使用 CPU 运行")
    return torch.device("cpu")

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

# ==================== 2. 辅助工具与强规则配置 ====================
PHONE_PATTERN = re.compile(r'1[3-9]\d{9}')
WECHAT_PATTERN = re.compile(r'(微信|vx|v信|QQ|qq)\s*[:：]?\s*([a-zA-Z0-9_-]{5,20})')
# 匹配任何非中文字符（用于语言检测）
NON_CHINESE_PATTERN = re.compile(r'[^\u4e00-\u9fa5]')
# 匹配连续重复3次以上的字符（如“好好好好”，只匹配汉字）
REPEAT_CHAR_PATTERN = re.compile(r'([\u4e00-\u9fa5])\1{2,}')



AD_KEYWORDS = ["刷单", "微商", "加盟", "代练", "兼职群", "日结包吃住", "0基础速成"]
WELFARE_KEYWORDS = ["双休", "下午茶", "包吃住", "五险一金", "带薪年假", "员工旅游"]

def clean_text_for_dedup(text):
    return re.sub(r'[^\w\u4e00-\u9fa5]', '', str(text)).lower()

def get_ngrams(text, n=3):
    return set([text[i:i+n] for i in range(len(text)-n+1)])

def jaccard_similarity(set1, set2):
    if not set1 or not set2: return 0.0
    return len(set1.intersection(set2)) / len(set1.union(set2))

def parse_experience(exp_str):
    if pd.isna(exp_str) or str(exp_str).strip() in ["不限", "无经验", "nan"]: return 0, 0
    if "10年以上" in str(exp_str): return 10, -1
    match = re.search(r'(\d+)-(\d+)', str(exp_str))
    if match: return int(match.group(1)), int(match.group(2))
    match_single = re.search(r'(\d+)', str(exp_str))
    if match_single: return int(match_single.group(1)), int(match_single.group(1))
    return 0, 0

def clean_salary(val):
    if pd.isna(val) or str(val).strip() == "": return ""
    try: return int(float(val) * 1000)
    except: return ""

def get_city_code(city_str):
    if pd.isna(city_str): return ""
    for city_name, code in CITY_MAP.items():
        if city_name in str(city_str): return code
    return ""

def map_industry(ind_str):
    if pd.isna(ind_str): return ""
    for k, v in IND_MAP.items():
        if k in str(ind_str): return v
    return ""

def format_date(date_str):
    if pd.isna(date_str) or str(date_str).strip() == "": return ""
    try: return pd.to_datetime(date_str).strftime('%Y-%m-%d')
    except: return ""

# ==================== 3. 主流程 ====================
def main():
    print("开始读取 raw_data.xlsx...")
    df = pd.read_excel('raw_data.xlsx', dtype=str)
    total_rows = len(df)
    
    # --- Step 1: 初始化全量丢弃统计字典 ---
    # 将官方要求的所有枚举值全部列出来，即使没命中也会在最终表格里输出 0
    drop_stats = {
        "DUPLICATE": {"count": 0, "ids": [], "desc": "多层组合去重（企业+城市硬约束）：EXACT+MINHASH+EMBEDDING"},
        "EMPTY_TEXT": {"count": 0, "ids": [], "desc": "正文为空或纯空格"},
        "NON_JOB_AD": {"count": 0, "ids": [], "desc": "命中硬广特征词，或短文本包含≥3个手机号/微信号"},
        "TOO_SHORT": {"count": 0, "ids": [], "desc": "正文长度<20个字符"},
        "LANGUAGE": {"count": 0, "ids": [], "desc": "中文字符占比<50%，判定为非中文"},
        "LOW_QUALITY": {"count": 0, "ids": [], "desc": "福利词密度>30%或包含连续重复无意义字符"},
        "OTHER": {"count": 0, "ids": [], "desc": "其他异常情况"}
    }
    
    print("正在执行 Step 1: 强规则拦截过滤...")
    valid_rows = []
    
    for index, row in df.iterrows():
        jd_id = str(row['id'])
        res = str(row['responsibility']) if pd.notna(row['responsibility']) else ""
        req = str(row['requirement']) if pd.notna(row['requirement']) else ""
        full_text = res + req
        name = str(row['name']) if pd.notna(row['name']) else ""
        
        # 1. 正文为空
        if len(full_text.strip()) == 0:
            drop_stats["EMPTY_TEXT"]["count"] += 1
            if len(drop_stats["EMPTY_TEXT"]["ids"]) < 20: drop_stats["EMPTY_TEXT"]["ids"].append(jd_id)
            continue
            
        # 2. 正文过短
        if len(full_text.strip()) < 20:
            drop_stats["TOO_SHORT"]["count"] += 1
            if len(drop_stats["TOO_SHORT"]["ids"]) < 20: drop_stats["TOO_SHORT"]["ids"].append(jd_id)
            continue
            
        # 3. 非中文拦截 (LANGUAGE)
        # 逻辑：去除标点空格后，如果纯中文长度不足总长度的一半，说明是外语或严重中英混杂
        clean_len = len(NON_CHINESE_PATTERN.sub('', full_text))
        if clean_len / max(len(full_text), 1) < 0.5:
            drop_stats["LANGUAGE"]["count"] += 1
            if len(drop_stats["LANGUAGE"]["ids"]) < 20: drop_stats["LANGUAGE"]["ids"].append(jd_id)
            continue

        # 4. 非招聘广告拦截 (NON_JOB_AD)
        is_ad = False
        if any(kw in name or kw in full_text for kw in AD_KEYWORDS):
            is_ad = True
        else:
            if len(full_text) < 200 and (len(PHONE_PATTERN.findall(full_text)) >= 3 or len(WECHAT_PATTERN.findall(full_text)) >= 3):
                is_ad = True
        if is_ad:
            drop_stats["NON_JOB_AD"]["count"] += 1
            if len(drop_stats["NON_JOB_AD"]["ids"]) < 20: drop_stats["NON_JOB_AD"]["ids"].append(jd_id)
            continue
            
        # 5. 质量低拦截 (LOW_QUALITY)
        is_low_quality = False
        if len(full_text) > 100:
            welfare_count = sum(full_text.count(kw) for kw in WELFARE_KEYWORDS)
            if welfare_count / len(full_text) > 0.3:
                is_low_quality = True

        if REPEAT_CHAR_PATTERN.search(full_text):
            is_low_quality = True

            
            
        if is_low_quality:
            drop_stats["LOW_QUALITY"]["count"] += 1
            if len(drop_stats["LOW_QUALITY"]["ids"]) < 20: drop_stats["LOW_QUALITY"]["ids"].append(jd_id)
            continue
            
        # 通过所有拦截的合法数据
        valid_rows.append(row)

    print(f"--> 规则过滤完成，当前合法数据 {len(valid_rows)} 条。")

    # --- Step 2: 多级组合去重 (更新 DUPLICATE 统计) ---
    print("正在加载 SentenceTransformer 模型 (初次运行需下载)...")
    device = get_device()
    embed_model = SentenceTransformer('shibing624/text2vec-base-chinese', device=str(device))
    print(f"--> 模型加载完成！运行设备: {device}")
    print("正在执行 Step 2: 多级组合去重...")
    
    df_valid = pd.DataFrame(valid_rows).copy()
    dedup_groups = []
    kept_ids = set()
    dropped_ids = set()
    
    df_valid['bucket'] = df_valid['company'].fillna("未知公司") + "_" + df_valid['city'].fillna("未知城市")
    group_id_counter = 1
    
    for bucket_name, bucket_df in df_valid.groupby('bucket'):
        if len(bucket_df) == 1:
            kept_ids.add(str(bucket_df.iloc[0]['id']))
            continue
            
        bucket_df = bucket_df.sort_values(by='time').reset_index(drop=True)
        bucket_texts = [clean_text_for_dedup(str(row['responsibility']) + str(row['requirement'])) for _, row in bucket_df.iterrows()]
        bucket_embeddings = embed_model.encode(
            bucket_texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True,
            device=str(device),
            convert_to_numpy=True
        )
        sim_matrix = np.dot(bucket_embeddings, bucket_embeddings.T)
        
        for i in range(len(bucket_df)):
            id_i = str(bucket_df.iloc[i]['id'])
            if id_i in dropped_ids or id_i in kept_ids: continue
            
            current_dups = [id_i]
            text_i_clean = clean_text_for_dedup(str(bucket_df.iloc[i]['responsibility']) + str(bucket_df.iloc[i]['requirement']))
            ngram_i = get_ngrams(text_i_clean, 3)
            max_sim = 1.0
            method_used = "EXACT"
            
            for j in range(i+1, len(bucket_df)):
                id_j = str(bucket_df.iloc[j]['id'])
                if id_j in dropped_ids or id_j in kept_ids: continue
                
                text_j_clean = clean_text_for_dedup(str(bucket_df.iloc[j]['responsibility']) + str(bucket_df.iloc[j]['requirement']))
                
                if text_i_clean == text_j_clean:
                    current_dups.append(id_j); dropped_ids.add(id_j); continue
                    
                sim_minhash = jaccard_similarity(ngram_i, get_ngrams(text_j_clean, 3))
                if sim_minhash > 0.85:
                    current_dups.append(id_j); dropped_ids.add(id_j); method_used = "NEAR_DUP_MINHASH"; max_sim = min(max_sim, sim_minhash); continue
                    
                sim_embedding = float(sim_matrix[i][j])
                if sim_embedding > 0.9:
                    current_dups.append(id_j); dropped_ids.add(id_j); method_used = "NEAR_DUP_EMBEDDING"; max_sim = min(max_sim, sim_embedding)
                elif 0.8 <= sim_embedding <= 0.9:
                    method_used = "MANUAL"; max_sim = min(max_sim, sim_embedding)
                    #待完善
                    
                            
            if len(current_dups) > 1:
                best_id = max(current_dups, key=lambda x: len(str(df_valid[df_valid['id'] == x]['responsibility'].values[0])))
                if best_id in dropped_ids: dropped_ids.remove(best_id)
                kept_ids.add(best_id)
                
                other_dups = [x for x in current_dups if x != best_id]
                dedup_groups.append({
                    "dedup_group_id": f"DEDUP_{group_id_counter:06d}",
                    "kept_jd_id": best_id,
                    "dropped_jd_ids": "|".join(other_dups),
                    "dedup_method": method_used,
                    "similarity": round(max_sim, 4) if max_sim < 1.0 else 1.0
                })
                group_id_counter += 1
            else:
                kept_ids.add(id_i)
    
    # 补充没重复的数据
    for index, row in df_valid.iterrows():
        jd_id = str(row['id'])
        if jd_id not in dropped_ids and jd_id not in kept_ids:
            kept_ids.add(jd_id)

    # 将去重结果合并回统一字典中
    if len(dropped_ids) > 0:
        drop_stats["DUPLICATE"]["count"] = len(dropped_ids)
        drop_stats["DUPLICATE"]["ids"] = list(dropped_ids)[:20]

    # --- 统一生成说明文档 jd_drop_summary.csv ---
    # 不管有没有命中，7种枚举全部输出
    drop_summary_data = []
    for reason, data in drop_stats.items():
        drop_summary_data.append({
            "drop_reason": reason,
            "record_count": data["count"],
            "rule_description": data["desc"],
            "sample_jd_ids": "|".join(data["ids"]) if data["ids"] else ""
        })
    pd.DataFrame(drop_summary_data).to_csv("jd_drop_summary.csv", index=False, encoding='utf-8')
    
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
    
    # 注意：这里的 quality_flags 已经不需要 LOW_QUALITY 标签了，因为已经在前面被丢弃了
    def get_flags(row):
        flags = []
        text_len = len(str(row['responsibility'])) + len(str(row['requirement']))
        if text_len < 30: flags.append("TOO_SHORT")
        if clean_salary(row['starting_salary']) == "": flags.append("SALARY_ANOMALY")
        return "|".join(flags)
    keep_df['quality_flags'] = final_df.apply(get_flags, axis=1)
    
    keep_df = keep_df.fillna("")
    keep_df.to_csv("jd_keep_ids.csv", index=False, encoding='utf-8')
    print(f"--> 全部完成！共保留 {len(keep_df)} 条有效JD。")

if __name__ == "__main__":
    main()