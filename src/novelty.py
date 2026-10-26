from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class NoveltyResult:
    name: str
    model: Any
    validation_scores: np.ndarray
    test_scores: np.ndarray
    threshold: float


def threshold_from_known_validation(scores: np.ndarray, known_rejection_rate: float) -> float:
    """Ngưỡng chỉ lấy từ known validation; test/zero-day không được dùng để chọn ngưỡng."""
    if not 0.0 < known_rejection_rate < 1.0:
        raise ValueError("known_rejection_rate phải thuộc (0, 1)")
    from src.contracts import finite_vector
    scores = finite_vector(scores, 'known validation novelty scores')
    if not len(scores):
        raise ValueError('Không thể chọn threshold trên validation rỗng')
    return float(np.quantile(np.asarray(scores), 1.0 - known_rejection_rate))


def deterministic_subsample(values: np.ndarray, maximum: int, random_state: int) -> np.ndarray:
    if len(values) <= maximum:
        return np.asarray(values, dtype=np.float32)
    rng = np.random.default_rng(random_state)
    selected = rng.choice(len(values), size=maximum, replace=False)
    return np.asarray(values[selected], dtype=np.float32)


def balanced_subsample_indices(
    labels: np.ndarray,
    candidate_indices: np.ndarray,
    maximum: int,
    random_state: int,
) -> np.ndarray:
    """Lấy mẫu gần cân bằng theo lớp để novelty model không bị lớp DDoS/DoS lấn át."""
    candidates = np.asarray(candidate_indices, dtype=np.int64)
    if len(candidates) <= maximum:
        return candidates
    values = np.asarray(labels[candidates])
    classes = np.unique(values)
    rng = np.random.default_rng(random_state)
    quota = max(1, maximum // len(classes))
    selected_parts = []
    used = np.zeros(len(candidates), dtype=bool)
    for class_id in classes:
        positions = np.flatnonzero(values == class_id)
        take = min(len(positions), quota)
        chosen = rng.choice(positions, size=take, replace=False)
        selected_parts.append(candidates[chosen])
        used[chosen] = True
    selected = np.concatenate(selected_parts)
    remaining_count = maximum - len(selected)
    if remaining_count > 0:
        remaining_positions = np.flatnonzero(~used)
        extra = rng.choice(remaining_positions, size=remaining_count, replace=False)
        selected = np.concatenate([selected, candidates[extra]])
    return rng.permutation(selected)


def score_max_probability(
    validation_probabilities: np.ndarray,
    test_probabilities: np.ndarray,
    rejection_rate: float,
) -> NoveltyResult:
    validation_scores = 1.0 - np.max(validation_probabilities, axis=1)
    test_scores = 1.0 - np.max(test_probabilities, axis=1)
    threshold = threshold_from_known_validation(validation_scores, rejection_rate)
    return NoveltyResult("max_probability", None, validation_scores, test_scores, threshold)


def fit_one_class_svm(
    train_features: np.ndarray,
    validation_features: np.ndarray,
    test_features: np.ndarray,
    config: dict[str, Any],
    rejection_rate: float,
    random_state: int,
) -> NoveltyResult:
    from sklearn.svm import OneClassSVM

    sampled = deterministic_subsample(train_features, int(config["max_training_samples"]), random_state)
    model = OneClassSVM(nu=float(config["nu"]), kernel=config["kernel"], gamma=config["gamma"])
    model.fit(sampled)
    validation_scores = -model.decision_function(np.asarray(validation_features, dtype=np.float32))
    test_scores = -model.decision_function(np.asarray(test_features, dtype=np.float32))
    threshold = threshold_from_known_validation(validation_scores, rejection_rate)
    return NoveltyResult("one_class_svm", model, validation_scores, test_scores, threshold)


def fit_isolation_forest(
    train_features: np.ndarray,
    validation_features: np.ndarray,
    test_features: np.ndarray,
    config: dict[str, Any],
    rejection_rate: float,
    random_state: int,
) -> NoveltyResult:
    from sklearn.ensemble import IsolationForest

    sampled = deterministic_subsample(train_features, int(config["max_samples"]), random_state)
    model = IsolationForest(
        n_estimators=int(config["n_estimators"]),
        max_samples=min(len(sampled), int(config["max_samples"])),
        contamination=config["contamination"],
        n_jobs=int(config["n_jobs"]),
        random_state=random_state,
    )
    model.fit(sampled)
    validation_scores = -model.score_samples(np.asarray(validation_features, dtype=np.float32))
    test_scores = -model.score_samples(np.asarray(test_features, dtype=np.float32))
    threshold = threshold_from_known_validation(validation_scores, rejection_rate)
    return NoveltyResult("isolation_forest", model, validation_scores, test_scores, threshold)


def save_novelty_model(result: NoveltyResult, directory: Path) -> None:
    if result.model is None:
        return
    import joblib

    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(result.model, directory / f"{result.name}.joblib")

