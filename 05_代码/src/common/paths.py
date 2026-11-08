# -*- coding: utf-8 -*-
"""集中路径常量（供 main.py 与各模块共用）。

职责：
    - 项目根目录 ROOT、代码目录 CODE_DIR；
    - data/ 下三阶段输入：raw_jd_full.csv、field_dictionary.csv、
      jd_job_fields.csv、jd_text_corpus.csv；
    - 附录 A/B/C 映射表路径（现位于 data/ 根目录）；
    - 产出目录 01_数据治理 / 02_岗位归一化 / 03_技能抽取 及各表文件路径。

约定：
    - 只放常量与目录创建等辅助函数，不放业务逻辑；
    - data/ 不入库、不打包，路径集中在此便于队友本地调整。
"""
