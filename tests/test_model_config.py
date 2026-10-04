from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.model_config import load_model_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ModelConfigTests(unittest.TestCase):
    def test_main_config_is_valid(self) -> None:
        config = load_model_config(PROJECT_ROOT / "configs" / "model_config.json")
        self.assertEqual(config["hardware"]["device"], "cuda:0")
        self.assertEqual(config["hardware"]["pytorch_cuda_wheel"], "cu130")
        self.assertEqual(config["autoencoder"]["latent_dim"], 16)
        self.assertGreaterEqual(config["stage1"]["oof_folds"], 5)

    def test_stage2_ablation_names_are_complete(self) -> None:
        with (PROJECT_ROOT / "configs" / "model_config.json").open(encoding="utf-8") as stream:
            config = json.load(stream)
        self.assertEqual(
            set(config["stage2"]["experiments"]),
            {"latent_only", "latent_plus_pattack_xgb", "latent_plus_pattack_mlp"},
        )


if __name__ == "__main__":
    unittest.main()

