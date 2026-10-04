from __future__ import annotations

from typing import Any

import numpy as np


def binary_metrics(y_true: np.ndarray, probabilities: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        balanced_accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    truth = np.asarray(y_true, dtype=np.int8)
    prob = np.asarray(probabilities, dtype=np.float64)
    pred = (prob >= threshold).astype(np.int8)
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(truth, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, pred)),
        "precision": float(precision_score(truth, pred, zero_division=0)),
        "recall_detection_rate": float(recall_score(truth, pred, zero_division=0)),
        "f1": float(f1_score(truth, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(truth, prob)),
        "pr_auc": float(average_precision_score(truth, prob)),
        "confusion_matrix": confusion_matrix(truth, pred, labels=[0, 1]).tolist(),
    }


def multiclass_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

    truth = np.asarray(y_true)
    pred = np.asarray(y_pred)
    return {
        "accuracy": float(accuracy_score(truth, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, pred)),
        "macro_f1": float(f1_score(truth, pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(truth, pred, average="weighted", zero_division=0)),
    }


def open_set_metrics(is_unknown: np.ndarray, novelty_scores: np.ndarray, threshold: float) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, f1_score, recall_score, roc_auc_score

    truth = np.asarray(is_unknown, dtype=np.int8)
    pred = (np.asarray(novelty_scores) >= threshold).astype(np.int8)
    result = {
        "threshold": float(threshold),
        "unknown_recall": float(recall_score(truth, pred, zero_division=0)),
        "unknown_f1": float(f1_score(truth, pred, zero_division=0)),
        "known_false_rejection_rate": float(pred[truth == 0].mean()) if np.any(truth == 0) else None,
    }
    if len(np.unique(truth)) == 2:
        result["open_set_roc_auc"] = float(roc_auc_score(truth, novelty_scores))
        result["open_set_pr_auc"] = float(average_precision_score(truth, novelty_scores))
    return result

