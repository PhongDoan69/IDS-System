from __future__ import annotations
import argparse
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from src.artifact_contracts import read_contract, write_contract, sidecar
from src.contracts import assert_new_outputs, exact_indices, probability_matrix, probability_vector
from src.data_loader import normalize_column_names, inspect_schema
from src.evaluation import compose_pipeline_predictions
from src.external_data import adapt_frame, approved_shared_features, iter_external_batches
from src.metrics import binary_metrics, multiclass_metrics, pipeline_diagnostics
from src.model_data import load_prepared_arrays
from src.model_config import load_model_config, validate_model_config, experiment_id
from src.preprocessing import TrainOnlyStandardScaler, load_scaler, feature_columns
from src.research_protocol import prepare_protocol, require_preprocessing, inner_partitions
from src.stage1_protocol import run_stage1
from src.training_utils import EarlyStopping
from src.training_utils import TrainingHistory

ROOT = Path(__file__).resolve().parents[1]


class NumericContracts(unittest.TestCase):
    def test_probability_rejects_nonfinite_range_and_shape(self):
        for values in [[np.nan], [np.inf], [-.1], [1.1], [[.5]]]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                probability_vector(values)

    def test_matrix_rejects_class_corruption(self):
        for values, classes in [([[.5,.5]],[0,1]), ([[.5,.5]],[1,1]), ([[.5,.2]],[1,2]), ([[.5,.5]],[1]), ([[np.nan,.5]],[1,2])]:
            with self.subTest(classes=classes), self.assertRaises(ValueError):
                probability_matrix(values, classes, 1)
        with self.assertRaises(ValueError):
            probability_matrix([[.5,.5]], [1,2], 1, held_out=2)

    def test_composition_fails_closed(self):
        with self.assertRaises(ValueError):
            compose_pipeline_predictions([np.nan], [[.2,.8]], [1,2], None, None, .5)
        with self.assertRaises(ValueError):
            compose_pipeline_predictions([.8], [[.2,.8]], [1,2], [np.inf], 1, .5)

    def test_known_and_unknown_error_decomposition(self):
        truth = np.array([0,0,1,2,9,9])
        p = np.array([.1,.9,.1,.9,.1,.9])
        q = np.array([[.8,.2]] * 6)
        pred = compose_pipeline_predictions(p, q, np.array([1,2]), np.ones(6), .5, .5)
        d = pipeline_diagnostics(truth, pred, p, q, [1,2], .5, 9)
        self.assertEqual(pred.tolist(), [0,-1,0,-1,0,-1])
        self.assertEqual(d['final_unknown_metrics']['unknown_blocked_by_stage1'], 1)
        self.assertEqual(d['final_unknown_metrics']['benign_rejected_unknown'], 1)
        self.assertEqual(d['final_unknown_metrics']['recall'], .5)
        self.assertEqual(d['error_decomposition']['total_errors'], 4)

    def test_metric_populations_and_undefined_auc(self):
        m = binary_metrics(np.array([0,0,1,1]), np.array([.1,.8,.2,.9]))
        self.assertEqual(m['false_positive_rate'], .5)
        self.assertEqual(m['false_negative_rate'], .5)
        self.assertEqual(m['average_precision'], m['pr_auc'])
        self.assertIsNone(binary_metrics(np.zeros(2), np.array([.1,.2]))['roc_auc'])
        multiclass = multiclass_metrics(np.array([0,1,1]), np.array([0,1,2]))
        self.assertEqual(multiclass['confusion_matrix'], [[1,0,0],[0,1,1],[0,0,0]])
        self.assertEqual(multiclass['per_class']['1']['support'], 2)

    def test_indices_and_names_fail_on_order_or_duplicates(self):
        with self.assertRaises(ValueError): exact_indices([1,0], [0,1])
        with self.assertRaises(ValueError): normalize_column_names([' X ', 'X'])
        with self.assertRaises(ValueError): feature_columns(['Label','X'], [])

    def test_csv_duplicate_header_detected_before_pandas_mangling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.csv'
            path.write_text('Label,Timestamp,Attempted Category,X,X\nBENIGN,a,0,1,2\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                inspect_schema({'_project_root':directory, 'data':{'raw_dir':directory, 'files':['sample.csv']}})

    def test_scaler_shape_and_early_stop_nan(self):
        s = TrainOnlyStandardScaler().fit(np.array([[1,2],[3,4]]))
        with self.assertRaises(ValueError): s.transform(np.array([[1]]))
        with self.assertRaises(ValueError): s.partial_fit(np.array([[1]]))
        with self.assertRaises(ValueError): EarlyStopping(2).update(np.nan)

    def test_config_and_run_ids(self):
        config = load_model_config(ROOT / 'configs/model_config.json')
        with self.assertRaises(ValueError): experiment_id(config, '../main')
        with self.assertRaises(ValueError): experiment_id(config, 'CON')
        config['evaluation']['decision_threshold'] = np.nan
        with self.assertRaises(ValueError): validate_model_config(config)

    def test_overwrite_guard_preserves_orphan_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'probabilities.npy'
            assert_new_outputs(output)
            contract = sidecar(output)
            contract.write_text('{"historical": true}', encoding='utf-8')
            with self.assertRaises(FileExistsError): assert_new_outputs(output)
            self.assertEqual(contract.read_text(encoding='utf-8'), '{"historical": true}')
            self.assertFalse(output.exists())

    def test_weighted_ce_invariant_to_batch_partition_cpu_forward_only(self):
        import torch
        from src.stage2 import weighted_validation_loss
        values = np.array([[2.,-1.],[1.,.2],[.4,.8],[-.3,2.],[.1,1.]], dtype=np.float32)
        targets = np.array([0,0,1,1,1])
        criterion = torch.nn.CrossEntropyLoss(weight=torch.tensor([.5,3.]))
        expected = float(criterion(torch.from_numpy(values), torch.from_numpy(targets)).item())
        for size in [1,2,3,5]:
            actual = weighted_validation_loss(torch.nn.Identity(), values, targets, np.arange(5), size, torch.device('cpu'), {'mixed_precision':False}, criterion)
            self.assertAlmostEqual(actual, expected, places=6)

    def test_autoencoder_dimensions_cpu_forward_only(self):
        import torch
        from src.autoencoder import build_autoencoder
        config = {'hidden_dims':[64,32], 'latent_dim':16}
        model = build_autoencoder(84, config)
        x = torch.randn(3,84)
        with torch.inference_mode():
            self.assertEqual(tuple(model.encode(x).shape), (3,16))
            self.assertEqual(tuple(model(x).shape), (3,84))


class ProtocolFixtures(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ids_alignment_test_')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'configs').mkdir()
        (self.root / 'data').mkdir()
        (self.root / 'metadata').mkdir()
        config = json.loads((ROOT / 'configs/model_config.json').read_text(encoding='utf-8'))
        config['experiment'].update(processed_dir='data', prepared_metadata_dir='metadata', models_dir='models', results_dir='results', metadata_dir='metadata')
        config['hardware'].update(device='cpu', require_cuda=False, mixed_precision=False)
        config['autoencoder'].update(hidden_dims=[4], latent_dim=2, epochs=2, batch_size=32, encode_batch_size=32)
        config['evaluation']['bootstrap_iterations'] = 2
        self.config_path = self.root / 'configs/model_config.json'
        self.config_path.write_text(json.dumps(config), encoding='utf-8')
        self.config = load_model_config(self.config_path)
        self.y = np.tile(np.array([0,1,2,3], dtype=np.int16), 200)
        self.s = np.repeat(np.array([0,1,2], dtype=np.int8), [480,160,160])
        self.x = np.random.default_rng(42).normal(size=(800,3)).astype(np.float32)
        # Heldout có distribution shift; scaler known-only phải loại khỏi mean.
        self.x[self.y == 3] += 100
        for name, data in {'features_raw':self.x, 'features_scaled':self.x, 'attack_label_ids':self.y,
                           'binary_labels':(self.y != 0).astype(np.int8), 'split_ids':self.s,
                           'row_hashes':np.arange(800,dtype=np.uint64)}.items():
            np.save(self.root / 'data' / (name+'.npy'), data)
        for name, data in {'feature_names':{'features':['a','b','c']}, 'label_mapping':{'0':'BENIGN','1':'a','2':'b','3':'c'}, 'split_config':{'seed':42}}.items():
            (self.root / 'metadata' / (name+'.json')).write_text(json.dumps(data), encoding='utf-8')

    def test_known_only_scaler_and_overwrite_guard(self):
        prepare_protocol(self.config, 'clean', 3)
        _, path, _ = require_preprocessing(self.config, 'clean', 3)
        scaler = load_scaler(path.parent / 'scaler.joblib')
        fit = np.flatnonzero((self.s == 0) & (self.y != 3))
        np.testing.assert_allclose(scaler.mean_, self.x[fit].astype(float).mean(0))
        self.assertEqual(scaler.n_samples_seen_, 360)
        with self.assertRaises(FileExistsError): prepare_protocol(self.config, 'clean', 3)
        with self.assertRaises(ValueError): require_preprocessing(self.config, 'clean', 2)

    def test_parent_tamper_rejected(self):
        prepare_protocol(self.config, 'clean', None)
        _, path, _ = require_preprocessing(self.config, 'clean', None)
        index_path = path.parent / 'fit_indices.npy'
        np.save(index_path, np.array([0,1]))
        with self.assertRaises(ValueError): read_contract(path, self.config, None)

    def test_sample_order_and_binary_corruption(self):
        np.save(self.root / 'data/binary_labels.npy', np.zeros(800, dtype=np.int8))
        with self.assertRaises(ValueError): load_prepared_arrays(self.root / 'data')

    def test_inner_scopes_are_disjoint_and_exclude_holdout(self):
        outer = np.flatnonzero((self.s == 0) & (self.y != 3))[:300]
        parts = inner_partitions(outer, self.y != 0, 42)
        np.testing.assert_array_equal(np.sort(np.concatenate(parts)), outer)
        self.assertEqual(len(np.unique(np.concatenate(parts))), len(outer))
        for a, b in [(0,1),(0,2),(1,2)]: self.assertEqual(len(np.intersect1d(parts[a], parts[b])), 0)

    def test_nested_stage1_orchestration_without_training(self):
        prepare_protocol(self.config, 'nested', 3)
        calls = []
        def fake_fit(kind, config, features, targets, fit, stop, groups, checkpoint, seed, device):
            self.assertFalse(np.any(self.y[fit] == 3))
            self.assertFalse(np.any(self.y[stop] == 3))
            self.assertFalse(np.any(self.s[fit] != 0))
            self.assertEqual(len(np.intersect1d(fit, stop)), 0)
            if 'holdout' in groups:
                for ids in groups.values():
                    self.assertEqual(len(np.intersect1d(ids, np.concatenate([fit, stop]))), 0)
                self.assertEqual(len(np.intersect1d(groups['holdout'], groups['calibration'])), 0)
            calls.append((fit.copy(), stop.copy(), groups))
            checkpoint.with_suffix('.json').write_text('{}', encoding='utf-8')
            return {name: np.clip(.5 + np.asarray(features[ids,0]) * .05, .1,.9).astype(np.float32) for name, ids in groups.items()}
        args = argparse.Namespace(config=str(self.config_path), run_id='nested', protocol='revised_v1', model='xgboost', representation='scaled', latent_path=None, held_out_label_id=3, check_only=False)
        with patch('src.stage1_protocol._fit_predict', side_effect=fake_fit) as fit_mock:
            run_stage1(args)
            fit_mock.reset_mock()
        self.assertEqual(len(calls), 6)
        output = self.root / 'data/experiments/nested/stage1_xgboost_scaled_p_attack_all.npy'
        p = np.load(output)
        self.assertTrue(np.isnan(p[(self.y == 3) & (self.s != 2)]).all())
        self.assertTrue(np.isfinite(p[self.s == 2]).all())
        read_contract(output, self.config, 3, kind='p_attack')

    def test_revised_pipeline_scripts_with_mock_models_and_real_contracts(self):
        """Integration wiring/metrics thật, model fit giả; tuyệt đối không là benchmark accuracy."""
        config = json.loads(self.config_path.read_text(encoding='utf-8'))
        config['novelty']['minimum_held_out_samples'] = 10  # Chỉ fixture, config project không đổi.
        self.config_path.write_text(json.dumps(config), encoding='utf-8')
        self.config = load_model_config(self.config_path)
        prepare_protocol(self.config, 'integration', 3)
        def run_script(name, flags):
            spec = importlib.util.spec_from_file_location('fixture_' + name, ROOT / 'scripts' / name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with patch.object(sys, 'argv', [name, '--config', str(self.config_path), *flags]):
                module.main()
        def fake_ae(features, fit, stop, config, hardware, device, checkpoint_path, random_state=42):
            self.assertFalse(np.any(self.y[fit] == 3))
            self.assertFalse(np.any(self.y[stop] == 3))
            self.assertTrue(np.all(self.s[fit] == 0))
            checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            checkpoint_path.write_text('mock, not a real model', encoding='utf-8')
            return object(), TrainingHistory(), 1, 1.0
        def fake_encode(model, features, output_path, latent_dim, *unused):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            np.save(output_path, np.asarray(features[:, :latent_dim]).copy())
        def fake_binary(kind, config, features, targets, fit, stop, groups, checkpoint, seed, device):
            if 'holdout' in groups:
                for part in [fit, stop, groups['calibration']]:
                    self.assertEqual(len(np.intersect1d(part, groups['holdout'])), 0)
            checkpoint.with_suffix('.json').write_text('mock', encoding='utf-8')
            return {name: np.clip(.5 + np.asarray(features[ids, 0]) * .05, .1, .9) for name, ids in groups.items()}
        common = ['--run-id','integration','--protocol','revised_v1','--held-out-label-id','3']
        with patch('src.autoencoder.train_autoencoder', side_effect=fake_ae) as ae_mock, patch('src.autoencoder.encode_to_memmap', side_effect=fake_encode) as encode_mock, patch('src.stage1_protocol._fit_predict', side_effect=fake_binary) as binary_mock:
            run_script('02_train_autoencoder.py', common)
            run_script('03_train_stage1.py', [*common, '--model','xgboost','--representation','latent'])
            ae_mock.reset_mock(); encode_mock.reset_mock(); binary_mock.reset_mock()
        class FakeClassifier:
            def predict_proba(self, x):
                p = np.clip(.5 + x[:,0] * .05, .1,.9)
                return np.column_stack([p, 1-p])
        def save_fake(model, path):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('mock', encoding='utf-8')
        with patch('src.stage2.fit_stage2_xgboost', return_value=FakeClassifier()) as fit_mock, patch('src.stage2.save_xgboost', side_effect=save_fake):
            run_script('04_train_stage2.py', [*common,'--experiment','latent_only'])
            fit_mock.reset_mock()
        s2 = self.root / 'results/stage2/integration/latent_only'
        p = self.root / 'data/experiments/integration/stage1_xgboost_latent_p_attack_all.npy'
        run_script('05_train_novelty.py', [*common, '--stage2-result-dir',str(s2),
                   '--ae-metadata', str(self.root/'metadata/autoencoder/integration/run.json'),
                   '--stage1-metadata',str(self.root/'metadata/stage1/integration/xgboost_latent.json'),
                   '--stage2-metadata',str(self.root/'metadata/stage2/integration/latent_only.json'),
                   '--methods','max_probability'])
        run_script('06_evaluate_pipeline.py', ['--run-id','evaluation', '--held-out-label-id','3',
                   '--p-attack-path',str(p),'--stage2-result-dir',str(s2), '--novelty-method','max_probability',
                   '--novelty-result-dir',str(self.root/'results/novelty/integration/heldout_3/latent_only'),
                   '--novelty-threshold-json',str(self.root/'artifacts/thresholds/integration/heldout_3/latent_only/max_probability.json')])
        report = json.loads((self.root/'results/pipeline/evaluation/metrics.json').read_text(encoding='utf-8'))
        self.assertIn('final_unknown_metrics', report)
        self.assertIn('score_only_unknown_metrics', report)
        self.assertEqual(report['test_samples'], 160)
        read_contract(self.root/'results/pipeline/evaluation', self.config, 3, kind='pipeline_evaluation')


class ExternalAdapters(unittest.TestCase):
    def test_invalid_drop_keeps_row_identity(self):
        b = adapt_frame(pd.DataFrame({'X':[1,np.inf,3]}), ['Benign','Attack','Attack'], 'CSE-CIC-IDS2018', 10)
        self.assertEqual(b['row_offsets'].tolist(), [10,12])
        self.assertEqual(b['binary_labels'].tolist(), [0,1])
        self.assertEqual(b['raw_labels'].tolist(), ['Benign','Attack'])

    def test_unsw_header_alignment_and_unknown_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pd.DataFrame({'X':[1,2,3]}).to_csv(root/'Data.csv', index=False)
            pd.DataFrame({'Label':[0,4,9]}).to_csv(root/'Lable.csv', index=False)
            batches = list(iter_external_batches('CIC-UNSW-NB15', root, rows_per_file=None, chunksize=2))
            self.assertEqual(sum(len(b['features']) for _, b in batches), 3)
            pd.DataFrame({'Label':[0,4]}).to_csv(root/'Lable.csv', index=False)
            with self.assertRaises(ValueError): list(iter_external_batches('CIC-UNSW-NB15', root, rows_per_file=None, chunksize=2))
        with self.assertRaises(ValueError): adapt_frame(pd.DataFrame({'X':[1]}), [10], 'CIC-UNSW-NB15')

    def test_shared_mapping_requires_approval_and_exact_order(self):
        batch = {'features':np.array([[1,2]]), 'feature_names':['b','a']}
        with self.assertRaises(ValueError): approved_shared_features(batch, ['a','b'], {'approved':False})
        result = approved_shared_features(batch, ['a','b'], {'approved':True, 'units_and_extractor_evidence':'synthetic fixture', 'canonical_to_native':{'a':'a','b':'b'}})
        self.assertEqual(result.tolist(), [[2,1]])


if __name__ == '__main__':
    unittest.main()
