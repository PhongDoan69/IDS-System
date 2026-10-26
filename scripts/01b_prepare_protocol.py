"""Tạo scaler riêng cho corrected main/LOACO; không train model, không sửa Phase 2."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from src.console import configure_utf8_console
from src.model_config import load_model_config, experiment_id
from src.research_protocol import prepare_protocol


def main():
    configure_utf8_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(PROJECT_ROOT / 'configs/model_config.json'))
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--held-out-label-id', type=int)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    config = load_model_config(args.config)
    prepare_protocol(config, experiment_id(config, args.run_id), args.held_out_label_id, args.check_only)


if __name__ == '__main__':
    main()
