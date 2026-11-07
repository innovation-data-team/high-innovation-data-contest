# self_check_report（自评报告）

> 逐项对照《五、提交前自查清单》，记每项检查的结论与证据。提交前必须全部通过。

| # | 自查项 | 结论 | 证据 |
| --- | --- | --- | --- |
| 1 | 目录结构与一级目录名、文件名与第一节完全一致，没加后缀 | 待检查 | 目录树 / ls 输出 |
| 2 | 主键在各表内唯一：jd_id / std_job_id / skill_id | 待检查 | pandas duplicated 统计 |
| 3 | std_job.jd_count = jd_job_map.csv 中该岗位的行数 | 待检查 | groupby 对账脚本输出 |
| 4 | manifest.record_counts = 各表实际行数 | 待检查 | 对账脚本输出 |
| 5 | 枚举值都在文档给出的列表内，没有自造值、没有大小写混用 | 待检查 | 枚举校验脚本输出 |
| 6 | 每个 std_job_name 是有意义的真实岗位名，且 job_family 已填 | 待检查 | 抽样清单 |
| 7 | 已运行 validate.py 并把 validate_report.json 放进 06_校验/ | 待检查 | 06_校验/validate_report.json |
| 8 | 提交包 ≤ 10 GB，单文件 ≤ 2 GB | 待检查 | 文件大小统计 |

## 编码与格式铁律自查

- [ ] 所有 CSV 为 UTF-8 无 BOM，遵循 RFC 4180（首行表头）
- [ ] 表头名照抄指导文档，未改名、未翻译、无多余空格
- [ ] 多值字段用竖线 `|` 分隔，分隔符前后无空格
- [ ] 空值直接留空（无 NULL/None/NaN/-/无/N/A）
- [ ] 布尔值用 1/0
- [ ] 比率用 0-1 小数，无百分号
- [ ] 日期为 YYYY-MM-DD（月日补零）
- [ ] jd_id 沿用官方原始 ID 未重编
- [ ] 含逗号/换行/引号的单元格用双引号包裹
- [ ] 所有外键均能对上（jd_keep_ids.std_job_id → std_job；jd_job_map 两侧；skill.std_job_id）
- [ ] 复现入口为 05_代码/main.py（Python 3），未使用 run.sh
