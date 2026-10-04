from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class EarlyStopping:
    patience: int
    min_delta: float = 0.0
    mode: str = "min"
    best_score: float | None = None
    bad_epochs: int = 0

    @property
    def best(self) -> float | None:
        return self.best_score

    @property
    def should_stop(self) -> bool:
        return self.bad_epochs >= self.patience

    def update(self, score: float) -> bool:
        """Trả True khi metric tốt hơn để caller lưu checkpoint ra đĩa."""
        improved = self.best_score is None
        if self.best_score is not None:
            if self.mode == "min":
                improved = score < self.best_score - self.min_delta
            else:
                improved = score > self.best_score + self.min_delta
        if improved:
            self.best_score = float(score)
            self.bad_epochs = 0
        else:
            self.bad_epochs += 1
        return improved


@dataclass
class TrainingHistory:
    epoch: list[int] = field(default_factory=list)
    train_loss: list[float] = field(default_factory=list)
    validation_loss: list[float] = field(default_factory=list)
    learning_rate: list[float] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def append(self, epoch: int, train_loss: float, validation_loss: float, learning_rate: float) -> None:
        self.epoch.append(int(epoch))
        self.train_loss.append(float(train_loss))
        self.validation_loss.append(float(validation_loss))
        self.learning_rate.append(float(learning_rate))

    def to_dict(self) -> dict[str, Any]:
        return {
            "epoch": self.epoch,
            "train_loss": self.train_loss,
            "validation_loss": self.validation_loss,
            "learning_rate": self.learning_rate,
            "elapsed_seconds": self.elapsed_seconds,
        }


def save_torch_checkpoint(
    path: Path,
    model,
    optimizer,
    epoch: int,
    validation_loss: float,
    metadata: dict[str, Any],
) -> None:
    import torch

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "epoch": int(epoch),
            "validation_loss": float(validation_loss),
            "metadata": metadata,
        },
        temporary,
    )
    temporary.replace(path)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=_json_default)
        stream.write("\n")
    temporary.replace(path)


def _json_default(value: Any):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Không serialize được {type(value).__name__}")


class Timer:
    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed = time.perf_counter() - self.started

