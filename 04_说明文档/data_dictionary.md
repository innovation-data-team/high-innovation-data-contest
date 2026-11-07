# data_dictionary（数据字典）

> 说明：本文件记录自建 / 改写字段的含义、取值与生成方式。逐表逐字段填写。

## 01_数据治理/jd_keep_ids.csv

| 字段 | 类型 | 取值/格式 | 生成方式 |
| --- | --- | --- | --- |
| jd_id | 字符串 | 官方原始 id，不重编 | 沿用官方主键 |
| std_job_id | 字符串 | STJ_xxxxxx；未归一填 STJ_000000 | 岗位归一化模块输出 |
| job_title_raw | 字符串 | 原始岗位名 | 原始 CSV `name` 列 |
| city_code | 字符串 | 6 位行政区划代码（GB/T 2260） | `city` 查附录 A；非广东/空值留空 |
| industry_code | 字符串 | GB/T 4754 行业代码 | `business` 查附录 C；无法映射留空 |
| education | 枚举 | 不限/初中及以下/高中/中专/大专/本科/硕士/博士 | 原始值查附录 B 映射 |
| experience_min | 整型 | 年；无经验→0，10 年以上→10 | 从原始经验字段解析 |
| experience_max | 整型 | 年；不限/无经验→0，10 年以上→-1 | 从原始经验字段解析 |
| salary_min | 整型 | 元/月 | `starting_salary` × 1000；缺失留空 |
| salary_max | 整型 | 元/月 | `salary` × 1000；缺失留空 |
| publish_date | 日期 | YYYY-MM-DD | 原始 `time` 列 |
| is_valid | 布尔 | 1=有效 / 0=无效 | 清洗规则判定 |
| quality_flags | 字符串 | 竖线分隔：NO_JD_TEXT/SALARY_ANOMALY/TOO_SHORT | 清洗规则标记，无则留空 |

## 01_数据治理/jd_drop_summary.csv

（待填写：drop_reason 枚举为 DUPLICATE/EMPTY_TEXT/NON_JOB_AD/TOO_SHORT/LANGUAGE/LOW_QUALITY/OTHER）

## 01_数据治理/dedup_groups.csv

（待填写：dedup_method 枚举为 EXACT/NEAR_DUP_MINHASH/NEAR_DUP_EMBEDDING/MANUAL）

## 02_岗位归一化/std_job.csv

（待填写：含大典层级码 dadian_l1/l2/l3_code 与 job_family）

## 02_岗位归一化/jd_job_map.csv

（待填写：assignment_method 枚举为 RULE/EMBEDDING/LLM/MANUAL/HYBRID）

## 02_岗位归一化/synonym_pairs.csv

（待填写）

## 03_技能抽取/skill.csv

（待填写：skill_type 枚举为 HARD_SKILL/SOFT_SKILL/TOOL/CERTIFICATE/LITERACY/SCENE）
