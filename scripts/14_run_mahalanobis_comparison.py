r"""Fit ONLY Mahalanobis; reuse verified LOACO AE/Stage1/Stage2 artifacts.

VS Code / PowerShell from project root:
 .\.venv\Scripts\python.exe -X utf8 -u -B scripts\14_run_mahalanobis_comparison.py --study-id mahalanobis_v1 --check-only
 .\.venv\Scripts\python.exe -X utf8 -u -B scripts\14_run_mahalanobis_comparison.py --study-id mahalanobis_v1 --run

No AE/XGBoost retraining, no dataset copying, no package installation. Fit all
known TRAIN attacks, tune only the fixed 95th percentile on known VALIDATION.
The three held-out TEST sets are evaluation only, never method selection.
CPU FP64/BLAS is used for this small 16-D covariance model; batch scoring bounds
RAM. This is a transparent Mahalanobis baseline, not a reproduction of OIDMD.
The existing shared validation reuse and historical test exposure remain limits.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.artifact_contracts import read_contract, require_link, sha256, sidecar, write_contract
from src.contracts import exact_indices, probability_matrix, probability_vector
from src.gate_policy import select_gate
from src.mahalanobis import SharedMahalanobis
from src.model_config import experiment_id, load_model_config, project_path
from src.model_data import load_prepared_arrays
from src.novelty import threshold_from_known_validation
from src.research_protocol import require_preprocessing
from src.training_utils import save_json


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def verify_upstream(source, held):
    run = f'{source}_h{held}_s42'
    config_path = ROOT/'configs'/f'{run}.json'
    config = load_model_config(config_path)
    if config['experiment']['id'] != run:
        raise ValueError('Source run ID mismatch')
    if config['evaluation']['decision_threshold'] != .5:
        raise ValueError('Fixed-gate reference must remain 0.5')
    processed = project_path(config, config['experiment']['processed_dir'])
    latent = processed/'experiments'/run/'latent_features.npy'
    pp = processed/'experiments'/run/'stage1_xgboost_latent_p_attack_all.npy'
    s2 = ROOT/'results/stage2'/run/'latent_only'
    gate = ROOT/'results/recall_gate_studies'/source/f'gate_h{held}.json'
    mcp = ROOT/'results/novelty'/run/f'heldout_{held}'/'latent_only'
    mcp_threshold = ROOT/'artifacts/thresholds'/run/f'heldout_{held}'/'latent_only/max_probability.json'
    metadata = [ROOT/'artifacts/metadata'/phase/run/name for phase, name in
                [('autoencoder', 'run.json'), ('stage1', 'xgboost_latent.json'), ('stage2', 'latent_only.json')]]
    for path in metadata:
        m = read(path)
        if m.get('status') != 'completed' or m.get('run_id') != run or m.get('held_out_label_id') != held:
            raise ValueError(f'Incomplete/mismatched upstream metadata: {path}')
    prepared, scaled, _ = require_preprocessing(config, run, held)
    prepared.close()
    latent_record = read_contract(latent, config, held, kind='latent', run_id=run)
    require_link(latent_record, scaled); require_link(latent_record, metadata[0])
    p_record = read_contract(pp, config, held, kind='p_attack', run_id=run)
    require_link(p_record, metadata[1]); require_link(p_record, latent)
    s2_record = read_contract(s2, config, held, kind='stage2', run_id=run)
    require_link(s2_record, latent); require_link(s2_record, metadata[2])
    if s2_record['extra']['experiment'] != 'latent_only' or s2_record['extra']['uses_p_attack']:
        raise ValueError('Comparison requires the frozen latent_only Stage2')
    baseline = read_contract(mcp, config, held, kind='novelty', run_id=run)
    require_link(baseline, sidecar(s2)); require_link(baseline, pp); require_link(baseline, mcp_threshold)
    arrays = load_prepared_arrays(processed, latent)
    try:
        labels, splits = arrays.attack_label_ids, arrays.split_ids
        train = np.flatnonzero((splits == 0) & (labels != 0) & (labels != held))
        val = np.flatnonzero((splits == 1) & (labels != 0) & (labels != held))
        test = np.flatnonzero(splits == 2)
        classes = np.load(s2/'class_ids.npy', allow_pickle=False)
        if arrays.features.shape[1] != 16 or not np.array_equal(classes, np.unique(labels[train])):
            raise ValueError('Latent/class IDs differ from the frozen pipeline')
        exact_indices(np.load(s2/'validation_indices.npy'), val, 'known validation')
        exact_indices(np.load(s2/'test_indices.npy'), test, 'Stage2 test')
        exact_indices(np.load(mcp/'test_indices.npy'), test, 'MCP test')
        probability_matrix(np.load(s2/'validation_probabilities.npy', mmap_mode='r'), classes, len(val), held)
        probability_matrix(np.load(s2/'test_probabilities.npy', mmap_mode='r'), classes, len(test), held)
        scores = np.load(pp, mmap_mode='r')
        known_val = np.flatnonzero((splits == 1) & (labels != held))
        probability_vector(scores[test], length=len(test))
        gate_record = read(gate)
        chosen = select_gate(scores[known_val], arrays.binary_labels[known_val], gate_record['benign_fpr_budget'])
        if (gate_record['run_id'] != run or gate_record['held_out_label_id'] != held
                or gate_record['p_attack_sha256'] != sha256(pp)
                or gate_record['selected_on'] != 'known_validation_only'
                or gate_record['test_used_for_selection'] is not False
                or gate_record['threshold'] != chosen['threshold']):
            raise ValueError('Gate provenance/replay mismatch')
        support = int(np.sum(labels[test] == held))
        if support < 500:
            raise ValueError('Heldout test support below 500')
        if config['novelty']['known_rejection_rate'] != .05:
            raise ValueError('Reference known rejection budget must be 5%')
        threshold_record = read(mcp_threshold)
        if (threshold_record['method'] != 'max_probability' or threshold_record['run_id'] != run
                or threshold_record['held_out_label_id'] != held
                or threshold_record['known_rejection_rate_target'] != .05):
            raise ValueError('MCP threshold differs from matched baseline')
        return {'run': run, 'held': held, 'config_path': str(config_path), 'latent': str(latent),
                'p_attack': str(pp), 'stage2': str(s2), 'gate': str(gate),
                'mcp': str(mcp), 'mcp_threshold': str(mcp_threshold), 'train_count': len(train),
                'validation_count': len(val), 'test_count': len(test), 'unknown_support': support}
    finally:
        arrays.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--study-id', required=True)
    p.add_argument('--source-study', default='recall_gate_v1_20261027')
    p.add_argument('--held-out-labels', nargs='+', type=int, default=[9, 25, 26])
    p.add_argument('--batch-size', type=int, default=8192)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-only', action='store_true'); mode.add_argument('--run', action='store_true')
    a = p.parse_args()
    for name in [a.study_id, a.source_study]:
        experiment_id({'experiment': {'id': name}}, name)
    if len(set(a.held_out_labels)) != len(a.held_out_labels) or a.batch_size < 1:
        raise ValueError('Distinct heldouts and positive batch size required')
    directory = ROOT/'results/mahalanobis_studies'/a.study_id
    if directory.exists():
        raise FileExistsError(f'No overwrite/resume: {directory}')
    state_source = read(ROOT/'results/recall_gate_studies'/a.source_study/'status.json')
    if state_source['status'] != 'completed' or any(x.get('returncode') != 0 for x in state_source['steps']):
        raise ValueError('Source study must have completed all steps successfully')
    for held in a.held_out_labels:
        for method in ['mcp', 'maha']:
            for gate_tag in ['fixed', 'recall']:
                name = f'{a.study_id}_h{held}_{method}_{gate_tag}'
                experiment_id({'experiment': {'id': name}}, name)
                if (ROOT/'results/pipeline'/name).exists():
                    raise FileExistsError(f'Evaluation ID exists: {name}')
    sources = {str(f): sha256(f) for area in ['src', 'scripts'] for f in (ROOT/area).glob('*.py')}
    inputs = []
    for held in a.held_out_labels:
        print(f'CHECK lineage heldout {held}; hashing can take time, no fitting', flush=True)
        inputs.append(verify_upstream(a.source_study, held))
    parents = {str(path): sha256(path) for x in inputs for path in
               [Path(x[k]) for k in ['config_path', 'gate', 'mcp_threshold']]}
    plan = {'study_id': a.study_id, 'source_study': a.source_study, 'reuse': inputs,
            'fit': 'known TRAIN attack class means + shared pooled LedoitWolf covariance',
            'score': 'minimum squared Mahalanobis over ALL known attack classes',
            'threshold': '95th percentile known VALIDATION attack scores; no test selection',
            'device': 'CPU FP64/BLAS', 'batch_size': a.batch_size, 'upstream_retraining': False,
            'source_hashes': sources, 'input_hashes': parents,
            'limitations': ['exploratory historical test already inspected', 'one seed and fixed split',
                            'validation also used upstream for stopping; no fresh calibration split',
                            'adapted Mahalanobis baseline, not exact OIDMD replication',
                            'pooled covariance dominated by frequent classes; rare means uncertain']}
    print(json.dumps({k: v for k, v in plan.items() if not k.endswith('hashes')}, ensure_ascii=False, indent=2), flush=True)
    if a.check_only:
        print('CHECK-ONLY OK: no fit, no outputs written', flush=True); return
    if shutil.disk_usage(ROOT).free < 512*1024**2:
        raise RuntimeError('Require at least 512 MiB free for scores/reports')
    spec = importlib.util.spec_from_file_location('recall_study_lock', ROOT/'scripts/13_run_recall_gate_study.py')
    lock_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(lock_module)
    state = {'status': 'running', 'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat(), 'steps': []}

    def verify_frozen():
        for path, expected in {**sources, **parents}.items():
            if sha256(path) != expected:
                raise RuntimeError(f'Source/input changed during study: {path}')

    def evaluate(x, method, tag, novelty_dir, threshold_path):
        verify_frozen()
        evaluation_id = f'{a.study_id}_h{x["held"]}_{method}_{tag}'
        log = directory/'logs'/f'{evaluation_id}.log'
        command = [sys.executable, '-X', 'utf8', '-u', '-B', 'scripts/06_evaluate_pipeline.py',
                   '--config', x['config_path'], '--run-id', evaluation_id,
                   '--p-attack-path', x['p_attack'], '--stage2-result-dir', x['stage2'],
                   '--held-out-label-id', str(x['held']), '--novelty-result-dir', str(novelty_dir),
                   '--novelty-method', 'max_probability' if method == 'mcp' else 'mahalanobis',
                   '--novelty-threshold-json', str(threshold_path)]
        if tag == 'recall':
            command += ['--stage1-threshold-json', x['gate']]
        item = {'name': evaluation_id, 'command': command, 'log': str(log), 'status': 'running'}
        state['steps'].append(item); state['current_step'] = evaluation_id
        save_json(directory/'status.json', state)
        with log.open('x', encoding='utf-8') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        item.update(returncode=result.returncode, status='completed' if result.returncode == 0 else 'failed')
        save_json(directory/'status.json', state)
        if result.returncode:
            raise RuntimeError(f'Evaluation failed: {log}')
        return read(ROOT/'results/pipeline'/evaluation_id/'metrics.json')

    with lock_module.gpu_lock():
        directory.mkdir(parents=True); (directory/'logs').mkdir()
        save_json(directory/'protocol_lock.json', plan); save_json(directory/'status.json', state)
        comparisons = {}
        try:
            for x in inputs:
                verify_frozen()
                config = load_model_config(x['config_path'])
                processed = project_path(config, config['experiment']['processed_dir'])
                arrays = load_prepared_arrays(processed, Path(x['latent']))
                held = x['held']; destination = directory/f'heldout_{held}'
                destination.mkdir()
                novelty_dir = destination/'novelty'; novelty_dir.mkdir()
                try:
                    labels, splits = arrays.attack_label_ids, arrays.split_ids
                    train = np.flatnonzero((splits == 0) & (labels != 0) & (labels != held))
                    val = np.flatnonzero((splits == 1) & (labels != 0) & (labels != held))
                    test = np.flatnonzero(splits == 2)
                    state['current_step'] = f'heldout_{held}_fit_known_train'
                    save_json(directory/'status.json', state)
                    print(f'FIT Mahalanobis heldout={held}, train={len(train)}, CPU FP64', flush=True)
                    started = time.perf_counter()
                    model = SharedMahalanobis.fit(arrays.features[train], labels[train])
                    validation_scores = model.score(arrays.features[val], a.batch_size)
                    threshold = threshold_from_known_validation(validation_scores, .05)
                    # Only after parameters and threshold are fixed, score test.
                    test_scores = model.score(arrays.features[test], a.batch_size)
                    model_path = destination/'mahalanobis.joblib'; joblib.dump(model, model_path)
                    reloaded = joblib.load(model_path)
                    if not np.allclose(reloaded.score(arrays.features[val[:32]], a.batch_size),
                                       validation_scores[:32], rtol=1e-12, atol=1e-12):
                        raise ValueError('Saved Mahalanobis model does not reproduce scores')
                    threshold_path = destination/'mahalanobis_threshold.json'
                    save_json(threshold_path, {'method': 'mahalanobis', 'threshold': threshold,
                              'run_id': x['run'], 'study_id': a.study_id, 'held_out_label_id': held,
                              'known_rejection_rate_target': .05, 'selected_on': 'known_validation_only'})
                    np.save(novelty_dir/'mahalanobis_validation_scores.npy', validation_scores)
                    np.save(novelty_dir/'mahalanobis_test_scores.npy', test_scores)
                    np.save(novelty_dir/'test_indices.npy', test)
                    np.save(destination/'fit_indices.npy', train)
                    np.save(destination/'validation_indices.npy', val)
                    fit_record = {'source_run': x['run'], 'upstream_retrained': False,
                                  'fit_samples': len(train), 'known_class_ids': model.class_ids.tolist(),
                                  'class_counts': model.counts.tolist(), 'shrinkage': model.shrinkage,
                                  'validation_rejection_actual': float(np.mean(validation_scores >= threshold)),
                                  'fit_and_score_seconds': time.perf_counter()-started,
                                  'test_used_for_fit_or_threshold': False}
                    save_json(destination/'fit.json', fit_record)
                    write_contract(novelty_dir, config, x['run'], held, 'novelty',
                                   parents=[Path(x['latent']), sidecar(Path(x['latent'])), sidecar(Path(x['stage2'])),
                                            Path(x['p_attack']), sidecar(Path(x['p_attack'])), threshold_path,
                                            model_path, destination/'fit_indices.npy', destination/'validation_indices.npy',
                                            destination/'fit.json'], extra=fit_record)
                finally:
                    arrays.close()
                comparisons[str(held)] = {}
                for tag in ['fixed', 'recall']:
                    base = evaluate(x, 'mcp', tag, x['mcp'], x['mcp_threshold'])
                    historical = read(ROOT/'results/pipeline'/(x['run']+'_'+tag)/'metrics.json')
                    if base['final_unknown_metrics'] != historical['final_unknown_metrics']:
                        raise ValueError('MCP replay differs from source evaluation; do not claim a matched comparison')
                    maha = evaluate(x, 'maha', tag, novelty_dir, threshold_path)
                    # Identical admission mask; differences must come from novelty only.
                    if (base['stage1_threshold'] != maha['stage1_threshold']
                            or base['stage1_test_metrics'] != maha['stage1_test_metrics']
                            or base['final_unknown_metrics']['unknown_support'] != maha['final_unknown_metrics']['unknown_support']):
                        raise ValueError('Unmatched gate/population in comparison')
                    comparisons[str(held)][tag] = {'mcp': base, 'mahalanobis': maha}
                save_json(directory/'comparison.json', comparisons)
            lines = ['# Mahalanobis vs MCP — matched frozen upstream', '',
                     'Primary comparison: recall gate; fixed gate is a secondary ablation.', '',
                     '| Heldout | Gate | Method | Detected/support | Precision | Recall | F1 | Known FRR | Benign unknown | Gate-blocked unknown |',
                     '|---|---|---|---|---|---|---|---|---|---|']
            for held, gates in comparisons.items():
                for tag, methods in gates.items():
                    for method, report in methods.items():
                        u = report['final_unknown_metrics']
                        lines.append(f"| {held} | {tag} | {method} | {u['unknown_detected']}/{u['unknown_support']} | {u['precision']:.6f} | {u['recall']:.6f} | {u['f1']:.6f} | {u['known_attack_false_rejection_rate']:.6f} | {u['benign_rejected_unknown']} | {u['unknown_blocked_by_stage1']} |")
            lines += ['', 'No superiority/significance claim: one seed, previously inspected test, shared validation.']
            (directory/'COMPARISON.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
            state['status'] = 'completed'
        except BaseException as error:
            state.update(status='failed', error=repr(error)); raise
        finally:
            state['ended_utc'] = datetime.now(timezone.utc).isoformat(); save_json(directory/'status.json', state)


if __name__ == '__main__':
    main()
