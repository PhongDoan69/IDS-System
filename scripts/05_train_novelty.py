from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import open_set_metrics
from src.console import configure_utf8_console
from src.model_config import experiment_id, load_model_config, phase_directory, project_path
from src.model_data import load_prepared_arrays, validate_held_out_label
from src.training_utils import save_json
from src.contracts import assert_new_outputs, exact_indices, probability_matrix
from src.artifact_contracts import read_contract, write_contract, require_link, sidecar
from src.research_protocol import require_preprocessing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LOACO novelty detection cho lớp tấn công chưa biết.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "model_config.json"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument('--protocol', choices=['revised_v1'], required=True)
    parser.add_argument("--held-out-label-id", type=int, required=True)
    parser.add_argument("--latent-path", default=None)
    parser.add_argument("--stage2-result-dir", required=True)
    parser.add_argument("--ae-metadata", required=True)
    parser.add_argument("--stage1-metadata", required=True)
    parser.add_argument("--stage2-metadata", required=True)
    parser.add_argument(
        "--methods", nargs="+",
        choices=["max_probability", "one_class_svm", "isolation_forest"],
        default=["max_probability", "one_class_svm", "isolation_forest"],
    )
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def _read_json(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _verify_loaco_contract(args: argparse.Namespace) -> list[str]:
    checked = []
    for name, path in [
        ("autoencoder", args.ae_metadata),
        ("stage1", args.stage1_metadata),
        ("stage2", args.stage2_metadata),
    ]:
        metadata = _read_json(path)
        if metadata.get('protocol') != 'revised_v1' or metadata.get('status') != 'completed' or metadata.get('run_id') != args.run_id:
            raise ValueError(f'{name}: cần metadata completed của đúng run revised_v1')
        if metadata.get("held_out_label_id") != args.held_out_label_id:
            raise ValueError(
                f"LOACO không hợp lệ: {name} có held_out_label_id="
                f"{metadata.get('held_out_label_id')}, cần {args.held_out_label_id}."
            )
        checked.append(str(Path(path).resolve()))
    return checked


def main() -> None:
    configure_utf8_console()
    args = parse_args()
    config = load_model_config(args.config)
    run_id = experiment_id(config, args.run_id)
    seed = int(config["experiment"]["random_state"])
    processed_dir = project_path(config, config["experiment"]["processed_dir"])
    latent_path = Path(args.latent_path).resolve() if args.latent_path else processed_dir / "experiments" / run_id / "latent_features.npy"
    arrays = load_prepared_arrays(processed_dir, latent_path)
    _, scaled_path, _ = require_preprocessing(config, run_id, args.held_out_label_id)
    latent_record = read_contract(latent_path, config, args.held_out_label_id, kind='latent', run_id=run_id)
    require_link(latent_record, scaled_path)
    validate_held_out_label(arrays.attack_label_ids, args.held_out_label_id)
    checked_metadata = _verify_loaco_contract(args)
    stage2_dir = Path(args.stage2_result_dir).resolve()
    stage2_record = read_contract(stage2_dir, config, args.held_out_label_id, kind='stage2', run_id=run_id)
    require_link(stage2_record, latent_path)
    require_link(stage2_record, Path(args.stage2_metadata))
    stage1_info = _read_json(args.stage1_metadata)
    p_path = Path(stage1_info['probabilities_path'])
    p_record = read_contract(p_path, config, args.held_out_label_id, kind='p_attack', run_id=run_id)
    require_link(p_record, Path(args.stage1_metadata))
    require_link(latent_record, Path(args.ae_metadata))
    validation_indices = np.load(stage2_dir / "validation_indices.npy")
    validation_probabilities = np.load(stage2_dir / "validation_probabilities.npy", mmap_mode="r")
    test_indices = np.load(stage2_dir / "test_indices.npy")
    test_probabilities = np.load(stage2_dir / "test_probabilities.npy", mmap_mode="r")
    if len(validation_indices) != len(validation_probabilities) or len(test_indices) != len(test_probabilities):
        raise ValueError("Index và probability của Stage 2 không cùng chiều")

    labels = arrays.attack_label_ids
    expected_validation = np.flatnonzero((arrays.split_ids == 1) & (labels != 0) & (labels != args.held_out_label_id))
    exact_indices(validation_indices, expected_validation, 'known validation indices')
    exact_indices(test_indices, np.flatnonzero(arrays.split_ids == 2), 'test indices')
    classes = np.load(stage2_dir / 'class_ids.npy', allow_pickle=False)
    probability_matrix(validation_probabilities, classes, len(validation_indices), args.held_out_label_id)
    probability_matrix(test_probabilities, classes, len(test_indices), args.held_out_label_id)
    train_known = np.flatnonzero(
        (np.asarray(arrays.split_ids) == 0)
        & (np.asarray(labels) != 0)
        & (np.asarray(labels) != args.held_out_label_id)
    )
    # Stage 2 đã lưu validation chỉ gồm known attacks sau LOACO.
    if np.any(np.asarray(labels[validation_indices]) == args.held_out_label_id):
        raise ValueError("Validation Stage 2 còn chứa held-out class; không được chọn threshold.")
    unknown_test = np.asarray(labels[test_indices]) == args.held_out_label_id
    attack_test = np.asarray(labels[test_indices]) != 0
    held_out_test_count = int(np.count_nonzero(unknown_test))
    if held_out_test_count < int(config["novelty"]["minimum_held_out_samples"]):
        raise ValueError(
            f"Held-out test chỉ có {held_out_test_count} mẫu, nhỏ hơn ngưỡng nghiên cứu "
            f"{config['novelty']['minimum_held_out_samples']}."
        )

    variant = stage2_record['extra']['experiment']
    suffix = Path(f'heldout_{args.held_out_label_id}') / variant
    output_dir = phase_directory(config, 'results_dir', 'novelty', run_id) / suffix
    model_dir = phase_directory(config, 'models_dir', 'novelty', run_id) / suffix
    threshold_dir = project_path(config, 'artifacts/thresholds') / run_id / suffix
    metadata_path = phase_directory(config, 'metadata_dir', 'novelty', run_id) / f'heldout_{args.held_out_label_id}_{variant}.json'
    assert_new_outputs(output_dir, model_dir, threshold_dir, metadata_path)
    plan = {
        "run_id": run_id,
        'protocol': args.protocol,
        'evaluation_protocol': 'leave_one_attack_class_out',
        'stage2_variant': variant,
        "held_out_label_id": args.held_out_label_id,
        "held_out_test_samples": held_out_test_count,
        "known_train_attack_samples": len(train_known),
        "known_validation_attack_samples": len(validation_indices),
        "all_test_samples": len(test_indices),
        "methods": args.methods,
        "verified_upstream_metadata": checked_metadata,
        "threshold_source": "known validation attacks only",
        "test_used_for_fit_or_threshold": False,
    }
    print(plan)
    if args.check_only:
        print("CHECK-ONLY OK: chưa fit novelty detector.")
        return

    from src.novelty import (
        balanced_subsample_indices,
        fit_isolation_forest,
        fit_one_class_svm,
        save_novelty_model,
        score_max_probability,
    )

    rejection_rate = float(config["novelty"]["known_rejection_rate"])
    save_json(metadata_path, {**plan, 'status': 'running'})
    validation_features = np.asarray(arrays.features[validation_indices], dtype=np.float32)
    test_features = np.asarray(arrays.features[test_indices], dtype=np.float32)
    results = []
    if "max_probability" in args.methods:
        results.append(score_max_probability(
            np.asarray(validation_probabilities), np.asarray(test_probabilities), rejection_rate
        ))
    if "one_class_svm" in args.methods:
        svm_train_indices = balanced_subsample_indices(
            labels, train_known,
            int(config["novelty"]["one_class_svm"]["max_training_samples"]), seed,
        )
        results.append(fit_one_class_svm(
            np.asarray(arrays.features[svm_train_indices], dtype=np.float32),
            validation_features, test_features,
            config["novelty"]["one_class_svm"], rejection_rate, seed,
        ))
    if "isolation_forest" in args.methods:
        if_train_indices = balanced_subsample_indices(
            labels, train_known,
            int(config["novelty"]["isolation_forest"]["max_samples"]), seed,
        )
        results.append(fit_isolation_forest(
            np.asarray(arrays.features[if_train_indices], dtype=np.float32),
            validation_features, test_features,
            config["novelty"]["isolation_forest"], rejection_rate, seed,
        ))

    output_dir.mkdir(parents=True, exist_ok=True)
    threshold_dir.mkdir(parents=True, exist_ok=True)
    metrics = {}
    truth_attack_only = unknown_test[attack_test]
    for result in results:
        save_novelty_model(result, model_dir)
        # Giữ precision của detector để threshold và replay không lệch do ép float32.
        np.save(output_dir / f"{result.name}_test_scores.npy", result.test_scores)
        np.save(output_dir / f"{result.name}_validation_scores.npy", result.validation_scores)
        method_report = open_set_metrics(
            truth_attack_only,
            np.asarray(result.test_scores)[attack_test],
            result.threshold,
        )
        metrics[result.name] = method_report
        save_json(
            threshold_dir / f"{result.name}.json",
            {
                "method": result.name,
                'run_id': run_id,
                'stage2_variant': variant,
                "threshold": result.threshold,
                "known_rejection_rate_target": rejection_rate,
                "selected_on": "known_validation_only",
                "held_out_label_id": args.held_out_label_id,
            },
        )
    report = {**plan, "metrics": metrics, "status": "completed"}
    save_json(output_dir / "metrics.json", report)
    save_json(metadata_path, report)
    np.save(output_dir / 'test_indices.npy', test_indices)
    write_contract(output_dir, config, run_id, args.held_out_label_id, 'novelty',
                   parents=[latent_path, sidecar(latent_path), sidecar(stage2_dir), p_path, sidecar(p_path), metadata_path,
                            *sorted(threshold_dir.glob('*.json')), *sorted(model_dir.glob('*.joblib'))], extra=plan)
    print(f"Đã lưu novelty scores/metrics: {output_dir}")


if __name__ == "__main__":
    main()

