import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('research_round', Path(__file__).resolve().parents[1] / 'scripts/08_run_research_round.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SelectionTests(unittest.TestCase):
    def fixture(self):
        return {v: {'validation_metrics': {'macro_f1': .8}, 'known_test_metrics': {'macro_f1': 1.0}} for v in module.VARIANTS}

    def test_only_validation_selects(self):
        values = self.fixture()
        values['latent_only_mlp']['validation_metrics']['macro_f1'] = .9
        values['latent_only_mlp']['known_test_metrics']['macro_f1'] = .1
        self.assertEqual(module.choose_stage2(values), 'latent_only_mlp')

    def test_tie_uses_declared_order(self):
        self.assertEqual(module.choose_stage2(self.fixture()), 'latent_only')

    def test_invalid_validation_rejected(self):
        values = self.fixture()
        values['latent_only']['validation_metrics']['macro_f1'] = float('nan')
        with self.assertRaises(ValueError):
            module.choose_stage2(values)
