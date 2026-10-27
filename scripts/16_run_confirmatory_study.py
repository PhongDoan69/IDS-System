r"""Fresh multi-seed LOACO, fixed kNN candidate vs matched MCP/Mahalanobis.

PowerShell / VS Code in D:\CAO HOC\IDS System:
 .\.venv\Scripts\python.exe -X utf8 -u -B scripts\16_run_confirmatory_study.py --study-id novelty_r3_20261027 --plan
 .\.venv\Scripts\python.exe -X utf8 -u -B scripts\16_run_confirmatory_study.py --study-id novelty_r3_20261027 --run

Name 'confirmatory' refers to a frozen hypothesis across fresh fitting seeds,
NOT independent test confirmation: knn_v1 test results motivated balanced_l2_k1.
No resume/overwrite, no test-based search. Runs sequentially under the GPU lock.
Canonical raw/prepared inputs remain fixed. Refit EVERY scaler, verify every
transformed row before hard-linking identical historical immutable storage.
Train EVERY AE, all 5 nested-OOF encoders/classifiers, final Stage1 and Stage2 anew.
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
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.artifact_contracts import sha256, dataset_identity
from src.model_config import experiment_id, load_model_config, project_path
from src.model_data import load_prepared_arrays
from src.research_protocol import require_preprocessing
from src.study_reporting import summarize_rows
from src.training_utils import save_json

METHODS = ['max_probability', 'mahalanobis', 'knn_distance']
GATES = ['fixed', 'recall']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def make_config(template, run, seed, processed, source):
    cfg = json.loads(json.dumps({k:v for k,v in template.items() if not k.startswith('_')}))
    cfg['experiment'].update(id=run, random_state=seed, processed_dir=str(processed),
                             prepared_metadata_dir=str(processed/'metadata'), models_dir='models',
                             results_dir='results', metadata_dir='artifacts/metadata',
                             verified_preprocessing_storage_source=source)
    cfg['hardware'].update(device='cuda:0', require_cuda=True)
    for phase in ['stage1', 'stage2']:
        cfg[phase]['xgboost'].update(device='cuda:0', tree_method='hist')
    cfg['evaluation'].update(decision_threshold=.5, save_predictions=False, save_compact_predictions=True)
    cfg['novelty']['known_rejection_rate'] = .05
    cfg['novelty']['matched_benchmark'] = {'methods': METHODS, 'k': 1, 'normalization': 'l2',
                                         'policy': 'balanced', 'max_reference_rows': 50000,
                                         'reference_seed': seed, 'threshold_source': 'known validation only'}
    return cfg


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--study-id', required=True)
    p.add_argument('--config', default=str(ROOT/'configs/model_config_round2_20261027_fp32_s42.json'))
    p.add_argument('--held-out-labels', nargs='+', type=int, default=[9,25,26])
    p.add_argument('--seeds', nargs='+', type=int, default=[42,43,44])
    p.add_argument('--storage-source-study', default='recall_gate_v1_20261027')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true'); mode.add_argument('--run', action='store_true')
    a = p.parse_args()
    for name in [a.study_id, a.storage_source_study]:
        experiment_id({}, name)
    if (len(a.study_id)>32 or len(set(a.held_out_labels))!=len(a.held_out_labels)
            or len(set(a.seeds))!=len(a.seeds) or any(s<0 for s in a.seeds)):
        raise ValueError('Short unique ID, distinct heldouts/seeds, nonnegative seeds required')
    cfg = load_model_config(a.config)
    if cfg['autoencoder']['latent_dim'] != 16 or cfg['stage1']['oof_folds'] != 5:
        raise ValueError('This study freezes AE16 and 5-fold nested OOF')
    processed = project_path(cfg, cfg['experiment']['processed_dir'])
    directory = ROOT/'results/novelty_confirmation'/a.study_id
    arrays = load_prepared_arrays(processed, processed/'features_raw.npy')
    try:
        labels, splits = arrays.attack_label_ids, arrays.split_ids
        names = read(processed/'metadata/label_mapping.json')
        support = []
        for held in a.held_out_labels:
            counts = [int(np.sum((labels==held)&(splits==s))) for s in range(3)]
            if held<=0 or min(counts)<500:
                raise ValueError(f'Heldout {held} needs >=500 rows in each split: {counts}')
            support.append({'heldout': held, 'name': names[str(held)], 'train_val_test': counts})
        input_bytes = arrays.features.nbytes
    finally:
        arrays.close()
    trials = [(held,seed,f'{a.study_id}_h{held}_s{seed}') for held in a.held_out_labels for seed in a.seeds]
    targets = [directory]
    sources_by_held = {}
    for held in a.held_out_labels:
        source = f'{a.storage_source_study}_h{held}_s42'
        # No source AE/Stage1/Stage2 model is reused. Only deterministic bytes.
        source_arrays, source_path, _ = require_preprocessing(cfg, source, held)
        source_arrays.close()
        if source_path.stat().st_dev != processed.stat().st_dev:
            raise ValueError('Hard-link source must be on the same filesystem')
        sources_by_held[held] = source
    for held,seed,run in trials:
        targets.extend([ROOT/'configs'/f'{run}.json', processed/'experiments'/run,
                        ROOT/'artifacts/thresholds'/run])
        for category in ['models','results','artifacts/metadata']:
            for phase in ['autoencoder','stage1','stage2','novelty']:
                targets.append(ROOT/category/phase/run)
        targets.append(ROOT/'results/pipeline'/(run+'_closed'))
        targets.extend(ROOT/'results/pipeline'/f'{run}_{method}_{gate}' for method in METHODS for gate in GATES)
    for target in targets:
        if target.exists():
            raise FileExistsError(f'No overwrite/resume: {target}')
    # Measured previous chain ~0.30 GiB excluding shared 0.656-GiB scaled array.
    # 0.42/trial covers final/fold models, probabilities, novelty and compact predictions.
    # Temporary fold raw-scaled+latent ~0.78 GiB, plus reserve >=1.5 GiB.
    required = 1.5 + input_bytes/1024**3 * (1+16/84) + .42*len(trials)
    free = shutil.disk_usage(processed).free/1024**3
    input_paths = [processed/(name+'.npy') for name in ['features_raw','features_scaled','row_hashes',
                    'split_ids','binary_labels','attack_label_ids']]
    input_paths += sorted((processed/'metadata').glob('*.json'))
    source_hashes = {str(f):sha256(f) for folder in ['src','scripts','tests'] for f in (ROOT/folder).glob('*.py')}
    inputs = {str(f):sha256(f) for f in input_paths}
    # Preserve baseline evidence in place: these files are read-only study parents.
    baseline_evidence = [ROOT/'results/recall_gate_studies/recall_gate_v1_20261027/comparison.json',
                         ROOT/'results/mahalanobis_studies/mahalanobis_v1/comparison.json',
                         ROOT/'results/knn_studies/knn_v1/comparison.json',
                         ROOT/'artifacts/metadata/raw_manifest.json']
    historical_hashes = {str(f):sha256(f) for f in baseline_evidence}
    base_path = project_path(cfg,cfg['experiment']['base_data_config'])
    input_config_hashes = {str(Path(a.config).resolve()):sha256(a.config), str(base_path):sha256(base_path)}
    reference_checks = read(ROOT/'results/research_rounds/round2_20261027_fp32_s42/reproduction_checks.json')
    for path in input_paths[:6]:
        if inputs[str(path)] != reference_checks[path.name]['new']:
            raise ValueError(f'Prepared benchmark changed since raw rebuild: {path}')
    plan = {'study_id': a.study_id, 'study_protocol': 'fixed_novelty_multiseed_v1',
            'artifact_protocol': 'revised_v1', 'created_utc':datetime.now(timezone.utc).isoformat(),
            'heldouts':support, 'seeds':a.seeds, 'trials':trials,
            'primary_candidate':'balanced_l2_k1', 'baselines':['max_probability','mahalanobis'],
            'selection':'NONE: same fixed candidate/baselines for every heldout and seed',
            'primary_gate':'recall: lowest known-validation threshold <=0.5 under benign FPR 0.001',
            'secondary_gate':'fixed 0.5', 'novelty_rejection_target':.05,
            'preprocessing':'fresh train-only scaler + full exact transform replay + immutable hard-link',
            'preprocessing_storage_sources':sources_by_held,
            'training':'fresh AE and nested OOF Stage1 and latent_only XGBoost Stage2 in every trial',
            'dataset_identity':dataset_identity(cfg), 'processed_dir':str(processed),
            'free_gib_at_plan':free, 'required_gib_estimate':required,
            'source_hashes':source_hashes, 'input_hashes':inputs, 'historical_evidence_hashes':historical_hashes,
            'input_config_hashes':input_config_hashes, 'input_config':{k:v for k,v in cfg.items() if not k.startswith('_')},
            'limitations':['candidate motivated by historical test: exploratory method-development evidence',
                           'same fixed stratified split; seed varies fitting AND kNN reference, not split',
                           'repeated seeds are not new independent test rows; no significance/superiority claim',
                           'known validation reused for upstream stopping and novelty calibration',
                           'feature-vector overlap remains; raw release provenance unverified; Attempted preserved',
                           'no external dataset, chronological split or real-world zero-day confirmation',
                           'unknown=-1, never recover the unseen attack semantic name',
                           'known-validation recall gate cannot guarantee unknown retention',
                           'CUDA training not guaranteed bitwise deterministic']}
    print(json.dumps({k:v for k,v in plan.items() if k not in ['source_hashes','input_hashes','input_config']},ensure_ascii=False,indent=2),flush=True)
    if a.plan:
        print('PLAN ONLY: no outputs/model fits; historical integrity checked',flush=True); return
    if free < required:
        raise RuntimeError(f'Disk insufficient: require {required:.2f} GiB; have {free:.2f}; no training started')
    spec = importlib.util.spec_from_file_location('study_lock',ROOT/'scripts/13_run_recall_gate_study.py')
    lock = importlib.util.module_from_spec(spec); spec.loader.exec_module(lock)
    state = {'status':'running','pid':os.getpid(),'started_utc':datetime.now(timezone.utc).isoformat(),
             'steps':[],'expected_subprocess_steps':3+13*len(trials)}
    config_hashes = dict(input_config_hashes)
    rows, comparisons = [], {}

    def step(name, args, seed=42):
        for path,expected in {**source_hashes,**config_hashes,**inputs,**historical_hashes}.items():
            if sha256(path)!=expected:
                raise RuntimeError(f'Locked source/config changed: {path}')
        if shutil.disk_usage(processed).free < 1.5*1024**3:
            raise RuntimeError('Less than 1.5 GiB free; preserve artifacts, do not auto-delete/retry')
        log = directory/'logs'/f'{len(state["steps"]):03d}_{name}.log'
        command = [sys.executable,'-X','utf8','-u','-B',*map(str,args)]
        item = {'name':name,'command':command,'log':str(log),'status':'running'}
        state['steps'].append(item); state['current_step']=name
        save_json(directory/'status.json',state)
        print(f'START {name} | {log}',flush=True); started=time.perf_counter()
        with log.open('x',encoding='utf-8') as stream:
            child = subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                         env={**os.environ,'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1','PYTHONHASHSEED':str(seed)})
            item['child_pid']=child.pid; save_json(directory/'status.json',state)
            try:
                while True:
                    try:
                        code=child.wait(timeout=60); break
                    except subprocess.TimeoutExpired:
                        print(f'RUNNING {name}: {time.perf_counter()-started:.0f}s',flush=True)
            except BaseException:
                child.terminate(); child.wait(); item['status']='interrupted'; raise
        item.update(returncode=code,status='completed' if code==0 else 'failed',seconds=time.perf_counter()-started)
        save_json(directory/'status.json',state)
        if code:
            raise RuntimeError(f'Failed {name}; inspect {log}; no automatic rerun')

    def report_progress():
        save_json(directory/'comparison.json',comparisons)
        save_json(directory/'summary.json',summarize_rows(rows))
        if rows:
            with (directory/'summary.csv').open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        lines=['# Đợt huấn luyện mới — so sánh novelty cố định', '',
               'Trạng thái: '+state['status']+'. Ứng viên kNN được đề xuất sau khi đã xem test lịch sử.',
               'Đây là kiểm tra độ ổn định theo seed trên split cố định, KHÔNG phải test độc lập.', '',
               '| Held-out | Seed | Gate | Method | Detected/support | Precision | Recall | F1 | Known FRR | E2E macro-F1 |',
               '|---|---|---|---|---|---|---|---|---|---|']
        for r in rows:
            lines.append(f"| {r['heldout']} | {r['seed']} | {r['gate']} | {r['method']} | {r['detected']}/{r['support']} | {r['precision']:.6f} | {r['recall']:.6f} | {r['f1']:.6f} | {r['known_frr']:.6f} | {r['e2e_macro_f1']:.6f} |")
        lines += ['', 'Vai trò metrics: final_unknown_metrics là kết quả sau gate; score_only_unknown_metrics bỏ qua gate và benign.',
                  'Đọc error_decomposition, per-class support/F1, class_rejection.json và compact predictions trong từng evaluation.',
                  'summary.json: mean/std/min/max theo heldout; paired delta cùng seed. Không cộng 3 seed thành 3 tập test độc lập.',
                  'Không chọn lại k, gate budget, threshold hoặc mô hình theo bảng test này.', '',
                  '## Giới hạn đã khóa', '', *['- '+text for text in plan['limitations']]]
        (directory/'RESEARCH_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

    with lock.gpu_lock():
        directory.mkdir(parents=True); (directory/'logs').mkdir()
        save_json(directory/'protocol_lock.json',plan); save_json(directory/'status.json',state)
        try:
            step('environment',['scripts/verify_environment.py','--config',a.config])
            step('unit_tests',['-m','unittest','discover','-s','tests','-v'])
            base = project_path(cfg,cfg['experiment']['base_data_config'])
            step('raw_audit',['scripts/00_audit_dataset.py','--config',base,'--output-dir',directory/'raw_audit'])
            identity = lambda records:{r['file']:(r['bytes'],r['sha256']) for r in records}
            if identity(read(directory/'raw_audit/metadata/raw_manifest.json')) != identity(read(ROOT/'artifacts/metadata/raw_manifest.json')):
                raise ValueError('Raw data changed; do not silently substitute benchmark')
            save_json(directory/'environment.json',{'python':sys.version,'pip_freeze':subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)})
            for held,seed,run in trials:
                # Check dataset bytes before every trial as well as the initial raw audit.
                for path,expected in inputs.items():
                    if sha256(path)!=expected:
                        raise RuntimeError(f'Locked prepared data changed: {path}')
                cpath=ROOT/'configs'/f'{run}.json'
                save_json(cpath,make_config(cfg,run,seed,processed,sources_by_held[held]))
                config_hashes[str(cpath)]=sha256(cpath)
                common=['--config',cpath,'--run-id',run,'--held-out-label-id',held]
                train=[*common,'--protocol','revised_v1']
                for tag,script,extra in [('preprocess','01b_prepare_protocol.py',[]),('ae','02_train_autoencoder.py',[]),
                                        ('stage1','03_train_stage1.py',['--model','xgboost','--representation','latent']),
                                        ('stage2','04_train_stage2.py',['--experiment','latent_only'])]:
                    step(run+'_'+tag,['scripts/'+script,*(common if tag=='preprocess' else train),*extra],seed)
                pp=processed/'experiments'/run/'stage1_xgboost_latent_p_attack_all.npy'
                s2=ROOT/'results/stage2'/run/'latent_only'; gate=directory/f'gate_h{held}_s{seed}.json'
                step(run+'_gate',['scripts/12_select_gate_threshold.py',*common,'--p-attack-path',pp,'--fpr-budget',.001,'--output',gate],seed)
                step(run+'_novelty',['scripts/05_train_novelty.py',*train,'--stage2-result-dir',s2,
                     '--ae-metadata',ROOT/'artifacts/metadata/autoencoder'/run/'run.json',
                     '--stage1-metadata',ROOT/'artifacts/metadata/stage1'/run/'xgboost_latent.json',
                     '--stage2-metadata',ROOT/'artifacts/metadata/stage2'/run/'latent_only.json','--methods',*METHODS],seed)
                novelty=ROOT/'results/novelty'/run/f'heldout_{held}'/'latent_only'
                evaluation=['scripts/06_evaluate_pipeline.py','--config',cpath,'--held-out-label-id',held,
                            '--p-attack-path',pp,'--stage2-result-dir',s2]
                step(run+'_closed', [*evaluation,'--run-id',run+'_closed','--stage1-threshold-json',gate],seed)
                matched = {}
                for method in METHODS:
                    threshold=ROOT/'artifacts/thresholds'/run/f'heldout_{held}'/'latent_only'/f'{method}.json'
                    for tag in GATES:
                        eid=f'{run}_{method}_{tag}'
                        ev=[*evaluation,'--run-id',eid,'--novelty-result-dir',novelty,'--novelty-method',method,
                            '--novelty-threshold-json',threshold]
                        if tag=='recall': ev+=['--stage1-threshold-json',gate]
                        step(eid,ev,seed)
                        report=read(ROOT/'results/pipeline'/eid/'metrics.json'); u=report['final_unknown_metrics']
                        if tag in matched and (matched[tag]['stage1_test_metrics']!=report['stage1_test_metrics']
                                               or matched[tag]['stage1_threshold']!=report['stage1_threshold']):
                            raise ValueError('Methods are not matched on the same gate/upstream')
                        matched[tag]=report; comparisons[eid]=report
                        pred=np.load(ROOT/'results/pipeline'/eid/'predictions.npz',allow_pickle=False)
                        truth=pred['true_label_id']; prediction=pred['predicted_label_id']
                        known=np.load(s2/'class_ids.npy',allow_pickle=False)
                        rejection={str(int(c)):{'support':int(np.sum(truth==c)),
                                  'rejected_unknown':int(np.sum((truth==c)&(prediction==-1))),
                                  'false_rejection_rate':float(np.mean(prediction[truth==c]==-1)) if np.any(truth==c) else None}
                                   for c in known}
                        pred.close()
                        save_json(directory/f'{eid}_class_rejection.json',rejection)
                        rows.append({'heldout':held,'seed':seed,'gate':tag,'method':method,'detected':u['unknown_detected'],
                                     'support':u['unknown_support'],'precision':u['precision'],'recall':u['recall'],'f1':u['f1'],
                                     'known_frr':u['known_attack_false_rejection_rate'],'benign_unknown':u['benign_rejected_unknown'],
                                     'blocked_unknown':u['unknown_blocked_by_stage1'],'e2e_macro_f1':report['end_to_end_metrics']['macro_f1']})
                report_progress()
            if len(state['steps'])!=state['expected_subprocess_steps'] or any(s.get('returncode')!=0 for s in state['steps']):
                raise ValueError('Incomplete step inventory; cannot mark study complete')
            state['status']='completed'; report_progress()
        except BaseException as error:
            state.update(status='failed',error=repr(error)); raise
        finally:
            state['ended_utc']=datetime.now(timezone.utc).isoformat(); save_json(directory/'status.json',state)


if __name__=='__main__':
    main()
