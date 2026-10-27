"""Select a recall-oriented Stage1 gate; never read test scores for selection."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.model_config import load_model_config, project_path
from src.artifact_contracts import read_contract, sha256
from src.contracts import assert_new_outputs
from src.gate_policy import select_gate
from src.training_utils import save_json


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--held-out-label-id', required=True, type=int)
    p.add_argument('--p-attack-path', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--fpr-budget', type=float, default=0.001)
    a = p.parse_args()
    config = load_model_config(a.config)
    output = Path(a.output).resolve()
    assert_new_outputs(output)
    path = Path(a.p_attack_path).resolve()
    read_contract(path, config, a.held_out_label_id, kind='p_attack', run_id=a.run_id)
    processed = project_path(config, config['experiment']['processed_dir'])
    labels = np.load(processed / 'attack_label_ids.npy', mmap_mode='r')
    splits = np.load(processed / 'split_ids.npy', mmap_mode='r')
    binary = np.load(processed / 'binary_labels.npy', mmap_mode='r')
    indices = np.flatnonzero((splits == 1) & (labels != a.held_out_label_id))
    scores = np.load(path, mmap_mode='r')
    record = select_gate(scores[indices], binary[indices], a.fpr_budget)
    record.update(run_id=a.run_id, held_out_label_id=a.held_out_label_id,
                  p_attack_path=str(path), p_attack_sha256=sha256(path),
                  validation_samples=len(indices), test_used_for_selection=False)
    save_json(output, record)
    print(record)


if __name__ == '__main__':
    main()
