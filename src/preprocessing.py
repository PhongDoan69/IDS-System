from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pickle

import numpy as np
import pandas as pd

try:
    import joblib
except ModuleNotFoundError:  # Allows Phase 2 smoke tests before the project venv is installed.
    joblib = None

from src.labels import add_label_columns


DERIVED_COLUMNS = {
    "attack_label_raw",
    "attack_label_normalized",
    "binary_label",
    "is_attempted",
    "attack_family",
}


def clean_chunk(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    before = len(frame)
    result = frame.copy()
    numeric_columns = [
        column for column in result.columns if column not in {"Timestamp", "Label"}
    ]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result[numeric_columns] = result[numeric_columns].replace([np.inf, -np.inf], np.nan)
    invalid_mask = result[numeric_columns].isna().any(axis=1) | result["Label"].isna()
    removed = int(invalid_mask.sum())
    if removed:
        result = result.loc[~invalid_mask].copy()
    result = add_label_columns(result)
    return result, {
        "before_count": int(before),
        "removed_invalid_count": removed,
        "after_count": int(len(result)),
    }


def feature_columns(schema: list[str], excluded: list[str]) -> list[str]:
    excluded_set = set(excluded)
    columns = [column for column in schema if column not in excluded_set]
    unexpected = DERIVED_COLUMNS.intersection(columns)
    if unexpected:
        raise ValueError(f"Derived labels cannot be model features: {sorted(unexpected)}")
    if not columns:
        raise ValueError("No feature columns remain after exclusions")
    return columns


@dataclass
class TrainOnlyStandardScaler:
    """Streaming population-standardization fitted only on training rows."""

    n_samples_seen_: int = 0
    mean_: np.ndarray | None = None
    m2_: np.ndarray | None = None
    var_: np.ndarray | None = None
    scale_: np.ndarray | None = None

    def partial_fit(self, values: np.ndarray) -> "TrainOnlyStandardScaler":
        array = np.asarray(values, dtype=np.float64)
        if array.ndim != 2:
            raise ValueError("Expected a two-dimensional feature matrix")
        if len(array) == 0:
            return self
        if not np.isfinite(array).all():
            raise ValueError("Scaler input contains NaN or infinity")

        batch_count = len(array)
        batch_mean = array.mean(axis=0)
        batch_m2 = ((array - batch_mean) ** 2).sum(axis=0)
        if self.n_samples_seen_ == 0:
            self.n_samples_seen_ = batch_count
            self.mean_ = batch_mean
            self.m2_ = batch_m2
        else:
            assert self.mean_ is not None and self.m2_ is not None
            total = self.n_samples_seen_ + batch_count
            delta = batch_mean - self.mean_
            self.mean_ = self.mean_ + delta * batch_count / total
            self.m2_ = (
                self.m2_
                + batch_m2
                + delta**2 * self.n_samples_seen_ * batch_count / total
            )
            self.n_samples_seen_ = total
        self.var_ = self.m2_ / self.n_samples_seen_
        self.scale_ = np.sqrt(self.var_)
        self.scale_[self.scale_ == 0] = 1.0
        return self

    def transform(self, values: np.ndarray, dtype: str = "float32") -> np.ndarray:
        if self.mean_ is None or self.scale_ is None:
            raise RuntimeError("Scaler has not been fitted")
        array = np.asarray(values, dtype=np.float64)
        transformed = (array - self.mean_) / self.scale_
        return transformed.astype(dtype, copy=False)

    def fit(self, values: np.ndarray) -> "TrainOnlyStandardScaler":
        return self.partial_fit(values)


def save_scaler(scaler: TrainOnlyStandardScaler, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if joblib is not None:
        joblib.dump(scaler, path)
    else:
        with path.open("wb") as stream:
            pickle.dump(scaler, stream)


def load_scaler(path: Path) -> TrainOnlyStandardScaler:
    if joblib is not None:
        return joblib.load(path)
    with path.open("rb") as stream:
        return pickle.load(stream)
