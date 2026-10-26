from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.model_config import experiment_id, load_model_config, phase_directory, project_path
from src.model_data import load_prepared_arrays, split_indices, validate_held_out_label
from src.training_utils import save_json
from src.console import configure_utf8_console
from src.contracts import assert_new_outputs
from src.artifact_contracts import write_contract, sidecar
from src.research_protocol import require_preprocessing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Huấn luyện Autoencoder CICIDS2017.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "configs" / "model_config.json"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument('--protocol', choices=['revised_v1'], required=True,
                        help='Xác nhận dùng protocol sửa, không tái dùng scaler legacy')
    parser.add_argument("--held-out-label-id", type=int, default=None,
                        help="LOACO: loại hoàn toàn lớp này khỏi train/validation AE.")
    parser.add_argument("--check-only", action="store_true",
                        help="Chỉ kiểm tra cấu hình/dữ liệu; không import Torch và không fit.")
    return parser.parse_args()


def main() -> None:
    configure_utf8_console()
    args = parse_args()
    config = load_model_config(args.config)
    run_id = experiment_id(config, args.run_id)
    processed_dir = project_path(config, config["experiment"]["processed_dir"])
    arrays, scaled_path, _ = require_preprocessing(config, run_id, args.held_out_label_id)
    validate_held_out_label(arrays.attack_label_ids, args.held_out_label_id)
    train_indices = split_indices(
        arrays.split_ids, 0, args.held_out_label_id, arrays.attack_label_ids
    )
    validation_indices = split_indices(
        arrays.split_ids, 1, args.held_out_label_id, arrays.attack_label_ids
    )
    checkpoint_path = phase_directory(config, "models_dir", "autoencoder", run_id) / "best.pt"
    latent_path = processed_dir / "experiments" / run_id / "latent_features.npy"
    metadata_path = phase_directory(config, "metadata_dir", "autoencoder", run_id) / "run.json"
    result_dir = phase_directory(config, 'results_dir', 'autoencoder', run_id)
    assert_new_outputs(checkpoint_path.parent, latent_path, metadata_path, result_dir)

    plan = {
        "run_id": run_id,
        'protocol': args.protocol,
        'scaled_path': str(scaled_path),
        "input_shape": list(arrays.features.shape),
        "train_samples": len(train_indices),
        "validation_samples": len(validation_indices),
        "held_out_label_id": args.held_out_label_id,
        "checkpoint": str(checkpoint_path),
        "latent_output": str(latent_path),
        "test_used_for_training_or_selection": False,
    }
    print(plan)
    if args.check_only:
        print("CHECK-ONLY OK: không có mô hình nào được khởi tạo hoặc huấn luyện.")
        return

    from src.autoencoder import encode_to_memmap, train_autoencoder
    from src.runtime import configure_torch_runtime, oom_guidance, set_reproducible_seed

    seed = int(config["experiment"]["random_state"])
    set_reproducible_seed(seed)
    device = configure_torch_runtime(config["hardware"])
    save_json(metadata_path, {**plan, 'status': 'running'})
    try:
        model, history, best_epoch, best_validation_loss = train_autoencoder(
            arrays.features,
            train_indices,
            validation_indices,
            config["autoencoder"],
            config["hardware"],
            device,
            checkpoint_path,
            random_state=seed,
        )
        encode_to_memmap(
            model,
            arrays.features,
            latent_path,
            int(config["autoencoder"]["latent_dim"]),
            int(config["autoencoder"]["encode_batch_size"]),
            device,
            config["hardware"],
        )
    except RuntimeError as error:
        if "out of memory" in str(error).lower():
            raise RuntimeError(oom_guidance(int(config["autoencoder"]["batch_size"]))) from error
        raise

    plan.update({
        "best_epoch": best_epoch,
        "best_validation_mse": best_validation_loss,
        "history": history.to_dict(),
        "status": "completed",
    })
    save_json(metadata_path, plan)
    write_contract(latent_path, config, run_id, args.held_out_label_id, 'latent',
                   parents=[scaled_path, sidecar(scaled_path), checkpoint_path, metadata_path], extra=plan)
    save_json(
        result_dir / "history.json",
        history.to_dict(),
    )
    print(f"Đã lưu latent: {latent_path}")


if __name__ == "__main__":
    main()

