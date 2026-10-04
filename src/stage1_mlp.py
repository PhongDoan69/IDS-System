from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.model_data import iter_index_batches, torch_batch
from src.training_utils import EarlyStopping, TrainingHistory, save_torch_checkpoint


def build_binary_mlp(input_dim: int, config: dict[str, Any]):
    import torch.nn as nn

    dimensions = [input_dim, *[int(value) for value in config["hidden_dims"]]]
    layers: list[nn.Module] = []
    for left, right in zip(dimensions, dimensions[1:]):
        # LayerNorm ổn định cả khi batch cuối chỉ còn một mẫu; BatchNorm sẽ lỗi trường hợp đó.
        layers.extend([nn.Linear(left, right), nn.LayerNorm(right), nn.ReLU(), nn.Dropout(float(config["dropout"]))])
    layers.append(nn.Linear(dimensions[-1], 1))
    return nn.Sequential(*layers)


def _validation_loss(model, features, targets, indices, batch_size, device, hardware, criterion) -> float:
    import torch

    model.eval()
    enabled = bool(hardware.get("mixed_precision", True)) and device.type == "cuda"
    dtype = torch.float16 if hardware.get("amp_dtype") == "float16" else torch.bfloat16
    total = 0.0
    with torch.inference_mode():
        for selected in iter_index_batches(indices, batch_size, shuffle=False, random_state=0):
            batch = torch_batch(features, selected, device, hardware.get("pin_memory", True))
            target = torch.as_tensor(np.asarray(targets[selected]), dtype=torch.float32, device=device)
            with torch.autocast(device_type=device.type, dtype=dtype, enabled=enabled):
                loss = criterion(model(batch).squeeze(1), target)
            total += float(loss.item()) * len(selected)
    return total / max(len(indices), 1)


def train_binary_mlp(
    features: np.ndarray,
    targets: np.ndarray,
    train_indices: np.ndarray,
    validation_indices: np.ndarray,
    config: dict[str, Any],
    hardware: dict[str, Any],
    device,
    checkpoint_path: Path,
    random_state: int,
):
    import torch

    model = build_binary_mlp(int(features.shape[1]), config).to(device)
    train_targets = np.asarray(targets[train_indices])
    positive = max(int(np.count_nonzero(train_targets == 1)), 1)
    negative = int(np.count_nonzero(train_targets == 0))
    criterion = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([negative / positive], dtype=torch.float32, device=device)
    )
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=float(config["learning_rate"]), weight_decay=float(config["weight_decay"])
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        patience=int(config["reduce_lr_patience"]),
        factor=float(config["reduce_lr_factor"]),
    )
    enabled = bool(hardware.get("mixed_precision", True)) and device.type == "cuda"
    dtype = torch.float16 if hardware.get("amp_dtype") == "float16" else torch.bfloat16
    scaler = torch.amp.GradScaler(device.type, enabled=enabled)
    stopper = EarlyStopping(int(config["early_stopping_patience"]), 1e-6)
    history = TrainingHistory()
    batch_size = int(config["batch_size"])

    for epoch in range(1, int(config["epochs"]) + 1):
        model.train()
        total = 0.0
        for selected in iter_index_batches(
            train_indices, batch_size, shuffle=True, random_state=random_state + epoch
        ):
            batch = torch_batch(features, selected, device, hardware.get("pin_memory", True))
            target = torch.as_tensor(np.asarray(targets[selected]), dtype=torch.float32, device=device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=dtype, enabled=enabled):
                loss = criterion(model(batch).squeeze(1), target)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(config["gradient_clip_norm"]))
            scaler.step(optimizer)
            scaler.update()
            total += float(loss.item()) * len(selected)

        train_loss = total / max(len(train_indices), 1)
        validation_loss = _validation_loss(
            model, features, targets, validation_indices, batch_size, device, hardware, criterion
        )
        scheduler.step(validation_loss)
        history.append(epoch, train_loss, validation_loss, optimizer.param_groups[0]["lr"])
        print(f"[Stage1-MLP] epoch={epoch:03d} train={train_loss:.8f} val={validation_loss:.8f}")
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
            break

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    return model, history


def predict_binary_mlp(model, features, indices, batch_size, device, hardware) -> np.ndarray:
    import torch

    model.eval()
    output = np.empty(len(indices), dtype=np.float32)
    enabled = bool(hardware.get("mixed_precision", True)) and device.type == "cuda"
    dtype = torch.float16 if hardware.get("amp_dtype") == "float16" else torch.bfloat16
    cursor = 0
    with torch.inference_mode():
        for selected in iter_index_batches(indices, batch_size, shuffle=False, random_state=0):
            batch = torch_batch(features, selected, device, hardware.get("pin_memory", True))
            with torch.autocast(device_type=device.type, dtype=dtype, enabled=enabled):
                probability = torch.sigmoid(model(batch).squeeze(1))
            output[cursor : cursor + len(selected)] = probability.float().cpu().numpy()
            cursor += len(selected)
    return output

