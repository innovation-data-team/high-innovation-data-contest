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
│   ├─ main.py               # 一键复现入口（Python 3）
│   ├─ requirements.txt      # 依赖清单
│   └─ （其余 Python 源码放这里）
└─ 06_校验/
    └─ validate_report.json  # validate.py 输出（当前为占位）
```

多放的文件（如 README、.gitignore）打包时**不会**放入 zip，仅用于仓库协作。

## 二、填表铁律（违反脚本无法解析）

1. 编码统一 **UTF-8 无 BOM**，CSV 遵循 RFC 4180（禁止 Excel 直接另存）
2. 表头名照抄指导文档，不可改名/翻译/加空格
3. 多值字段用竖线 `|` 分隔，前后不加空格
4. 空值直接留空，不写 NULL/None/NaN/-/无/N/A
5. 布尔用 1/0；比率用 0-1 小数；日期 YYYY-MM-DD 补零
6. `jd_id` 沿用官方原始 ID；ID 形如 `STJ_000001`（前缀+6 位序号）
7. 含逗号/换行/引号的单元格整格用双引号包裹
8. 外键必须能对上；`std_job.jd_count` 必须等于 `jd_job_map.csv` 中该岗位行数
9. 复现入口固定为 `05_代码/main.py`（Python 3，不用 run.sh）

## 三、GitHub 协作规范

- `main` 分支保持可提交状态；开发请在 `feature/<模块>` 分支进行，PR 合并
- 模块建议分工：`01_数据治理` / `02_岗位归一化` / `03_技能抽取` / `04_说明文档` 各设负责人
- `05_代码/` 下按模块拆分源码，`main.py` 只做编排入口
- 提交信息建议：`[治理] 去重规则实现`、`[归一化] 簇名生成` 这类前缀

## 四、常用命令

```powershell
# 安装依赖
pip install -r 05_代码/requirements.txt

# 一键复现（产出 01~03 各表）
python 05_代码/main.py

# 官方校验（通过后把输出的 validate_report.json 放进 06_校验/）
python validate.py --package P1_<团队编号>.zip --stage P1
```

## 五、待办

- [ ] 替换 `00_manifest.json` 中的占位 `team_id`（T0001 → 实际团队编号）
- [ ] 官方原始数据放入 `data/`（已 gitignore，不入库）
- [ ] 撰写 `04_说明文档/数据集说明文档.pdf`
- [ ] 运行 `validate.py` 生成真实 `06_校验/validate_report.json`
