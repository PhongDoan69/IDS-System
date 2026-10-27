import tempfile
from pathlib import Path
import unittest
import joblib
import numpy as np
from src.knn_distance import LatentKNN, reference_indices, transform_latent


class KNNDistanceTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(7)
        self.reference = rng.normal(size=(30, 4))
        self.query = rng.normal(size=(13, 4))

    def test_exact_squared_distance_matches_bruteforce(self):
        for normal in ['none', 'l2']:
            model = LatentKNN.fit(self.reference, normal)
            q = transform_latent(self.query, normal)
            r = transform_latent(self.reference, normal)
            expected = np.sort(np.sum((q[:,None,:]-r[None,:,:])**2, axis=2), axis=1)
            scores = model.score_many(self.query, [5, 1, 10], batch_size=3, workers=1)
            for k in [1, 5, 10]:
                np.testing.assert_allclose(scores[k], expected[:,k-1], rtol=1e-12, atol=1e-12)

    def test_same_reference_size_deterministic_no_outside_rows(self):
        labels = np.r_[np.ones(100, dtype=int), np.full(25,2), np.full(3,3), np.full(10,9)]
        train = np.arange(128)
        for policy in ['natural', 'balanced']:
            refs = reference_indices(labels, train, 30, policy, 42)
            self.assertEqual(len(refs), 30)
            self.assertEqual(len(np.unique(refs)), 30)
            self.assertTrue(np.isin(refs, train).all())
            self.assertFalse(np.any(labels[refs] == 9))
            np.testing.assert_array_equal(refs, reference_indices(labels, train, 30, policy, 42))
        balanced = reference_indices(labels, train, 30, 'balanced', 42)
        self.assertEqual(np.sum(labels[balanced] == 3), 3)
        self.assertLessEqual(abs(np.sum(labels[balanced] == 1)-np.sum(labels[balanced] == 2)), 1)

    def test_small_database_never_oversamples(self):
        refs = reference_indices(np.array([1,1,2,3]), np.arange(4), 100, 'balanced')
        np.testing.assert_array_equal(refs, np.arange(4))

    def test_invalid_references_rejected(self):
        for ids in [np.array([0,0]), np.array([-1,2]), np.array([0,8])]:
            with self.assertRaises(ValueError):
                reference_indices(np.array([1,1,2]), ids, 2, 'natural')
        with self.assertRaises(ValueError):
            reference_indices(np.array([0,1,2]), np.arange(3), 2, 'natural')
        with self.assertRaises(ValueError):
            reference_indices(np.array([1,2,3]), np.arange(3), 2, 'balanced')

    def test_serialization_batch_order_and_query_does_not_refit(self):
        model = LatentKNN.fit(self.reference, 'l2')
        before = model.reference.copy()
        expected = model.score_many(self.query, [1, 10], 1, 1)
        np.testing.assert_array_equal(before, model.reference)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'index.joblib'; joblib.dump(model, path)
            actual = joblib.load(path).score_many(self.query, [1, 10], 7, 1)
            for k in expected:
                np.testing.assert_allclose(expected[k], actual[k], rtol=1e-12, atol=1e-12)

    def test_zero_vectors_and_duplicate_values_are_preserved(self):
        model = LatentKNN.fit(np.array([[0.,0.],[0.,0.],[1.,0.]]), 'l2')
        score = model.score_many(np.array([[0.,0.]]), [1,2,3], workers=1)
        self.assertEqual(len(model.reference), 3)
        self.assertEqual(score[1][0], 0)
        self.assertEqual(score[2][0], 0)
        self.assertTrue(np.isfinite(score[3]).all())

    def test_bad_queries_rejected(self):
        model = LatentKNN.fit(self.reference)
        for ks in [[0], [31], [1,1], []]:
            with self.assertRaises(ValueError):
                model.score_many(self.query, ks)
        with self.assertRaises(ValueError):
            model.score_many(np.full((2,4),np.nan), [1])
        with self.assertRaises(ValueError):
            model.score_many(np.ones((2,3)), [1])

    def test_l2_positive_scaling_invariance(self):
        model = LatentKNN.fit(self.reference, 'l2')
        np.testing.assert_allclose(model.score_many(self.query,[5],workers=1)[5],
                                   model.score_many(self.query*7,[5],workers=1)[5], rtol=1e-9, atol=1e-9)
