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

| 文件（位于 `data/` 根目录） | 来源 | 列 | 用途 |
| --- | --- | --- | --- |
| `data/appendix_a_city_code.csv` | 附录 A 广东省 21 地市 | `city_name` / `city_code` / `city_full_name` | `jd_keep_ids.city_code` 查表；非广东值及空值留空，`is_valid` 可标 0 |
| `data/appendix_b_education.csv` | 附录 B 学历原始值 | `education_raw` / `education_std` / `note` | `jd_keep_ids.education` 映射 |
| `data/appendix_c_industry.csv` | 附录 C 行业（节选，选填） | `business_raw` / `industry_code` / `industry_name` | `jd_keep_ids.industry_code` 查表；表里没有的可按 GB/T 4754-2017 推断，推断不了留空 |

这三张表是 `main.py` 复现时做字段转换的查表数据，现放在本地 `data/` 根目录（与官方原始数据同目录）。它们属于**自建辅助映射表**，不是 01~03 的产出表，表头为自建命名（指导文件「表头照抄」铁律只约束 01~03 各表）。原始 Word 中括号内的中文名称已拆为独立列，代码列保留原文组合值（如 `C34/C35`）。

注意：`data/` 被 `.gitignore` 排除，这三张表不会入库、也不在提交包内。队友 `clone` 后需自行按附录提取或从团队内部获取，放到 `data/` 根目录，否则 `main.py` 会因缺表失败；若后续官方校验要求查表数据随包分发，需再放回 `05_代码/`。

## 二、本地数据目录 `data/`（严禁入库）

`data/` 整体被 `.gitignore` 排除。队友 `clone` 后需自行从官方渠道下载原始文件，并把附录 A/B/C 三张映射表放到 `data/` 根目录，再运行 `prepare_data.py` 生成三阶段输入：

```text
data/                                      ← 官方原始文件与查表数据放这里（不入库、不打包）
├─ 团队预览_5万条.xlsx                     # 官方原始 JD，50000 行 × 19 列
├─ 数据集字段解释.xlsx                     # 官方字段字典，18 个字段
├─ 初赛赛事指导文件（参赛者版） (2).docx     # 规范原件（附录已提取到 data/）
├─ appendix_a_city_code.csv                # 附录 A：地市 → 行政区划代码
├─ appendix_b_education.csv                # 附录 B：学历原始值 → 规范枚举
├─ appendix_c_industry.csv                 # 附录 C：行业 → 行业分类代码
├─ 01_数据治理/                           # 阶段一输入
│   ├─ raw_jd_full.csv                    # 50000 × 19，全量原始字段
│   └─ field_dictionary.csv                # 18 行，原始字段解释
├─ 02_岗位归一化/                         # 阶段二输入
│   └─ jd_job_fields.csv                   # 50000 × 17，结构化岗位字段（不含长正文）
└─ 03_技能抽取/                           # 阶段三输入
    └─ jd_text_corpus.csv                  # 50000 × 4，id/name/responsibility/requirement 原文
```

| 目录 | 切分依据 | 对应产出 |
| --- | --- | --- |
| `01_数据治理` | 清洗、去重、判空、薪资/学历/城市/行业转换需要全量字段与双正文 | `01_数据治理/` 三张表 |
| `02_岗位归一化` | 岗位聚类用 `name`/`keyword`/`business`/`city`/`education`/`experience` 等结构化字段，排除长文本便于向量化与规则匹配 | `02_岗位归一化/` 三张表 |
| `03_技能抽取` | `evidence_span` 必须能在对应 `jd_id` 原文中定位，故单独保留 `responsibility` + `requirement` 原文 | `03_技能抽取/skill.csv` |

补充说明：

- 三份阶段输入 CSV 均为 UTF-8 无 BOM、RFC 4180（`requirement` 含换行/逗号时自动加双引号），由 `05_代码/prepare_data.py` 生成，属于**可重建的本地中间产物，不入库、不打包**；附录 A/B/C 三张映射表同在 `data/`，但不是中间产物，不能删。
- `02_岗位归一化/` 还需《国家职业分类大典（2022 版）》细类代码表、官方映射表等资产（对应 `00_manifest.json` 的 `official_assets_version`）。官方发布后放入该目录，并在 manifest 登记版本号。
- 不要把全量清洗文本或大体积中间文件塞进提交包（指导文件常见错误 12）。

## 三、填表铁律（违反脚本无法解析）

1. 编码统一 **UTF-8 无 BOM**，CSV 遵循 RFC 4180（禁止 Excel 直接另存）
2. 表头名照抄指导文档，不可改名/翻译/加空格
3. 多值字段用竖线 `|` 分隔，前后不加空格
4. 空值直接留空，不写 NULL/None/NaN/-/无/N/A
5. 布尔用 1/0；比率用 0-1 小数；日期 YYYY-MM-DD 补零
6. `jd_id` 沿用官方原始 ID；ID 形如 `STJ_000001`（前缀+6 位序号）
7. 含逗号/换行/引号的单元格整格用双引号包裹
8. 外键必须能对上；`std_job.jd_count` 必须等于 `jd_job_map.csv` 中该岗位行数
9. 复现入口固定为 `05_代码/main.py`（Python 3，不用 run.sh）

## 四、GitHub 协作规范

- `main` 分支保持可提交状态；开发请在 `feature/<模块>` 分支进行，PR 合并
- 模块建议分工：`01_数据治理` / `02_岗位归一化` / `03_技能抽取` / `04_说明文档` 各设负责人
- `05_代码/` 下按模块拆分源码，`main.py` 只做编排入口
- 提交信息建议：`[治理] 去重规则实现`、`[归一化] 簇名生成` 这类前缀
- **官方原始数据严禁上传到 GitHub**：`data/`、`*.xlsx`、`*.docx` 已在 `.gitignore` 中排除，也不要用 `git add -f` 绕过
- `data/01~03` 的阶段数据由 `prepare_data.py` 本地重建，不要手工提交或在群里互传大 CSV
- 打包 zip 时只包含 `00_manifest.json` + `01~06` 目录，禁止放入原始数据或清洗中间产物

## 五、常用命令

```powershell
# 安装依赖
pip install -r 05_代码/requirements.txt

# 准备三阶段数据（首次 clone 或原始文件更新后运行；官方原始 xlsx 需先放入 data/）
python 05_代码/prepare_data.py

# 一键复现（产出 01~03 各表）
python 05_代码/main.py

# 官方校验（通过后把输出的 validate_report.json 放进 06_校验/）
python validate.py --package P1_<团队编号>.zip --stage P1
```

## 六、待办

- [ ] 替换 `00_manifest.json` 中的占位 `team_id`（T0001 → 实际团队编号）
- [ ] 队友各自把官方原始文件与附录 A/B/C 三张映射表放入本地 `data/` 根目录并运行 `prepare_data.py`（严禁入库 / 打包）
- [ ] 官方大典代码表等资产发布后放入 `data/02_岗位归一化/`，登记 `official_assets_version`
- [ ] 撰写 `04_说明文档/数据集说明文档.pdf`
- [ ] 运行 `validate.py` 生成真实 `06_校验/validate_report.json`
