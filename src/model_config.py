from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_model_config(path: str | Path) -> dict[str, Any]:
    """Đọc cấu hình model và gắn project root để mọi script dùng cùng đường dẫn."""
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as stream:
        config = json.load(stream)
    config["_config_path"] = str(config_path)
    config["_project_root"] = str(config_path.parent.parent)
    validate_model_config(config)
    return config


def validate_model_config(config: dict[str, Any]) -> None:
    required = {"experiment", "hardware", "autoencoder", "stage1", "stage2", "novelty", "evaluation"}
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Thiếu các phần cấu hình model: {sorted(missing)}")

    hardware = config["hardware"]
    if hardware["amp_dtype"] not in {"float16", "bfloat16"}:
        raise ValueError("hardware.amp_dtype phải là float16 hoặc bfloat16")
    if int(config["autoencoder"]["latent_dim"]) <= 0:
        raise ValueError("autoencoder.latent_dim phải lớn hơn 0")
    if int(config["stage1"]["oof_folds"]) < 2:
        raise ValueError("stage1.oof_folds phải từ 2 trở lên để tránh stacking leakage")


def project_root(config: dict[str, Any]) -> Path:
    return Path(config["_project_root"])


def project_path(config: dict[str, Any], value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root(config) / path


def experiment_id(config: dict[str, Any], override: str | None = None) -> str:
    value = override or str(config["experiment"]["id"])
    cleaned = "".join(character if character.isalnum() or character in "-_" else "_" for character in value)
    if not cleaned:
        raise ValueError("experiment id không hợp lệ")
    return cleaned


def phase_directory(config: dict[str, Any], category: str, phase: str, run_id: str) -> Path:
    base = project_path(config, config["experiment"][category])
    return base / phase / run_id

