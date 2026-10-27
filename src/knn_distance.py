"""Exact latent kNN novelty, with a train-only reference database."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.spatial import cKDTree


def reference_indices(labels, known_train, maximum, policy, seed=42):
    """Without replacement; balanced uses equal quotas with deficit redistribution.

    Caller proves known_train is the outer-fold known-attack TRAIN population.
    No oversampling, synthetic rows or deduplication by feature values.
    """
    labels = np.asarray(labels)
    ids = np.asarray(known_train)
    if (ids.ndim != 1 or not len(ids) or not np.issubdtype(ids.dtype, np.integer)
            or len(np.unique(ids)) != len(ids) or np.any(ids < 0) or np.any(ids >= len(labels))
            or np.any(labels[ids] <= 0) or maximum < 1):
        raise ValueError('Invalid known-train candidates/reference size')
    if policy not in ['natural', 'balanced']:
        raise ValueError('Unknown reference sampling policy')
    rng = np.random.default_rng(seed)
    count = min(int(maximum), len(ids))
    if policy == 'natural':
        return np.sort(rng.choice(ids, count, replace=False))
    classes = np.unique(labels[ids])
    if count < len(classes):
        raise ValueError('Balanced reference needs at least one row per known class')
    groups = [ids[labels[ids] == label] for label in classes]
    quotas = np.zeros(len(groups), dtype=int)
    remaining = count
    while remaining:
        active = np.flatnonzero([len(g) > n for g, n in zip(groups, quotas)])
        if not len(active):
            raise ValueError('Cannot allocate balanced reference quota')
        share = max(1, remaining // len(active))
        for position in active:
            take = min(len(groups[position])-quotas[position], share, remaining)
            quotas[position] += take; remaining -= take
            if not remaining:
                break
    return np.sort(np.concatenate([rng.choice(g, n, replace=False) for g, n in zip(groups, quotas)]))


def transform_latent(features, normalization):
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or not x.shape[1] or not np.isfinite(x).all():
        raise ValueError('Latent must be a finite 2-D matrix')
    if normalization == 'none':
        return np.array(x, order='C', copy=True)
    if normalization != 'l2':
        raise ValueError('Normalization must be none or l2')
    # Per-row transform only: no parameters learned from validation/test.
    # Same epsilon convention as the paper's reference implementation.
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    if not np.isfinite(norms).all():
        raise ValueError('Latent norm overflow')
    return np.ascontiguousarray(x / (norms + 1e-10))


@dataclass
class LatentKNN:
    normalization: str
    reference: np.ndarray
    tree: cKDTree

    @classmethod
    def fit(cls, train_reference, normalization='l2'):
        values = transform_latent(train_reference, normalization)
        if len(values) < 1:
            raise ValueError('Empty reference database')
        # Exact CPU index. No ANN or package installation; cKDTree ships with SciPy.
        tree = cKDTree(values, leafsize=32, compact_nodes=True, balanced_tree=True, copy_data=True)
        return cls(normalization, values, tree)

    def score_many(self, features, ks, batch_size=1024, workers=-1, progress=None):
        x = np.asarray(features)
        ranks = list(ks)
        if (x.ndim != 2 or x.shape[1] != self.reference.shape[1] or batch_size < 1
                or not ranks or len(set(ranks)) != len(ranks)
                or any(not isinstance(k, (int, np.integer)) or k < 1 or k > len(self.reference) for k in ranks)
                or workers == 0 or workers < -1):
            raise ValueError('Invalid query dimensions/k/batch/workers')
        output = {int(k): np.empty(len(x), dtype=np.float64) for k in ranks}
        for start in range(0, len(x), batch_size):
            stop = min(start+batch_size, len(x))
            values = transform_latent(x[start:stop], self.normalization)
            distance, _ = self.tree.query(values, k=ranks, eps=0.0, p=2, workers=workers)
            scores = np.square(distance)  # squared Euclidean distance, higher = more novel
            if not np.isfinite(scores).all():
                raise ValueError('Non-finite kNN distance; do not clip or impute')
            for column, k in enumerate(ranks):
                output[int(k)][start:stop] = scores[:, column]
            if progress:
                progress(stop, len(x))
        return output
