import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.config import load_config
from src.data_loader import inspect_schema, iter_csv_chunks


class DataLoaderTests(unittest.TestCase):
    def test_schema_validation_and_chunk_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            config_dir = root / "configs"
            raw.mkdir()
            config_dir.mkdir()
            frame = pd.DataFrame(
                {
                    " Feature ": [1, 2],
                    "Timestamp": ["a", "b"],
                    "Label": ["BENIGN", "DDoS"],
                    "Attempted Category": [-1, -1],
                }
            )
            for name in ("a.csv", "b.csv"):
                frame.to_csv(raw / name, index=False)
            config = {
                "random_state": 42,
                "data": {
                    "raw_dir": "raw",
                    "files": ["a.csv", "b.csv"],
                    "chunksize": 1,
                    "duplicate_policy": "drop_exact",
                    "attempted_policy": "preserve",
                },
                "features": {"excluded": ["Label"], "dtype": "float32"},
                "split": {"train": 0.7, "validation": 0.15, "test": 0.15},
                "outputs": {
                    "interim_dir": "interim",
                    "processed_dir": "processed",
                    "metadata_dir": "metadata",
                    "preprocessors_dir": "preprocessors",
                    "results_dir": "results",
                },
            }
            path = config_dir / "test.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            loaded = load_config(path)
            self.assertEqual(inspect_schema(loaded)[0], "Feature")
            chunks = list(iter_csv_chunks(loaded))
            self.assertEqual(sum(len(chunk) for _, _, chunk in chunks), 4)


if __name__ == "__main__":
    unittest.main()
