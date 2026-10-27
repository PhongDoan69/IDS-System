import tempfile
from pathlib import Path
import unittest
import joblib
import numpy as np
from src.mahalanobis import SharedMahalanobis
from src.novelty import threshold_from_known_validation


class MahalanobisTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(8)
        self.x = np.r_[rng.normal(-2, .4, (40, 4)), rng.normal(2, .4, (40, 4))]
        self.y = np.repeat([2, 9], 40)

    def test_matches_direct_quadratic_distance(self):
        model = SharedMahalanobis.fit(self.x, self.y)
        z = self.x[:8] + .1
        expected = np.min([[((v-m) @ model.precision @ (v-m)) for m in model.means] for v in z], axis=1)
        np.testing.assert_allclose(model.score(z, 3), expected, rtol=1e-10)

    def test_far_points_have_larger_scores(self):
        model = SharedMahalanobis.fit(self.x, self.y)
        self.assertGreater(model.score(np.full((1, 4), 50.))[0], model.score(self.x).max())

    def test_singleton_class_uses_shared_covariance(self):
        model = SharedMahalanobis.fit(np.r_[self.x, [[0., 0., 0., 0.]]], np.r_[self.y, 12])
        self.assertEqual(model.counts[-1], 1)
        self.assertTrue(np.isfinite(model.score(self.x)).all())

    def test_serialization_and_batch_order(self):
        model = SharedMahalanobis.fit(self.x, self.y)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'model.joblib'; joblib.dump(model, p)
            loaded = joblib.load(p)
            np.testing.assert_allclose(model.score(self.x, 1), loaded.score(self.x, 23))

    def test_bad_fit_and_score_rejected(self):
        with self.assertRaises(ValueError):
            SharedMahalanobis.fit(self.x, np.zeros(80, dtype=int))
        with self.assertRaises(ValueError):
            SharedMahalanobis.fit(self.x*np.nan, self.y)
        model = SharedMahalanobis.fit(self.x, self.y)
        with self.assertRaises(ValueError):
            model.score(np.ones((2, 3)))
        with self.assertRaises(ValueError):
            model.score(np.full((2, 4), np.inf))

    def test_threshold_frozen_before_test(self):
        model = SharedMahalanobis.fit(self.x, self.y)
        before = model.means.copy()
        threshold = threshold_from_known_validation(model.score(self.x), .05)
        model.score(np.full((3, 4), 100.))
        np.testing.assert_array_equal(before, model.means)
        self.assertEqual(threshold, threshold_from_known_validation(model.score(self.x), .05))

    def test_no_per_class_covariance_inversion_for_collinear_input(self):
        x = np.c_[self.x[:, 0], self.x[:, 0], np.ones(len(self.x))]
        model = SharedMahalanobis.fit(x, self.y)
        self.assertTrue(np.isfinite(model.score(x)).all())
