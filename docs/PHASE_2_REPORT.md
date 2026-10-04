# Phase 2 Report - CICIDS2017 Data Pipeline

Date: 2026-10-04

## Scope

Phase 2 implements dataset audit, non-lossy label derivation, leakage-aware feature
selection, exact-duplicate removal, reproducible train/validation/test allocation, and
train-only standardization. No machine-learning model was created or trained.

## Source data

The canonical input consists of the five daily CSV files under `CICIDS2017/`. Raw files
were read only. Their SHA-256 checksums are stored in
`artifacts/metadata/raw_manifest.json`.

## Audit result

- Raw rows: 2,099,971
- Columns: 89
- Raw labels: 27
- Missing values: 0
- Positive/negative infinity values: 0
- Invalid numeric values: 0
- Globally constant columns: 0
- Exact duplicate occurrences detected by row hash: 3,167

## Cleaning and feature policy

- Valid unique rows retained: 2,096,804
- Invalid rows removed: 0
- Exact duplicates removed before splitting: 3,167
- Model features retained: 84
- Numeric storage type: `float32`
- Attempted labels remain separate; they are not silently merged into parent classes.

The main feature matrix excludes `Label`, `Attempted Category`, `Timestamp`,
`Src IP dec`, and `Dst IP dec`. Reasons are recorded in
`artifacts/metadata/excluded_features.json`. Ports and protocol remain available for a
later ablation experiment.

## Reproducible split

Random state: 42

| Split | Rows |
|---|---:|
| Train | 1,467,762 |
| Validation | 314,521 |
| Test | 314,521 |

All 27 exact labels were retained. Classes with at least three samples receive at least
one validation and one test sample. Metrics for extremely rare labels must be reported
as unstable and must not drive model selection.

## Leakage controls verified

- Every retained row hash is unique.
- Saved train, validation, and test indices agree with the split assignment array.
- Raw and scaled feature arrays contain no NaN or infinity.
- The scaler was fitted on exactly 1,467,762 training rows.
- Maximum absolute mean over scaled training features: approximately `1.27e-08`.
- Standard deviation of non-constant scaled training features is approximately 1.0.
- Validation and test values were transformed without changing scaler state.

## Generated artifacts

Small, versionable metadata and tables:

- `results/dataset_summary.csv`
- `results/label_distribution.csv`
- `results/data_quality_report.json`
- `results/split_summary.csv`
- `artifacts/metadata/raw_manifest.json`
- `artifacts/metadata/schema.json`
- `artifacts/metadata/feature_names.json`
- `artifacts/metadata/label_mapping.json`
- `artifacts/metadata/source_mapping.json`
- `artifacts/metadata/cleaning_report.json`
- `artifacts/metadata/split_config.json`

Large generated arrays under `data/processed/` are intentionally ignored by Git. The
two feature matrices are approximately 672 MiB each.

## Verification commands

```powershell
python scripts\00_audit_dataset.py --config configs\base.json
python scripts\01_prepare_data.py --config configs\base.json --max-rows-per-file 1000 --output-dir data\interim\smoke
python scripts\01_prepare_data.py --config configs\base.json
python -m unittest discover -s tests -v
```

Eight unit tests passed. The integration checks above also passed.

## Remaining environment issue

Windows currently has no registered system Python interpreter. Phase 2 was verified with
the read-only Python runtime bundled with Codex. Before Phase 3, install Python 3.10-3.12,
create the project `.venv`, install `requirements.txt`, and repeat the test suite from
that environment. This environment task does not invalidate the generated Phase 2 data
artifacts.
