from __future__ import annotations

from pathlib import Path

import numpy as np


def _probability_logit(probabilities: np.ndarray) -> np.ndarray:
    from src.contracts import probability_vector
    probability_vector(probabilities)
    clipped = np.clip(np.asarray(probabilities, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    return np.log(clipped / (1.0 - clipped)).reshape(-1, 1)


def fit_platt_calibrator(oof_probabilities: np.ndarray, train_targets: np.ndarray, random_state: int):
    """Fit trên score held-out được caller cung cấp; caller phải chứng minh fit/stop/cal disjoint."""
    from sklearn.linear_model import LogisticRegression

    calibrator = LogisticRegression(solver="lbfgs", random_state=random_state)
    calibrator.fit(_probability_logit(oof_probabilities), np.asarray(train_targets, dtype=np.int8))
    return calibrator


def apply_platt_calibrator(calibrator, probabilities: np.ndarray) -> np.ndarray:
    return calibrator.predict_proba(_probability_logit(probabilities))[:, 1].astype(np.float32)


def save_calibrator(calibrator, path: Path) -> None:
    import joblib

    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrator, path)

