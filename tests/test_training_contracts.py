from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

from src.evaluation import UNKNOWN_ATTACK_ID, compose_pipeline_predictions
from src.model_data import validate_held_out_label
from src.novelty import balanced_subsample_indices, threshold_from_known_validation
from src.stage2 import attack_class_mapping, remap_targets
from src.training_utils import _replace_atomic_with_retry, save_json, save_torch_checkpoint


class AtomicSaveTests(unittest.TestCase):
    @staticmethod
    def windows_error(code):
        error = PermissionError("fixture Windows file lock")
        error.winerror = code
        return error

    def test_windows_transient_errors_recover_atomically(self):
        for code in [5, 32, 33]:
            with self.subTest(winerror=code), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "checkpoint"
                temporary = Path(directory) / "checkpoint.tmp"
                target.write_bytes(b"old")
                temporary.write_bytes(b"new")
                original = Path.replace
                calls = []
                def replace(source, destination):
                    calls.append(1)
                    if len(calls) < 3:
                        self.assertEqual(target.read_bytes(), b"old")
                        raise self.windows_error(code)
                    return original(source, destination)
                with patch.object(Path, "replace", replace), patch("src.training_utils.time.sleep") as sleep:
                    _replace_atomic_with_retry(temporary, target)
                    self.assertEqual(sleep.call_count, 2)
                self.assertEqual(target.read_bytes(), b"new")
                self.assertFalse(temporary.exists())

    def test_persistent_lock_preserves_old_and_temporary(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "checkpoint"
            temporary = Path(directory) / "checkpoint.tmp"
            target.write_bytes(b"old")
            temporary.write_bytes(b"new")
            with patch.object(Path, "replace", side_effect=self.windows_error(5)) as replace, patch("src.training_utils.time.sleep") as sleep:
                with self.assertRaises(PermissionError):
                    _replace_atomic_with_retry(temporary, target)
                self.assertEqual(replace.call_count, 8)
                self.assertEqual(sleep.call_count, 7)
            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(temporary.read_bytes(), b"new")

    def test_other_errors_are_not_retried(self):
        for error in [OSError(28, "disk full"), PermissionError("non-Windows permission error")]:
            with patch.object(Path, "replace", side_effect=error) as replace, patch("src.training_utils.time.sleep") as sleep:
                with self.assertRaises(OSError):
                    _replace_atomic_with_retry(Path("unused.tmp"), Path("unused"))
                self.assertEqual(replace.call_count, 1)
                sleep.assert_not_called()

    def test_json_uses_retry_helper(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "status.json"
            with patch("src.training_utils._replace_atomic_with_retry", wraps=_replace_atomic_with_retry) as replace:
                save_json(target, {"status": "fixture"})
                replace.assert_called_once()
            self.assertIn("fixture", target.read_text())

    def test_repeated_checkpoint_saves_without_training(self):
        import torch
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "best.pt"
            model = torch.nn.Linear(2, 1)
            optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
            with patch("src.training_utils._replace_atomic_with_retry", wraps=_replace_atomic_with_retry) as replace:
                for epoch in range(20):
                    save_torch_checkpoint(target, model, optimizer, epoch, 1.0, {"fixture": True})
                self.assertEqual(replace.call_count, 20)
            checkpoint = torch.load(target, map_location="cpu", weights_only=True)
            self.assertEqual(checkpoint["epoch"], 19)
            self.assertFalse(target.with_suffix(".pt.tmp").exists())


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

