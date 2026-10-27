from __future__ import annotations

import json
import logging
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
        if not np.isfinite(score):
            raise ValueError('Early stopping nhận metric NaN/Inf')
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
    _started: float = field(default_factory=time.perf_counter, repr=False)

    def append(self, epoch: int, train_loss: float, validation_loss: float, learning_rate: float) -> None:
        self.elapsed_seconds = time.perf_counter() - self._started
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


def _replace_atomic_with_retry(temporary: Path, path: Path) -> None:
    """Retry only Windows access/sharing/lock errors during atomic replacement.

    Checkpoint readers/indexers can briefly hold a Windows file handle. Retry the
    already-written temporary file, never delete the previous good checkpoint or
    fall back to a non-atomic write. A persistent ACL/lock failure still raises
    after eight attempts (at most 4.5 seconds of backoff); keep both files for
    diagnosis. This changes I/O robustness, not training/selection semantics.
    """
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except OSError as error:
            if getattr(error, "winerror", None) not in {5, 32, 33} or attempt == 7:
                raise
            if attempt == 0:
                logging.getLogger(__name__).warning(
                    "Windows temporarily denied atomic replace of %s (winerror=%s); "
                    "retrying without deleting the previous artifact.",
                    path, error.winerror,
                )
            time.sleep(min(0.1 * (2 ** attempt), 1.0))


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
    # Close our own writer before replacement; Windows does not permit replacing
    # a file while a conflicting handle remains open.
    with temporary.open("wb") as stream:
        torch.save(
            {
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "epoch": int(epoch),
                "validation_loss": float(validation_loss),
                "metadata": metadata,
            },
            stream,
        )
    _replace_atomic_with_retry(temporary, path)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=_json_default)
        stream.write("\n")
    _replace_atomic_with_retry(temporary, path)


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

