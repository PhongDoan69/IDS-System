from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    """Load a JSON config and attach its project root for path resolution."""
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as stream:
        config = json.load(stream)
    config["_config_path"] = str(config_path)
    config["_project_root"] = str(config_path.parent.parent)
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    required = {"random_state", "data", "features", "split", "outputs"}
    missing = required.difference(config)
    if missing:
        raise ValueError(f"Missing config sections: {sorted(missing)}")

    ratios = config["split"]
    total = sum(float(ratios[name]) for name in ("train", "validation", "test"))
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"Split ratios must sum to 1.0, got {total}")
    if config["data"]["duplicate_policy"] not in {"drop_exact", "keep"}:
        raise ValueError("duplicate_policy must be 'drop_exact' or 'keep'")
    if config["data"]["attempted_policy"] != "preserve":
        raise ValueError("Phase 2 only supports the non-lossy attempted_policy='preserve'")


def project_path(config: dict[str, Any], value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(config["_project_root"]) / path


def output_path(config: dict[str, Any], key: str) -> Path:
    return project_path(config, config["outputs"][key])
