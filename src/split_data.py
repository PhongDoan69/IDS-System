from __future__ import annotations

import numpy as np
import pandas as pd


TRAIN_ID = 0
VALIDATION_ID = 1
TEST_ID = 2
SPLIT_NAMES = {TRAIN_ID: "train", VALIDATION_ID: "validation", TEST_ID: "test"}


def constrained_stratified_split(
    label_ids: np.ndarray,
    *,
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
    random_state: int,
) -> np.ndarray:
    """Deterministic per-class split that preserves even classes with 3-5 rows."""
    ratios = train_ratio + validation_ratio + test_ratio
    if abs(ratios - 1.0) > 1e-9:
        raise ValueError("Split ratios must sum to 1.0")
    labels = np.asarray(label_ids)
    split_ids = np.full(len(labels), -1, dtype=np.int8)
    rng = np.random.default_rng(random_state)

    for label in np.unique(labels):
        indices = np.flatnonzero(labels == label)
        indices = rng.permutation(indices)
        count = len(indices)
        if count == 1:
            n_validation, n_test = 0, 0
        elif count == 2:
            n_validation, n_test = 0, 1
        else:
            n_validation = max(1, int(round(count * validation_ratio)))
            n_test = max(1, int(round(count * test_ratio)))
            if n_validation + n_test >= count:
                n_validation, n_test = 1, 1
        n_train = count - n_validation - n_test
        split_ids[indices[:n_train]] = TRAIN_ID
        split_ids[indices[n_train : n_train + n_validation]] = VALIDATION_ID
        split_ids[indices[n_train + n_validation :]] = TEST_ID

    if (split_ids < 0).any():
        raise RuntimeError("At least one sample was not assigned to a split")
    return split_ids


def split_summary(split_ids: np.ndarray, label_ids: np.ndarray, id_to_label: dict[int, str]) -> pd.DataFrame:
    rows = []
    for label_id in sorted(id_to_label):
        label_mask = label_ids == label_id
        for split_id, split_name in SPLIT_NAMES.items():
            rows.append(
                {
                    "attack_label_id": int(label_id),
                    "attack_label": id_to_label[label_id],
                    "split": split_name,
                    "count": int(np.sum(label_mask & (split_ids == split_id))),
                }
            )
    return pd.DataFrame(rows)
