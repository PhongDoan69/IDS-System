"""Manifest v1: hash nội dung, dataset identity, config/source/runtime và ancestry.

Hash chứng minh tính toàn vẹn local, không chứng minh provenance upstream hay split độc lập.
Không tạo manifest hồi tố cho model lịch sử để giả mạo training lineage.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from src.model_config import project_path
from src.training_utils import save_json

PROTOCOL = 'revised_v1'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def metadata_directory(config):
    return project_path(config, config['experiment'].get('prepared_metadata_dir', 'artifacts/metadata'))


def dataset_identity(config):
    directory = project_path(config, config['experiment']['processed_dir'])
    names = ['features_raw.npy', 'row_hashes.npy', 'split_ids.npy', 'binary_labels.npy', 'attack_label_ids.npy']
    files = {name: sha256(directory / name) for name in names}
    for name in ['feature_names.json', 'label_mapping.json', 'split_config.json']:
        files[name] = sha256(metadata_directory(config) / name)
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def sidecar(path):
    path = Path(path)
    return path / 'contract.json' if path.is_dir() else path.with_name(path.name + '.contract.json')


def file_records(paths):
    return [{'path': str(Path(p).resolve()), 'sha256': sha256(p)} for p in paths]


def read_contract(path, config, held_out, *, kind=None, run_id=None):
    path = Path(path)
    manifest_path = sidecar(path)
    if not manifest_path.is_file():
        raise ValueError(f'Thiếu lineage revised_v1: {manifest_path}; không dùng artifact cũ cho training mới')
    record = json.loads(manifest_path.read_text(encoding='utf-8'))
    if record.get('protocol') != PROTOCOL or record.get('status') != 'completed':
        raise ValueError('Protocol/status của artifact không hợp lệ')
    if record.get('held_out_label_id') != held_out or record.get('dataset_identity') != dataset_identity(config):
        raise ValueError('Artifact không cùng heldout/dataset/split/schema/labels')
    if kind is not None and record.get('kind') != kind:
        raise ValueError(f'Artifact kind phải là {kind}')
    if run_id is not None and record.get('run_id') != run_id:
        raise ValueError('Artifact không cùng run-id')
    expected_path = str(path.resolve())
    if record.get('artifact_path') != expected_path:
        raise ValueError('Artifact bị di chuyển; cần migration có kiểm chứng, không sửa metadata ngầm')
    verify_record_files(record)
    if not path.is_dir() and expected_path not in {item['path'] for item in record['outputs']}:
        raise ValueError('Manifest không bảo vệ chính artifact được yêu cầu')
    return record


def verify_record_files(record, seen=None):
    """Kiểm cả ancestry sidecars; cache trong một lần walk để tránh đọc lặp DAG."""
    seen = {} if seen is None else seen
    for item in record['outputs'] + record['parents']:
        path = item['path']
        if path in seen:
            if seen[path] != item['sha256']:
                raise ValueError('Ancestry có hai checksum mâu thuẫn')
            continue
        actual = sha256(path)
        if actual != item['sha256']:
            raise ValueError(f'Artifact/parent đã thay đổi: {path}')
        seen[path] = actual
        if path.endswith('.contract.json') or Path(path).name == 'contract.json':
            parent = json.loads(Path(path).read_text(encoding='utf-8'))
            if parent.get('protocol') != PROTOCOL or parent.get('status') != 'completed' or parent.get('dataset_identity') != record['dataset_identity'] or parent.get('held_out_label_id') != record['held_out_label_id']:
                raise ValueError('Ancestry không cùng protocol/heldout/dataset')
            verify_record_files(parent, seen)


def write_contract(path, config, run_id, held_out, kind, *, parents=(), extra=None):
    path = Path(path)
    outputs = sorted(p for p in path.rglob('*') if p.is_file() and p.name != 'contract.json') if path.is_dir() else [path]
    root = Path(config['_project_root'])
    sources = sorted(root.glob('src/*.py')) + sorted(root.glob('scripts/*.py'))
    record = {
        'protocol': PROTOCOL, 'status': 'completed', 'kind': kind,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'run_id': run_id, 'held_out_label_id': held_out,
        'artifact_path': str(path.resolve()), 'dataset_identity': dataset_identity(config),
        'dataset_name': 'CICIDS2017 local daily CSV; upstream release UNVERIFIED',
        'config': config, 'python': platform.python_version(), 'platform': platform.platform(),
        'packages': {p: importlib.metadata.version(p) for p in ['numpy', 'pandas', 'scikit-learn', 'torch', 'xgboost', 'joblib']},
        'source_files': file_records(sources), 'outputs': file_records(outputs),
        'parents': file_records(parents), 'extra': extra or {},
    }
    save_json(sidecar(path), record)
    return record


def require_link(record, path):
    """Ràng buộc đúng file upstream, không chỉ cùng tên run hoặc cùng số dòng."""
    resolved = str(Path(path).resolve())
    if not any(item['path'] == resolved and item['sha256'] == sha256(path) for item in record['parents']):
        raise ValueError(f'Không có ancestry tới {resolved}')
