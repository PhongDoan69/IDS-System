from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, output_path, project_path
from src.data_loader import inspect_schema, iter_csv_chunks, stable_row_hash
from src.preprocessing import TrainOnlyStandardScaler, clean_chunk, feature_columns, save_scaler
from src.split_data import TRAIN_ID, constrained_stratified_split, split_summary
from src.utils import ensure_directories, set_global_seed, write_json
from src.contracts import assert_new_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean, split, and scale CICIDS2017 without test leakage.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "base.json"))
    parser.add_argument("--max-rows-per-file", type=int, default=None)
    parser.add_argument("--output-dir", default=None)
    return parser.parse_args()


def collect_unique_metadata(config: dict, schema: list[str], limit: int | None):
    seen: set[int] = set()
    hash_parts: list[np.ndarray] = []
    label_parts: list[np.ndarray] = []
    binary_parts: list[np.ndarray] = []
    attempted_parts: list[np.ndarray] = []
    source_parts: list[np.ndarray] = []
    label_to_id: dict[str, int] = {'BENIGN': 0}
    source_to_id = {name: index for index, name in enumerate(config["data"]["files"])}
    counters = Counter()

    for source_file, _, raw_chunk in iter_csv_chunks(config, max_rows_per_file=limit):
        cleaned, report = clean_chunk(raw_chunk)
        counters["before_count"] += report["before_count"]
        counters["removed_invalid_count"] += report["removed_invalid_count"]
        hashes = stable_row_hash(cleaned, schema)
        keep = np.zeros(len(hashes), dtype=bool)
        for index, value in enumerate(hashes):
            key = int(value)
            if config["data"]["duplicate_policy"] == "drop_exact" and key in seen:
                counters["removed_duplicate_count"] += 1
                continue
            seen.add(key)
            keep[index] = True
        if not keep.any():
            continue

        labels = cleaned.loc[keep, "attack_label_normalized"]
        if any(label.casefold() == 'benign' and label != 'BENIGN' for label in labels.unique()):
            raise ValueError('Nhãn benign không đúng spelling BENIGN của protocol CICIDS2017; không đổi label ngầm')
        for label in labels.unique():
            if label not in label_to_id:
                label_to_id[label] = len(label_to_id)
        hash_parts.append(hashes[keep])
        label_parts.append(labels.map(label_to_id).to_numpy(dtype=np.int16))
        binary_parts.append(cleaned.loc[keep, "binary_label"].to_numpy(dtype=np.int8))
        attempted_parts.append(cleaned.loc[keep, "is_attempted"].to_numpy(dtype=np.int8))
        source_parts.append(np.full(int(keep.sum()), source_to_id[source_file], dtype=np.int8))

    counters["after_count"] = sum(len(part) for part in hash_parts)
    return (
        np.concatenate(hash_parts),
        np.concatenate(label_parts),
        np.concatenate(binary_parts),
        np.concatenate(attempted_parts),
        np.concatenate(source_parts),
        label_to_id,
        source_to_id,
        dict(counters),
    )


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    set_global_seed(int(config["random_state"]))
    schema = inspect_schema(config)
    features = feature_columns(schema, config["features"]["excluded"])
    if args.output_dir:
        processed_dir = project_path(config, args.output_dir)
        preprocessor_dir = processed_dir / "preprocessors"
        metadata_dir = processed_dir / "metadata"
        results_dir = processed_dir
    else:
        processed_dir = output_path(config, "processed_dir")
        preprocessor_dir = output_path(config, "preprocessors_dir")
        metadata_dir = output_path(config, "metadata_dir")
        results_dir = output_path(config, "results_dir")
    # Kiểm mọi output, kể cả metadata của lần chạy dở dang, trước khi ghi bất kỳ file nào.
    array_outputs = ['features_raw.npy', 'features_scaled.npy', 'row_hashes.npy',
                     'attack_label_ids.npy', 'binary_labels.npy', 'attempted_flags.npy',
                     'source_ids.npy', 'split_ids.npy', 'train_indices.npy',
                     'validation_indices.npy', 'test_indices.npy', 'split_summary.csv']
    metadata_outputs = ['feature_names.json', 'label_mapping.json', 'source_mapping.json',
                        'cleaning_report.json', 'split_config.json']
    assert_new_outputs(*(processed_dir / name for name in array_outputs),
                       *(metadata_dir / name for name in metadata_outputs),
                       preprocessor_dir / 'scaler.joblib', results_dir / 'split_summary.csv')
    ensure_directories([processed_dir, preprocessor_dir, metadata_dir, results_dir])

    (
        row_hashes,
        label_ids,
        binary_labels,
        attempted_flags,
        source_ids,
        label_to_id,
        source_to_id,
        cleaning_report,
    ) = collect_unique_metadata(config, schema, args.max_rows_per_file)

    split_config = config["split"]
    split_ids = constrained_stratified_split(
        label_ids,
        train_ratio=float(split_config["train"]),
        validation_ratio=float(split_config["validation"]),
        test_ratio=float(split_config["test"]),
        random_state=int(config["random_state"]),
    )

    sample_count = len(row_hashes)
    raw_path = processed_dir / "features_raw.npy"
    raw_matrix = np.lib.format.open_memmap(
        raw_path, mode="w+", dtype=config["features"]["dtype"], shape=(sample_count, len(features))
    )
    seen: set[int] = set()
    cursor = 0
    for _, _, raw_chunk in iter_csv_chunks(config, max_rows_per_file=args.max_rows_per_file):
        cleaned, _ = clean_chunk(raw_chunk)
        hashes = stable_row_hash(cleaned, schema)
        keep = np.zeros(len(hashes), dtype=bool)
        for index, value in enumerate(hashes):
            key = int(value)
            if config["data"]["duplicate_policy"] == "drop_exact" and key in seen:
                continue
            seen.add(key)
            keep[index] = True
        kept_hashes = hashes[keep]
        end = cursor + len(kept_hashes)
        if not np.array_equal(kept_hashes, row_hashes[cursor:end]):
            raise RuntimeError("Row order changed between preparation passes")
        values = cleaned.loc[keep, features].to_numpy(dtype=config["features"]["dtype"])
        if not np.isfinite(values).all():
            raise ValueError("Cleaned feature matrix contains NaN or infinity")
        raw_matrix[cursor:end] = values
        cursor = end
    raw_matrix.flush()
    if cursor != sample_count:
        raise RuntimeError(f"Expected {sample_count} prepared rows but wrote {cursor}")

    scaler = TrainOnlyStandardScaler()
    batch_size = int(config["data"]["chunksize"])
    for start in range(0, sample_count, batch_size):
        end = min(start + batch_size, sample_count)
        train_mask = split_ids[start:end] == TRAIN_ID
        scaler.partial_fit(raw_matrix[start:end][train_mask])
    save_scaler(scaler, preprocessor_dir / "scaler.joblib")

    scaled_matrix = np.lib.format.open_memmap(
        processed_dir / "features_scaled.npy",
        mode="w+",
        dtype=config["features"]["dtype"],
        shape=raw_matrix.shape,
    )
    for start in range(0, sample_count, batch_size):
        end = min(start + batch_size, sample_count)
        scaled_matrix[start:end] = scaler.transform(raw_matrix[start:end], config["features"]["dtype"])
    scaled_matrix.flush()

    arrays = {
        "row_hashes.npy": row_hashes,
        "attack_label_ids.npy": label_ids,
        "binary_labels.npy": binary_labels,
        "attempted_flags.npy": attempted_flags,
        "source_ids.npy": source_ids,
        "split_ids.npy": split_ids,
    }
    for name, values in arrays.items():
        np.save(processed_dir / name, values)
    for split_id, name in ((0, "train"), (1, "validation"), (2, "test")):
        np.save(processed_dir / f"{name}_indices.npy", np.flatnonzero(split_ids == split_id))

    id_to_label = {identifier: label for label, identifier in label_to_id.items()}
    summary = split_summary(split_ids, label_ids, id_to_label)
    summary.to_csv(processed_dir / "split_summary.csv", index=False)
    if results_dir != processed_dir:
        summary.to_csv(results_dir / "split_summary.csv", index=False)
    write_json(metadata_dir / "feature_names.json", {"features": features})
    write_json(metadata_dir / "label_mapping.json", {str(key): value for key, value in id_to_label.items()})
    write_json(metadata_dir / "source_mapping.json", {str(value): key for key, value in source_to_id.items()})
    write_json(metadata_dir / "cleaning_report.json", cleaning_report)
    write_json(
        metadata_dir / "split_config.json",
        {
            "random_state": config["random_state"],
            "ratios": split_config,
            "sample_count": sample_count,
            "max_rows_per_file": args.max_rows_per_file,
        },
    )
    print(f"Prepared {sample_count:,} unique valid rows with {len(features)} features")
    print(f"Train/validation/test: {np.bincount(split_ids, minlength=3).tolist()}")
    print(f"Processed data: {processed_dir}")


if __name__ == "__main__":
    main()
