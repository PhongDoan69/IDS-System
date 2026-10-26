"""Điều phối đợt CICIDS2017 đầy đủ, một subprocess/job tại một thời điểm.

Không thay thuật toán/hyperparameters; không resume/overwrite run. Lỗi ở bất kỳ
phase nào dừng toàn chuỗi và giữ log/artifact. --plan không ghi file hoặc train.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.training_utils import save_json

STAGE1 = [('xgboost', 'latent'), ('xgboost', 'scaled'), ('mlp', 'scaled'), ('mlp', 'latent')]
VARIANTS = ['latent_only', 'latent_plus_pattack_xgb', 'latent_only_mlp', 'latent_plus_pattack_mlp']
METHODS = ['max_probability', 'one_class_svm', 'isolation_forest']


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def choose_stage2(reports):
    """Chỉ validation macro-F1; tie theo thứ tự VARIANTS đã chốt trước run."""
    scores = [float(reports[name]['validation_metrics']['macro_f1']) for name in VARIANTS]
    if not all(math.isfinite(s) and 0 <= s <= 1 for s in scores):
        raise ValueError('Validation score không hợp lệ')
    return VARIANTS[max(range(len(scores)), key=lambda i: (scores[i], -i))]


def plan(round_id):
    return {
        'round_id': round_id, 'protocol': 'revised_v1', 'seed': 42,
        'primary_dataset': 'CICIDS2017 local daily CSV; upstream release unverified',
        'main_run_id': round_id + '_main', 'loaco_run_id': round_id + '_loaco26',
        'start_from': 'raw CSV audit and isolated Phase 2 rebuild; verify against legacy identities',
        'stage1': [f'{m}_{r}' for m, r in STAGE1], 'stage2': VARIANTS,
        'primary_gate': 'xgboost_latent', 'gate_threshold': 0.5,
        'stage2_selection': 'max validation macro_f1; ties use declared variant order',
        'loaco_heldout': 26, 'loaco_stage2': 'selected main Stage 2; refit whole chain',
        'novelty_methods': METHODS, 'known_validation_rejection_rate': 0.05,
        'budget': 'one fixed configuration per model, seed 42; existing epoch/tree budgets unchanged',
        'external_datasets': 'not trained in round 1',
        'limitations': ['exploratory: historical test already inspected',
                       'fixed random split retains feature-vector overlap',
                       'Attempted preserved; provenance/target semantics unresolved',
                       'one seed and one heldout; no superiority/significance/novelty proof',
                       'Stage 1 family comparison separate from fixed-gate Stage 2 ablation',
                       'no raw-to-model latency benchmark; no flat/no-AE Stage 2 control'],
    }


class Round:
    def __init__(self, round_id):
        self.spec = plan(round_id)
        self.directory = ROOT / 'results/research_rounds' / round_id
        self.processed = ROOT / 'data/processed' / round_id
        self.config = ROOT / 'configs' / f'model_config_{round_id}.json'
        self.base = ROOT / 'configs' / f'base_{round_id}.json'
        self.main_id = self.spec['main_run_id']
        self.loaco_id = self.spec['loaco_run_id']
        for target in [self.directory, self.processed, self.config, self.base]:
            if target.exists():
                raise FileExistsError(f'Không overwrite/resume: {target}')
        for run_id in [self.main_id, self.loaco_id]:
            for category in ['models', 'results', 'artifacts/metadata']:
                for phase in ['autoencoder', 'stage1', 'stage2', 'novelty']:
                    if (ROOT / category / phase / run_id).exists():
                        raise FileExistsError(f'Run ID đã tồn tại: {run_id}')
        if shutil.disk_usage(ROOT).free < 6 * 1024**3:
            raise RuntimeError('Cần ít nhất 6 GiB trống trước khi bắt đầu')
        self.directory.mkdir(parents=True)
        (self.directory / 'logs').mkdir()
        base = read(ROOT / 'configs/base.json')
        model = read(ROOT / 'configs/model_config.json')
        if base['random_state'] != 42 or model['experiment']['random_state'] != 42:
            raise ValueError('Đợt 1 đã chốt seed 42')
        if model['evaluation']['decision_threshold'] != .5 or model['novelty']['known_rejection_rate'] != .05:
            raise ValueError('Ngưỡng khác protocol đã chốt')
        model['experiment'].update(id=self.main_id, processed_dir=str(self.processed),
                                   prepared_metadata_dir=str(self.processed / 'metadata'),
                                   base_data_config=str(self.base))
        save_json(self.base, base)
        save_json(self.config, model)
        self.sources = {str(p): digest(p) for folder in ['src', 'scripts'] for p in sorted((ROOT / folder).glob('*.py'))}
        self.sources.update({str(self.base): digest(self.base), str(self.config): digest(self.config)})
        self.spec.update(created_utc=datetime.now(timezone.utc).isoformat(),
                         git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                         source_hashes=self.sources, config=str(self.config), base_config=str(self.base))
        save_json(self.directory / 'protocol_lock.json', self.spec)
        self.state = {'status': 'running', 'pid': os.getpid(), 'started_utc': self.spec['created_utc'], 'steps': []}
        self.persist()

    def persist(self):
        save_json(self.directory / 'status.json', self.state)

    def verify_sources(self):
        for name, expected in self.sources.items():
            if digest(name) != expected:
                raise RuntimeError(f'Source/config đổi giữa run; dừng để giữ protocol: {name}')

    def step(self, name, arguments):
        self.verify_sources()
        if shutil.disk_usage(ROOT).free < 2 * 1024**3:
            raise RuntimeError('Dưới 2 GiB trống; dừng trước phase kế tiếp')
        log = self.directory / 'logs' / f'{len(self.state["steps"]):02d}_{name}.log'
        command = [sys.executable, '-X', 'utf8', '-u', '-B', *map(str, arguments)]
        item = {'name': name, 'status': 'running', 'command': command, 'log': str(log),
                'started_utc': datetime.now(timezone.utc).isoformat()}
        self.state['steps'].append(item)
        self.state['current_step'] = name
        self.persist()
        print(f'START {name} | {log}', flush=True)
        started = time.perf_counter()
        with log.open('x', encoding='utf-8') as stream:
            child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                     env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1', 'PYTHONHASHSEED': '42'})
            item['child_pid'] = child.pid
            self.persist()
            try:
                code = child.wait()
            except BaseException:
                child.terminate()
                child.wait()
                raise
        item.update(returncode=code, seconds=time.perf_counter() - started,
                    ended_utc=datetime.now(timezone.utc).isoformat(), status='completed' if code == 0 else 'failed')
        self.persist()
        if code:
            raise RuntimeError(f'{name} thất bại (exit={code}); xem {log}')
        print(f'DONE {name}: {item["seconds"]:.1f}s', flush=True)

    def train(self, script, run_id, *args):
        return [f'scripts/{script}', '--config', self.config, '--run-id', run_id, '--protocol', 'revised_v1', *args]

    def p_path(self, run_id):
        return self.processed / 'experiments' / run_id / 'stage1_xgboost_latent_p_attack_all.npy'

    def evaluation(self, run_id, variant, evaluation_id, *extra):
        return ['scripts/06_evaluate_pipeline.py', '--config', self.config, '--run-id', evaluation_id,
                '--p-attack-path', self.p_path(run_id), '--stage2-result-dir', ROOT / 'results/stage2' / run_id / variant, *extra]

    def run(self):
        self.step('environment', ['scripts/verify_environment.py', '--config', self.config])
        self.step('tests', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        self.step('raw_audit', ['scripts/00_audit_dataset.py', '--config', self.base, '--output-dir', self.directory / 'raw_audit'])
        expected = read(ROOT / 'artifacts/metadata/raw_manifest.json')
        observed = read(self.directory / 'raw_audit/metadata/raw_manifest.json')
        identity = lambda rows: {r['file']: (r['bytes'], r['sha256']) for r in rows}
        if identity(expected) != identity(observed):
            raise ValueError('Raw dataset khác manifest lịch sử; không đổi benchmark ngầm')
        self.step('prepare_from_raw', ['scripts/01_prepare_data.py', '--config', self.base, '--output-dir', self.processed])
        comparisons = {}
        for name in ['features_raw.npy', 'features_scaled.npy', 'row_hashes.npy', 'attack_label_ids.npy', 'binary_labels.npy', 'split_ids.npy']:
            comparisons[name] = {'new': digest(self.processed / name), 'reference': digest(ROOT / 'data/processed' / name)}
        for name in ['feature_names.json', 'label_mapping.json']:
            comparisons[name] = {'new': read(self.processed / 'metadata' / name), 'reference': read(ROOT / 'artifacts/metadata' / name)}
        save_json(self.directory / 'reproduction_checks.json', comparisons)
        if any(v['new'] != v['reference'] for v in comparisons.values()):
            raise ValueError('Phase 2 rebuild khác baseline; dừng trước training')
        if read(self.processed / 'metadata/label_mapping.json').get('26') != 'DDoS':
            raise ValueError('Heldout 26 không phải DDoS trong mapping')
        self.step('main_preprocessing', ['scripts/01b_prepare_protocol.py', '--config', self.config, '--run-id', self.main_id])
        self.step('main_autoencoder', self.train('02_train_autoencoder.py', self.main_id))
        for model, representation in STAGE1:
            self.step(f'main_stage1_{model}_{representation}', self.train('03_train_stage1.py', self.main_id, '--model', model, '--representation', representation))
        for variant in VARIANTS:
            extra = ['--p-attack-path', self.p_path(self.main_id)] if 'plus_pattack' in variant else []
            self.step('main_stage2_' + variant, self.train('04_train_stage2.py', self.main_id, '--experiment', variant, *extra))
        # Chỉ lấy validation field để chọn; không xếp hạng theo test dù training scripts đã lưu test metrics.
        reports = {v: read(ROOT / 'results/stage2' / self.main_id / v / 'metrics.json') for v in VARIANTS}
        self.selected = choose_stage2(reports)
        save_json(self.directory / 'selection_validation_only.json', {
            'selected': self.selected, 'selected_utc': datetime.now(timezone.utc).isoformat(),
            'criterion': self.spec['stage2_selection'], 'gate_fixed': 'xgboost_latent',
            'validation_macro_f1': {v: reports[v]['validation_metrics']['macro_f1'] for v in VARIANTS},
            'test_used_for_selection': False})
        for variant in VARIANTS:
            self.step('closed_' + variant, self.evaluation(self.main_id, variant, self.spec['round_id'] + '_closed_' + variant))
        held = ['--held-out-label-id', '26']
        self.step('loaco_preprocessing', ['scripts/01b_prepare_protocol.py', '--config', self.config, '--run-id', self.loaco_id, *held])
        self.step('loaco_autoencoder', self.train('02_train_autoencoder.py', self.loaco_id, *held))
        self.step('loaco_stage1', self.train('03_train_stage1.py', self.loaco_id, '--model', 'xgboost', '--representation', 'latent', *held))
        extra = ['--p-attack-path', self.p_path(self.loaco_id)] if 'plus_pattack' in self.selected else []
        self.step('loaco_stage2', self.train('04_train_stage2.py', self.loaco_id, '--experiment', self.selected, *held, *extra))
        self.step('loaco_novelty', self.train('05_train_novelty.py', self.loaco_id, *held,
            '--stage2-result-dir', ROOT / 'results/stage2' / self.loaco_id / self.selected,
            '--ae-metadata', ROOT / 'artifacts/metadata/autoencoder' / self.loaco_id / 'run.json',
            '--stage1-metadata', ROOT / 'artifacts/metadata/stage1' / self.loaco_id / 'xgboost_latent.json',
            '--stage2-metadata', ROOT / 'artifacts/metadata/stage2' / self.loaco_id / (self.selected + '.json'),
            '--methods', *METHODS))
        for method in METHODS:
            self.step('open_' + method, self.evaluation(self.loaco_id, self.selected, self.spec['round_id'] + '_open_' + method, *held,
                '--novelty-result-dir', ROOT / 'results/novelty' / self.loaco_id / 'heldout_26' / self.selected,
                '--novelty-method', method, '--novelty-threshold-json', ROOT / 'artifacts/thresholds' / self.loaco_id / 'heldout_26' / self.selected / (method + '.json')))
        self.verify_sources()
        self.report()
        self.state.update(status='completed', ended_utc=datetime.now(timezone.utc).isoformat(), selected_stage2=self.selected)
        self.persist()

    def report(self):
        """Chỉ tổng hợp JSON thực sự tồn tại sau tất cả commands thành công."""
        s1 = {f'{m}_{r}': read(ROOT / 'results/stage1' / self.main_id / f'{m}_{r}' / 'metrics.json') for m, r in STAGE1}
        s2 = {v: read(ROOT / 'results/stage2' / self.main_id / v / 'metrics.json') for v in VARIANTS}
        closed = {v: read(ROOT / 'results/pipeline' / (self.spec['round_id'] + '_closed_' + v) / 'metrics.json') for v in VARIANTS}
        opened = {m: read(ROOT / 'results/pipeline' / (self.spec['round_id'] + '_open_' + m) / 'metrics.json') for m in METHODS}
        save_json(self.directory / 'comparison.json', {'protocol': self.spec, 'selected_stage2': self.selected,
                  'stage1': s1, 'stage2': s2, 'closed_set': closed, 'open_set': opened})
        lines = ['# Kết quả đợt 1 — CICIDS2017', '', '[VERIFIED FROM EXPERIMENTS] Các số dưới đây đọc từ metrics.json của run mới; xem comparison.json và logs để truy vết.', '',
                 '## Stage 1 — binary detection', '', '| Cấu hình | Val F1 | Test F1 | Precision | Recall | FPR | FNR | AUROC | AP | Brier |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
        for name, value in s1.items():
            t = value['test_metrics']
            nums = [value['validation_metrics']['f1'], *[t[k] for k in ['f1','precision','recall_detection_rate','false_positive_rate','false_negative_rate','roc_auc','average_precision','brier_score']]]
            lines.append('| ' + name + ' | ' + ' | '.join(f'{x:.6f}' for x in nums) + ' |')
        lines += ['', '## Stage 2 và cascade — cùng gate XGB latent 0,5', '', '| Biến thể | Val attack macro-F1 | Test attack macro-F1 | E2E accuracy | Balanced accuracy | Macro-F1 | Weighted-F1 |', '|---|---:|---:|---:|---:|---:|---:|']
        for v in VARIANTS:
            nums = [s2[v]['validation_metrics']['macro_f1'], s2[v]['known_test_metrics']['macro_f1'], *[closed[v]['end_to_end_metrics'][k] for k in ['accuracy','balanced_accuracy','macro_f1','weighted_f1']]]
            lines.append('| ' + v + ' | ' + ' | '.join(f'{x:.6f}' for x in nums) + ' |')
        lines += ['', f'[VERIFIED FROM EXPERIMENTS] Stage 2 được khóa bằng validation: `{self.selected}`. Không đổi lựa chọn theo test.', '',
                  '## LOACO 26 — unknown sau gate', '', '| Method | Unknown precision | Recall | F1 | Known attack false rejection | Benign → unknown | Unknown bị gate chặn | E2E macro-F1 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
        for m, value in opened.items():
            u = value['final_unknown_metrics']
            nums = [u[k] for k in ['precision','recall','f1','known_attack_false_rejection_rate','benign_rejected_unknown','unknown_blocked_by_stage1']] + [value['end_to_end_metrics']['macro_f1']]
            lines.append('| ' + m + ' | ' + ' | '.join(f'{x:.6f}' for x in nums) + ' |')
        lines += ['', '## Hiệu ứng meta-feature cùng họ classifier', '', '| So sánh | Δ validation attack macro-F1 | Δ test E2E macro-F1 |', '|---|---:|---:|']
        for base, plus in [('latent_only', 'latent_plus_pattack_xgb'), ('latent_only_mlp', 'latent_plus_pattack_mlp')]:
            dv = s2[plus]['validation_metrics']['macro_f1'] - s2[base]['validation_metrics']['macro_f1']
            dt = closed[plus]['end_to_end_metrics']['macro_f1'] - closed[base]['end_to_end_metrics']['macro_f1']
            lines.append(f'| {plus} − {base} | {dv:+.6f} | {dt:+.6f} |')
        lines += ['', '[TECHNICAL INTERPRETATION] Delta là quan sát của một seed/split, không phải kiểm định ý nghĩa thống kê. Đọc per_class, support, confusion_matrix và error_decomposition trong comparison.json trước khi kết luận.', '',
                  '[REQUIRES FURTHER VERIFICATION] Kết hợp thuật toán có sẵn và điểm số cao không tự chứng minh tính mới. Cần đối chứng no-AE/flat theo kế hoạch duyệt, multi-seed, split độc lập, multi-heldout và đối chiếu tài liệu khoa học.', '',
                  '[TECHNICAL INTERPRETATION] Pipeline được chọn là ứng viên thăm dò cho giai đoạn tiếp theo, chưa là chuẩn đã xác nhận. CSE-CIC-IDS2018/CIC-UNSW-NB15 chưa chạy; phải chốt feature semantics, units, ontology và phân biệt retrain với zero-shot.', '',
                  '## Giới hạn đã chốt trước run', '', *['- ' + item for item in self.spec['limitations']], '',
                  'Thời gian từng subprocess ở status.json gồm I/O/checksum/metrics, không phải độ trễ inference. Không có kết quả model-reload latency trong đợt này.', '']
        (self.directory / 'RESEARCH_REPORT.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--round-id', default='round1_20261026_s42')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan', action='store_true')
    mode.add_argument('--run', action='store_true')
    args = parser.parse_args()
    from src.model_config import experiment_id
    experiment_id({'experiment': {'id': args.round_id}}, args.round_id)
    if args.plan:
        print(json.dumps(plan(args.round_id), ensure_ascii=False, indent=2))
        return
    task = Round(args.round_id)
    try:
        task.run()
    except BaseException as error:
        task.state.update(status='failed', error=str(error), ended_utc=datetime.now(timezone.utc).isoformat())
        task.persist()
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == '__main__':
    main()
