"""Descriptive matched-seed summaries; never turn repeated rows into IID evidence."""
from __future__ import annotations
from collections import defaultdict
import numpy as np


def summarize_rows(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['heldout'], row['gate'], row['method'])].append(row)
    metrics = ['recall', 'precision', 'f1', 'known_frr', 'benign_unknown', 'blocked_unknown', 'e2e_macro_f1']
    summary = []
    for (held, gate, method), records in sorted(groups.items()):
        if len({r['seed'] for r in records}) != len(records):
            raise ValueError('Duplicate seed/heldout/gate/method summary unit')
        entry = {'heldout': held, 'gate': gate, 'method': method,
                 'seeds': sorted(r['seed'] for r in records), 'n_fits': len(records),
                 'test_support_per_fit': sorted({r['support'] for r in records})}
        for metric in metrics:
            v = np.asarray([r[metric] for r in records], dtype=float)
            entry[metric] = {'mean': float(v.mean()), 'sample_std': float(v.std(ddof=1)) if len(v)>1 else None,
                             'min': float(v.min()), 'max': float(v.max())}
        summary.append(entry)
    lookup = {(r['heldout'], r['seed'], r['gate'], r['method']): r for r in rows}
    paired = []
    for r in rows:
        if r['method'] != 'knn_distance':
            continue
        for baseline in ['max_probability', 'mahalanobis']:
            b = lookup[(r['heldout'], r['seed'], r['gate'], baseline)]
            if r['support'] != b['support'] or r['blocked_unknown'] != b['blocked_unknown']:
                raise ValueError('Unmatched population/gate in paired comparison')
            paired.append({'heldout': r['heldout'], 'seed': r['seed'], 'gate': r['gate'], 'baseline': baseline,
                           **{f'delta_{m}': float(r[m]-b[m]) for m in metrics}})
    return {'unit': 'one fitted chain per heldout/seed; same test rows reused across seeds',
            'independent_test_datasets': 0, 'inferential_significance_test': 'NOT PERFORMED',
            'groups': summary, 'paired_knn_minus_baseline': paired}
