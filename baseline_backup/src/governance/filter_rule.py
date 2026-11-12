import pandas as pd
import re


def is_missing(value):
    """安全的缺失判断：None/NaN 视为缺失；list/空容器也视为缺失。"""
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def clean_text(text):
    if is_missing(text):
        return ""
    text = str(text)
    text = re.sub(r"\s+", "", text)
    return text


def check_city(city_name, city_dict):
    """城市名命中字典（含'深圳市'/'深圳'两种写法）才算通过。"""
    if is_missing(city_name):
        return False
    name = str(city_name).strip()
    if name in city_dict:
        return True
    if name.endswith("市") and name[:-1] in city_dict:
        return True
    return False


def judge_ad(title, content, ban_words):
    title_clean = clean_text(title)
    content_clean = clean_text(content)
    full_text = title_clean + content_clean
    for word in ban_words:
        if word in full_text:
            return True
    if len(content_clean) < 200:
        phone = len(re.findall(r"1[3-9]\d{9}", content_clean))
        qq = len(re.findall(r"QQ[:：]\d+", content_clean))
        wechat = len(re.findall(r"微信[:：]\w+", content_clean))
        if phone + qq + wechat >= 3:
            return True
    return False


def judge_low_quality(content, welfare_words):
    content_clean = clean_text(content)
    if len(content_clean) <= 100:
        return False
    hit = 0
    for w in welfare_words:
        hit += content_clean.count(w)
    if hit / len(content_clean) > 0.3:
        return True
    if re.search(r"(.)\1{3,}", content_clean):
        return True
    return False


def single_filter(row, ban_words, welfare_words, city_dict):
    content = clean_text(row.get("jd_content"))
    if len(content) == 0:
        return False, "D01"
    # D05 必须放在 D02 之前：核心字段缺失不能被误计为"非广东城市"
    if is_missing(row.get("job_title_raw")) or is_missing(row.get("city_name")):
        return False, "D05"
    if not check_city(row.get("city_name"), city_dict):
        return False, "D02"
    if judge_low_quality(row.get("jd_content"), welfare_words):
        return False, "D03"
    if judge_ad(row.get("job_title_raw"), row.get("jd_content"), ban_words):
        return False, "D04"
    return True, None
