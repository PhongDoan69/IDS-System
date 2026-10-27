import unittest
import numpy as np
from src.gate_policy import select_gate


class GatePolicyTests(unittest.TestCase):
    def test_recall_increases_without_exceeding_budget(self):
        r = select_gate(np.array([.01, .02, .03, .04, .2, .8], dtype=np.float32),
                        np.array([0, 0, 0, 0, 1, 1]), .25)
        self.assertLess(r['threshold'], .5)
        self.assertEqual(r['selected_validation_metrics']['recall_detection_rate'], 1)
        self.assertLessEqual(r['selected_validation_metrics']['false_positive_rate'], .25)

    def test_tied_benign_scores_do_not_exceed_budget(self):
        r = select_gate(np.array([.1, .1, .1, .01, .2, .8], dtype=np.float32),
                        np.array([0, 0, 0, 0, 1, 1]), .25)
        self.assertEqual(r['selected_validation_metrics']['false_positive_rate'], 0)

    def test_infeasible_baseline_is_not_silently_changed(self):
        with self.assertRaises(ValueError):
            select_gate(np.array([.9, .1, .8]), np.array([0, 0, 1]), 0)

    def test_one_class_and_invalid_budget_rejected(self):
        with self.assertRaises(ValueError):
            select_gate(np.array([.1, .2]), np.array([0, 0]))
        with self.assertRaises(ValueError):
            select_gate(np.array([.1, .8]), np.array([0, 1]), 1)
