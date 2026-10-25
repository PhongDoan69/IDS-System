
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data/external/CIC-UNSW-NB15")

data_path = DATA_DIR / "Data.csv"
label_path = DATA_DIR / "Lable.csv"

if not data_path.exists():
    raise FileNotFoundError(data_path)

# Chỉ đọc một phần nhỏ để kiểm tra schema
df = pd.read_csv(data_path, nrows=10, low_memory=False)
df.columns = df.columns.str.strip()

print("===== DATASET INFORMATION =====")
print("Số cột:", len(df.columns))
print("Tên các cột:")
for col in df.columns:
    print(repr(col))

print("\n===== SAMPLE DATA =====")
print(df.head())

print("\n===== DATA TYPES =====")
print(df.dtypes)

print("\n===== MISSING VALUES IN SAMPLE =====")
print(df.isna().sum())

print("\n===== LABEL FILE =====")
if label_path.exists():
    labels = pd.read_csv(label_path, nrows=10, header=None)
    print(labels.head())
else:
    print("Không tìm thấy Lable.csv")

print("\n===== LABEL METADATA =====")
readme_path = DATA_DIR / "Readme.txt"
if readme_path.exists():
    print(readme_path.read_text(
        encoding="utf-8", errors="replace"
    ))
