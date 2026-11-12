# -*- coding: utf-8 -*-
"""01 数据治理：清洗 / 去重 / 字段转换，实现集中在 governance.py。"""
from .governance import DataGovernance

if __name__ == "__main__":
    dg = DataGovernance()
    dg.execute()
