"""Recall-oriented gate selection using known validation only."""
from __future__ import annotations
import math
import numpy as np
from src.contracts import probability_vector
from src.metrics import binary_metrics


def select_gate(probabilities, binary_targets, fpr_budget=0.001, baseline=0.5):
    p = probability_vector(probabilities)
    y = np.asarray(binary_targets)
    if y.shape != p.shape or not np.isin(y, [0, 1]).all() or len(np.unique(y)) != 2:
        raise ValueError('Known validation must contain benign and known attacks')
    if not 0 <= fpr_budget < 1 or not 0 < baseline <= 1:
        raise ValueError('Invalid FPR budget/baseline')
    before = binary_metrics(y, p, baseline)
    if before['false_positive_rate'] > fpr_budget:
        raise ValueError('Baseline already exceeds FPR budget; do not silently raise the gate')
    benign = np.sort(np.asarray(p[y == 0], dtype=np.float64))[::-1]
    allowed = math.floor(fpr_budget * len(benign))
    # A representable float32 successor keeps >= comparisons safe at tied scores.
    boundary = float(np.nextafter(np.float32(benign[allowed]), np.float32(np.inf)))
    threshold = min(float(baseline), boundary)
    after = binary_metrics(y, p, threshold)
    if after['false_positive_rate'] > fpr_budget or after['recall_detection_rate'] < before['recall_detection_rate']:
        raise ValueError('Gate selection violated FPR/recall constraints')
    return {'threshold': threshold, 'baseline_threshold': baseline,
            'benign_fpr_budget': fpr_budget, 'allowed_benign_false_positives': allowed,
            'selected_on': 'known_validation_only',
            'criterion': 'lowest float32-safe threshold <= baseline satisfying benign FPR budget',
            'baseline_validation_metrics': before, 'selected_validation_metrics': after}
