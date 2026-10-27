r"""Exact kNN novelty ablation, reusing frozen LOACO latent/Stage1/Stage2.

VS Code / PowerShell in D:\CAO HOC\IDS System:
 .\.venv\Scripts\python.exe -X utf8 -u -B scripts\15_run_knn_distance_study.py --study-id knn_v1 --check-only
 .\.venv\Scripts\python.exe -X utf8 -u -B scripts\15_run_knn_distance_study.py --study-id knn_v1 --run

Default: 3 heldouts x 2 normalizations x 2 train-reference policies x 3 k values.
Primary PREDECLARED variant: natural_l2_k50; others are ablations, NOT a sweep
that chooses a winner from test. Reference sizes are matched (max 50,000 rows).
Only known TRAIN attacks enter any index. Known VALIDATION fixes the 95th
percentile; TEST is queried only after ALL k thresholds of that index are locked.
No AE/XGBoost retraining, CUDA package changes, ANN approximation or overwrites.
Exact CPU cKDTree query can take time in 16 dimensions; batches/progress bound
RAM and show liveness. Historical test exposure/shared validation still apply.
"""
from __future__ import annotations
import argparse
import csv
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
from src.artifact_contracts import sha256, sidecar, write_contract
from src.knn_distance import LatentKNN, reference_indices
from src.model_config import experiment_id, load_model_config, project_path
from src.model_data import load_prepared_arrays
from src.novelty import threshold_from_known_validation
from src.training_utils import save_json


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_helper(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/filename)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--study-id', required=True)
    p.add_argument('--source-study', default='recall_gate_v1_20261027')
    p.add_argument('--held-out-labels', nargs='+', type=int, default=[9, 25, 26])
    p.add_argument('--ks', nargs='+', type=int, default=[1, 10, 50])
    p.add_argument('--reference-size', type=int, default=50000)
    p.add_argument('--reference-seed', type=int, default=42)
    p.add_argument('--batch-size', type=int, default=1024)
    p.add_argument('--workers', type=int, default=-1)
    p.add_argument('--gates', nargs='+', choices=['fixed', 'recall'], default=['recall'])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-only', action='store_true'); mode.add_argument('--run', action='store_true')
    a = p.parse_args()
    for name in [a.study_id, a.source_study]:
        experiment_id({'experiment': {'id': name}}, name)
    if (len(a.study_id) > 32 or len(set(a.held_out_labels)) != len(a.held_out_labels)
            or len(set(a.ks)) != len(a.ks) or any(k < 1 for k in a.ks) or 50 not in a.ks
            or a.reference_size < max(a.ks) or a.reference_seed < 0 or a.batch_size < 1
            or a.workers == 0 or a.workers < -1 or len(set(a.gates)) != len(a.gates) or 'recall' not in a.gates):
        raise ValueError('Distinct heldouts/k/gates, k50, recall gate, valid reference/batch/workers required')
    a.ks = sorted(a.ks)
    variants = [f'{policy}_{normal}_k{k}' for policy in ['natural', 'balanced']
                for normal in ['none', 'l2'] for k in a.ks]
    directory = ROOT/'results/knn_studies'/a.study_id
    if directory.exists():
        raise FileExistsError(f'No overwrite/resume: {directory}')
    source_status = read(ROOT/'results/recall_gate_studies'/a.source_study/'status.json')
    if source_status['status'] != 'completed' or any(x.get('returncode') != 0 for x in source_status['steps']):
        raise ValueError('Source LOACO study is not complete')
    for held in a.held_out_labels:
        for variant in ['mcp', *variants]:
            for tag in a.gates:
                name = f'{a.study_id}_h{held}_{variant}_{tag}'
                experiment_id({'experiment': {'id': name}}, name)
                if (ROOT/'results/pipeline'/name).exists():
                    raise FileExistsError(f'Evaluation ID already exists: {name}')
    # Shared preflight only: importing this helper never fits Mahalanobis.
    helper = load_helper('knn_upstream_check', '14_run_mahalanobis_comparison.py')
    inputs = []
    for held in a.held_out_labels:
        print(f'CHECK lineage heldout {held}; no fitting', flush=True)
        x = helper.verify_upstream(a.source_study, held)
        if min(a.reference_size, x['train_count']) < max(a.ks):
            raise ValueError('Reference database is smaller than requested k')
        inputs.append(x)
    sources = {str(f): sha256(f) for folder in ['src', 'scripts'] for f in (ROOT/folder).glob('*.py')}
    input_hashes = {x[k]: sha256(x[k]) for x in inputs for k in ['config_path', 'gate', 'mcp_threshold']}
    plan = {'study_id': a.study_id, 'source_study': a.source_study, 'reuse': inputs,
            'primary_variant': 'natural_l2_k50', 'variants': variants, 'gates': a.gates,
            'reference_size_maximum': a.reference_size, 'reference_seed': a.reference_seed,
            'reference_policies': ['natural without replacement', 'balanced capped quotas, redistribute deficits; no oversampling'],
            'normalization': ['none', 'per-row L2 with epsilon 1e-10'],
            'score': 'squared Euclidean distance to kth nearest known TRAIN attack; higher=novel',
            'index': 'exact scipy.spatial.cKDTree, eps=0, CPU float64',
            'ks': a.ks, 'batch_size': a.batch_size, 'workers': a.workers,
            'threshold': '95th percentile known validation attack scores, >= rejection; report ties',
            'selection': 'NONE; predeclared primary and all ablations reported, never choose by test',
            'upstream_retrained': False, 'source_hashes': sources, 'input_hashes': input_hashes,
            'paper': 'https://proceedings.mlr.press/v162/sun22d.html',
            'limitations': ['adaptation on AE latent, not reproduction of image-model results',
                            'historical tests already seen; exploratory; one seed/fixed split',
                            'shared known validation already used for stopping upstream',
                            'natural/ balanced reference use same capped size, not full training set',
                            'no feature-vector deduplication; split overlap remains',
                            'L2 may remove magnitude information; no assumed winner']}
    print(json.dumps({k:v for k,v in plan.items() if not k.endswith('hashes')}, ensure_ascii=False, indent=2), flush=True)
    if a.check_only:
        print('CHECK-ONLY OK: no database fitted, no output written', flush=True); return
    if shutil.disk_usage(ROOT).free < 1024**3:
        raise RuntimeError('Require >=1 GiB free for study/evaluation artifacts')
    locking = load_helper('knn_shared_lock', '13_run_recall_gate_study.py')
    state = {'status': 'running', 'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat(), 'steps': []}

    def event(text):
        print(text, flush=True)
        with (directory/'events.log').open('a', encoding='utf-8') as stream:
            stream.write(datetime.now(timezone.utc).isoformat()+' '+text+'\n')

    def frozen():
        for path, expected in {**sources, **input_hashes}.items():
            if sha256(path) != expected:
                raise RuntimeError(f'Source/input changed during study: {path}')

    def evaluate(x, variant, tag, novelty_dir, threshold_file):
        frozen()
        name = f'{a.study_id}_h{x["held"]}_{variant}_{tag}'
        log = directory/'logs'/f'{name}.log'
        command = [sys.executable, '-X', 'utf8', '-u', '-B', 'scripts/06_evaluate_pipeline.py',
                   '--config', x['config_path'], '--run-id', name, '--held-out-label-id', str(x['held']),
                   '--p-attack-path', x['p_attack'], '--stage2-result-dir', x['stage2'],
                   '--novelty-result-dir', str(novelty_dir), '--novelty-threshold-json', str(threshold_file),
                   '--novelty-method', 'max_probability' if variant == 'mcp' else 'knn_distance']
        if tag == 'recall':
            command += ['--stage1-threshold-json', x['gate']]
        item = {'name': name, 'command': command, 'log': str(log), 'status': 'running'}
        state['steps'].append(item); state['current_step'] = name
        save_json(directory/'status.json', state); event('EVALUATE '+name)
        started = time.perf_counter()
        with log.open('x', encoding='utf-8') as stream:
            child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            item['child_pid'] = child.pid; save_json(directory/'status.json', state)
            try:
                while True:
                    try:
                        code = child.wait(timeout=60); break
                    except subprocess.TimeoutExpired:
                        event(f'RUNNING {name}: {time.perf_counter()-started:.0f}s')
            except BaseException:
                child.terminate(); child.wait(); item['status'] = 'interrupted'; raise
        item.update(returncode=code, status='completed' if code == 0 else 'failed', seconds=time.perf_counter()-started)
        save_json(directory/'status.json', state)
        if code:
            raise RuntimeError(f'Evaluation failed: {log}')
        return read(ROOT/'results/pipeline'/name/'metrics.json')

    with locking.gpu_lock():
        if directory.exists():
            raise FileExistsError('Study created by another process')
        directory.mkdir(parents=True); (directory/'logs').mkdir()
        save_json(directory/'protocol_lock.json', plan); save_json(directory/'status.json', state)
        comparisons = {}; rows = []
        try:
            for x in inputs:
                frozen()
                config = load_model_config(x['config_path'])
                processed = project_path(config, config['experiment']['processed_dir'])
                arrays = load_prepared_arrays(processed, Path(x['latent']))
                held = x['held']; held_dir = directory/f'heldout_{held}'; held_dir.mkdir()
                comparisons[str(held)] = {tag: {'knn': {}} for tag in a.gates}
                try:
                    labels, splits = arrays.attack_label_ids, arrays.split_ids
                    train = np.flatnonzero((splits == 0) & (labels != 0) & (labels != held))
                    val = np.flatnonzero((splits == 1) & (labels != 0) & (labels != held))
                    test = np.flatnonzero(splits == 2)
                    np.save(held_dir/'known_train_indices.npy', train)
                    np.save(held_dir/'validation_indices.npy', val)
                    for tag in a.gates:
                        baseline = evaluate(x, 'mcp', tag, x['mcp'], x['mcp_threshold'])
                        old = read(ROOT/'results/pipeline'/(x['run']+'_'+tag)/'metrics.json')
                        if baseline['final_unknown_metrics'] != old['final_unknown_metrics']:
                            raise ValueError('MCP replay differs from historical source')
                        comparisons[str(held)][tag]['mcp'] = baseline
                        mcp_scores = np.load(Path(x['mcp'])/'max_probability_test_scores.npy', mmap_mode='r')
                        mcp_threshold = read(x['mcp_threshold'])['threshold']
                        pgate = .5 if tag == 'fixed' else read(x['gate'])['threshold']
                        admitted = np.load(x['p_attack'], mmap_mode='r')[test] >= pgate
                        rejected = (mcp_scores >= mcp_threshold) & admitted
                        baseline_classes = {str(int(c)): {'support': int(np.sum(labels[test]==c)),
                                            'false_rejection_rate': float(rejected[labels[test]==c].mean())}
                                            for c in np.unique(labels[train]) if np.any(labels[test]==c)}
                        save_json(held_dir/f'mcp_known_class_rejection_{tag}.json', baseline_classes)
                    for policy in ['natural', 'balanced']:
                        refs = reference_indices(labels, train, a.reference_size, policy, a.reference_seed)
                        if not np.isin(refs, train).all() or np.intersect1d(refs, np.r_[val,test]).size:
                            raise ValueError('Reference database contains non-train rows')
                        reference_path = held_dir/f'{policy}_reference_indices.npy'; np.save(reference_path, refs)
                        counts = {str(int(c)): int(np.sum(labels[refs] == c)) for c in np.unique(labels[train])}
                        for normal in ['none', 'l2']:
                            frozen(); geometry = held_dir/f'{policy}_{normal}'; geometry.mkdir()
                            state['current_step'] = f'heldout_{held}_{policy}_{normal}_index'
                            save_json(directory/'status.json', state)
                            event(f'INDEX heldout={held} policy={policy} normalization={normal} reference={len(refs)}')
                            start = time.perf_counter()
                            model = LatentKNN.fit(arrays.features[refs], normal)
                            model_path = geometry/'knn_index.joblib'; joblib.dump(model, model_path)
                            last = [time.monotonic()]

                            def progress(done, total):
                                if done == total or time.monotonic()-last[0] >= 30:
                                    event(f'QUERY {state["current_step"]}: {done}/{total}')
                                    last[0] = time.monotonic()

                            state['current_step'] = f'heldout_{held}_{policy}_{normal}_validation_query'
                            save_json(directory/'status.json', state)
                            validation = model.score_many(arrays.features[val], a.ks, a.batch_size, a.workers, progress)
                            thresholds = {k: threshold_from_known_validation(validation[k], .05) for k in a.ks}
                            save_json(geometry/'locked_validation_thresholds.json', {str(k):v for k,v in thresholds.items()})
                            loaded = joblib.load(model_path)
                            replay = loaded.score_many(arrays.features[val[:16]], a.ks, 16, 1)
                            if any(not np.allclose(replay[k], validation[k][:16], rtol=1e-12, atol=1e-12) for k in a.ks):
                                raise ValueError('Serialized index does not reproduce scores')
                            del loaded
                            # No test query occurs before every declared k threshold of this index is locked.
                            state['current_step'] = f'heldout_{held}_{policy}_{normal}_test_query'
                            save_json(directory/'status.json', state)
                            scores = model.score_many(arrays.features[test], a.ks, a.batch_size, a.workers, progress)
                            parameters = {'source_run': x['run'], 'held_out': held, 'upstream_retrained': False,
                                          'policy': policy, 'normalization': normal, 'reference_size': len(refs),
                                          'reference_seed': a.reference_seed, 'reference_class_counts': counts,
                                          'known_classes_missing_from_reference': [c for c,n in counts.items() if n == 0],
                                          'zero_reference_vectors': int(np.sum(np.linalg.norm(np.asarray(arrays.features[refs], dtype=np.float64),axis=1)==0)),
                                          'index_and_query_seconds': time.perf_counter()-start,
                                          'test_used_for_fit_or_threshold': False}
                            save_json(geometry/'parameters.json', parameters)
                            for k in a.ks:
                                variant = f'{policy}_{normal}_k{k}'
                                output = geometry/f'k{k}'; output.mkdir(); novelty_dir = output/'novelty'; novelty_dir.mkdir()
                                threshold = thresholds[k]; threshold_path = output/'threshold.json'
                                actual = float(np.mean(validation[k] >= threshold))
                                save_json(threshold_path, {'method': 'knn_distance', 'variant': variant, 'k': k,
                                          'threshold': threshold, 'run_id': x['run'], 'held_out_label_id': held,
                                          'selected_on': 'known_validation_only', 'known_rejection_rate_target': .05,
                                          'validation_rejection_actual': actual, 'test_used_for_selection': False})
                                if abs(actual-.05) > .002:
                                    event(f'WARNING {variant} validation rejection={actual:.6f}; quantile ties, not corrected using test')
                                np.save(novelty_dir/'knn_distance_validation_scores.npy', validation[k])
                                np.save(novelty_dir/'knn_distance_test_scores.npy', scores[k])
                                np.save(novelty_dir/'test_indices.npy', test)
                                write_contract(novelty_dir, config, x['run'], held, 'novelty',
                                               parents=[Path(x['latent']), sidecar(Path(x['latent'])), sidecar(Path(x['stage2'])),
                                                        Path(x['p_attack']), sidecar(Path(x['p_attack'])), model_path,
                                                        reference_path, held_dir/'known_train_indices.npy', held_dir/'validation_indices.npy',
                                                        geometry/'parameters.json', threshold_path],
                                               extra={**parameters, 'variant': variant, 'k': k, 'study_id': a.study_id})
                                for tag in a.gates:
                                    report = evaluate(x, variant, tag, novelty_dir, threshold_path)
                                    base = comparisons[str(held)][tag]['mcp']
                                    if (report['stage1_test_metrics'] != base['stage1_test_metrics']
                                            or report['stage1_threshold'] != base['stage1_threshold']):
                                        raise ValueError('Gate/upstream mismatch')
                                    comparisons[str(held)][tag]['knn'][variant] = report
                                    pgate = .5 if tag == 'fixed' else read(x['gate'])['threshold']
                                    p_attack = np.load(x['p_attack'], mmap_mode='r')[test]
                                    rejected = (scores[k] >= threshold) & (p_attack >= pgate)
                                    per_class = {str(int(c)): {'support': int(np.sum(labels[test]==c)),
                                                 'false_rejection_rate': float(rejected[labels[test]==c].mean())}
                                                 for c in np.unique(labels[train]) if np.any(labels[test]==c)}
                                    save_json(output/f'known_class_rejection_{tag}.json', per_class)
                                    u = report['final_unknown_metrics']
                                    rows.append({'heldout': held, 'gate': tag, 'variant': variant,
                                                 'primary': variant == 'natural_l2_k50',
                                                 'detected': u['unknown_detected'], 'support': u['unknown_support'],
                                                 'precision': u['precision'], 'recall': u['recall'], 'f1': u['f1'],
                                                 'known_frr': u['known_attack_false_rejection_rate'],
                                                 'benign_unknown': u['benign_rejected_unknown'],
                                                 'blocked_unknown': u['unknown_blocked_by_stage1'],
                                                 'e2e_macro_f1': report['end_to_end_metrics']['macro_f1'],
                                                 'validation_rejection_actual': actual})
                                    save_json(directory/'comparison.json', comparisons)
                            del model
                finally:
                    arrays.close()
            with (directory/'summary.csv').open('x', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
            lines = ['# kNN novelty — all predeclared ablations, no test-based selection', '',
                     'Primary: natural_l2_k50, recall gate. MCP baseline and full metrics: comparison.json.', '',
                     '| Heldout | Gate | Variant | Detected/support | Precision | Recall | F1 | Known FRR | Benign unknown | E2E macro-F1 |',
                     '|---|---|---|---|---|---|---|---|---|---|']
            for r in rows:
                lines.append(f"| {r['heldout']} | {r['gate']} | {r['variant']} | {r['detected']}/{r['support']} | {r['precision']:.6f} | {r['recall']:.6f} | {r['f1']:.6f} | {r['known_frr']:.6f} | {r['benign_unknown']} | {r['e2e_macro_f1']:.6f} |")
            lines += ['', 'Do not choose per-heldout winner from these historical tests. Class-wise rejection reports accompany every variant.']
            (directory/'COMPARISON.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
            state['status'] = 'completed'
        except BaseException as error:
            state.update(status='failed', error=repr(error)); raise
        finally:
            state['ended_utc'] = datetime.now(timezone.utc).isoformat(); save_json(directory/'status.json', state)


if __name__ == '__main__':
    main()
