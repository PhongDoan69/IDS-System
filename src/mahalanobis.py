"""Post-hoc class means + pooled Ledoit-Wolf covariance. Not an OIDMD replica."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass
class SharedMahalanobis:
    class_ids: np.ndarray
    means: np.ndarray
    covariance: np.ndarray
    precision: np.ndarray
    cholesky_precision: np.ndarray
    counts: np.ndarray
    shrinkage: float

    @classmethod
    def fit(cls, features, labels):
        from sklearn.covariance import LedoitWolf
        x = np.asarray(features, dtype=np.float64)
        y = np.asarray(labels)
        if (x.ndim != 2 or not len(x) or not np.isfinite(x).all()
                or y.shape != (len(x),) or not np.issubdtype(y.dtype, np.integer)
                or np.any(y <= 0)):
            raise ValueError('Fit requires finite known-attack features and positive integer labels')
        ids, inverse, counts = np.unique(y, return_inverse=True, return_counts=True)
        if len(ids) < 2:
            raise ValueError('Need at least two known attack classes')
        means = np.vstack([x[y == label].mean(axis=0) for label in ids])
        # All fitting uses known TRAIN only; no validation/test covariance estimates.
        residual = x - means[inverse]
        estimator = LedoitWolf(assume_centered=True).fit(residual)
        precision = (estimator.precision_ + estimator.precision_.T) / 2
        if not np.isfinite(precision).all():
            raise ValueError('Non-finite covariance/precision')
        try:
            factor = np.linalg.cholesky(precision)
        except np.linalg.LinAlgError as error:
            raise ValueError('Degenerate training geometry; do not silently change regularization') from error
        return cls(ids, means, estimator.covariance_, precision, factor, counts, float(estimator.shrinkage_))

    def score(self, features, batch_size=8192):
        """min_c squared Mahalanobis; higher = more novel, all distances FP64.

        Work in whitened coordinates, avoiding an N x classes x dimensions
        tensor. CPU BLAS is intentional for 16-D vectors; no CUDA dependency.
        """
        x = np.asarray(features)
        if x.ndim != 2 or x.shape[1] != self.means.shape[1] or batch_size < 1:
            raise ValueError('Invalid scoring shape/batch size')
        centers = self.means @ self.cholesky_precision
        output = np.empty(len(x), dtype=np.float64)
        for start in range(0, len(x), batch_size):
            values = np.asarray(x[start:start+batch_size], dtype=np.float64)
            if not np.isfinite(values).all():
                raise ValueError('Scoring input contains NaN/Inf')
            white = values @ self.cholesky_precision
            distances = np.full(len(white), np.inf)
            for center in centers:
                delta = white - center
                distances = np.minimum(distances, np.einsum('ij,ij->i', delta, delta))
            if not np.isfinite(distances).all():
                raise ValueError('Scoring overflow; no clipping or test-driven fallback')
            output[start:start+len(white)] = distances
        return output
