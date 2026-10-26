from __future__ import annotations

from typing import Any

import numpy as np

from src.contracts import finite_vector, probability_vector


def _pair(truth, values):
    truth = finite_vector(truth, 'truth')
    values = finite_vector(values, 'prediction/score', len(truth))
    if not len(truth):
        raise ValueError('Không tính metric trên population rỗng')
    return truth, values


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

    truth, prob = _pair(y_true, probabilities)
    probability_vector(prob)
    if not np.isin(truth, [0, 1]).all() or not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError('Binary truth/threshold không hợp lệ')
    pred = (prob >= threshold).astype(np.int8)
    tn, fp, fn, tp = confusion_matrix(truth, pred, labels=[0, 1]).ravel()
    both_classes = len(np.unique(truth)) == 2
    ap = float(average_precision_score(truth, prob)) if both_classes else None
    return {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(truth, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, pred)),
        "precision": float(precision_score(truth, pred, zero_division=0)),
        "recall_detection_rate": float(recall_score(truth, pred, zero_division=0)),
        "f1": float(f1_score(truth, pred, zero_division=0)),
        "false_positive_rate": float(fp / (tn + fp)) if tn + fp else None,
        "false_negative_rate": float(fn / (fn + tp)) if fn + tp else None,
        "roc_auc": float(roc_auc_score(truth, prob)) if both_classes else None,
        "average_precision": ap,
        "pr_auc": ap,  # Alias lịch sử: AP, không phải trapezoidal PR-AUC.
        "pr_auc_definition": "average_precision; undefined here when only one true class",
        "support": len(truth),
        "brier_score": float(np.mean((prob - truth) ** 2)),
        "confusion_matrix": confusion_matrix(truth, pred, labels=[0, 1]).tolist(),
    }


def multiclass_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, confusion_matrix, precision_recall_fscore_support

    truth, pred = _pair(y_true, y_pred)
    labels = np.union1d(truth, pred)
    precision, recall, f1, support = precision_recall_fscore_support(truth, pred, labels=labels, zero_division=0)
    matrix = confusion_matrix(truth, pred, labels=labels)
    return {
        "accuracy": float(accuracy_score(truth, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, pred)),
        "macro_f1": float(f1_score(truth, pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(truth, pred, average="weighted", zero_division=0)),
        "support": len(truth),
        "class_id_order": labels.astype(int).tolist(),
        "confusion_matrix": matrix.tolist(),
        "confusion_matrix_normalized_true": np.divide(matrix, matrix.sum(1, keepdims=True), out=np.zeros_like(matrix, dtype=float), where=matrix.sum(1, keepdims=True) != 0).tolist(),
        "per_class": {str(int(c)): {'precision': float(p), 'recall': float(r), 'f1': float(f), 'support': int(n)} for c, p, r, f, n in zip(labels, precision, recall, f1, support)},
    }


def open_set_metrics(is_unknown: np.ndarray, novelty_scores: np.ndarray, threshold: float) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, f1_score, recall_score, roc_auc_score

    truth, novelty_scores = _pair(np.asarray(is_unknown, dtype=np.int8), novelty_scores)
    if not np.isin(truth, [0, 1]).all() or not np.isfinite(threshold):
        raise ValueError('Unknown truth/threshold không hợp lệ')
    pred = (novelty_scores >= threshold).astype(np.int8)
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


def pipeline_diagnostics(truth, final, p_attack, stage2_probabilities, class_ids, threshold, held_out=None):
    """Population: full test; conditional metrics được gắn mẫu số, không dùng truth để routing."""
    from sklearn.metrics import precision_score, recall_score, f1_score
    truth, final = _pair(truth, final)
    gate = probability_vector(p_attack, length=len(truth)) >= threshold
    attack = truth != 0
    known = attack & (truth != held_out) if held_out is not None else attack
    evaluation_truth = np.where(truth == held_out, -1, truth) if held_out is not None else truth
    parts = {
        'benign_passed_gate': int(np.sum(~attack & gate)),
        'attack_blocked_gate': int(np.sum(attack & ~gate)),
        'passed_attack_wrong_final': int(np.sum(attack & gate & (final != evaluation_truth))),
    }
    parts['total_errors'] = int(np.sum(final != evaluation_truth))
    if sum(parts[k] for k in ['benign_passed_gate', 'attack_blocked_gate', 'passed_attack_wrong_final']) != parts['total_errors']:
        raise ValueError('Error decomposition không khớp cascade output')
    oracle = np.asarray(class_ids)[np.asarray(stage2_probabilities).argmax(axis=1)]
    result = {'error_decomposition': parts,
              'stage2_oracle_known_attack_metrics': multiclass_metrics(truth[known], oracle[known]) if known.any() else None,
              'stage2_admitted_known_attack_metrics': multiclass_metrics(truth[known & gate], oracle[known & gate]) if (known & gate).any() else None}
    if held_out is not None:
        unknown = truth == held_out
        rejected = final == -1
        result['final_unknown_metrics'] = {
            'population': 'all_test_including_benign; final prediction after gate',
            'unknown_support': int(unknown.sum()), 'known_attack_support': int(known.sum()),
            'precision': float(precision_score(unknown, rejected, zero_division=0)),
            'recall': float(recall_score(unknown, rejected, zero_division=0)),
            'f1': float(f1_score(unknown, rejected, zero_division=0)),
            'unknown_detected': int(np.sum(unknown & rejected)),
            'unknown_blocked_by_stage1': int(np.sum(unknown & ~gate)),
            'benign_rejected_unknown': int(np.sum(~attack & rejected)),
            'known_attack_false_rejection_rate': float(rejected[known].mean()) if known.any() else None,
        }
    return result

