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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LOACO novelty detection cho lớp tấn công chưa biết.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "model_config.json"))
    parser.add_argument("--run-id", default=None)
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
    validate_held_out_label(arrays.attack_label_ids, args.held_out_label_id)
    checked_metadata = _verify_loaco_contract(args)
    stage2_dir = Path(args.stage2_result_dir).resolve()
    validation_indices = np.load(stage2_dir / "validation_indices.npy")
    validation_probabilities = np.load(stage2_dir / "validation_probabilities.npy", mmap_mode="r")
    test_indices = np.load(stage2_dir / "test_indices.npy")
    test_probabilities = np.load(stage2_dir / "test_probabilities.npy", mmap_mode="r")
    if len(validation_indices) != len(validation_probabilities) or len(test_indices) != len(test_probabilities):
        raise ValueError("Index và probability của Stage 2 không cùng chiều")

    labels = arrays.attack_label_ids
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

    output_dir = phase_directory(config, "results_dir", "novelty", run_id) / f"heldout_{args.held_out_label_id}"
    model_dir = phase_directory(config, "models_dir", "novelty", run_id) / f"heldout_{args.held_out_label_id}"
    threshold_dir = project_path(config, "artifacts/thresholds") / run_id / f"heldout_{args.held_out_label_id}"
    plan = {
        "run_id": run_id,
        "protocol": "leave_one_attack_class_out",
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
        np.save(output_dir / f"{result.name}_test_scores.npy", result.test_scores.astype(np.float32))
        np.save(output_dir / f"{result.name}_validation_scores.npy", result.validation_scores.astype(np.float32))
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
                "threshold": result.threshold,
                "known_rejection_rate_target": rejection_rate,
                "selected_on": "known_validation_only",
                "held_out_label_id": args.held_out_label_id,
            },
        )
    report = {**plan, "metrics": metrics, "status": "completed"}
    save_json(output_dir / "metrics.json", report)
    save_json(
        phase_directory(config, "metadata_dir", "novelty", run_id) / f"heldout_{args.held_out_label_id}.json",
        report,
    )
    print(f"Đã lưu novelty scores/metrics: {output_dir}")


if __name__ == "__main__":
    main()

