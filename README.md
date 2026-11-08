# 初赛提交包项目（GitHub 协作仓库）

本仓库严格按照《初赛赛事指导文件（参赛者版）》搭建。四步走：**建目录 → 填表 → 自查 → 打包**。

## 一、目录结构（与提交包完全一致，目录/文件名一个都不能改）

```text
<团队编号>.zip
├─ 00_manifest.json          # 提交包身份证明 + 目录（team_id 为占位符 T0001，待替换）
├─ 01_数据治理/
│   ├─ jd_keep_ids.csv       # 保留 JD 清单（含归一化结果）
│   ├─ jd_drop_summary.csv   # 丢弃原因统计
│   └─ dedup_groups.csv      # 重复组与保留代表
├─ 02_岗位归一化/
│   ├─ std_job.csv           # 标准岗位总表
│   ├─ jd_job_map.csv        # JD → 标准岗位归属
│   └─ synonym_pairs.csv     # 别名 → 规范名对照
├─ 03_技能抽取/
│   └─ skill.csv             # 技能点明细
├─ 04_说明文档/
│   ├─ 数据集说明文档.pdf     # 评审用整体说明（待撰写）
│   ├─ data_dictionary.md    # 自建/改写字段说明
│   └─ self_check_report.md  # 自评报告
├─ 05_代码/
│   ├─ main.py                    # 一键复现入口（Python 3）
│   ├─ prepare_data.py            # 本地阶段数据准备（读取 data/，随代码分发）
│   ├─ requirements.txt           # 依赖清单
│   └─ src/                       # 其余 Python 源码按模块放这里
└─ 06_校验/
    └─ validate_report.json  # validate.py 输出（当前为占位）
```

仓库根目录的协作文件（README、.gitignore）打包时**不会**放入 zip。
附录 A/B/C 三张映射表已移到本地 `data/` 根目录，不在提交包内（见第二、三节）。

### 附录映射表（从指导文件 Word 附录 A/B/C 提取）

| 文件（位于 `data/` 根目录）     | 来源                      | 列                                                       | 用途                                                                                 |
| --------------------------------- | ------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `data/appendix_a_city_code.csv` | 附录 A 广东省 21 地市     | `city_name` / `city_code` / `city_full_name`       | `jd_keep_ids.city_code` 查表；非广东值及空值留空，`is_valid` 可标 0              |
| `data/appendix_b_education.csv` | 附录 B 学历原始值         | `education_raw` / `education_std` / `note`         | `jd_keep_ids.education` 映射                                                       |
| `data/appendix_c_industry.csv`  | 附录 C 行业（节选，选填） | `business_raw` / `industry_code` / `industry_name` | `jd_keep_ids.industry_code` 查表；表里没有的可按 GB/T 4754-2017 推断，推断不了留空 |

这三张表是 `main.py` 复现时做字段转换的查表数据，现放在本地 `data/` 根目录（与官方原始数据同目录）。

注意：`data/` 被 `.gitignore` 排除，这三张表不会入库、也不在提交包内。队友 `clone` 后需自行按附录提取或从团队内部获取，放到 `data/` 根目录，否则 `main.py` 会因缺表失败；若后续官方校验要求查表数据随包分发，需再放回 `05_代码/`。
