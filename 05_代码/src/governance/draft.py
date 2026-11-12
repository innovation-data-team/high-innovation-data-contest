
import hashlib
import re
import zlib
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

# ---- 路径与阈值 ----
ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data" / "data"
OUT_DIR = ROOT / "01_数据治理"
STD_JOB_FILE = ROOT / "02_岗位归一化" / "std_job.csv"

TOO_SHORT_LEN, TOO_SHORT_FLAG_LEN = 40, 100  
MIN_UNIQUE_CHARS = 30                         
CJK_MIN_RATIO = 0.05                          
AD_CONTACT_BODY, AD_CONTACT_MIN = 200, 3      
WELFARE_MIN_COUNT, WELFARE_COVER = 6, 0.25    
REPEAT_CHAR_MIN = 4                           
DEDUP_EXACT_TH, DEDUP_VEC_TH = 0.85, 0.80     
DEDUP_GRAY_LO, SALARY_GRAY_MAX = 0.70, 0.30   
MINHASH_PERM, MINHASH_BANDS = 32, 16
UNKNOWN_STD_JOB = "STJ_000000"

# ---- 词表（广告词经人工复核校准，过程见 data/data/治理复核记录_20261110.md）----
AD_STRONG_WORDS = ("刷单", "办证刻章", "扫码关注", "扫码入群", "博彩", "刷信誉", "点赞员", "打字员兼职")
WELFARE_WORDS = ("双休", "下午茶", "包吃", "包住", "五险一金", "带薪年假", "员工旅游",
                 "节日福利", "年终奖", "绩效奖金", "住房补贴", "餐补", "交通补助")
DUTY_KEYWORDS = ("负责", "职责", "任职", "要求", "工作内容", "岗位", "熟悉", "掌握")
DROP_REASONS = ["EMPTY_TEXT", "LANGUAGE", "TOO_SHORT", "NON_JOB_AD", "LOW_QUALITY", "OTHER", "DUPLICATE"]

RULE_DESC = {
    "EMPTY_TEXT": "responsibility 与 requirement 去空白后均为空，正文长度 = 0，无法进行技能抽取。",
    "LANGUAGE": f"正文汉字占比 < {CJK_MIN_RATIO:.0%}，属纯英文/纯符号 JD，不属于中文岗位描述。",
    "TOO_SHORT": f"正文去空白后字符数 < {TOO_SHORT_LEN}，信息量不足以抽取职责与技能。",
    "NON_JOB_AD": (
        "规则引擎拦截（特征词、否定豁免与阈值均经人工逐词复核校准）：① 正文或标题命中强广告特征词"
        "（刷单/办证刻章/博彩/刷信誉/点赞员/打字员兼职/扫码关注等，且命中处前方无\"不/无/非/禁\"等否定字，"
        "排除\"合规运营，不刷单\"类表述）；② 正文 < 200 字且含 ≥ 3 个手机号/QQ号/微信号且无职责句式。"
        "复核记录：本数据集为 58同城/智联正规渠道爬取，几乎不存在经典垃圾广告；微商、办证、代练、返利、"
        "代开发票、加微信等词因误杀真实岗位（微商城、船员办证、游戏代练、销售返利、会计代开发票、加微信投递）"
        "已移除；\"一般广告词+短正文\"规则（招商/日结/招生等）经 20 例人工复核误杀率 >90%，已整体移除。"
    ),
    "LOW_QUALITY": (
        f"规则引擎拦截：① 正文 > 100 字且福利词（双休/包吃住/五险一金等）出现 ≥ {WELFARE_MIN_COUNT} 次"
        f"且字符覆盖 > {WELFARE_COVER:.0%}（原阈值 30% 经人工复核后放宽）；"
        f"② 检测到连续 ≥ {REPEAT_CHAR_MIN} 个相同汉字（如\"急急急急\"，仅统计去空白后的汉字，避免标点空格误报）；"
        f"③ 正文 ≥ {TOO_SHORT_LEN} 字符但去重后字符 < {MIN_UNIQUE_CHARS}（重复堆砌）。"
    ),
    "OTHER": "必填字段无法满足：job_title_raw 为空，或 city 缺失且无法映射到附录 A 的 6 位行政区划代码。",
    "DUPLICATE": (
        "多层组合去重（企业+城市硬约束）：① EXACT——强清洗后【公司+城市+岗位名+职责+要求】MD5 相同；"
        f"② MINHASH——同公司同城市内正文 3-gram Jaccard ≥ {DEDUP_EXACT_TH}；"
        f"③ EMBEDDING——字符 3-gram 词频向量余弦 ≥ {DEDUP_VEC_TH}（无预训练模型环境，用词袋向量近似，"
        f"公司维度已由分桶硬约束）；④ 灰区相似度 [{DEDUP_GRAY_LO}, {DEDUP_EXACT_TH}) 需薪资差 ≤ "
        f"{SALARY_GRAY_MAX:.0%}，超过则强制排除出重复组。组内保留正文最完整项。"
    ),
}

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[\s\u3000-\u303f\uff00-\uffef0-9a-zA-Z·、，。；：！？（）()【】《》\-—/\\|~`@#$%^&*+=<>\[\]{}'\"…]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_TEL = re.compile(r"1[3-9]\d{9}")
_QQ = re.compile(r"[Qq][Qq][:： ]*\d{5,11}")
_WX = re.compile(r"微信[:： ]*[a-zA-Z0-9_\-]{5,20}|(?<![a-zA-Z])[Vv]{1,2}[:： ][a-zA-Z0-9_\-]{5,20}")
_REPEAT = re.compile(r"([\u4e00-\u9fff])\1{%d,}" % (REPEAT_CHAR_MIN - 1))
NEGATIONS = "无非绝禁拒不"

PRIME = (1 << 61) - 1
_rng = np.random.default_rng(20260501)
HASH_A = _rng.integers(1, PRIME, size=MINHASH_PERM, dtype=np.int64)
HASH_B = _rng.integers(0, PRIME, size=MINHASH_PERM, dtype=np.int64)


# ---------------------------------------------------------------- 工具函数
def S(v):
    """安全取字符串：非字符串（NaN 等）一律当空串。"""
    return v.strip() if isinstance(v, str) else ""


def clean_text(s):
    """去掉空白与标点，做指纹 / 相似度前统一用它。"""
    return _PUNCT.sub("", s)


def hit_ad(text):
    """命中强广告词即判广告；命中词前 3 字内有否定字（如"不刷单"）则豁免。"""
    for w in AD_STRONG_WORDS:
        p = text.find(w)
        while p >= 0:
            if not any(c in text[max(0, p - 3):p] for c in NEGATIONS):
                return True
            p = text.find(w, p + 1)
    return False


def parse_experience(v):
    """无经验 → (0, 0)；a-b 年 → (a, b)；N 年以上 → (N, -1)，-1 表示无上限。"""
    s = S(v)
    if s == "无经验":
        return 0, 0
    if s == "10年以上":
        return 10, -1
    m = re.match(r"^(\d+)\s*-\s*(\d+)\s*年$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^(\d+)\s*年以上$", s)
    if m:
        return int(m.group(1)), -1
    return pd.NA, pd.NA


def to_salary(v):
    """原始单位千元/月，×1000 转元/月。"""
    try:
        return int(round(float(v) * 1000))
    except (TypeError, ValueError):
        return pd.NA


def to_date(v):
    try:
        return pd.to_datetime(v).strftime("%Y-%m-%d")
    except Exception:
        return ""


def salary_close(r1, r2):
    """灰区合并前的薪资校验：中点差 ≤ 30%，缺薪资视为不合并。"""
    s = [to_salary(r[k]) for r in (r1, r2) for k in ("starting_salary", "salary")]
    if any(pd.isna(x) for x in s):
        return False
    m1, m2 = (s[0] + s[1]) / 2, (s[2] + s[3]) / 2
    return m1 > 0 and m2 > 0 and abs(m1 - m2) / max(m1, m2) <= SALARY_GRAY_MAX


# ---------------------------------------------------------------- 相似度
def shingles(text, k=3, cap=200):
    """3-gram 的 crc32 哈希集合（截断到 cap 个）。"""
    t = clean_text(text)
    if not t:
        return np.empty(0, dtype=np.int64)
    if len(t) < k:
        return np.array([zlib.crc32(t.encode())], dtype=np.int64)
    grams = {zlib.crc32(t[i:i + k].encode()) for i in range(len(t) - k + 1)}
    return np.fromiter(grams, dtype=np.int64, count=len(grams))[:cap]


def minhash_sig(hashes):
    if not hashes.size:
        return np.zeros(MINHASH_PERM, dtype=np.int64)
    h = (HASH_A[:, None] * hashes[None, :] + HASH_B[:, None]) % PRIME
    return h.min(axis=1)


def jaccard(a, b, k=3):
    ta, tb = clean_text(a), clean_text(b)
    sa = {ta[i:i + k] for i in range(len(ta) - k + 1)}
    sb = {tb[i:i + k] for i in range(len(tb) - k + 1)}
    if not sa or not sb:
        return 1.0 if ta == tb else 0.0
    return len(sa & sb) / len(sa | sb)


_vec_cache = {}


def cosine(a, b, k=3):
    """字符 3-gram 词频向量的余弦相似度。"""
    def vec(t):
        t = clean_text(t)
        return Counter({t: 1}) if 0 < len(t) < k else Counter(t[i:i + k] for i in range(len(t) - k + 1))

    v1 = _vec_cache.setdefault(a, vec(a))
    v2 = _vec_cache.setdefault(b, vec(b))
    dot = sum(c * v2.get(g, 0) for g, c in v1.items())
    n1 = sum(c * c for c in v1.values()) ** 0.5
    n2 = sum(c * c for c in v2.values()) ** 0.5
    return dot / (n1 * n2) if n1 and n2 else 0.0


def pair_sim(a, b, ma, mb):
    """两条 JD 的（有效相似度, 判定方法）。"""
    if ma == mb:
        return 1.0, "EXACT"
    ja = jaccard(a, b)
    if ja >= DEDUP_EXACT_TH:
        return ja, "NEAR_DUP_MINHASH"
    co = cosine(a, b)
    method = "NEAR_DUP_MINHASH" if ja >= DEDUP_VEC_TH else "NEAR_DUP_EMBEDDING"
    return max(ja, co), method


class UnionFind:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


# ---------------------------------------------------------------- 三个步骤
def judge(body, row, city_map):
    """单条 JD 的丢弃判定，返回 (drop_reason, quality_flags)。"""
    resp, req, title, city = S(row.responsibility), S(row.requirement), S(row.name), S(row.city)
    plain = _WS.sub("", body)

    if not plain:
        return "EMPTY_TEXT", []
    if len(_CJK.findall(plain)) / len(plain) < CJK_MIN_RATIO:
        return "LANGUAGE", []
    if len(plain) < TOO_SHORT_LEN:
        return "TOO_SHORT", []

    contacts = sum(len(r.findall(body + " " + title)) for r in (_TEL, _QQ, _WX))
    wcount = sum(plain.count(w) for w in WELFARE_WORDS)
    wcover = sum(plain.count(w) * len(w) for w in WELFARE_WORDS) / max(len(plain), 1)
    if hit_ad(body) or hit_ad(title):
        return "NON_JOB_AD", []
    if len(plain) < AD_CONTACT_BODY and contacts >= AD_CONTACT_MIN \
            and not any(k in body for k in DUTY_KEYWORDS):
        return "NON_JOB_AD", []
    if _REPEAT.search(plain):
        return "LOW_QUALITY", []
    if len(plain) > 100 and wcount >= WELFARE_MIN_COUNT and wcover > WELFARE_COVER:
        return "LOW_QUALITY", []
    if len(set(plain)) < MIN_UNIQUE_CHARS:
        return "LOW_QUALITY", []
    if not title or city not in city_map:
        return "OTHER", []

    flags = []
    if len(plain) < TOO_SHORT_FLAG_LEN:
        flags.append("TOO_SHORT")
        if not resp or not req:
            flags.append("NO_JD_TEXT")
    return "", flags


def dedup(alive):
    """三层去重：EXACT（MD5）→ MinHash+LSH 分桶 → 向量余弦。
    同公司同城市才可比；灰区 [0.70, 0.85) 需薪资差 ≤ 30%。
    返回 (keep_idx, dedup_records, dup_dropped)。"""
    n = len(alive)
    body = alive["_body"]
    companies = [S(v) for v in alive["company"]]
    cities = [S(v) for v in alive["city"]]
    jd_ids = [str(v) for v in alive["id"]]
    md5s = [hashlib.md5("|".join(map(clean_text, (
        companies[i], cities[i], S(alive["name"].iloc[i]), body.iloc[i]))).encode()).hexdigest()
        for i in range(n)]

    def is_dup(i, j):
        eff, _ = pair_sim(body.iloc[i], body.iloc[j], md5s[i], md5s[j])
        return eff >= DEDUP_EXACT_TH or (eff >= DEDUP_GRAY_LO and salary_close(alive.iloc[i], alive.iloc[j]))

    # 第一层：强清洗后 MD5 完全一致
    uf = UnionFind(n)
    first_seen = {}
    for i, key in enumerate(md5s):
        if key in first_seen:
            uf.union(first_seen[key], i)
        else:
            first_seen[key] = i

    # 第二、三层：MinHash+LSH 分桶，桶内两两复核（桶键含公司+城市）
    sigs = np.vstack([minhash_sig(shingles(b)) for b in body])
    per_band = MINHASH_PERM // MINHASH_BANDS
    buckets = {}
    for i in range(n):
        bkey = companies[i] + "|" + cities[i]
        for band in range(MINHASH_BANDS):
            seg = sigs[i, band * per_band:(band + 1) * per_band]
            lst = buckets.setdefault((bkey, band, seg.tobytes()), [])
            for j in lst[-10:]:
                if uf.find(i) != uf.find(j) and is_dup(i, j):
                    uf.union(i, j)
            lst.append(i)

    groups = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)

    # 每组保留正文最长者（并列取 id 最小，保证可复现）
    keep_idx, dedup_records, dup_dropped = [], [], []
    gid = 0
    for members in groups.values():
        if len(members) == 1:
            keep_idx.append(members[0])
            continue
        rep = sorted(members, key=lambda i: (-len(_WS.sub("", body.iloc[i])), jd_ids[i]))[0]
        dropped, sims, methods = [], [], []
        for i in members:
            if i == rep:
                continue
            eff, method = pair_sim(body.iloc[i], body.iloc[rep], md5s[i], md5s[rep])
            if eff >= DEDUP_EXACT_TH or (eff >= DEDUP_GRAY_LO and salary_close(alive.iloc[i], alive.iloc[rep])):
                dropped.append(i)
                sims.append(eff)
                methods.append(method)
            else:
                keep_idx.append(i)
        keep_idx.append(rep)
        if not dropped:
            continue

        dup_dropped += dropped
        gid += 1
        dedup_records.append({
            "dedup_group_id": f"DG{gid:05d}",
            "kept_jd_id": jd_ids[rep],
            "dropped_jd_ids": "|".join(jd_ids[i] for i in dropped),
            "dedup_method": "EXACT" if all(m == "EXACT" for m in methods)
            else ("NEAR_DUP_MINHASH" if "NEAR_DUP_MINHASH" in methods else "NEAR_DUP_EMBEDDING"),
            "similarity": round(float(np.mean(sims)), 4),
        })
    return keep_idx, dedup_records, dup_dropped


def build_keep(alive, keep_idx, city_map, edu_map, ind_map):
    """拼装 jd_keep_ids.csv 的内容。"""
    std_job_map = {}
    if STD_JOB_FILE.exists():
        sj = pd.read_csv(STD_JOB_FILE, dtype=str)
        if {"job_title_raw", "std_job_id"}.issubset(sj.columns):
            std_job_map = dict(zip(sj["job_title_raw"].str.strip(), sj["std_job_id"].str.strip()))

    keep = alive.iloc[keep_idx].reset_index(drop=True)
    exp = [parse_experience(v) for v in keep["experience"]]
    out = pd.DataFrame({
        "jd_id": keep["id"].astype(str),
        "std_job_id": keep["name"].astype(str).str.strip().map(std_job_map).fillna(UNKNOWN_STD_JOB),
        "job_title_raw": keep["name"].astype(str).str.strip(),
        "city_code": keep["city"].astype(str).str.strip().map(city_map),
        "industry_code": keep["business"].astype(str).str.strip().map(ind_map).fillna(""),
        "education": keep["education"].astype(str).str.strip().map(edu_map).fillna(""),
        "publish_date": [to_date(v) for v in keep["time"]],
        "experience_min": pd.array([e[0] for e in exp], dtype="Int64"),
        "experience_max": pd.array([e[1] for e in exp], dtype="Int64"),
        "salary_min": pd.array([to_salary(v) for v in keep["starting_salary"]], dtype="Int64"),
        "salary_max": pd.array([to_salary(v) for v in keep["salary"]], dtype="Int64"),
    })

    # 质量标记 = 判定阶段的标记 + 薪资异常
    def flags_str(i):
        lo, hi = out["salary_min"].iloc[i], out["salary_max"].iloc[i]
        bad = pd.isna(lo) or pd.isna(hi) or lo <= 0 or hi < lo or lo > 200_000 or hi > 500_000
        return "|".join(x for x in ("|".join(keep["_flags"].iloc[i]), "SALARY_ANOMALY" if bad else "") if x)

    out["quality_flags"] = [flags_str(i) for i in range(len(out))]
    out["is_valid"] = (out["quality_flags"] == "").astype(int)
    return out[["jd_id", "std_job_id", "job_title_raw", "city_code", "industry_code",
                "education", "experience_min", "experience_max", "salary_min",
                "salary_max", "publish_date", "is_valid", "quality_flags"]]


def build_summary(raw, alive, dup_dropped):
    """拼装 jd_drop_summary.csv 的内容。"""
    counts = {r: 0 for r in DROP_REASONS}
    samples = {r: [] for r in DROP_REASONS}
    for reason, jd_id in zip(raw["_drop_reason"], raw["id"]):
        if reason:
            counts[reason] += 1
            if len(samples[reason]) < 20:
                samples[reason].append(str(jd_id))
    for i in dup_dropped:
        counts["DUPLICATE"] += 1
        if len(samples["DUPLICATE"]) < 20:
            samples["DUPLICATE"].append(str(alive["id"].iloc[i]))

    return pd.DataFrame([{
        "drop_reason": r,
        "record_count": counts[r],
        "rule_description": RULE_DESC[r],
        "sample_jd_ids": "|".join(samples[r]),
    } for r in DROP_REASONS])


# ---------------------------------------------------------------- 主流程
def main():
    raw = pd.read_excel(DATA_DIR / "raw_data.xlsx")
    city = pd.read_csv(DATA_DIR / "appendix_a_city_code.csv", dtype=str)
    edu = pd.read_csv(DATA_DIR / "appendix_b_education.csv", dtype=str)
    ind = pd.read_csv(DATA_DIR / "appendix_c_industry.csv", dtype=str)
    city_map = dict(zip(city["city_name"].str.strip(), city["city_code"].str.strip()))
    edu_map = dict(zip(edu["education_raw"].str.strip(), edu["education_std"].str.strip()))
    ind_map = dict(zip(ind["business_raw"].str.strip(), ind["industry_code"].str.strip()))
    print(f"[1/6] 读取原始数据 {len(raw)} 条")

    # 1. 逐条判定丢弃规则
    bodies = ["\n".join(x for x in (S(a), S(b)) if x)
              for a, b in zip(raw["responsibility"], raw["requirement"])]
    judged = [judge(b, r, city_map) for b, r in zip(bodies, raw.itertuples(index=False))]
    raw = raw.assign(_body=bodies, _drop_reason=[j[0] for j in judged], _flags=[j[1] for j in judged])
    print(f"[2/6] 规则判定完成，存活 {(raw['_drop_reason'] == '').sum()} 条")

    # 2. 去重
    alive = raw[raw["_drop_reason"] == ""].reset_index(drop=True)
    keep_idx, dedup_records, dup_dropped = dedup(alive)
    print(f"[3/6] 去重完成：{len(dedup_records)} 组，因重复丢弃 {len(dup_dropped)} 条")

    # 3. 三张表
    out = build_keep(alive, keep_idx, city_map, edu_map, ind_map)
    print(f"[4/6] jd_keep_ids.csv 生成完毕（{len(out)} 行）")
    summary = build_summary(raw, alive, dup_dropped)
    print(f"[5/6] jd_drop_summary.csv 生成完毕（丢弃 {summary['record_count'].sum()} 条）")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_DIR / "jd_keep_ids.csv", index=False, encoding="utf-8")
    summary.to_csv(OUT_DIR / "jd_drop_summary.csv", index=False, encoding="utf-8")
    pd.DataFrame(dedup_records, columns=[
        "dedup_group_id", "kept_jd_id", "dropped_jd_ids", "dedup_method", "similarity",
    ]).to_csv(OUT_DIR / "dedup_groups.csv", index=False, encoding="utf-8")
    print(f"[6/6] 输出目录：{OUT_DIR}")


if __name__ == "__main__":
    main()
