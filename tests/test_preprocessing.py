import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.preprocessing import TrainOnlyStandardScaler, clean_chunk, load_scaler, save_scaler


class PreprocessingTests(unittest.TestCase):
    def test_clean_chunk_removes_invalid_rows_and_reports_counts(self):
        frame = pd.DataFrame(
            {
                "Timestamp": ["a", "b"],
                "Feature": [1.0, np.inf],
                "Attempted Category": [-1, -1],
                "Label": ["BENIGN", "DDoS"],
            }
        )
        cleaned, report = clean_chunk(frame)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(report["before_count"], 2)
        self.assertEqual(report["removed_invalid_count"], 1)
        self.assertEqual(report["after_count"], 1)

    def test_scaler_state_is_not_changed_by_test_transform(self):
        train = np.array([[0.0, 10.0], [2.0, 14.0]])
        test = np.array([[1000.0, -1000.0]])
        scaler = TrainOnlyStandardScaler().fit(train)
        mean_before = scaler.mean_.copy()
        transformed = scaler.transform(test)
        np.testing.assert_array_equal(scaler.mean_, mean_before)
        self.assertEqual(transformed.dtype, np.float32)

    def test_scaler_can_be_persisted(self):
        scaler = TrainOnlyStandardScaler().fit(np.array([[0.0], [2.0]]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scaler.joblib"
            save_scaler(scaler, path)
            loaded = load_scaler(path)
            np.testing.assert_allclose(loaded.transform([[1.0]]), [[0.0]])


if __name__ == "__main__":
    unittest.main()
