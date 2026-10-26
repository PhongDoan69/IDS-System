"""Corrective protocol v1; giữ nguyên target/split đã lưu, không tự chia lại dataset."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.artifact_contracts import read_contract, write_contract, metadata_directory
from src.contracts import assert_new_outputs, exact_indices
from src.model_config import project_path
from src.model_data import load_prepared_arrays, split_indices, validate_held_out_label
from src.preprocessing import TrainOnlyStandardScaler, save_scaler, load_scaler
from src.training_utils import save_json


def protocol_directory(config, run_id):
    return project_path(config, config['experiment']['processed_dir']) / 'experiments' / run_id / 'preprocessing'


def fit_transform_scope(raw, fit_indices, output, scaler_path, batch_size=100000):
    """Fit đúng indices được giao, transform toàn bộ nhưng không cập nhật state."""
    fit_indices = np.asarray(fit_indices, dtype=np.int64)
    if not len(fit_indices) or len(np.unique(fit_indices)) != len(fit_indices):
        raise ValueError('Scaler fit indices rỗng hoặc trùng')
    scaler = TrainOnlyStandardScaler()
    for start in range(0, len(fit_indices), batch_size):
        scaler.partial_fit(raw[fit_indices[start:start + batch_size]])
    save_scaler(scaler, Path(scaler_path))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    destination = np.lib.format.open_memmap(output, mode='w+', dtype='float32', shape=raw.shape)
    for start in range(0, len(raw), batch_size):
        destination[start:start + batch_size] = scaler.transform(raw[start:start + batch_size])
    destination.flush()
    return destination


def prepare_protocol(config, run_id, held_out, check_only=False):
    processed = project_path(config, config['experiment']['processed_dir'])
    arrays = load_prepared_arrays(processed, processed / 'features_raw.npy')
    validate_held_out_label(arrays.attack_label_ids, held_out)
    metadata = metadata_directory(config)
    names = json.loads((metadata / 'feature_names.json').read_text(encoding='utf-8'))['features']
    mapping = json.loads((metadata / 'label_mapping.json').read_text(encoding='utf-8'))
    if len(names) != arrays.features.shape[1] or len(set(names)) != len(names) or mapping.get('0') != 'BENIGN':
        raise ValueError('Schema/label mapping không phù hợp Phase 2')
    if set(map(int, mapping)) != set(np.unique(arrays.attack_label_ids)):
        raise ValueError('Label mapping không khớp label array')
    if len(np.unique(arrays.row_hashes)) != len(arrays.row_hashes):
        raise ValueError('Row identity không duy nhất; cần kiểm tra preparation')
    fit = split_indices(arrays.split_ids, 0, held_out, arrays.attack_label_ids)
    directory = protocol_directory(config, run_id)
    assert_new_outputs(directory)
    plan = {'protocol': 'revised_v1', 'run_id': run_id, 'held_out_label_id': held_out,
            'fit_samples': len(fit), 'features': names, 'split_policy': 'reuse fixed Phase 2; no resplit',
            'output': str(directory), 'status': 'checked_only' if check_only else 'running'}
    print(plan)
    if check_only:
        return plan
    directory.mkdir(parents=True)
    save_json(directory / 'execution.json', plan)
    np.save(directory / 'fit_indices.npy', fit)
    fit_transform_scope(arrays.features, fit, directory / 'features_scaled.npy', directory / 'scaler.joblib')
    plan['status'] = 'completed'
    save_json(directory / 'execution.json', plan)
    write_contract(directory / 'features_scaled.npy', config, run_id, held_out, 'preprocessing',
                   parents=[processed / 'features_raw.npy', directory / 'scaler.joblib', directory / 'fit_indices.npy'],
                   extra=plan)
    return plan


def require_preprocessing(config, run_id, held_out):
    directory = protocol_directory(config, run_id)
    path = directory / 'features_scaled.npy'
    record = read_contract(path, config, held_out, kind='preprocessing', run_id=run_id)
    processed = project_path(config, config['experiment']['processed_dir'])
    arrays = load_prepared_arrays(processed, path)
    expected = split_indices(arrays.split_ids, 0, held_out, arrays.attack_label_ids)
    exact_indices(np.load(directory / 'fit_indices.npy', allow_pickle=False), expected, 'scaler fit_indices')
    scaler = load_scaler(directory / 'scaler.joblib')
    if scaler.n_samples_seen_ != len(expected):
        raise ValueError('Scaler sample count không khớp known-only fit scope')
    return arrays, path, record


def inner_partitions(indices, binary_labels, seed):
    """80% fit / 10% early-stop / 10% calibration trong outer-training; không đụng outer holdout.

    Chia theo binary target, không cố giữ mọi nhãn attack hiếm. Đây là chi tiết protocol
    sửa có version; phải công bố và không thay fractions sau khi nhìn test.
    """
    from sklearn.model_selection import train_test_split
    indices = np.asarray(indices, dtype=np.int64)
    fit, development = train_test_split(indices, test_size=.2, stratify=binary_labels[indices], random_state=seed)
    stop, calibration = train_test_split(development, test_size=.5, stratify=binary_labels[development], random_state=seed + 1)
    for part in [fit, stop, calibration]:
        if len(np.unique(binary_labels[part])) != 2:
            raise ValueError('Inner partition không đủ hai binary classes')
    return fit, stop, calibration
