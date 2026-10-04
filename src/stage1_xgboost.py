from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def _class_ratio(targets: np.ndarray) -> float:
    positives = max(int(np.count_nonzero(targets == 1)), 1)
    negatives = int(np.count_nonzero(targets == 0))
    return negatives / positives


def build_classifier(config: dict[str, Any], targets: np.ndarray, random_state: int):
    """XGBoost GPU dùng histogram và max_bin thấp để phù hợp VRAM 4 GB."""
    from xgboost import XGBClassifier

    params = dict(config)
    early_stopping_rounds = int(params.pop("early_stopping_rounds"))
    return XGBClassifier(
        **params,
        objective="binary:logistic",
        scale_pos_weight=_class_ratio(targets),
        random_state=random_state,
        n_jobs=-1,
        early_stopping_rounds=early_stopping_rounds,
    )


def fit_classifier(
    train_features: np.ndarray,
    train_targets: np.ndarray,
    validation_features: np.ndarray,
    validation_targets: np.ndarray,
    config: dict[str, Any],
    random_state: int,
):
    model = build_classifier(config, train_targets, random_state)
    model.fit(
        np.asarray(train_features, dtype=np.float32),
        np.asarray(train_targets, dtype=np.int8),
        eval_set=[
            (
                np.asarray(validation_features, dtype=np.float32),
                np.asarray(validation_targets, dtype=np.int8),
            )
        ],
        verbose=50,
    )
    return model


def positive_probability(model, features: np.ndarray) -> np.ndarray:
    return model.predict_proba(np.asarray(features, dtype=np.float32))[:, 1].astype(np.float32)


def save_classifier(model, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(path))

