from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config, output_path
from src.data_loader import audit_dataset, raw_manifest
from src.utils import ensure_directories, write_json
from src.contracts import assert_new_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the configured CICIDS2017 CSV files.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "base.json"))
    parser.add_argument('--output-dir', default=None, help='Thư mục mới để không ghi đè audit cũ')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    results_dir = output_path(config, "results_dir")
    metadata_dir = output_path(config, "metadata_dir")
    if args.output_dir:
        results_dir = Path(args.output_dir).resolve()
        metadata_dir = results_dir / 'metadata'
    assert_new_outputs(results_dir / 'dataset_summary.csv', results_dir / 'label_distribution.csv',
                       results_dir / 'data_quality_report.json', metadata_dir / 'raw_manifest.json', metadata_dir / 'schema.json')
    ensure_directories([results_dir, metadata_dir])

    report = audit_dataset(config)
    manifest = raw_manifest(config)
    total_rows = report["total_rows"]

    pd.DataFrame(
        [
            {
                "file": item["file"],
                "rows": report["rows_by_file"][item["file"]],
                "columns": report["column_count"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
            }
            for item in manifest
        ]
    ).to_csv(results_dir / "dataset_summary.csv", index=False)

    pd.DataFrame(
        [
            {
                "label": label,
                "count": count,
                "percentage": 100.0 * count / total_rows,
            }
            for label, count in report["label_counts"].items()
        ]
    ).to_csv(results_dir / "label_distribution.csv", index=False)

    write_json(results_dir / "data_quality_report.json", report)
    write_json(metadata_dir / "raw_manifest.json", manifest)
    write_json(metadata_dir / "schema.json", {"columns": report["schema"]})
    print(f"Audited {total_rows:,} rows across {len(manifest)} files")
    print(f"Exact duplicate occurrences by row hash: {report['duplicate_rows_by_hash']:,}")
    print(f"Results: {results_dir}")


if __name__ == "__main__":
    main()
