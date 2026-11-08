from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
RAW_XLSX = DATA_DIR / "raw_data.xlsx"

df = pd.read_excel(RAW_XLSX)
print(df.head())
print("列数：", df.shape[1], "行数：", df.shape[0])
