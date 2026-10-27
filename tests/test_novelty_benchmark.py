from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from src.novelty_benchmark import fit_matched_novelty, METHODS
from src.mahalanobis import SharedMahalanobis
from src.study_reporting import summarize_rows


class MatchedNoveltyTests(unittest.TestCase):
    def test_all_thresholds_locked_before_test_and_reference_is_train_only(self):
        rng=np.random.default_rng(19)
        x=rng.normal(size=(140,4)).astype(np.float32)
        y=np.tile([1,2],70)
        train=np.arange(80); val=np.arange(80,100); test=np.arange(100,140)
        x[test]+=100; y[test]=9
        probabilities=np.tile([.8,.2],(20,1)); tq=np.tile([.55,.45],(40,1))
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); out=root/'scores'; models=root/'models'
            original=SharedMahalanobis.score
            calls=[]
            def check(model, values, *args, **kwargs):
                if np.min(values)>50:
                    lock=json.loads((out/'locked_validation_thresholds.json').read_text())
                    self.assertEqual(set(lock['thresholds']),set(METHODS))
                    self.assertFalse(lock['test_queried_at_lock']); calls.append('test')
                return original(model,values,*args,**kwargs)
            with patch.object(SharedMahalanobis,'score',check):
                results=fit_matched_novelty(x,y,train,val,test,probabilities,tq,.05,42,out,models,20,lambda s:None)
            self.assertEqual(calls,['test'])
            refs=np.load(models/'reference_indices.npy')
            self.assertTrue(np.isin(refs,train).all()); self.assertEqual(len(np.unique(refs)),20)
            self.assertEqual(set(y[refs]),{1,2})
            for result in results:
                self.assertEqual(result.threshold,float(np.quantile(result.validation_scores,.95)))
                self.assertEqual(len(result.test_scores),40)
            self.assertTrue((models/'mahalanobis.joblib').is_file())
            self.assertTrue((models/'knn_distance.joblib').is_file())

    def test_overlap_fails_before_fitting_or_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with self.assertRaises(ValueError):
                fit_matched_novelty(np.ones((12,2)),np.tile([1,2],6),np.arange(6),np.arange(5,9),
                                    np.arange(9,12),np.ones((4,2))*.5,np.ones((3,2))*.5,.05,42,
                                    root/'out',root/'models')
            self.assertFalse((root/'out').exists())

    def test_summary_keeps_seed_as_fit_not_independent_test(self):
        rows=[]
        for seed in [42,43,44]:
            for method,value in [('max_probability',.2),('mahalanobis',.1),('knn_distance',.8)]:
                rows.append({'heldout':9,'seed':seed,'gate':'recall','method':method,'support':100,
                             'recall':value,'precision':.9,'f1':value,'known_frr':.05,'benign_unknown':2,
                             'blocked_unknown':3,'e2e_macro_f1':.7})
        report=summarize_rows(rows)
        self.assertEqual(report['independent_test_datasets'],0)
        self.assertEqual(len(report['paired_knn_minus_baseline']),6)
        for entry in report['groups']:
            self.assertEqual(entry['test_support_per_fit'],[100]); self.assertEqual(entry['n_fits'],3)
        rows[-1]['blocked_unknown']=4
        with self.assertRaises(ValueError): summarize_rows(rows)

    def test_runner_config_preserves_baselines_and_freezes_methods(self):
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('confirm_runner',root/'scripts/16_run_confirmatory_study.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        template=json.loads((root/'configs/model_config_round2_20261027_fp32_s42.json').read_text())
        cfg=module.make_config(template,'new_h9_s43',43,Path('unused'),'storage_source')
        self.assertEqual(template['stage1']['xgboost'],cfg['stage1']['xgboost'])
        self.assertEqual(template['stage2']['xgboost'],cfg['stage2']['xgboost'])
        self.assertEqual(cfg['novelty']['matched_benchmark']['methods'],list(METHODS))
        self.assertEqual(cfg['experiment']['random_state'],43)
        self.assertTrue(cfg['evaluation']['save_compact_predictions'])


if __name__=='__main__':
    unittest.main()
