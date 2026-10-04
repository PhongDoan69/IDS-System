from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.calibration import apply_platt_calibrator, fit_platt_calibrator, save_calibrator
from src.console import configure_utf8_console
from src.metrics import binary_metrics
from src.model_config import experiment_id, load_model_config, phase_directory, project_path
from src.model_data import load_prepared_arrays, split_indices, validate_held_out_label
from src.training_utils import save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 1: BENIGN vs ATTACK với xác suất OOF.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "model_config.json"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--model", choices=["xgboost", "mlp"], required=True)
    parser.add_argument("--representation", choices=["scaled", "latent"], default="latent")
    parser.add_argument("--latent-path", default=None)
    parser.add_argument("--held-out-label-id", type=int, default=None)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def representation_path(args: argparse.Namespace, processed_dir: Path, run_id: str) -> Path:
    if args.representation == "scaled":
        return processed_dir / "features_scaled.npy"
    return Path(args.latent_path).resolve() if args.latent_path else processed_dir / "experiments" / run_id / "latent_features.npy"


def main() -> None:
    configure_utf8_console()
    args = parse_args()
    config = load_model_config(args.config)
    run_id = experiment_id(config, args.run_id)
    seed = int(config["experiment"]["random_state"])
    processed_dir = project_path(config, config["experiment"]["processed_dir"])
    feature_path = representation_path(args, processed_dir, run_id)
    arrays = load_prepared_arrays(processed_dir, feature_path)
    validate_held_out_label(arrays.attack_label_ids, args.held_out_label_id)
    train_indices = split_indices(arrays.split_ids, 0, args.held_out_label_id, arrays.attack_label_ids)
    validation_indices = split_indices(arrays.split_ids, 1, args.held_out_label_id, arrays.attack_label_ids)
    test_indices = split_indices(arrays.split_ids, 2)
    tag = f"{args.model}_{args.representation}"
    model_dir = phase_directory(config, "models_dir", "stage1", run_id) / tag
    result_dir = phase_directory(config, "results_dir", "stage1", run_id) / tag
    metadata_path = phase_directory(config, "metadata_dir", "stage1", run_id) / f"{tag}.json"
    probabilities_path = processed_dir / "experiments" / run_id / f"stage1_{tag}_p_attack_all.npy"

    plan = {
        "run_id": run_id,
        "model": args.model,
        "representation": args.representation,
        "feature_path": str(feature_path),
        "feature_shape": list(arrays.features.shape),
        "train_samples": len(train_indices),
        "validation_samples": len(validation_indices),
        "test_samples": len(test_indices),
        "oof_folds": int(config["stage1"]["oof_folds"]),
        "held_out_label_id": args.held_out_label_id,
        "test_used_for_training_calibration_or_selection": False,
        "p_attack_contract": "train=OOF; validation/test=final-model; rows aligned with Phase 2",
        "probabilities_path": str(probabilities_path),
    }
    print(plan)
    if args.check_only:
        print("CHECK-ONLY OK: không fit XGBoost/MLP.")
        return

    from sklearn.model_selection import StratifiedKFold
    from src.runtime import clear_cuda_cache, configure_torch_runtime, set_reproducible_seed

    device = None
    if args.model == "mlp":
        set_reproducible_seed(seed)
        device = configure_torch_runtime(config["hardware"])

    train_targets = np.asarray(arrays.binary_labels[train_indices], dtype=np.int8)
    oof_probabilities = np.empty(len(train_indices), dtype=np.float32)
    splitter = StratifiedKFold(
        n_splits=int(config["stage1"]["oof_folds"]), shuffle=True, random_state=seed
    )

    for fold, (fit_positions, holdout_positions) in enumerate(
        splitter.split(np.zeros(len(train_indices)), train_targets), start=1
    ):
        fit_indices = train_indices[fit_positions]
        holdout_indices = train_indices[holdout_positions]
        print(f"[Stage1] OOF fold {fold}: fit={len(fit_indices)}, holdout={len(holdout_indices)}")
        if args.model == "xgboost":
            from src.stage1_xgboost import fit_classifier, positive_probability, save_classifier

            model = fit_classifier(
                arrays.features[fit_indices], arrays.binary_labels[fit_indices],
                arrays.features[holdout_indices], arrays.binary_labels[holdout_indices],
                config["stage1"]["xgboost"], seed + fold,
            )
            oof_probabilities[holdout_positions] = positive_probability(model, arrays.features[holdout_indices])
            save_classifier(model, model_dir / f"oof_fold_{fold}.json")
        else:
            from src.stage1_mlp import predict_binary_mlp, train_binary_mlp

            checkpoint = model_dir / f"oof_fold_{fold}.pt"
            model, _ = train_binary_mlp(
                arrays.features, arrays.binary_labels, fit_indices, holdout_indices,
                config["stage1"]["mlp"], config["hardware"], device, checkpoint, seed + fold,
            )
            oof_probabilities[holdout_positions] = predict_binary_mlp(
                model, arrays.features, holdout_indices,
                int(config["stage1"]["mlp"]["batch_size"]), device, config["hardware"],
            )
        del model
        gc.collect()
        clear_cuda_cache()

    calibrator = None
    if config["stage1"].get("calibrate_probabilities", True):
        calibrator = fit_platt_calibrator(oof_probabilities, train_targets, seed)
        oof_probabilities = apply_platt_calibrator(calibrator, oof_probabilities)
        save_calibrator(calibrator, model_dir / "platt_calibrator.joblib")

    # Mô hình cuối cùng dùng toàn bộ train và validation chỉ để early stopping.
    if args.model == "xgboost":
        from src.stage1_xgboost import fit_classifier, positive_probability, save_classifier

        final_model = fit_classifier(
            arrays.features[train_indices], arrays.binary_labels[train_indices],
            arrays.features[validation_indices], arrays.binary_labels[validation_indices],
            config["stage1"]["xgboost"], seed,
        )
        validation_probabilities = positive_probability(final_model, arrays.features[validation_indices])
        test_probabilities = positive_probability(final_model, arrays.features[test_indices])
        save_classifier(final_model, model_dir / "final.json")
    else:
        from src.stage1_mlp import predict_binary_mlp, train_binary_mlp

        final_model, final_history = train_binary_mlp(
            arrays.features, arrays.binary_labels, train_indices, validation_indices,
            config["stage1"]["mlp"], config["hardware"], device,
            model_dir / "final.pt", seed,
        )
        batch_size = int(config["stage1"]["mlp"]["batch_size"])
        validation_probabilities = predict_binary_mlp(
            final_model, arrays.features, validation_indices, batch_size, device, config["hardware"]
        )
        test_probabilities = predict_binary_mlp(
            final_model, arrays.features, test_indices, batch_size, device, config["hardware"]
        )
        save_json(result_dir / "final_history.json", final_history.to_dict())

    if calibrator is not None:
        validation_probabilities = apply_platt_calibrator(calibrator, validation_probabilities)
        test_probabilities = apply_platt_calibrator(calibrator, test_probabilities)

    all_probabilities = np.full(len(arrays.binary_labels), np.nan, dtype=np.float32)
    all_probabilities[train_indices] = oof_probabilities
    all_probabilities[validation_indices] = validation_probabilities
    all_probabilities[test_indices] = test_probabilities
    probabilities_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(probabilities_path, all_probabilities)
    report = {
        **plan,
        "oof_train_metrics": binary_metrics(train_targets, oof_probabilities),
        "validation_metrics": binary_metrics(arrays.binary_labels[validation_indices], validation_probabilities),
        "test_metrics": binary_metrics(arrays.binary_labels[test_indices], test_probabilities),
        "status": "completed",
    }
    save_json(metadata_path, report)
    save_json(result_dir / "metrics.json", report)
    print(f"Đã lưu P_attack: {probabilities_path}")


if __name__ == "__main__":
    main()

