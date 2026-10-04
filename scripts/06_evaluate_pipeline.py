from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation import UNKNOWN_ATTACK_ID, compose_pipeline_predictions
from src.console import configure_utf8_console
from src.metrics import binary_metrics, multiclass_metrics, open_set_metrics
from src.model_config import experiment_id, load_model_config, phase_directory, project_path
from src.model_data import load_prepared_arrays, validate_held_out_label
from src.training_utils import save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Đánh giá pipeline IDS end-to-end trên test cố định.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "model_config.json"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--p-attack-path", required=True)
    parser.add_argument("--stage2-result-dir", required=True)
    parser.add_argument("--held-out-label-id", type=int, default=None)
    parser.add_argument("--novelty-result-dir", default=None)
    parser.add_argument("--novelty-method", choices=["max_probability", "one_class_svm", "isolation_forest"])
    parser.add_argument("--novelty-threshold-json", default=None)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def _bootstrap_accuracy_interval(correct: np.ndarray, iterations: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    values = np.asarray(correct, dtype=np.float32)
    estimates = np.empty(iterations, dtype=np.float32)
    for iteration in range(iterations):
        selected = rng.integers(0, len(values), size=len(values))
        estimates[iteration] = values[selected].mean()
    return np.quantile(estimates, [0.025, 0.975]).astype(float).tolist()


def main() -> None:
    configure_utf8_console()
    args = parse_args()
    config = load_model_config(args.config)
    run_id = experiment_id(config, args.run_id)
    processed_dir = project_path(config, config["experiment"]["processed_dir"])
    arrays = load_prepared_arrays(processed_dir)
    validate_held_out_label(arrays.attack_label_ids, args.held_out_label_id)
    p_attack = np.load(Path(args.p_attack_path).resolve(), mmap_mode="r")
    stage2_dir = Path(args.stage2_result_dir).resolve()
    test_indices = np.load(stage2_dir / "test_indices.npy")
    stage2_probabilities = np.load(stage2_dir / "test_probabilities.npy", mmap_mode="r")
    class_ids = np.load(stage2_dir / "class_ids.npy")
    expected_test = np.flatnonzero(np.asarray(arrays.split_ids) == 2)
    if not np.array_equal(test_indices, expected_test):
        raise ValueError("test_indices của Stage 2 không khớp split cố định Phase 2")
    if len(p_attack) != len(arrays.binary_labels):
        raise ValueError("P_attack không căn hàng với Phase 2")

    novelty_scores = None
    novelty_threshold = None
    if args.novelty_method:
        if not args.novelty_result_dir or not args.novelty_threshold_json:
            raise ValueError("Đánh giá open-set cần cả --novelty-result-dir và --novelty-threshold-json")
        novelty_scores = np.load(
            Path(args.novelty_result_dir).resolve() / f"{args.novelty_method}_test_scores.npy",
            mmap_mode="r",
        )
        with Path(args.novelty_threshold_json).open("r", encoding="utf-8") as stream:
            novelty_threshold = float(json.load(stream)["threshold"])
        if len(novelty_scores) != len(test_indices):
            raise ValueError("Novelty score không cùng thứ tự/chiều với test_indices")

    plan = {
        "run_id": run_id,
        "test_samples": len(test_indices),
        "stage1_threshold": float(config["evaluation"]["decision_threshold"]),
        "held_out_label_id": args.held_out_label_id,
        "novelty_method": args.novelty_method,
        "novelty_threshold": novelty_threshold,
        "test_is_evaluation_only": True,
    }
    print(plan)
    if args.check_only:
        print("CHECK-ONLY OK: chưa tạo dự đoán hoặc metric.")
        return

    predictions = compose_pipeline_predictions(
        np.asarray(p_attack[test_indices]),
        np.asarray(stage2_probabilities),
        class_ids,
        np.asarray(novelty_scores) if novelty_scores is not None else None,
        novelty_threshold,
        float(config["evaluation"]["decision_threshold"]),
    )
    truth = np.asarray(arrays.attack_label_ids[test_indices], dtype=np.int32)
    evaluation_truth = truth.copy()
    if args.held_out_label_id is not None:
        evaluation_truth[evaluation_truth == args.held_out_label_id] = UNKNOWN_ATTACK_ID
    report = {
        **plan,
        "stage1_test_metrics": binary_metrics(
            arrays.binary_labels[test_indices], p_attack[test_indices],
            float(config["evaluation"]["decision_threshold"]),
        ),
        "end_to_end_metrics": multiclass_metrics(evaluation_truth, predictions),
        "accuracy_bootstrap_95ci": _bootstrap_accuracy_interval(
            predictions == evaluation_truth,
            int(config["evaluation"]["bootstrap_iterations"]),
            int(config["evaluation"]["bootstrap_seed"]),
        ),
    }
    if args.held_out_label_id is not None and novelty_scores is not None:
        attack_mask = truth != 0
        report["open_set_metrics"] = open_set_metrics(
            truth[attack_mask] == args.held_out_label_id,
            np.asarray(novelty_scores)[attack_mask],
            float(novelty_threshold),
        )

    output_dir = phase_directory(config, "results_dir", "pipeline", run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(output_dir / "metrics.json", report)
    if config["evaluation"].get("save_predictions", True):
        frame = pd.DataFrame({
            "row_hash": np.asarray(arrays.row_hashes[test_indices]),
            "true_label_id": truth,
            "evaluation_label_id": evaluation_truth,
            "predicted_label_id": predictions,
            "p_attack": np.asarray(p_attack[test_indices]),
        })
        if novelty_scores is not None:
            frame["novelty_score"] = np.asarray(novelty_scores)
        # CSV gzip không cần thêm pyarrow; giữ row_hash để truy vết về split Phase 2.
        frame.to_csv(output_dir / "test_predictions.csv.gz", index=False, compression="gzip")
    print(f"Đã lưu báo cáo end-to-end: {output_dir}")


if __name__ == "__main__":
    main()

