基线版本备份（冻结，不改动业务逻辑）
=====================================

备份时间：2026-11-11
来源：05_代码/（改造前可运行完整版本）

基线行为（全量 50000 条，约 36 秒）：
- 保留 44884 条
- D01=182  D02=0  D03=2508  D04=3  D05=15  D06=2408
- 去重重复组 1088 组（dedup_groups.csv 只记录真正的重复组，不含单条）
- 输出直接写入 01_数据治理/（无 output_run_* 子目录）

包含的关键业务逻辑（后续副本不得改动）：
- responsibility + requirement 拼接为 jd_content（merge_jd_content）
- 附录A 城市字典加载与 city_code 映射（load_city_dict / city_code_of）
- numpy 向量化汉明距离 simhash 去重（dedup_rule.run_deduplicate，threshold=3）

内容：
- main.py、requirements.txt
- src/__init__.py、src/governance/{governance.py, filter_rule.py, dedup_rule.py, __init__.py}
- src/governance/__init__.py 已修复循环导入（from .governance import DataGovernance）

约定：
- 此目录只作对照与回滚，不参与运行、不随提交包打包
- 后续所有实验性修改在 05_代码/ 上进行
- 依赖：pandas>=2.0, openpyxl>=3.1, simhash>=2.1, numpy>=1.26
- 运行方式：cd 05_代码 && python main.py（数据在仓库根 data/，即 Desktop/sjk/data 的联接）
