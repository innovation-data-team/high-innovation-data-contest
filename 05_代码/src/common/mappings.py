# -*- coding: utf-8 -*-
"""附录 A/B/C 查表封装。

职责：
    - appendix_a_city_code.csv：city → 6 位行政区划代码（非广东/空值留空）；
    - appendix_b_education.csv：学历原始值 → 规范枚举；
    - appendix_c_industry.csv：business → 国民经济行业分类代码。

说明：
    - 三张表现位于本地 data/ 根目录（不入库、不打包），路径常量见 common.paths；
    - 三张表为权威映射，代码只做查表与兜底，不在代码里硬编码映射结果；
    - 查不到的键按字段要求留空（city_code 另可用 is_valid 标 0）。
"""
