# -*- coding: utf-8 -*-
"""枚举 / 主键 / 外键自查。

职责：
    - 枚举取值白名单（drop_reason、dedup_method、assignment_method、
      skill_type、proficiency、importance、source_type、extractor 等）；
    - 主键唯一性（jd_id / std_job_id / skill_id）；
    - 外键完整性（jd_keep_ids→std_job、jd_job_map→两张表、skill→std_job）；
    - std_job.jd_count 与 jd_job_map 行数一致性。

说明：
    - 本模块只做提交前自检，不产出报告文件；
    - 官方校验以 validate.py 的 validate_report.json 为准。
"""
