from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.metrics import multiclass_metrics
from src.console import configure_utf8_console
from src.model_config import experiment_id, load_model_config, phase_directory, project_path
from src.model_data import load_prepared_arrays, validate_held_out_label
from src.stage2 import attack_class_mapping, remap_targets, stage2_matrix
from src.training_utils import save_json


EXPERIMENTS = {
    "latent_only": ("xgboost", False),
    "latent_plus_pattack_xgb": ("xgboost", True),
    "latent_plus_pattack_mlp": ("mlp", True),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 2: phân loại đa lớp cho các flow tấn công.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "model_config.json"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--experiment", choices=sorted(EXPERIMENTS), required=True)
    parser.add_argument("--latent-path", default=None)
    parser.add_argument("--p-attack-path", default=None)
    parser.add_argument("--held-out-label-id", type=int, default=None)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def _predict_xgboost_batches(model, values: np.ndarray, batch_size: int = 65536) -> np.ndarray:
    chunks = []
    for start in range(0, len(values), batch_size):
        chunks.append(model.predict_proba(np.asarray(values[start : start + batch_size], dtype=np.float32)))
    return np.concatenate(chunks, axis=0).astype(np.float32)


def main() -> None:
    configure_utf8_console()
    args = parse_args()
    config = load_model_config(args.config)
    run_id = experiment_id(config, args.run_id)
    seed = int(config["experiment"]["random_state"])
    model_kind, uses_p_attack = EXPERIMENTS[args.experiment]
    processed_dir = project_path(config, config["experiment"]["processed_dir"])
    latent_path = Path(args.latent_path).resolve() if args.latent_path else processed_dir / "experiments" / run_id / "latent_features.npy"
    arrays = load_prepared_arrays(processed_dir, latent_path)
    validate_held_out_label(arrays.attack_label_ids, args.held_out_label_id)
    p_attack_path = None
    p_attack = None
    if uses_p_attack:
        if not args.p_attack_path:
            raise ValueError("Thí nghiệm latent+P_attack bắt buộc truyền --p-attack-path của Stage 1.")
        p_attack_path = Path(args.p_attack_path).resolve()
        p_attack = np.load(p_attack_path, mmap_mode="r")
        if len(p_attack) != len(arrays.features):
            raise ValueError("P_attack không cùng số dòng với latent/Phase 2")

    labels = arrays.attack_label_ids
    train_mask = (np.asarray(arrays.split_ids) == 0) & (np.asarray(labels) != 0)
    validation_mask = (np.asarray(arrays.split_ids) == 1) & (np.asarray(labels) != 0)
    if args.held_out_label_id is not None:
        train_mask &= np.asarray(labels) != args.held_out_label_id
        validation_mask &= np.asarray(labels) != args.held_out_label_id
    train_indices = np.flatnonzero(train_mask)
    validation_indices = np.flatnonzero(validation_mask)
    test_indices = np.flatnonzero(np.asarray(arrays.split_ids) == 2)  # Lưu mọi test flow cho pipeline cuối.
    known_test_mask = (np.asarray(labels[test_indices]) != 0)
    if args.held_out_label_id is not None:
        known_test_mask &= np.asarray(labels[test_indices]) != args.held_out_label_id
    known_test_positions = np.flatnonzero(known_test_mask)

    forward, reverse = attack_class_mapping(labels, train_indices)
    train_targets = remap_targets(labels, train_indices, forward)
    validation_targets = remap_targets(labels, validation_indices, forward)
    model_dir = phase_directory(config, "models_dir", "stage2", run_id) / args.experiment
    result_dir = phase_directory(config, "results_dir", "stage2", run_id) / args.experiment
    metadata_path = phase_directory(config, "metadata_dir", "stage2", run_id) / f"{args.experiment}.json"
    plan = {
        "run_id": run_id,
        "experiment": args.experiment,
        "model": model_kind,
        "uses_p_attack": uses_p_attack,
        "latent_path": str(latent_path),
        "p_attack_path": str(p_attack_path) if p_attack_path else None,
        "train_attack_samples": len(train_indices),
        "validation_attack_samples": len(validation_indices),
        "test_all_samples": len(test_indices),
        "known_attack_classes": sorted(forward),
        "held_out_label_id": args.held_out_label_id,
        "test_used_for_training_or_selection": False,
    }
    print(plan)
    if uses_p_attack:
        relevant = np.concatenate([train_indices, validation_indices, test_indices])
        if not np.isfinite(np.asarray(p_attack[relevant])).all():
            raise ValueError("P_attack chứa NaN/Inf tại dòng cần dùng; kiểm tra cùng run-id/LOACO.")
    if args.check_only:
        print("CHECK-ONLY OK: không fit Stage 2.")
        return

    # Ma trận latent nhỏ hơn nhiều so với 84 đặc trưng; tạo một bản float32 trong RAM.
    all_indices = np.arange(len(arrays.features), dtype=np.int64)
    features = stage2_matrix(arrays.features, all_indices, p_attack if uses_p_attack else None)
    validation_probabilities: np.ndarray
    test_probabilities: np.ndarray

    if model_kind == "xgboost":
        from src.stage2 import fit_stage2_xgboost, save_xgboost

        model = fit_stage2_xgboost(
            features[train_indices], train_targets,
            features[validation_indices], validation_targets,
            len(forward), config["stage2"]["xgboost"], seed,
        )
        validation_probabilities = _predict_xgboost_batches(model, features[validation_indices])
        test_probabilities = _predict_xgboost_batches(model, features[test_indices])
        save_xgboost(model, model_dir / "final.json")
    else:
        from src.runtime import configure_torch_runtime, set_reproducible_seed
        from src.stage2 import predict_stage2_mlp, train_stage2_mlp

        target_aligned = np.full(len(labels), -1, dtype=np.int32)
        target_aligned[train_indices] = train_targets
        target_aligned[validation_indices] = validation_targets
        set_reproducible_seed(seed)
        device = configure_torch_runtime(config["hardware"])
        model, history = train_stage2_mlp(
            features, target_aligned, train_indices, validation_indices, len(forward),
            config["stage2"]["mlp"], config["hardware"], device,
            model_dir / "final.pt", seed,
        )
        batch_size = int(config["stage2"]["mlp"]["batch_size"])
        validation_probabilities = predict_stage2_mlp(
            model, features, validation_indices, batch_size, device, config["hardware"]
        )
        test_probabilities = predict_stage2_mlp(
            model, features, test_indices, batch_size, device, config["hardware"]
        )
        save_json(result_dir / "history.json", history.to_dict())

    result_dir.mkdir(parents=True, exist_ok=True)
    np.save(result_dir / "validation_indices.npy", validation_indices)
    np.save(result_dir / "validation_probabilities.npy", validation_probabilities)
    np.save(result_dir / "test_indices.npy", test_indices)
    np.save(result_dir / "test_probabilities.npy", test_probabilities)
    class_ids = np.asarray([reverse[position] for position in range(len(reverse))], dtype=np.int32)
    np.save(result_dir / "class_ids.npy", class_ids)
    known_probabilities = test_probabilities[known_test_positions]
    known_predictions = class_ids[np.argmax(known_probabilities, axis=1)]
    report = {
        **plan,
        "class_id_order": class_ids.tolist(),
        "validation_metrics": multiclass_metrics(
            labels[validation_indices], class_ids[np.argmax(validation_probabilities, axis=1)]
        ),
        "known_test_metrics": multiclass_metrics(
            labels[test_indices[known_test_positions]], known_predictions
        ),
        "status": "completed",
    }
    save_json(metadata_path, report)
    save_json(result_dir / "metrics.json", report)
    print(f"Đã lưu xác suất Stage 2: {result_dir}")


if __name__ == "__main__":
    main()

