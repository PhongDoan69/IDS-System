import unittest

import numpy as np

from src.split_data import constrained_stratified_split


class SplitTests(unittest.TestCase):
    def test_split_is_reproducible_and_disjoint(self):
        labels = np.repeat(np.arange(4), [100, 20, 5, 3])
        first = constrained_stratified_split(
            labels, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15, random_state=42
        )
        second = constrained_stratified_split(
            labels, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15, random_state=42
        )
        np.testing.assert_array_equal(first, second)
        self.assertTrue(np.isin(first, [0, 1, 2]).all())
        for label in np.unique(labels):
            class_splits = first[labels == label]
            self.assertIn(0, class_splits)
            self.assertIn(1, class_splits)
            self.assertIn(2, class_splits)


if __name__ == "__main__":
    unittest.main()
