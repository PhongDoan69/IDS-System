# IDS System - CICIDS2017 Research Pipeline

This repository implements the experimental pipeline for a master's thesis on
machine-learning-based intrusion detection. The current completed scope is Phase 2:
dataset audit, non-lossy label derivation, leakage-aware feature selection,
reproducible train/validation/test splitting, and train-only scaling.

No raw file under `CICIDS2017/` is modified.

## Dataset

Place these five verified CSV files under `CICIDS2017/`:

- `monday.csv`
- `tuesday.csv`
- `wednesday.csv`
- `thursday.csv`
- `friday.csv`

The pipeline deliberately ignores legacy merged/preprocessed CSV files because their
delimiter and header integrity has not been established.

## Environment

Install a normal 64-bit Python 3.10-3.12 distribution first, then run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For a CUDA-specific PyTorch wheel, follow the official PyTorch selector for the CUDA
version installed on the machine instead of assuming that a local-version wheel is
available from PyPI.

## Phase 2 commands

Audit without modifying raw data:

```powershell
.\.venv\Scripts\python.exe scripts\00_audit_dataset.py --config configs\base.json
```

Smoke preparation (1,000 rows per source file):

```powershell
.\.venv\Scripts\python.exe scripts\01_prepare_data.py --config configs\base.json --max-rows-per-file 1000 --output-dir data\interim\smoke
```

Full preparation:

```powershell
.\.venv\Scripts\python.exe scripts\01_prepare_data.py --config configs\base.json
```

Tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Leakage controls

- Exact duplicate rows are removed before splitting.
- `Label`, `Attempted Category`, `Timestamp`, `Src IP dec`, and `Dst IP dec` are
  excluded from the main feature matrix with reasons stored in
  `artifacts/metadata/excluded_features.json`.
- Attempted labels are preserved rather than silently merged.
- The scaler is fitted only on rows assigned to the training split.
- Validation and test rows are transformed using the frozen training scaler.
- Split IDs and row hashes are saved for reuse by all subsequent experiments.

## Planned later phases

Phase 3 onward will add the Autoencoder, raw-feature baselines, Stage 1 XGBoost/MLP,
OOF attack probabilities, Stage 2 multiclass classification, and leave-one-attack-class-out
novelty experiments. These models are intentionally not implemented in Phase 2.
