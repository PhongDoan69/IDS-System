from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.model_data import iter_index_batches, torch_batch
from src.training_utils import EarlyStopping, TrainingHistory, save_torch_checkpoint


def attack_class_mapping(labels: np.ndarray, indices: np.ndarray) -> tuple[dict[int, int], dict[int, int]]:
    """Ánh xạ label ID gốc sang [0..K-1]; BENIGN (0) không thuộc Stage 2."""
    original = sorted(int(value) for value in np.unique(np.asarray(labels[indices])) if int(value) != 0)
    if len(original) < 2:
        raise ValueError("Stage 2 cần ít nhất hai lớp tấn công trong tập train")
    forward = {label_id: position for position, label_id in enumerate(original)}
    reverse = {position: label_id for label_id, position in forward.items()}
    return forward, reverse


def remap_targets(labels: np.ndarray, indices: np.ndarray, mapping: dict[int, int]) -> np.ndarray:
    try:
        return np.asarray([mapping[int(labels[index])] for index in indices], dtype=np.int32)
    except KeyError as error:
        raise ValueError(f"Gặp lớp chưa biết khi remap Stage 2: {error.args[0]}") from error


def stage2_matrix(latent: np.ndarray, indices: np.ndarray, p_attack: np.ndarray | None) -> np.ndarray:
    values = np.asarray(latent[indices], dtype=np.float32)
    if p_attack is None:
        return values
    probability = np.asarray(p_attack[indices], dtype=np.float32).reshape(-1, 1)
    return np.concatenate([values, probability], axis=1)


def fit_stage2_xgboost(
    train_features: np.ndarray,
    train_targets: np.ndarray,
    validation_features: np.ndarray,
    validation_targets: np.ndarray,
    num_classes: int,
    config: dict[str, Any],
    random_state: int,
):
    from sklearn.utils.class_weight import compute_sample_weight
    from xgboost import XGBClassifier

    params = dict(config)
    early_stopping_rounds = int(params.pop("early_stopping_rounds"))
    model = XGBClassifier(
        **params,
        objective="multi:softprob",
        num_class=num_classes,
        random_state=random_state,
        n_jobs=-1,
        early_stopping_rounds=early_stopping_rounds,
    )
    weights = compute_sample_weight(class_weight="balanced", y=train_targets)
    model.fit(
        np.asarray(train_features, dtype=np.float32),
        train_targets,
        sample_weight=weights,
        eval_set=[(np.asarray(validation_features, dtype=np.float32), validation_targets)],
        verbose=50,
    )
    return model


def build_multiclass_mlp(input_dim: int, num_classes: int, config: dict[str, Any]):
    import torch.nn as nn

    dimensions = [input_dim, *[int(value) for value in config["hidden_dims"]]]
    layers: list[nn.Module] = []
    for left, right in zip(dimensions, dimensions[1:]):
        layers.extend([nn.Linear(left, right), nn.LayerNorm(right), nn.ReLU(), nn.Dropout(float(config["dropout"]))])
    layers.append(nn.Linear(dimensions[-1], num_classes))
    return nn.Sequential(*layers)


def train_stage2_mlp(
    features: np.ndarray,
    targets: np.ndarray,
    train_indices: np.ndarray,
    validation_indices: np.ndarray,
    num_classes: int,
    config: dict[str, Any],
    hardware: dict[str, Any],
    device,
    checkpoint_path: Path,
    random_state: int,
):
    import torch

    model = build_multiclass_mlp(int(features.shape[1]), num_classes, config).to(device)
    train_target_values = np.asarray(targets[train_indices], dtype=np.int64)
    counts = np.bincount(train_target_values, minlength=num_classes)
    weights = len(train_target_values) / (num_classes * np.maximum(counts, 1))
    criterion = torch.nn.CrossEntropyLoss(
        weight=torch.as_tensor(weights, dtype=torch.float32, device=device)
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

    def loss_on(indices: np.ndarray) -> float:
        model.eval()
        total = 0.0
        with torch.inference_mode():
            for selected in iter_index_batches(indices, batch_size, shuffle=False, random_state=0):
                batch = torch_batch(features, selected, device, hardware.get("pin_memory", True))
                target = torch.as_tensor(np.asarray(targets[selected]), dtype=torch.long, device=device)
                with torch.autocast(device_type=device.type, dtype=dtype, enabled=enabled):
                    loss = criterion(model(batch), target)
                total += float(loss.item()) * len(selected)
        return total / max(len(indices), 1)

    for epoch in range(1, int(config["epochs"]) + 1):
        model.train()
        total = 0.0
        for selected in iter_index_batches(
            train_indices, batch_size, shuffle=True, random_state=random_state + epoch
        ):
            batch = torch_batch(features, selected, device, hardware.get("pin_memory", True))
            target = torch.as_tensor(np.asarray(targets[selected]), dtype=torch.long, device=device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=dtype, enabled=enabled):
                loss = criterion(model(batch), target)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(config["gradient_clip_norm"]))
            scaler.step(optimizer)
            scaler.update()
            total += float(loss.item()) * len(selected)

        train_loss = total / max(len(train_indices), 1)
        validation_loss = loss_on(validation_indices)
        scheduler.step(validation_loss)
        history.append(epoch, train_loss, validation_loss, optimizer.param_groups[0]["lr"])
        print(f"[Stage2-MLP] epoch={epoch:03d} train={train_loss:.8f} val={validation_loss:.8f}")
        if stopper.update(validation_loss):
            save_torch_checkpoint(
                checkpoint_path,
                model,
                optimizer,
                epoch,
                validation_loss,
                {"input_dim": int(features.shape[1]), "num_classes": num_classes, "model_config": config},
            )
        if stopper.should_stop:
            break

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    return model, history


def predict_stage2_mlp(model, features, indices, batch_size, device, hardware) -> np.ndarray:
    import torch

    model.eval()
    chunks: list[np.ndarray] = []
    enabled = bool(hardware.get("mixed_precision", True)) and device.type == "cuda"
    dtype = torch.float16 if hardware.get("amp_dtype") == "float16" else torch.bfloat16
    with torch.inference_mode():
        for selected in iter_index_batches(indices, batch_size, shuffle=False, random_state=0):
            batch = torch_batch(features, selected, device, hardware.get("pin_memory", True))
            with torch.autocast(device_type=device.type, dtype=dtype, enabled=enabled):
                probabilities = torch.softmax(model(batch), dim=1)
            chunks.append(probabilities.float().cpu().numpy())
    return np.concatenate(chunks, axis=0)


def save_xgboost(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))

