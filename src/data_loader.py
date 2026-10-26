from __future__ import annotations

from collections import Counter, defaultdict
import csv
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from src.config import project_path
from src.utils import sha256_file


def normalize_column_names(columns: list[object]) -> list[str]:
    normalized = [" ".join(str(column).strip().split()) for column in columns]
    if len(set(normalized)) != len(normalized) or any(not c for c in normalized):
        raise ValueError('Tên cột rỗng hoặc trùng sau chuẩn hóa')
    return normalized


def dataset_paths(config: dict) -> list[Path]:
    raw_dir = project_path(config, config["data"]["raw_dir"])
    paths = [raw_dir / name for name in config["data"]["files"]]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing configured CICIDS2017 files: {missing}")
    return paths


def inspect_schema(config: dict) -> list[str]:
    schemas: dict[str, list[str]] = {}
    for path in dataset_paths(config):
        # Đọc header gốc trước pandas: pandas có thể tự đổi duplicate thành tên .1,
        # làm mất bằng chứng schema trùng nếu chỉ kiểm DataFrame.columns.
        with path.open('r', encoding='utf-8-sig', newline='') as stream:
            columns = normalize_column_names(next(csv.reader(stream), []))
        schemas[path.name] = columns
    unique = {tuple(columns) for columns in schemas.values()}
    if len(unique) != 1:
        raise ValueError(f"CSV schemas are inconsistent: {schemas}")
    schema = next(iter(schemas.values()))
    for required in ("Label", "Attempted Category", "Timestamp"):
        if required not in schema:
            raise ValueError(f"Required column is missing: {required}")
    return list(schema)


def iter_csv_chunks(
    config: dict,
    *,
    max_rows_per_file: int | None = None,
) -> Iterator[tuple[str, int, pd.DataFrame]]:
    chunksize = int(config["data"]["chunksize"])
    expected_schema = inspect_schema(config)
    for path in dataset_paths(config):
        emitted = 0
        for chunk in pd.read_csv(path, chunksize=chunksize, low_memory=False):
            chunk.columns = normalize_column_names(chunk.columns.tolist())
            if chunk.columns.tolist() != expected_schema:
                raise ValueError(f"Schema changed while reading {path.name}")
            if max_rows_per_file is not None:
                remaining = max_rows_per_file - emitted
                if remaining <= 0:
                    break
                chunk = chunk.iloc[:remaining].copy()
            if chunk.empty:
                break
            yield path.name, emitted, chunk
            emitted += len(chunk)


def stable_row_hash(frame: pd.DataFrame, columns: list[str]) -> np.ndarray:
    return pd.util.hash_pandas_object(frame[columns], index=False).to_numpy(dtype=np.uint64)


def raw_manifest(config: dict) -> list[dict]:
    manifest = []
    for path in dataset_paths(config):
        manifest.append(
            {
                "file": path.name,
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return manifest


def audit_dataset(config: dict) -> dict:
    schema = inspect_schema(config)
    rows_by_file: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    attempted_counts: Counter[str] = Counter()
    missing_counts: Counter[str] = Counter()
    infinity_counts: Counter[str] = Counter()
    invalid_numeric_counts: Counter[str] = Counter()
    dtype_sets: dict[str, set[str]] = defaultdict(set)
    first_values: dict[str, str] = {}
    nonconstant: set[str] = set()
    seen_hashes: set[int] = set()
    duplicate_count = 0
    expected_non_numeric = {"Timestamp", "Label"}

    for source_file, _, chunk in iter_csv_chunks(config):
        rows_by_file[source_file] += len(chunk)
        label_counts.update(chunk["Label"].astype(str))
        attempted_counts.update(chunk["Attempted Category"].astype(str))
        missing = chunk.isna().sum()
        missing_counts.update({key: int(value) for key, value in missing.items() if value})

        numeric = chunk.select_dtypes(include=[np.number])
        if len(numeric.columns):
            infinities = np.isinf(numeric).sum()
            infinity_counts.update(
                {key: int(value) for key, value in infinities.items() if value}
            )

        for column in chunk.columns:
            dtype_sets[column].add(str(chunk[column].dtype))
            values = chunk[column].drop_duplicates().head(2).tolist()
            for value in values:
                key = "<NA>" if pd.isna(value) else repr(value)
                if column not in first_values:
                    first_values[column] = key
                elif first_values[column] != key:
                    nonconstant.add(column)

            if column not in expected_non_numeric and not pd.api.types.is_numeric_dtype(chunk[column]):
                converted = pd.to_numeric(chunk[column], errors="coerce")
                bad = chunk[column].notna() & converted.isna() & chunk[column].astype(str).str.strip().ne("")
                if bad.any():
                    invalid_numeric_counts[column] += int(bad.sum())

        for value in stable_row_hash(chunk, schema):
            row_hash = int(value)
            if row_hash in seen_hashes:
                duplicate_count += 1
            else:
                seen_hashes.add(row_hash)

    return {
        "total_rows": int(sum(rows_by_file.values())),
        "column_count": len(schema),
        "schema": schema,
        "rows_by_file": dict(rows_by_file),
        "label_counts": dict(label_counts.most_common()),
        "attempted_category_counts": dict(attempted_counts.most_common()),
        "missing_total": int(sum(missing_counts.values())),
        "missing_by_column": dict(missing_counts),
        "infinity_total": int(sum(infinity_counts.values())),
        "infinity_by_column": dict(infinity_counts),
        "invalid_numeric_total": int(sum(invalid_numeric_counts.values())),
        "invalid_numeric_by_column": dict(invalid_numeric_counts),
        "duplicate_rows_by_hash": int(duplicate_count),
        "constant_columns": [column for column in schema if column not in nonconstant],
        "dtype_sets": {column: sorted(values) for column, values in dtype_sets.items()},
    }
