from __future__ import annotations

import unittest

import numpy as np

from src.evaluation import UNKNOWN_ATTACK_ID, compose_pipeline_predictions
from src.model_data import validate_held_out_label
from src.novelty import balanced_subsample_indices, threshold_from_known_validation
from src.stage2 import attack_class_mapping, remap_targets


class TrainingContractTests(unittest.TestCase):
    def test_stage2_excludes_benign_from_class_mapping(self) -> None:
        labels = np.array([0, 1, 2, 2, 3], dtype=np.int16)
        indices = np.arange(len(labels))
        forward, reverse = attack_class_mapping(labels, indices)
        self.assertNotIn(0, forward)
        self.assertEqual(remap_targets(labels, np.array([1, 2, 4]), forward).tolist(), [0, 1, 2])
        self.assertEqual(reverse[0], 1)

    def test_novelty_threshold_uses_upper_quantile(self) -> None:
        scores = np.arange(100, dtype=np.float32)
        threshold = threshold_from_known_validation(scores, 0.05)
        self.assertAlmostEqual(threshold, np.quantile(scores, 0.95))

    def test_novelty_sampling_keeps_minority_classes(self) -> None:
        labels = np.array([1] * 95 + [2] * 5)
        selected = balanced_subsample_indices(labels, np.arange(100), 20, 42)
        self.assertEqual(len(selected), 20)
        self.assertEqual(set(labels[selected]), {1, 2})

    def test_pipeline_gating(self) -> None:
        p_attack = np.array([0.1, 0.9, 0.8])
        stage2 = np.array([[0.9, 0.1], [0.2, 0.8], [0.7, 0.3]])
        novelty = np.array([0.9, 0.1, 0.8])
        result = compose_pipeline_predictions(
            p_attack, stage2, np.array([5, 9]), novelty, 0.5, 0.5
        )
        self.assertEqual(result.tolist(), [0, 9, UNKNOWN_ATTACK_ID])

    def test_loaco_rejects_benign_as_held_out(self) -> None:
        with self.assertRaises(ValueError):
            validate_held_out_label(np.array([0, 1, 2]), 0)


if __name__ == "__main__":
    unittest.main()

