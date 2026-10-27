"""Matched fixed novelty models: no candidate selection and no heldout fitting.

Uses the same known-train latent and known validation as the historical studies.
balanced_l2_k1 is a POST-HOC hypothesis from knn_v1, not an independent discovery.
All three thresholds are persisted before querying any test features here.
"""
from __future__ import annotations
import time
import joblib
import numpy as np
from src.knn_distance import LatentKNN, reference_indices
from src.mahalanobis import SharedMahalanobis
from src.novelty import NoveltyResult, threshold_from_known_validation
from src.training_utils import save_json


METHODS = ('max_probability', 'mahalanobis', 'knn_distance')


def fit_matched_novelty(features, labels, train, validation, test, validation_probabilities,
                        test_probabilities, rejection_rate, reference_seed, output_dir,
                        model_dir, reference_size=50000, progress=print):
    """Fixed k=1/L2/balanced; return models and scores for existing evaluator.

    Caller must verify train/validation/test against the artifact contracts first.
    Save fit/reference indices, class counts, shrinkage, threshold ties and replay.
    CPU FP64 exact cKDTree and LedoitWolf preserve the historical baselines.
    AE/XGBoost training remains CUDA upstream; no package or backend change here.
    """
    train, validation, test = [np.asarray(ids, dtype=np.int64) for ids in (train, validation, test)]
    for ids in (train, validation, test):
        if len(ids) == 0 or len(np.unique(ids)) != len(ids):
            raise ValueError('Empty/duplicate novelty population')
    if (np.intersect1d(train, validation).size or np.intersect1d(train, test).size
            or np.intersect1d(validation, test).size or np.any(labels[train] <= 0)
            or not np.array_equal(np.unique(labels[train]), np.unique(labels[validation]))):
        raise ValueError('Overlapping scopes or inconsistent known attack classes')
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    np.save(model_dir/'fit_indices.npy', train)
    np.save(model_dir/'validation_indices.npy', validation)
    refs = reference_indices(labels, train, reference_size, 'balanced', reference_seed)
    np.save(model_dir/'reference_indices.npy', refs)
    counts = {str(int(c)): int(np.sum(labels[refs] == c)) for c in np.unique(labels[train])}
    if any(n == 0 for n in counts.values()):
        raise ValueError('Balanced index omitted a known class')
    started = time.perf_counter()
    progress('FIT Mahalanobis: known train only; CPU FP64')
    maha = SharedMahalanobis.fit(features[train], labels[train])
    progress('FIT kNN: balanced known train, L2, k=1; exact CPU FP64')
    knn = LatentKNN.fit(features[refs], 'l2')
    models = {'max_probability': None, 'mahalanobis': maha, 'knn_distance': knn}
    v = {'max_probability': 1.0 - np.max(validation_probabilities, axis=1),
         'mahalanobis': maha.score(features[validation]),
         'knn_distance': knn.score_many(features[validation], [1], workers=-1)[1]}
    thresholds = {name: threshold_from_known_validation(v[name], rejection_rate) for name in METHODS}
    save_json(output_dir/'locked_validation_thresholds.json', {
        'thresholds': thresholds, 'selected_on': 'known_validation_only',
        'test_queried_at_lock': False, 'candidate_selection': 'NONE; all fixed methods reported'})
    # Each saved model must reproduce the validation scores; do not trust dump alone.
    for name, model in models.items():
        if model is None:
            continue
        path = model_dir/f'{name}.joblib'
        joblib.dump(model, path)
        loaded = joblib.load(path)
        replay = (loaded.score(features[validation[:16]]) if name == 'mahalanobis'
                  else loaded.score_many(features[validation[:16]], [1], workers=1)[1])
        if not np.allclose(replay, v[name][:16], rtol=1e-12, atol=1e-12):
            raise ValueError('Serialized novelty model does not reproduce validation')
        del loaded
    progress('All novelty thresholds locked; now score TEST without fitting/selection')
    t = {'max_probability': 1.0 - np.max(test_probabilities, axis=1),
         'mahalanobis': maha.score(features[test]),
         'knn_distance': knn.score_many(features[test], [1], workers=-1)[1]}
    parameters = {'fit_samples': len(train), 'validation_samples': len(validation),
                  'reference_size': len(refs), 'reference_seed': reference_seed,
                  'reference_class_counts': counts, 'knn': {'k': 1, 'normalization': 'l2',
                  'policy': 'balanced', 'epsilon': 1e-10, 'score': 'squared Euclidean', 'exact': True},
                  'mahalanobis': {'covariance': 'pooled within-class LedoitWolf',
                                  'shrinkage': maha.shrinkage, 'class_ids': maha.class_ids.tolist()},
                  'validation_rejection_actual': {n: float(np.mean(v[n] >= thresholds[n])) for n in METHODS},
                  'validation_zero_distance_fraction': float(np.mean(v['knn_distance'] == 0)),
                  'fit_score_seconds_NOT_deployment_latency': time.perf_counter()-started,
                  'test_used_for_fit_or_threshold': False}
    save_json(model_dir/'parameters.json', parameters)
    return [NoveltyResult(name, models[name], v[name], t[name], thresholds[name]) for name in METHODS]
