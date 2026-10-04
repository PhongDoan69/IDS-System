from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.model_data import iter_index_batches, torch_batch
from src.training_utils import EarlyStopping, TrainingHistory, save_torch_checkpoint


def build_autoencoder(input_dim: int, config: dict[str, Any]):
    """Tạo Autoencoder đối xứng: input -> hidden -> latent -> hidden -> input."""
    import torch.nn as nn

    hidden_dims = [int(value) for value in config["hidden_dims"]]
    latent_dim = int(config["latent_dim"])

    def dense_stack(dimensions: list[int], final_activation: bool) -> list[nn.Module]:
        layers: list[nn.Module] = []
        for position, (left, right) in enumerate(zip(dimensions, dimensions[1:])):
            layers.append(nn.Linear(left, right))
            if final_activation or position < len(dimensions) - 2:
                layers.append(nn.ReLU())
        return layers

    class TabularAutoencoder(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = nn.Sequential(*dense_stack([input_dim, *hidden_dims, latent_dim], False))
            # Lớp cuối tuyến tính vì đầu vào đã StandardScaler, có thể mang giá trị âm.
            self.decoder = nn.Sequential(*dense_stack([latent_dim, *reversed(hidden_dims), input_dim], False))

        def encode(self, values):
            return self.encoder(values)

        def forward(self, values):
            return self.decoder(self.encode(values))

    return TabularAutoencoder()


def _mean_reconstruction_loss(model, features, indices, batch_size, device, hardware, criterion) -> float:
    import torch

    model.eval()
    amp_enabled = bool(hardware.get("mixed_precision", True)) and device.type == "cuda"
    amp_dtype = torch.float16 if hardware.get("amp_dtype") == "float16" else torch.bfloat16
    total_loss = 0.0
    total_count = 0
    with torch.inference_mode():
        for batch_indices in iter_index_batches(indices, batch_size, shuffle=False, random_state=0):
            batch = torch_batch(features, batch_indices, device, hardware.get("pin_memory", True))
            with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=amp_enabled):
                loss = criterion(model(batch), batch)
            total_loss += float(loss.item()) * len(batch_indices)
            total_count += len(batch_indices)
    return total_loss / max(total_count, 1)


def train_autoencoder(
    features: np.ndarray,
    train_indices: np.ndarray,
    validation_indices: np.ndarray,
    config: dict[str, Any],
    hardware: dict[str, Any],
    device,
    checkpoint_path: Path,
):
    """Fit chỉ trên train; validation chỉ dùng early stopping; test tuyệt đối không tham gia."""
    import torch

    model = build_autoencoder(int(features.shape[1]), config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"]),
    )
    criterion = torch.nn.MSELoss()
    amp_enabled = bool(hardware.get("mixed_precision", True)) and device.type == "cuda"
    amp_dtype = torch.float16 if hardware.get("amp_dtype") == "float16" else torch.bfloat16
    scaler = torch.amp.GradScaler(device.type, enabled=amp_enabled)
    stopper = EarlyStopping(int(config["early_stopping_patience"]), float(config["min_delta"]))
    history = TrainingHistory()
    batch_size = int(config["batch_size"])

    for epoch in range(1, int(config["epochs"]) + 1):
        model.train()
        total_loss = 0.0
        total_count = 0
        for batch_indices in iter_index_batches(
            train_indices,
            batch_size,
            shuffle=True,
            random_state=epoch,
        ):
            batch = torch_batch(features, batch_indices, device, hardware.get("pin_memory", True))
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=amp_enabled):
                loss = criterion(model(batch), batch)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(config["gradient_clip_norm"]))
            scaler.step(optimizer)
            scaler.update()
            total_loss += float(loss.item()) * len(batch_indices)
            total_count += len(batch_indices)

        train_loss = total_loss / max(total_count, 1)
        validation_loss = _mean_reconstruction_loss(
            model, features, validation_indices, batch_size, device, hardware, criterion
        )
        history.append(epoch, train_loss, validation_loss, optimizer.param_groups[0]["lr"])
        print(f"[AE] epoch={epoch:03d} train_mse={train_loss:.8f} val_mse={validation_loss:.8f}")

        if stopper.update(validation_loss):
            save_torch_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                epoch,
                validation_loss,
                {"input_dim": int(features.shape[1]), "model_config": config},
            )
        if stopper.should_stop:
            print(f"[AE] Early stopping tại epoch {epoch}; best={stopper.best:.8f}")
            break

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    return model, history, int(checkpoint["epoch"]), float(checkpoint["validation_loss"])


def encode_to_memmap(
    model,
    features: np.ndarray,
    output_path: Path,
    latent_dim: int,
    batch_size: int,
    device,
    hardware: dict[str, Any],
) -> None:
    """Mã hóa theo batch và giữ nguyên thứ tự dòng Phase 2 để ghép nhãn/split an toàn."""
    import torch

    output_path.parent.mkdir(parents=True, exist_ok=True)
    destination = np.lib.format.open_memmap(
        output_path,
        mode="w+",
        dtype=np.float32,
        shape=(len(features), latent_dim),
    )
    model.eval()
    amp_enabled = bool(hardware.get("mixed_precision", True)) and device.type == "cuda"
    amp_dtype = torch.float16 if hardware.get("amp_dtype") == "float16" else torch.bfloat16
    with torch.inference_mode():
        all_indices = np.arange(len(features), dtype=np.int64)
        for indices in iter_index_batches(all_indices, batch_size, shuffle=False, random_state=0):
            batch = torch_batch(features, indices, device, hardware.get("pin_memory", True))
            with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=amp_enabled):
                latent = model.encode(batch)
            destination[indices] = latent.float().cpu().numpy()
    destination.flush()

