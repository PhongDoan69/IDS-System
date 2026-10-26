"""Kiểm schema/cleaning/label alignment external, không training hoặc download."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src.console import configure_utf8_console
from src.contracts import assert_new_outputs
from src.external_data import inspect_external
from src.training_utils import save_json


def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=['CSE-CIC-IDS2018', 'CIC-UNSW-NB15'], required=True)
    parser.add_argument('--data-dir')
    parser.add_argument('--feature-metadata', default=str(PROJECT_ROOT / 'artifacts/metadata/feature_names.json'))
    parser.add_argument('--rows-per-file', type=int, default=1000)
    parser.add_argument('--full', action='store_true', help='Đọc toàn CSV; tốn I/O, không phải model training')
    parser.add_argument('--output', help='JSON mới; nếu bỏ qua chỉ in stdout')
    args = parser.parse_args()
    if args.rows_per_file <= 0:
        parser.error('--rows-per-file phải dương')
    if args.output:
        assert_new_outputs(Path(args.output))
    names = json.loads(Path(args.feature_metadata).read_text(encoding='utf-8'))['features']
    root = Path(args.data_dir) if args.data_dir else PROJECT_ROOT / 'data/external' / args.dataset
    report = inspect_external(args.dataset, root, names, None if args.full else args.rows_per_file)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.output:
        save_json(Path(args.output), report)


if __name__ == '__main__':
    main()
