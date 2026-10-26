"""Stage 1 revised_v1: outer-fold chỉ predict; inner fit/stop/calibration riêng biệt."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.console import configure_utf8_console
from src.stage1_protocol import run_stage1


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(PROJECT_ROOT / 'configs/model_config.json'))
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--protocol', choices=['revised_v1'], required=True)
    parser.add_argument('--model', choices=['xgboost', 'mlp'], required=True)
    parser.add_argument('--representation', choices=['scaled', 'latent'], default='latent')
    parser.add_argument('--latent-path')
    parser.add_argument('--held-out-label-id', type=int)
    parser.add_argument('--check-only', action='store_true')
    return parser.parse_args()


def main():
    configure_utf8_console()
    run_stage1(parse_args())


if __name__ == '__main__':
    main()
