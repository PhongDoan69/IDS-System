import pandas as pd
from pathlib import Path

data_dir = Path("data/external/CSE-CIC-IDS2018")

csv_files = sorted(data_dir.glob("*.csv"))

print("Number of CSV files:", len(csv_files))

for file in csv_files:
    df = pd.read_csv(file, nrows=5, low_memory=False)

    print("\nFile:", file.name)
    print("Number of features:", len(df.columns))
    print("Columns:", df.columns.tolist())
    print("First 5 rows:")
    print(df.head())

    label_cols = [
        c for c in df.columns
        if c.strip().lower() == "label"
    ]

    if label_cols:
        print("Label column:", label_cols[0])