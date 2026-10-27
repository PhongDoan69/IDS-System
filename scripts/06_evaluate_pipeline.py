from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation import UNKNOWN_ATTACK_ID, compose_pipeline_predictions
from src.console import configure_utf8_console
from src.metrics import binary_metrics, multiclass_metrics, open_set_metrics, pipeline_diagnostics
from src.contracts import assert_new_outputs, probability_matrix, probability_vector, exact_indices
from src.artifact_contracts import read_contract, write_contract, require_link, sidecar
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
    parser.add_argument("--novelty-method", choices=["max_probability", "one_class_svm", "isolation_forest", "mahalanobis", "knn_distance"])
    parser.add_argument("--novelty-threshold-json", default=None)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument('--stage1-threshold-json', help='Optional known-validation gate policy; leaves historical fixed-gate runs unchanged')
    parser.add_argument('--allow-legacy-artifacts', action='store_true',
                        help='Chỉ replay artifact cũ; không xác nhận strict OOF/LOACO hoặc lineage')
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
    gate_record = None
    if args.stage1_threshold_json:
        from src.artifact_contracts import sha256
        from src.gate_policy import select_gate
        gate_record = json.loads(Path(args.stage1_threshold_json).read_text(encoding='utf-8'))
        p_record_gate = read_contract(Path(args.p_attack_path), config, args.held_out_label_id, kind='p_attack')
        if (gate_record.get('run_id') != p_record_gate['run_id']
                or gate_record.get('held_out_label_id') != args.held_out_label_id
                or gate_record.get('p_attack_path') != str(Path(args.p_attack_path).resolve())
                or gate_record.get('p_attack_sha256') != sha256(Path(args.p_attack_path))
                or gate_record.get('selected_on') != 'known_validation_only'
                or gate_record.get('test_used_for_selection') is not False):
            raise ValueError('Gate threshold provenance mismatch')
        known_val = np.flatnonzero((arrays.split_ids == 1) & (arrays.attack_label_ids != args.held_out_label_id))
        replay = select_gate(p_attack[known_val], arrays.binary_labels[known_val], gate_record['benign_fpr_budget'])
        if replay['threshold'] != gate_record['threshold']:
            raise ValueError('Gate threshold does not reproduce from known validation')
        config['evaluation']['decision_threshold'] = float(gate_record['threshold'])
    stage2_dir = Path(args.stage2_result_dir).resolve()
    test_indices = np.load(stage2_dir / "test_indices.npy")
    stage2_probabilities = np.load(stage2_dir / "test_probabilities.npy", mmap_mode="r")
    class_ids = np.load(stage2_dir / "class_ids.npy")
    expected_test = np.flatnonzero(np.asarray(arrays.split_ids) == 2)
    if not np.array_equal(test_indices, expected_test):
        raise ValueError("test_indices của Stage 2 không khớp split cố định Phase 2")
    if len(p_attack) != len(arrays.binary_labels):
        raise ValueError("P_attack không căn hàng với Phase 2")
    probability_vector(p_attack[test_indices], length=len(test_indices))
    probability_matrix(stage2_probabilities, class_ids, len(test_indices), args.held_out_label_id)
    expected_classes = np.unique(arrays.attack_label_ids[(arrays.split_ids == 0) & (arrays.attack_label_ids != 0)])
    if args.held_out_label_id is not None:
        expected_classes = expected_classes[expected_classes != args.held_out_label_id]
    if not np.array_equal(np.sort(class_ids), expected_classes):
        raise ValueError('Stage 2 không có đúng known class set của training')
    if not args.allow_legacy_artifacts:
        p_record = read_contract(Path(args.p_attack_path), config, args.held_out_label_id, kind='p_attack')
        s2_record = read_contract(stage2_dir, config, args.held_out_label_id, kind='stage2', run_id=p_record['run_id'])
        if s2_record['extra']['uses_p_attack']:
            require_link(s2_record, Path(args.p_attack_path))

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
            threshold_record = json.load(stream)
        if args.held_out_label_id is None or threshold_record.get('method') != args.novelty_method or threshold_record.get('held_out_label_id') != args.held_out_label_id:
            raise ValueError('Novelty method/heldout không khớp threshold metadata')
        novelty_threshold = float(threshold_record['threshold'])
        if not args.allow_legacy_artifacts:
            n_record = read_contract(Path(args.novelty_result_dir), config, args.held_out_label_id, kind='novelty', run_id=p_record['run_id'])
            require_link(n_record, sidecar(stage2_dir))
            require_link(n_record, Path(args.p_attack_path))
            require_link(n_record, Path(args.novelty_threshold_json))
            exact_indices(np.load(Path(args.novelty_result_dir) / 'test_indices.npy'), test_indices, 'novelty test indices')
        if len(novelty_scores) != len(test_indices):
            raise ValueError("Novelty score không cùng thứ tự/chiều với test_indices")

    plan = {
        'protocol': 'legacy_replay_UNVERIFIED_LINEAGE' if args.allow_legacy_artifacts else 'revised_v1',
        "run_id": run_id,
        "test_samples": len(test_indices),
        "stage1_threshold": float(config["evaluation"]["decision_threshold"]),
        "held_out_label_id": args.held_out_label_id,
        "novelty_method": args.novelty_method,
        "novelty_threshold": novelty_threshold,
        "test_is_evaluation_only": True,
    }
    if not args.novelty_method and (args.novelty_result_dir or args.novelty_threshold_json):
        raise ValueError('Thiếu --novelty-method; không bỏ qua novelty input ngầm')
    # check-only phải chạy cùng validator/composition với evaluation, không chỉ kiểm file tồn tại.
    started = time.perf_counter()
    predictions = compose_pipeline_predictions(
        np.asarray(p_attack[test_indices]), np.asarray(stage2_probabilities), class_ids,
        np.asarray(novelty_scores) if novelty_scores is not None else None,
        novelty_threshold, float(config['evaluation']['decision_threshold']))
    composition_seconds = time.perf_counter() - started
    print(plan)
    if args.check_only:
        print('CHECK-ONLY OK: đã validate và compose trong RAM; không ghi output, không tính metric/fit. Không chứng minh scientific validity.')
        return

    output_dir = phase_directory(config, 'results_dir', 'pipeline', run_id)
    assert_new_outputs(output_dir)
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
        **pipeline_diagnostics(truth, predictions, p_attack[test_indices], stage2_probabilities, class_ids,
                               float(config['evaluation']['decision_threshold']), args.held_out_label_id),
        'composition_seconds_only_NOT_model_inference': composition_seconds,
        'model_inference_performance': 'NOT MEASURED; precomputed scores, not raw-to-model latency',
        'stage1_threshold_selection': gate_record or 'fixed_config; NOT validation-optimized',
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
        report['score_only_unknown_metrics'] = {
            **report['open_set_metrics'], 'population': 'true_attack_test_only; ignores Stage 1 gate and benign'}
        report['open_set_metrics_definition'] = 'legacy alias for score-only, NOT final unknown metrics'

    output_dir = phase_directory(config, "results_dir", "pipeline", run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(output_dir / "metrics.json", report)
    if config['evaluation'].get('save_compact_predictions', False):
        # Integer predictions + aligned indices are sufficient for error audit.
        # Scores remain in their hashed upstream artifacts, not duplicated as CSV.
        np.savez_compressed(output_dir / 'predictions.npz', test_indices=test_indices,
                            true_label_id=truth, evaluation_label_id=evaluation_truth,
                            predicted_label_id=predictions)
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
    if not args.allow_legacy_artifacts:
        parents = [Path(args.p_attack_path), sidecar(Path(args.p_attack_path)), sidecar(stage2_dir)]
        if args.novelty_method:
            parents.extend([sidecar(Path(args.novelty_result_dir)), Path(args.novelty_threshold_json)])
        if args.stage1_threshold_json:
            parents.append(Path(args.stage1_threshold_json))
        write_contract(output_dir, config, run_id, args.held_out_label_id, 'pipeline_evaluation', parents=parents, extra=plan)
    print(f"Đã lưu báo cáo end-to-end: {output_dir}")


if __name__ == "__main__":
    main()

