r"""Fresh CUDA LOACO runs with validation-selected recall gate.
VS Code: python -X utf8 -u -B scripts/13_run_recall_gate_study.py --study-id recall_gate_v1 --plan
Replace --plan with --run only after disk preflight passes. No overwrite/resume.
For another PREPARED dataset supply --config, --processed-dir and its label IDs.
This is not a raw CSV adapter: schema, units, labels and split must be audited first.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.artifact_contracts import sha256
from src.model_config import experiment_id, load_model_config
from src.training_utils import save_json


@contextmanager
def gpu_lock():
    import msvcrt
    path = ROOT / 'artifacts/external_training.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if path.stat().st_size == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--study-id', required=True)
    p.add_argument('--config', default=str(ROOT / 'configs/model_config_round2_20261027_fp32_s42.json'))
    p.add_argument('--processed-dir', default=str(ROOT / 'data/processed/round2_20261027_fp32_s42'))
    p.add_argument('--held-out-labels', nargs='+', type=int, default=[9, 25, 26])
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--fpr-budget', type=float, default=0.001)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true'); mode.add_argument('--run', action='store_true')
    a = p.parse_args()
    experiment_id({'experiment': {'id': a.study_id}}, a.study_id)
    if len(a.study_id) > 32 or len(set(a.held_out_labels)) != len(a.held_out_labels):
        raise ValueError('Short unique study ID and distinct held-out labels required')
    if not 0 <= a.fpr_budget < 1 or a.seed < 0:
        raise ValueError('Invalid seed/FPR budget')
    processed = Path(a.processed_dir).resolve()
    config = load_model_config(a.config)
    config = {k: v for k, v in config.items() if not k.startswith('_')}
    labels = np.load(processed / 'attack_label_ids.npy', mmap_mode='r')
    splits = np.load(processed / 'split_ids.npy', mmap_mode='r')
    mapping = json.loads((processed / 'metadata/label_mapping.json').read_text(encoding='utf-8'))
    support = []
    for held in a.held_out_labels:
        n = int(np.sum((labels == held) & (splits == 2)))
        if held == 0 or n < 500:
            raise ValueError(f'Heldout {held}: test support {n}, require >=500 attack rows')
        support.append({'id': held, 'name': mapping[str(held)], 'test_support': n})
    directory = ROOT / 'results/recall_gate_studies' / a.study_id
    trials = [(held, f'{a.study_id}_h{held}_s{a.seed}') for held in a.held_out_labels]
    targets = [directory]
    for _, run in trials:
        targets += [ROOT / 'configs' / f'{run}.json', processed / 'experiments' / run]
        for base in ['models', 'results', 'artifacts/metadata']:
            targets += [ROOT / base / phase / run for phase in ['autoencoder', 'stage1', 'stage2', 'novelty']]
        targets += [ROOT / 'results/pipeline' / (run + suffix) for suffix in ['_fixed', '_recall']]
        targets.append(ROOT / 'artifacts/thresholds' / run)
    for target in targets:
        if target.exists():
            raise FileExistsError(f'No overwrite/resume: {target}')
    raw = processed / 'features_raw.npy'
    # At least 2 GiB reserved, plus measured scaled/latent/model footprints per run.
    per_run = max(1.05, raw.stat().st_size / 1024**3 * 1.6)
    required = 2 + per_run * len(trials)
    free = shutil.disk_usage(processed).free / 1024**3
    plan = {'study_id': a.study_id, 'protocol': 'recall_gate_v1', 'seed': a.seed,
            'held_out_classes': support, 'free_gib': free, 'required_gib_estimate': required,
            'gate_policy': {'benign_validation_fpr_budget': a.fpr_budget, 'threshold_ceiling': 0.5,
                            'source': 'known validation only; heldout excluded'},
            'fixed_methods': 'AE16/XGB-latent/XGB-latent_only/max_probability',
            'novelty_known_rejection_rate': 0.05,
            'split': 'reuse prepared split; seed changes fitting only',
            'limitations': ['historical tests already seen; exploratory', 'single seed unless rerun separately',
                            'random split/vector overlap/provenance limitations remain',
                            'no guarantee known-validation recall transfers to unknown attacks']}
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if a.plan:
        return
    if free < required:
        raise RuntimeError('Insufficient free disk; preserve old artifacts and free space before training')
    config['hardware'].update(device='cuda:0', require_cuda=True)
    for stage in ['stage1', 'stage2']:
        config[stage]['xgboost'].update(device='cuda:0', tree_method='hist')
    if config['autoencoder']['latent_dim'] != 16 or config['stage1']['oof_folds'] != 5:
        raise ValueError('Fixed AE16 and 5-fold OOF required')
    config['evaluation']['decision_threshold'] = 0.5
    config['novelty']['known_rejection_rate'] = 0.05
    config['experiment'].update(processed_dir=str(processed), prepared_metadata_dir=str(processed / 'metadata'),
                                random_state=a.seed, models_dir='models', results_dir='results',
                                metadata_dir='artifacts/metadata')
    state = {'status': 'running', 'pid': os.getpid(), 'steps': [], 'started_utc': datetime.now(timezone.utc).isoformat()}
    sources = {str(f): sha256(f) for folder in ['src', 'scripts'] for f in (ROOT / folder).glob('*.py')}
    config_hashes = {}

    def step(name, args):
        for path, expected in {**sources, **config_hashes}.items():
            if sha256(path) != expected:
                raise RuntimeError(f'Source/config changed: {path}')
        if shutil.disk_usage(processed).free < 2 * 1024**3:
            raise RuntimeError('Less than 2 GiB free before next step')
        log = directory / 'logs' / f'{len(state["steps"]):02d}_{name}.log'
        cmd = [sys.executable, '-X', 'utf8', '-u', '-B', *map(str, args)]
        item = {'name': name, 'command': cmd, 'log': str(log), 'status': 'running'}
        state['steps'].append(item); state['current_step'] = name
        save_json(directory / 'status.json', state)
        started = time.perf_counter()
        print(f'START {name} | {log}', flush=True)
        with log.open('x', encoding='utf-8') as stream:
            child = subprocess.Popen(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                     env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1', 'PYTHONHASHSEED': str(a.seed)})
            item['child_pid'] = child.pid; save_json(directory / 'status.json', state)
            try:
                while True:
                    try:
                        code = child.wait(timeout=60); break
                    except subprocess.TimeoutExpired:
                        print(f'RUNNING {name}: {time.perf_counter()-started:.0f}s', flush=True)
            except BaseException:
                child.terminate(); child.wait(); item['status'] = 'interrupted'; raise
        item.update(status='completed' if code == 0 else 'failed', returncode=code, seconds=time.perf_counter()-started)
        save_json(directory / 'status.json', state)
        if code:
            raise RuntimeError(f'{name} failed; inspect {log}')

    with gpu_lock():
        directory.mkdir(parents=True); (directory / 'logs').mkdir()
        save_json(directory / 'protocol_lock.json', {**plan, 'sources': sources, 'input_config': config})
        save_json(directory / 'status.json', state)
        try:
            step('environment', ['scripts/verify_environment.py', '--config', a.config])
            # Environment/package manifest is small; training commands/checkpoints stay in this project.
            save_json(directory / 'packages.json', {'python': sys.version,
                      'pip_freeze': subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)})
            for held, run in trials:
                cpath = ROOT / 'configs' / f'{run}.json'
                cfg = json.loads(json.dumps(config)); cfg['experiment']['id'] = run
                save_json(cpath, cfg); config_hashes[str(cpath)] = sha256(cpath)
                common = ['--config', cpath, '--run-id', run, '--held-out-label-id', held]
                train = [*common, '--protocol', 'revised_v1']
                step(run+'_preprocess', ['scripts/01b_prepare_protocol.py', *common])
                step(run+'_ae', ['scripts/02_train_autoencoder.py', *train])
                step(run+'_stage1', ['scripts/03_train_stage1.py', *train, '--model', 'xgboost', '--representation', 'latent'])
                step(run+'_stage2', ['scripts/04_train_stage2.py', *train, '--experiment', 'latent_only'])
                ppath = processed / 'experiments' / run / 'stage1_xgboost_latent_p_attack_all.npy'
                gate = directory / f'gate_h{held}.json'
                step(run+'_gate', ['scripts/12_select_gate_threshold.py', *common, '--p-attack-path', ppath,
                                   '--fpr-budget', a.fpr_budget, '--output', gate])
                s2 = ROOT / 'results/stage2' / run / 'latent_only'
                step(run+'_novelty', ['scripts/05_train_novelty.py', *train, '--stage2-result-dir', s2,
                     '--ae-metadata', ROOT/'artifacts/metadata/autoencoder'/run/'run.json',
                     '--stage1-metadata', ROOT/'artifacts/metadata/stage1'/run/'xgboost_latent.json',
                     '--stage2-metadata', ROOT/'artifacts/metadata/stage2'/run/'latent_only.json', '--methods', 'max_probability'])
                for tag in ['fixed', 'recall']:
                    evalargs = ['scripts/06_evaluate_pipeline.py', '--config', cpath, '--run-id', run+'_'+tag,
                                '--held-out-label-id', held, '--p-attack-path', ppath, '--stage2-result-dir', s2,
                                '--novelty-result-dir', ROOT/'results/novelty'/run/f'heldout_{held}'/'latent_only',
                                '--novelty-method', 'max_probability', '--novelty-threshold-json',
                                ROOT/'artifacts/thresholds'/run/f'heldout_{held}'/'latent_only/max_probability.json']
                    if tag == 'recall':
                        evalargs += ['--stage1-threshold-json', gate]
                    step(run+'_'+tag, evalargs)
            comparison = {run: {tag: json.loads((ROOT/'results/pipeline'/(run+'_'+tag)/'metrics.json').read_text(encoding='utf-8'))
                                for tag in ['fixed', 'recall']} for _, run in trials}
            save_json(directory/'comparison.json', comparison)
            state['status'] = 'completed'
        except BaseException as error:
            state.update(status='failed', error=repr(error)); raise
        finally:
            state['ended_utc'] = datetime.now(timezone.utc).isoformat()
            save_json(directory/'status.json', state)


if __name__ == '__main__':
    main()
