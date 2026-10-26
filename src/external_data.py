"""Adapters native-schema, không tự coi schema/nhãn external tương đương CICIDS2017."""
from __future__ import annotations
from collections import Counter
from itertools import zip_longest
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_loader import normalize_column_names

UNSW_LABELS = {0: 'Benign', 1: 'Analysis', 2: 'Backdoor', 3: 'DoS', 4: 'Exploits',
               5: 'Fuzzers', 6: 'Generic', 7: 'Reconnaissance', 8: 'Shellcode', 9: 'Worms'}


def adapt_frame(features, labels, dataset, row_offset=0):
    """Giữ labels nguyên nghĩa; drop numeric invalid đồng thời ở X/y/identity, không fit gì."""
    features = features.copy()
    features.columns = normalize_column_names(features.columns.tolist())
    labels = pd.Series(np.asarray(labels)).reset_index(drop=True)
    if len(features) != len(labels):
        raise ValueError('External feature/label row counts không khớp')
    values = features.apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
    invalid = values.isna().any(axis=1).to_numpy() | labels.isna().to_numpy() | labels.astype(str).str.strip().eq('').to_numpy()
    raw_labels = labels.astype(str).str.strip().to_numpy()
    if dataset == 'CIC-UNSW-NB15':
        numeric = pd.to_numeric(labels, errors='raise').to_numpy()
        if not np.isin(numeric, list(UNSW_LABELS)).all():
            raise ValueError('UNSW Label ID không thuộc Readme.txt mapping 0..9')
        binary = (numeric != 0).astype(np.int8)
    elif dataset == 'CSE-CIC-IDS2018':
        binary = (np.char.lower(raw_labels.astype(str)) != 'benign').astype(np.int8)
    else:
        raise ValueError('Dataset adapter không hỗ trợ')
    with np.errstate(over='ignore'):
        matrix = values.to_numpy(dtype=np.float32)
    invalid |= ~np.isfinite(matrix).all(axis=1)
    keep = ~invalid
    return {'features': matrix[keep], 'feature_names': list(features.columns),
            'raw_labels': raw_labels[keep], 'binary_labels': binary[keep],
            'row_offsets': np.flatnonzero(keep) + row_offset,
            'input_rows': len(features), 'invalid_rows': int(invalid.sum())}


def iter_external_batches(dataset, root, *, rows_per_file=1000, chunksize=100000):
    root = Path(root)
    if dataset == 'CSE-CIC-IDS2018':
        files = sorted(root.glob('*.csv'))
        if not files:
            raise FileNotFoundError('Không có CSV hoàn chỉnh có extension .csv')
        schema = None
        for path in files:
            offset = 0
            with closing(pd.read_csv(path, chunksize=chunksize, nrows=rows_per_file, low_memory=False)) as reader:
                for frame in reader:
                    frame.columns = normalize_column_names(frame.columns.tolist())
                    if 'Label' not in frame or 'Timestamp' not in frame:
                        raise ValueError(f'{path.name}: thiếu Label/Timestamp')
                    native = [c for c in frame.columns if c not in {'Label', 'Timestamp', 'Flow ID', 'Src IP', 'Dst IP'}]
                    if schema is not None and native != schema:
                        raise ValueError('CSE schemas không nhất quán; cần adapter version riêng, không fill cột thiếu')
                    schema = native
                    batch = adapt_frame(frame[native], frame['Label'], dataset, offset)
                    yield path.name, batch
                    offset += len(frame)
    elif dataset == 'CIC-UNSW-NB15':
        # Lable.csv có HEADER Label; không dùng header=None như script khám phá cũ.
        with closing(pd.read_csv(root / 'Data.csv', chunksize=chunksize, nrows=rows_per_file, low_memory=False)) as features, closing(pd.read_csv(root / 'Lable.csv', chunksize=chunksize, nrows=rows_per_file)) as labels:
            offset = 0
            for x, y in zip_longest(features, labels):
                if x is None or y is None or list(y.columns) != ['Label'] or len(x) != len(y):
                    raise ValueError('UNSW Data.csv/Lable.csv header hoặc alignment không khớp')
                batch = adapt_frame(x, y['Label'], dataset, offset)
                yield 'Data.csv + Lable.csv', batch
                offset += len(x)
    else:
        raise ValueError('Dataset không được hỗ trợ')


def approved_shared_features(batch, canonical_names, specification):
    """Chỉ dùng map có phê duyệt semantics/units; giao tên cột không đủ chứng minh tương đương."""
    if specification.get('approved') is not True or not specification.get('units_and_extractor_evidence'):
        raise ValueError('REQUIRES RESEARCHER APPROVAL: shared feature semantics/units')
    mapping = specification.get('canonical_to_native', {})
    if set(mapping) != set(canonical_names) or len(set(mapping.values())) != len(mapping):
        raise ValueError('Feature mapping thiếu/thừa hoặc nhiều canonical dùng chung một nguồn')
    names = batch['feature_names']
    if any(mapping[name] not in names for name in canonical_names):
        raise ValueError('Không được tự fill thiếu feature bằng 0')
    return batch['features'][:, [names.index(mapping[name]) for name in canonical_names]]


def inspect_external(dataset, root, primary_features, rows_per_file=1000):
    counts, binary = Counter(), Counter()
    files = {}
    names = None
    for name, batch in iter_external_batches(dataset, root, rows_per_file=rows_per_file):
        names = batch['feature_names']
        counts.update(batch['raw_labels'].tolist())
        binary.update(map(int, batch['binary_labels']))
        info = files.setdefault(name, {'input_rows': 0, 'invalid_rows': 0})
        info['input_rows'] += batch['input_rows']
        info['invalid_rows'] += batch['invalid_rows']
    names = names or []
    return {'dataset': dataset, 'root': str(Path(root).resolve()), 'mode': 'full_scan' if rows_per_file is None else 'prefix_sample_NOT_global_distribution',
            'rows_per_file': rows_per_file, 'files': files, 'native_feature_names': names,
            'valid_raw_label_counts': dict(counts), 'valid_binary_counts': dict(binary),
            'label_mapping': UNSW_LABELS if dataset == 'CIC-UNSW-NB15' else 'Benign case-insensitive -> 0; other raw nonempty labels -> 1; retain raw names',
            'exact_name_intersection_NOT_semantic_approval': [n for n in primary_features if n in names],
            'missing_exact_primary_features': [n for n in primary_features if n not in names],
            'unrecognized_non_csv_files': [p.name for p in sorted(Path(root).glob('*.csv.*'))],
            'cross_dataset_inference': 'NOT REPRODUCIBLE: shared features/units/extractor/ontology not approved; no models trained',
            'intra_dataset_replication': 'adapter implemented; native-schema training integration/split protocol pending approval'}
