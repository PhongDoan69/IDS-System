r"""Chạy pipeline IDS cho CSE-CIC-IDS2018 — một entrypoint trong project hiện tại.

CHỈ SCRIPT; khi không có --run tuyệt đối không train.
PowerShell / VS Code:
  Set-Location 'D:\CAO HOC\IDS System'
  .\.venv\Scripts\python.exe -X utf8 -u -B scripts/09_run_cse_cic_ids2018.py --check-only
  .\.venv\Scripts\python.exe -X utf8 -u -B scripts/09_run_cse_cic_ids2018.py --audit-only
  .\.venv\Scripts\python.exe -X utf8 -u -B scripts/09_run_cse_cic_ids2018.py --self-test
  .\.venv\Scripts\python.exe -X utf8 -u -B scripts/09_run_cse_cic_ids2018.py --run --run-id zd_v2 --held-out-labels "TEN_ATTACK_1" "TEN_ATTACK_2"

Thay tên heldout bằng tên native chính xác từ --audit-only, chốt trước chạy.
--held-out-label "TEN_ATTACK" vẫn được hỗ trợ cho một lớp.
Nếu CHỈ cần closed-set: --run --run-id closed_v2 --closed-set-only.
Không đưa --closed-set-only cùng heldout; không tự chọn hoặc bỏ lớp theo điểm test.

CHUẨN HÓA ĐẦU VÀO VÀ PHƯƠNG PHÁP:
- Áp dụng cùng phương pháp với CICIDS2017, HUẤN LUYỆN LẠI trên từng dataset.
  Không chuyển weights/scaler CICIDS2017; không khẳng định zero-shot transfer.
- Giữ schema native và thứ tự cột đã kiểm tra; không ép 84 cột bằng zero-fill,
  không tự đồng nhất feature units/extractor chỉ vì tên gần giống.
- Bỏ Label/Timestamp/IP/Flow ID khỏi X; chặn annotation/derived label còn sót.
  Float32 hữu hạn; drop NaN/Inf/overflow đồng bộ X/y; không impute/clip theo test.
  BENIGN=0, attack IDs native riêng, unknown=-1 CHỈ trong đánh giá cuối.
- Dedup float32 X + nhãn trước split; KHÁC full-row dedup CICIDS2017.
  Random stratified 70/15/15, seed42; vẫn báo feature-overlap và rare support.
- Z-score theo mean/variance TRAIN, constant scale=1; val/test chỉ transform.
  Mỗi LOACO fit lại scaler known-only. OOF 5-fold fit scaler/AE inner-fit,
  early-stop/calibration inner known train; không nối latent khác fold vào Stage2.
- AE native_dim->64->32->16; 4 Stage1 (XGB/MLP x scaled/latent),
  4 Stage2 (XGB/MLP x latent/latent+P_attack), 4 closed-set cascade.
  Primary khóa từ validation CICIDS2017: XGB latent gate0.5 + latent_plus_pattack_xgb.
  External validation winner chỉ báo cáo secondary, KHÔNG thay primary.
- Giữ reference config đợt1: CUDA runtime theo wheel cu130, không theo mức tối đa
  driver; AE/MLP batch8192, tối đa100epochs, XGB hist/max_bin128/1500trees.
  Không tự giảm mẫu/budget khi thiếu RAM/VRAM/disk. Chạy dataset lần lượt.
- Với mỗi heldout: train lại TOÀN CHAIN, không reuse closed-set weights.
  Loại heldout khỏi fit, early-stop, calibration và threshold. Novelty gồm
  max_probability, one_class_svm, isolation_forest; q95 từ KNOWN-ATTACK validation.
  Unknown chỉ đánh giá trên heldout TEST, không đưa heldout train/val vào test.
  Mỗi lớp có run ID riêng; tối thiểu500 heldout test theo benchmark hiện có.
  Danh sách/support được khóa trong zero_day_plan.json TRƯỚC model fit.
- LOACO là MÔ PHỎNG zero-day theo lớp chưa thấy, không chứng minh zero-day thực tế;
  attack family liên quan có thể vẫn nằm trong known classes. Cần family-heldout,
  temporal/group split và nhiều seed để kết luận tổng quát hóa mạnh hơn.

CHẠY VÀ ĐỌC KẾT QUẢ:
- --check-only: header/inventory. --audit-only: đọc toàn bộ, không ghi/fit,
  in số lượng nhãn sau cleaning/dedup để bạn chốt lớp heldout.
- CSE còn *.csv.* / *.part sẽ bị chặn: chờ dữ liệu đầy đủ; chỉ chủ động thêm
  --allow-partial-dataset nếu chấp nhận kết quả TẬP CON. Giao cột giữa các ngày
  khác schema cần --allow-schema-intersection, luôn ghi rõ các cột bị bỏ.
- UNSW đọc Data.csv và Lable.csv (header Label), không cắt ngắn khi lệch hàng.
- --run tạo config/artifacts MỚI trong project, không overwrite/resume run cũ;
  cần src/ và scripts/02..08 hiện có, không cần script dataset còn lại.
- results/research_rounds/<dataset_run>/ chứa status.json, logs/, protocol_lock.json,
  normalization_checks.json, zero_day_plan.json, comparison.json,
  zero_day_comparison.csv và RESEARCH_REPORT.md. Đọc unknown recall/F1 SAU GATE,
  known false rejection, benign->unknown, support và error decomposition;
  AUROC score-only cao không đảm bảo recall sau gate cao.
- Không kết luận từ accuracy closed-set; không chọn detector/heldout tốt nhất theo
  test; báo toàn bộ lớp đã đăng ký. Multi-heldout vẫn một seed, không CI độc lập.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing, contextmanager
import csv
from datetime import datetime, timezone
import gc
import importlib.util
from itertools import zip_longest
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATASET = "CSE-CIC-IDS2018"
SLUG = "cse2018"
PRIMARY = "latent_plus_pattack_xgb"  # Khóa từ validation CICIDS2017, KHÔNG chọn lại bằng external test.
PHASES = {"01b_prepare_protocol.py", "02_train_autoencoder.py", "03_train_stage1.py",
          "04_train_stage2.py", "05_train_novelty.py", "06_evaluate_pipeline.py"}
INPUT_PROTOCOL = "external_native_v2_zero_day"
EXCLUDED = {"Label", "Timestamp", "Flow ID", "Src IP", "Dst IP", "Src IP dec", "Dst IP dec",
            "Source IP", "Destination IP", "FlowID"}
FORBIDDEN_TARGETS = {"attemptedcategory", "attacklabelraw", "attacklabelnormalized", "binarylabel",
                     "isattempted", "attackfamily", "labelid", "target", "category", "class"}

# Tái sử dụng runner trong project, không phụ thuộc script của dataset còn lại.
_spec = importlib.util.spec_from_file_location("ids_round_base", ROOT / "scripts/08_run_research_round.py")
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
from src.external_data import adapt_frame, UNSW_LABELS
from src.data_loader import normalize_column_names
from src.split_data import constrained_stratified_split, split_summary
from src.model_config import experiment_id, validate_model_config
from src.training_utils import save_json
import numpy as np
import pandas as pd


def header(path):
    """Đọc trước pandas để phát hiện header trùng, tránh pandas tự đổi thành .1."""
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return normalize_column_names(next(csv.reader(stream), []))


def inspect_input(directory, allow_partial=False, allow_intersection=False, enforce=False):
    """Không đọc toàn dataset, không ghi file, không fit khi chỉ preflight."""
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    warnings, blockers = [], []
    if DATASET == "CSE-CIC-IDS2018":
        files = sorted(directory.glob("*.csv"))
        suspicious = sorted(set(directory.glob("*.csv.*")) | set(directory.glob("*.part")) | set(directory.glob("*.crdownload")))
        if not files:
            raise FileNotFoundError("Không có file .csv trong " + str(directory))
        if suspicious:
            warnings.append("Tệp chưa xác nhận hoàn chỉnh bị loại: " + ", ".join(p.name for p in suspicious))
            if not allow_partial:
                blockers.append("Cần hoàn thiện/xác minh dataset hoặc truyền --allow-partial-dataset để CHẤP NHẬN chạy tập con.")
        schemas = {}
        for path in files:
            cols = header(path)
            if "Label" not in cols or "Timestamp" not in cols:
                raise ValueError(f"{path.name}: thiếu Label/Timestamp")
            schemas[path.name] = [c for c in cols if c not in EXCLUDED]
        first = next(iter(schemas.values()))
        common = set(first).intersection(*map(set, schemas.values()))
        if any(v != first for v in schemas.values()):
            warnings.append("Các CSV khác schema/order; dùng giao tên native, thứ tự theo CSV đầu, KHÔNG zero-fill.")
            if not allow_intersection:
                blockers.append("Cần --allow-schema-intersection để xác nhận harmonization trong CSE.")
        names = [n for n in first if n in common]
        dropped = {k: [n for n in v if n not in common] for k, v in schemas.items()}
        partial = bool(suspicious)
    else:
        files = [directory / "Data.csv", directory / "Lable.csv"]
        if not all(p.is_file() for p in files):
            raise FileNotFoundError("Cần Data.csv và Lable.csv (đúng spelling Lable).")
        if header(files[1]) != ["Label"]:
            raise ValueError("Lable.csv phải có header Label, không được đọc header=None.")
        names = header(files[0])
        if any(c in EXCLUDED or c.startswith("Unnamed:") for c in names):
            raise ValueError("Data.csv chứa annotation/identifier không thuộc native schema; cần kiểm tra nguồn.")
        dropped, partial = {}, False
    suspicious_features = [n for n in names if "".join(c for c in n.casefold() if c.isalnum()) in FORBIDDEN_TARGETS]
    if suspicious_features:
        raise ValueError(f"Annotation/target trong predictors: {suspicious_features}; không train.")
    if "__target__" in names:
        raise ValueError("Tên predictor __target__ được dành riêng cho fingerprint.")
    if not names:
        raise ValueError("Không còn predictor.")
    info = {"dataset": DATASET, "directory": str(directory), "files": [str(p) for p in files],
            "feature_names": names, "input_dim": len(names), "dropped_noncommon_features": dropped,
            "partial_dataset": partial, "warnings": warnings, "blocking_reasons": blockers,
            "completeness": "Local inventory only; upstream release/completeness NOT verified"}
    if enforce and blockers:
        raise ValueError("\n".join(blockers))
    return info


def batches(info, chunksize):
    """X/y drop invalid đồng bộ; không fit scaler ở đây; raw CSV không bị sửa."""
    names = info["feature_names"]
    if DATASET == "CSE-CIC-IDS2018":
        for source, path in enumerate(map(Path, info["files"])):
            offset = 0
            with closing(pd.read_csv(path, chunksize=chunksize, low_memory=False, encoding="utf-8-sig")) as reader:
                for frame in reader:
                    frame.columns = normalize_column_names(frame.columns.tolist())
                    batch = adapt_frame(frame[names], frame["Label"], DATASET, offset)
                    yield source, batch
                    offset += len(frame)
    else:
        with closing(pd.read_csv(info["files"][0], chunksize=chunksize, low_memory=False)) as xs, closing(pd.read_csv(info["files"][1], chunksize=chunksize)) as ys:
            offset = 0
            for x, y in zip_longest(xs, ys):
                if x is None or y is None or list(y.columns) != ["Label"] or len(x) != len(y):
                    raise ValueError("Data.csv và Lable.csv lệch hàng/header; không tự cắt ngắn.")
                x.columns = normalize_column_names(x.columns.tolist())
                batch = adapt_frame(x[names], y["Label"], DATASET, offset)
                yield 0, batch
                offset += len(x)


def targets(batch):
    if DATASET == "CIC-UNSW-NB15":
        # Giữ native IDs 0..9; tên nhãn gốc trong Readme; chỉ tên BENIGN chuẩn hóa.
        return np.array([str(int(float(x))) for x in batch["raw_labels"]])
    values = batch["raw_labels"].copy()
    values[batch["binary_labels"] == 0] = "BENIGN"
    return values


def fingerprints(batch):
    """Dedup native float32 predictors + target, KHÔNG dedup bằng row number.
    Đây là policy external_native_v1, khác full-89-column dedup của CICIDS2017.
    Metadata timestamp/IP đã loại khỏi predictors và không dùng để dedup.
    Các vector cùng X nhưng khác nhãn được giữ; báo overlap, không gộp nhãn ngầm.
    """
    frame = pd.DataFrame(batch["features"], columns=batch["feature_names"])
    feature_hash = pd.util.hash_pandas_object(frame, index=False).to_numpy(dtype=np.uint64)
    frame["__target__"] = targets(batch)
    row_hash = pd.util.hash_pandas_object(frame, index=False).to_numpy(dtype=np.uint64)
    return feature_hash, row_hash


def manifest(info):
    return [{"path": p, "bytes": Path(p).stat().st_size, "sha256": _base.digest(p)} for p in info["files"]]



def input_contract(info):
    """Cùng giao thức số học, không khẳng định schema/units/ontology tương đương."""
    return {
        "version": INPUT_PROTOCOL, "dataset": DATASET,
        "feature_order": info["feature_names"], "input_dim": info["input_dim"],
        "matrix_dtype": "float32", "missing_nonfinite_overflow": "drop row jointly in X/y; no imputation",
        "labels": "BENIGN=0; native attacks retain separate IDs; unknown=-1 only at evaluation",
        "scaler": "population z-score (x-mean_train)/std_train; constant scale=1",
        "main_fit_scope": "train only", "loaco_fit_scope": "train excluding the heldout class",
        "oof_fit_scope": "inner-fit only; scaler and AE refit per fold",
        "validation_test": "transform only; no fit, clipping, tuning or threshold selection from test",
        "input_dim_policy": "native columns; no zero-padding to CICIDS2017 84 columns",
        "transfer_claim": "same method retrained per dataset; NOT cross-dataset model transfer",
        "units_and_extractor_equivalence": "NOT VERIFIED; no automatic cross-dataset column mapping",
    }


def label_mapping(native_labels):
    if DATASET == "CIC-UNSW-NB15":
        return {str(int(n)): ("BENIGN" if int(n) == 0 else UNSW_LABELS[int(n)])
                for n in sorted(native_labels, key=int)}
    attacks = sorted(n for n in native_labels if n != "BENIGN")
    return {"0": "BENIGN", **{str(i + 1): n for i, n in enumerate(attacks)}}


def plan_heldouts(mapping, y, split, requested, minimum):
    """Pre-register every requested case BEFORE any model fit. Never silently skip.
    Support checks are label counts, not model scores; do not lower the benchmark
    minimum or auto-select a 'good' heldout after inspecting test performance.
    """
    names = [requested] if isinstance(requested, str) else list(requested or [])
    if len(set(names)) != len(names):
        raise ValueError("Heldout list bị trùng; mỗi lớp chỉ chạy một lần.")
    cases = []
    for name in names:
        matches = [int(i) for i, label in mapping.items() if label == name]
        if len(matches) != 1 or matches[0] == 0:
            raise ValueError(f"Heldout phải là tên native attack, không phải ID/benign: {name}. Mapping: {mapping}")
        heldout = matches[0]
        counts = {part: int(np.sum((y == heldout) & (split == s)))
                  for s, part in enumerate(["train", "validation", "test"])}
        if counts["test"] < minimum:
            raise ValueError(f"{name}: test support={counts['test']} < {minimum}; không tự hạ ngưỡng hoặc bỏ lớp.")
        if len(mapping) < 4:
            raise ValueError("LOACO phải còn ít nhất hai known attack classes.")
        cases.append({"label_id": heldout, "label": name, "support": counts,
                      "excluded_from_fit": ["scaler", "AE", "OOF", "Stage1", "Stage2", "novelty"],
                      "excluded_from_selection": ["early stopping", "calibration", "threshold"],
                      "unknown_evaluation_scope": "heldout TEST rows only; heldout train/validation unused"})
    return cases


def audit_input(info, chunksize):
    """Full raw read, float32 cleaning/dedup and label counts; NO fit or artifact writes.
    Display native names before the researcher pre-registers heldouts. No ranking by scores.
    """
    counts, seen = Counter(), set()
    total = invalid = duplicates = 0
    before = manifest(info)
    for _, batch in batches(info, chunksize):
        total += batch["input_rows"]
        invalid += batch["invalid_rows"]
        _, hashes = fingerprints(batch)
        for h, name in zip(hashes, targets(batch)):
            if int(h) in seen:
                duplicates += 1
            else:
                seen.add(int(h))
                counts[str(name)] += 1
    if manifest(info) != before:
        raise ValueError("Raw input changed during audit.")
    mapping = label_mapping(counts)
    rows = []
    for native, count in sorted(counts.items()):
        test = max(1, int(round(count * .15))) if count >= 2 else 0
        rows.append({"native_label": mapping[native] if DATASET == "CIC-UNSW-NB15" else native,
                     "clean_unique_count": count, "expected_test_support": test})
    return {"mode": "FULL_AUDIT_NO_TRAIN", "input_contract": input_contract(info),
            "input_rows": total, "invalid_rows": invalid, "duplicates": duplicates,
            "classes": rows, "raw_manifest": before, "blocking_reasons": info["blocking_reasons"],
            "partial_dataset": info["partial_dataset"],
            "note": "Counts only; no heldout auto-selection. Actual split/LOACO eligibility checked again before fit."}


def zero_day_rows(opened):
    """One row per heldout/detector. Keep score-only and AFTER-GATE populations distinct."""
    rows = []
    for case in opened.values():
        for method, report in case["methods"].items():
            final = report["final_unknown_metrics"]
            score = report.get("score_only_unknown_metrics", {})
            rows.append({"heldout": case["label"], "heldout_id": case["label_id"], "method": method,
                "unknown_test_feature_matches_known_train": case.get("unknown_test_feature_matches_known_train"),
                "unknown_support": final["unknown_support"],
                "known_attack_support": final["known_attack_support"],
                "final_precision": final["precision"], "final_recall": final["recall"], "final_f1": final["f1"],
                "unknown_detected": final["unknown_detected"],
                "unknown_blocked_by_gate": final["unknown_blocked_by_stage1"],
                "known_attack_false_rejection": final["known_attack_false_rejection_rate"],
                "benign_rejected_unknown": final["benign_rejected_unknown"],
                "score_only_auroc": score.get("open_set_roc_auc"),
                "score_only_average_precision": score.get("open_set_pr_auc"),
                "e2e_macro_f1": report["end_to_end_metrics"]["macro_f1"],
                "evaluation_population": "full test AFTER predicted Stage1 gate",
                "score_only_population": "full test BEFORE gate; includes benign as known"})
    return rows


def prepare(info, destination, chunksize, heldout_names=None, min_unknown=500):
    """Hai lượt đọc, memmap float32; không ghép toàn X vào RAM.
    Dừng nếu thiếu dung lượng; không giảm mẫu để vừa máy hoặc làm đẹp metric.
    """
    if destination.exists():
        raise FileExistsError(f"Không overwrite: {destination}")
    destination.mkdir(parents=True)
    meta = destination / "metadata"
    meta.mkdir()
    before = manifest(info)
    save_json(meta / "raw_manifest.json", before)
    seen, temporary_mapping = set(), {}
    parts = {k: [] for k in ["hashes", "feature_hashes", "labels", "source_ids", "row_offsets"]}
    input_count = invalid_count = duplicate_count = 0
    raw_counts = Counter()
    for source, batch in batches(info, chunksize):
        input_count += batch["input_rows"]
        invalid_count += batch["invalid_rows"]
        feature_h, row_h = fingerprints(batch)
        keep = np.zeros(len(row_h), dtype=bool)
        for i, h in enumerate(row_h):
            key = int(h)
            if key in seen:
                duplicate_count += 1
            else:
                seen.add(key)
                keep[i] = True
        names = targets(batch)[keep]
        raw_counts.update(names.tolist())
        for label in np.unique(names):
            temporary_mapping.setdefault(str(label), len(temporary_mapping))
        parts["hashes"].append(row_h[keep])
        parts["feature_hashes"].append(feature_h[keep])
        parts["labels"].append(np.array([temporary_mapping[str(n)] for n in names], dtype=np.int32))
        parts["source_ids"].append(np.full(int(keep.sum()), source, dtype=np.int16))
        parts["row_offsets"].append(batch["row_offsets"][keep].astype(np.int64))
        print(f"[prepare pass1] input={input_count:,} unique={len(seen):,} invalid={invalid_count:,}", flush=True)
    if not seen:
        raise ValueError("Không có dòng hợp lệ.")
    arrays = {k: np.concatenate(v) for k, v in parts.items()}
    del parts, seen
    gc.collect()
    mapping = label_mapping(temporary_mapping)
    if DATASET == "CIC-UNSW-NB15":
        conversion = np.array([int(n) for n in temporary_mapping], dtype=np.int16)
    else:
        reverse = {name: int(i) for i, name in mapping.items()}
        conversion = np.array([reverse[n] for n in temporary_mapping], dtype=np.int16)
    if mapping.get("0") != "BENIGN" or not np.any(conversion == 0) or len(mapping) < 3:
        raise ValueError("Cần BENIGN và ít nhất hai attack classes.")
    y = conversion[arrays["labels"]]
    split = constrained_stratified_split(y, train_ratio=.7, validation_ratio=.15, test_ratio=.15, random_state=42)
    cases = plan_heldouts(mapping, y, split, heldout_names, min_unknown)
    # Random split is not automatically leakage-free. Quantify identical X across
    # different labels specifically for each LOACO; do not silently resplit/drop.
    for case in cases:
        heldout = case["label_id"]
        known_train_hashes = np.unique(arrays["feature_hashes"][(split == 0) & (y != heldout)])
        unknown_test_hashes = arrays["feature_hashes"][(split == 2) & (y == heldout)]
        case["unknown_test_feature_matches_known_train"] = int(np.isin(unknown_test_hashes, known_train_hashes).sum())
        case["overlap_interpretation"] = "identical float32 X across labels; independence risk, NOT temporal/group validation"
    for c in np.unique(y):
        if not all(np.any((y == c) & (split == s)) for s in [0, 1, 2]):
            raise ValueError(f"Class {c} không phủ đủ train/val/test; cần quyết định protocol, không oversample test.")
    n, d = len(y), len(info["feature_names"])
    # Tính dư cho raw, common/fold/LOACO scaled, latent, class probabilities và overhead.
    required = int(n * (4 * d * (4 + len(cases)) + (256 + len(mapping) * 8) * (1 + len(cases))) + 2 * 1024**3)
    free = shutil.disk_usage(destination).free
    if free < required:
        raise RuntimeError(f"Cần khoảng {required / 1024**3:.1f} GiB trống, đang có {free / 1024**3:.1f} GiB. Không tự subsample.")
    raw = np.lib.format.open_memmap(destination / "features_raw.npy", mode="w+", dtype=np.float32, shape=(n, d))
    cursor = 0
    try:
        for source, batch in batches(info, chunksize):
            # Dùng offset/source đã chốt ở pass1; không fit, không chọn lại hàng.
            offsets = batch["row_offsets"]
            if not len(offsets):
                continue
            end = cursor
            while end < n and arrays["source_ids"][end] == source and arrays["row_offsets"][end] <= offsets[-1]:
                end += 1
            wanted = arrays["row_offsets"][cursor:end]
            positions = np.searchsorted(offsets, wanted)
            if len(wanted) and (np.any(positions >= len(offsets)) or not np.array_equal(offsets[positions], wanted)):
                raise ValueError("Row alignment thay đổi giữa hai pass.")
            _, hashes = fingerprints(batch)
            if not np.array_equal(hashes[positions], arrays["hashes"][cursor:end]):
                raise ValueError("Row content/order thay đổi giữa hai pass.")
            raw[cursor:end] = batch["features"][positions]
            cursor = end
        if cursor != n or manifest(info) != before:
            raise ValueError("Nguồn thay đổi trong preparation hoặc thiếu hàng.")
        raw.flush()
    finally:
        raw._mmap.close()
    for name, value in {"attack_label_ids": y, "binary_labels": (y != 0).astype(np.int8),
                        "split_ids": split, "row_hashes": arrays["hashes"],
                        "source_ids": arrays["source_ids"], "source_row_offsets": arrays["row_offsets"]}.items():
        np.save(destination / (name + ".npy"), value)
    for s, name in enumerate(["train", "validation", "test"]):
        np.save(destination / (name + "_indices.npy"), np.flatnonzero(split == s))
    train_hashes = np.unique(arrays["feature_hashes"][split == 0])
    overlap = {name: int(np.isin(arrays["feature_hashes"][split == s], train_hashes).sum()) for s, name in [(1, "validation_rows_matching_train_X"), (2, "test_rows_matching_train_X")]}
    summary = {"dataset": DATASET, "status": "completed", "samples": n, "input_dim": d,
               "input_rows": input_count, "invalid_rows": invalid_count, "duplicate_rows_removed": duplicate_count,
               "native_label_counts_after_clean_dedup": dict(raw_counts), "heldout_cases": cases,
               "label_mapping": mapping, "input_contract": input_contract(info), "feature_hash_overlap": overlap,
               "hash_note": "64-bit pandas hashes; collisions theoretically possible",
               "partial_dataset": info["partial_dataset"], "raw_manifest": before}
    save_json(meta / "feature_names.json", {"features": info["feature_names"]})
    save_json(meta / "label_mapping.json", mapping)
    save_json(meta / "source_mapping.json", {str(i): p for i, p in enumerate(info["files"][:1] if DATASET == "CIC-UNSW-NB15" else info["files"])})
    save_json(meta / "split_config.json", {"dataset": DATASET, "protocol": INPUT_PROTOCOL, "random_state": 42,
              "ratios": [.7, .15, .15], "strategy": "constrained_stratified_per_class",
              "dedup": "native float32 X + canonical native target; before split", "info": info})
    save_json(meta / "preparation_report.json", summary)
    split_summary(split, y, {int(k): v for k, v in mapping.items()}).to_csv(destination / "split_summary.csv", index=False)
    return summary


@contextmanager
def dataset_contract_scope():
    """Compatibility shim chỉ cho serializer của manifest.
    src/artifact_contracts.py có tên CICIDS2017 hardcoded. Thay tên trước khi ghi,
    KHÔNG sửa source chung, weights, validation, identity hashes hay artifact cũ.
    Phạm vi chỉ trong subprocess của script external; luôn restore khi thoát.
    """
    import src.artifact_contracts as contracts
    original = contracts.save_json
    def save_native(path, record):
        if isinstance(record, dict) and "dataset_identity" in record and "artifact_path" in record:
            record = {**record, "dataset_name": DATASET, "dataset_protocol": INPUT_PROTOCOL}
        original(path, record)
    contracts.save_json = save_native
    try:
        yield
    finally:
        contracts.save_json = original


def internal_phase(arguments):
    phase, *forward = arguments
    if Path(phase).name not in PHASES or phase != "scripts/" + Path(phase).name:
        raise ValueError("Internal phase không được phép.")
    if "--config" not in forward:
        raise ValueError("Thiếu config external.")
    cfg = _base.read(forward[forward.index("--config") + 1])
    if cfg["experiment"].get("dataset_name") != DATASET:
        raise ValueError("Config thuộc dataset khác.")
    old = sys.argv
    try:
        sys.argv = [str(ROOT / phase), *forward]
        with dataset_contract_scope():
            runpy.run_path(str(ROOT / phase), run_name="__main__")
    finally:
        sys.argv = old


class ExternalRound(_base.Round):
    def __init__(self, args, info):
        self.args, self.info = args, info
        self.normalization_checks = {}
        rid = args.run_id or (SLUG + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_s42")
        if not rid.startswith(SLUG + "_"):
            rid = SLUG + "_" + rid
        experiment_id({"experiment": {"id": rid}}, rid)
        self.directory = ROOT / "results/research_rounds" / rid
        self.processed = ROOT / "data/processed" / rid
        self.config = ROOT / "configs" / ("external_model_" + rid + ".json")
        self.base = ROOT / "configs" / ("external_data_" + rid + ".json")
        self.main_id = rid + "_main"
        for path in [self.directory, self.processed, self.config, self.base]:
            if path.exists():
                raise FileExistsError(f"Không overwrite/resume: {path}; dùng --run-id mới.")
        for run in [self.main_id]:
            for parent in ["models", "results", "artifacts/metadata"]:
                for phase in ["autoencoder", "stage1", "stage2", "novelty"]:
                    if (ROOT / parent / phase / run).exists():
                        raise FileExistsError(f"Artifact collision: {run}")
        model = _base.read(args.reference_config)
        validate_model_config(model)
        if model["experiment"]["random_state"] != 42 or model["evaluation"]["decision_threshold"] != .5 or model["novelty"]["known_rejection_rate"] != .05 or model["stage1"]["oof_folds"] != 5:
            raise ValueError("Script khóa seed 42/gate 0,5/known rejection 0,05/OOF 5 như đợt 1; không đổi ngầm.")
        if not model["hardware"]["require_cuda"] or not model["hardware"]["device"].startswith("cuda"):
            raise ValueError("Protocol yêu cầu CUDA, không fallback CPU.")
        model["experiment"].update(id=self.main_id, processed_dir=str(self.processed),
            prepared_metadata_dir=str(self.processed / "metadata"), base_data_config=str(self.base),
            models_dir="models", results_dir="results", metadata_dir="artifacts/metadata", dataset_name=DATASET)
        # Numeric fix v1: uniform FP32 encoding; AMP training remains unchanged.
        # Recorded explicitly so these results are not claimed bitwise-equivalent
        # to historical AMP-encoded runs. Never clip or rescale using unknown/test.
        model["hardware"]["encoding_precision"] = "float32"
        self.directory.mkdir(parents=True)
        (self.directory / "logs").mkdir()
        save_json(self.base, info)
        save_json(self.config, model)
        self.sources = {str(p): _base.digest(p) for folder in ["src", "scripts"] for p in sorted((ROOT / folder).glob("*.py"))}
        self.sources.update({str(self.config): _base.digest(self.config), str(self.base): _base.digest(self.base)})
        self.spec = {"round_id": rid, "dataset": DATASET, "task": "intra_dataset_retraining_NOT_zero_shot",
            "protocol": INPUT_PROTOCOL + " + revised_v1 training contracts", "created_utc": datetime.now(timezone.utc).isoformat(),
            "seed": 42, "primary_stage1": "xgboost_latent", "primary_stage2": PRIMARY,
            "primary_selection_source": "CICIDS2017 round1 validation; unchanged on external datasets",
            "secondary_selection": "external validation macro-F1, descriptive only; does not replace frozen primary",
            "gate_threshold": .5, "stage1": _base.STAGE1, "stage2": _base.VARIANTS,
            "heldout_labels_registered_before_training": args.held_out_labels,
            "loaco": "one independently retrained chain per requested native attack; no automatic test-based selection",
            "zero_day_claim": "class-heldout simulation only; NOT proof of real zero-day or cross-domain transfer",
            "input_contract": input_contract(info),
            "numeric_policy": "fp32_encoding_v1; all splits/folds; AMP training unchanged; no test-based clipping",
            "reference_config": str(Path(args.reference_config).resolve()), "reference_sha256": _base.digest(args.reference_config),
            "input": info, "source_hashes": self.sources,
            "limitations": ["native schemas/class ontologies differ; scores not directly comparable tasks",
                "random split may retain conflicting-label feature overlap; see preparation_report",
                "native X+label dedup differs from CICIDS2017 full-row dedup",
                "one seed; related known classes may overlap heldout family; no temporal/group test or proof of real zero-day",
                "subprocess time is not inference latency; no standalone deployment entrypoint"]}
        save_json(self.directory / "protocol_lock.json", self.spec)
        self.state = {"status": "running", "pid": os.getpid(), "started_utc": self.spec["created_utc"], "steps": []}
        self.persist()

    def step(self, name, arguments):
        if arguments and Path(str(arguments[0])).name in PHASES:
            arguments = [str(Path(__file__).resolve()), "--_phase", *arguments]
        super().step(name, arguments)

    def run(self):
        self.step("environment", ["scripts/verify_environment.py", "--config", self.config])
        self.verify_sources()
        item = {"name": "prepare_native", "status": "running", "started_utc": datetime.now(timezone.utc).isoformat()}
        self.state["steps"].append(item)
        self.state["current_step"] = item["name"]
        self.persist()
        started = time.perf_counter()
        try:
            self.prepared = prepare(self.info, self.processed, self.args.chunksize,
                self.args.held_out_labels, int(_base.read(self.config)["novelty"]["minimum_held_out_samples"]))
        except BaseException:
            item.update(status="failed", returncode=1, seconds=time.perf_counter() - started)
            self.persist()
            raise
        item.update(status="completed", returncode=0, seconds=time.perf_counter() - started)
        self.persist()
        # Pre-register ALL cases before any fit; an invalid/rare requested class fails the entire plan.
        save_json(self.directory / "zero_day_plan.json", {
            "input_protocol": INPUT_PROTOCOL, "cases": self.prepared["heldout_cases"],
            "primary_stage2": PRIMARY, "methods": _base.METHODS, "seed": 42,
            "threshold_source": "known attack validation only; rejection=0.05",
            "test_used_for_selection": False, "family_disjointness": "NOT GUARANTEED"})
        self.step("main_preprocessing", ["scripts/01b_prepare_protocol.py", "--config", self.config, "--run-id", self.main_id])
        self.verify_normalization(self.main_id, None)
        # Evaluator legacy loads root features_scaled only for shape/finite/identity.
        # Models LOACO ALWAYS use their own known-only per-run scaler via contracts.
        # Hardlink immutable main scaled tránh lưu lặp GB; fallback copy nếu filesystem không hỗ trợ.
        scaled = self.processed / "experiments" / self.main_id / "preprocessing/features_scaled.npy"
        alias = self.processed / "features_scaled.npy"
        if alias.exists():
            raise FileExistsError(alias)
        try:
            os.link(scaled, alias)
        except OSError:
            if shutil.disk_usage(alias.parent).free < scaled.stat().st_size + 2 * 1024**3:
                raise RuntimeError("Thiếu disk để tạo compatibility scaled array.")
            shutil.copyfile(scaled, alias)
        self.step("main_autoencoder", self.train("02_train_autoencoder.py", self.main_id))
        for model, representation in _base.STAGE1:
            self.step(f"main_stage1_{model}_{representation}", self.train("03_train_stage1.py", self.main_id, "--model", model, "--representation", representation))
        for variant in _base.VARIANTS:
            extra = ["--p-attack-path", self.p_path(self.main_id)] if "plus_pattack" in variant else []
            self.step("main_stage2_" + variant, self.train("04_train_stage2.py", self.main_id, "--experiment", variant, *extra))
        reports = {v: _base.read(ROOT / "results/stage2" / self.main_id / v / "metrics.json") for v in _base.VARIANTS}
        save_json(self.directory / "selection_validation_only.json", {
            "primary_frozen_from_CICIDS2017": PRIMARY,
            "secondary_external_validation_winner": _base.choose_stage2(reports),
            "validation_macro_f1": {v: reports[v]["validation_metrics"]["macro_f1"] for v in _base.VARIANTS},
            "test_used_for_selection": False})
        for variant in _base.VARIANTS:
            self.step("closed_" + variant, self.evaluation(self.main_id, variant, self.spec["round_id"] + "_closed_" + variant))
        for case in self.prepared["heldout_cases"]:
            heldout = case["label_id"]
            loaco_id = self.spec["round_id"] + f"_loaco_{heldout}"
            prefix = f"loaco_{heldout}"
            held = ["--held-out-label-id", str(heldout)]
            self.step(prefix + "_preprocessing", ["scripts/01b_prepare_protocol.py", "--config", self.config, "--run-id", loaco_id, *held])
            self.verify_normalization(loaco_id, heldout)
            self.step(prefix + "_autoencoder", self.train("02_train_autoencoder.py", loaco_id, *held))
            self.step(prefix + "_stage1", self.train("03_train_stage1.py", loaco_id, "--model", "xgboost", "--representation", "latent", *held))
            self.step(prefix + "_stage2", self.train("04_train_stage2.py", loaco_id, "--experiment", PRIMARY, "--p-attack-path", self.p_path(loaco_id), *held))
            self.step(prefix + "_novelty", self.train("05_train_novelty.py", loaco_id, *held,
                "--stage2-result-dir", ROOT / "results/stage2" / loaco_id / PRIMARY,
                "--ae-metadata", ROOT / "artifacts/metadata/autoencoder" / loaco_id / "run.json",
                "--stage1-metadata", ROOT / "artifacts/metadata/stage1" / loaco_id / "xgboost_latent.json",
                "--stage2-metadata", ROOT / "artifacts/metadata/stage2" / loaco_id / (PRIMARY + ".json"),
                "--methods", *_base.METHODS))
            for method in _base.METHODS:
                self.step(prefix + "_open_" + method, self.evaluation(loaco_id, PRIMARY, loaco_id + "_open_" + method, *held,
                    "--novelty-result-dir", ROOT / "results/novelty" / loaco_id / f"heldout_{heldout}" / PRIMARY,
                    "--novelty-method", method, "--novelty-threshold-json", ROOT / "artifacts/thresholds" / loaco_id / f"heldout_{heldout}" / PRIMARY / (method + ".json")))
        self.verify_sources()
        self.report()
        self.state.update(status="completed", ended_utc=datetime.now(timezone.utc).isoformat(), primary_stage2=PRIMARY)
        self.persist()

    def verify_normalization(self, run_id, heldout):
        """Read-only contract/fit-index check; no refit using validation or test."""
        from src.model_config import load_model_config
        from src.research_protocol import require_preprocessing
        from src.preprocessing import load_scaler
        arrays, scaled, record = require_preprocessing(load_model_config(self.config), run_id, heldout)
        try:
            scaler = load_scaler(scaled.parent / "scaler.joblib")
            if record["dataset_name"] != DATASET or len(scaler.mean_) != self.info["input_dim"]:
                raise ValueError("Scaler/schema/dataset contract mismatch.")
            check = {"heldout_id": heldout, "fit_samples": int(scaler.n_samples_seen_),
                     "fit_indices_sha256": _base.digest(scaled.parent / "fit_indices.npy"),
                     "scaler_sha256": _base.digest(scaled.parent / "scaler.joblib"),
                     "scaled_shape": list(arrays.features.shape),
                     "constant_train_features": [n for n, v in zip(self.info["feature_names"], scaler.var_) if v == 0],
                     "known_train_scope_verified": True, "test_used_for_fit": False}
            self.normalization_checks[run_id] = check
            save_json(self.directory / "normalization_checks.json", self.normalization_checks)
        finally:
            arrays.close()

    def report(self):
        s1 = {f"{m}_{r}": _base.read(ROOT / "results/stage1" / self.main_id / f"{m}_{r}" / "metrics.json") for m, r in _base.STAGE1}
        s2 = {v: _base.read(ROOT / "results/stage2" / self.main_id / v / "metrics.json") for v in _base.VARIANTS}
        closed = {v: _base.read(ROOT / "results/pipeline" / (self.spec["round_id"] + "_closed_" + v) / "metrics.json") for v in _base.VARIANTS}
        opened = {str(c["label_id"]): {**c, "methods": {
            m: _base.read(ROOT / "results/pipeline" / (self.spec["round_id"] + f"_loaco_{c['label_id']}_open_" + m) / "metrics.json")
            for m in _base.METHODS}} for c in self.prepared["heldout_cases"]}
        rows = zero_day_rows(opened)
        if rows:
            pd.DataFrame(rows).to_csv(self.directory / "zero_day_comparison.csv", index=False)
        save_json(self.directory / "comparison.json", {"protocol": self.spec, "preparation": self.prepared,
            "stage1": s1, "stage2": s2, "closed_set": closed, "open_set": opened,
            "normalization_checks": self.normalization_checks, "zero_day_comparison": rows})
        lines = [f"# Kết quả {DATASET}", "", "[VERIFIED FROM EXPERIMENTS] Chỉ tạo sau khi tất cả phase thành công. Nguồn: comparison.json và metrics.json từng phase.", "",
            f"Primary khóa từ CICIDS2017: XGB latent gate 0,5 → {PRIMARY}. Huấn luyện lại trên native dataset, KHÔNG zero-shot.", "",
            f"Native features: {self.prepared['input_dim']}; rows: {self.prepared['samples']}; partial dataset: {self.prepared['partial_dataset']}.", "",
            "## Stage 1", "", "| Model | Val F1 | Test F1 | P | R | FPR | FNR | AUROC | AP | Brier |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for name, value in s1.items():
            metrics = [value["validation_metrics"]["f1"]] + [value["test_metrics"][k] for k in ["f1", "precision", "recall_detection_rate", "false_positive_rate", "false_negative_rate", "roc_auc", "average_precision", "brier_score"]]
            lines.append("| " + name + " | " + " | ".join(f"{x:.6f}" if x is not None else "undefined" for x in metrics) + " |")
        lines += ["", "## Stage 2/cascade", "", "| Variant | Val attack macro-F1 | Oracle test macro-F1 | E2E accuracy | Balanced accuracy | E2E macro-F1 | Weighted-F1 |", "|---|---:|---:|---:|---:|---:|---:|"]
        for v in _base.VARIANTS:
            metrics = [s2[v]["validation_metrics"]["macro_f1"], s2[v]["known_test_metrics"]["macro_f1"]] + [closed[v]["end_to_end_metrics"][k] for k in ["accuracy", "balanced_accuracy", "macro_f1", "weighted_f1"]]
            lines.append("| " + v + " | " + " | ".join(f"{x:.6f}" for x in metrics) + " |")
        lines += ["", "## LOACO", ""]
        if not opened:
            lines.append("NOT RUN: --closed-set-only được yêu cầu; KHÔNG có bằng chứng zero-day.")
        else:
            lines += ["LOACO là mô phỏng lớp chưa biết; toàn bộ heldout đã chốt trước training.", "",
                "| Heldout | Method | Unknown support | P sau gate | R sau gate | F1 sau gate | Known FRR | Benign→unknown | Unknown bị gate chặn |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
            fmt = lambda v: "undefined" if v is None else f"{v:.6f}"
            for row in rows:
                numbers = [row[k] for k in ["unknown_support", "final_precision", "final_recall", "final_f1",
                    "known_attack_false_rejection", "benign_rejected_unknown", "unknown_blocked_by_gate"]]
                lines.append("| " + row["heldout"] + " | " + row["method"] + " | " + " | ".join(map(fmt, numbers)) + " |")
            lines += ["", "Score-only AUROC/AP, known support và E2E macro-F1: zero_day_comparison.csv.",
                "CSV cũng ghi unknown test có X trùng known train; LOACO theo nhãn không bảo đảm độc lập feature/family.",
                "Không gộp các test lặp giữa heldouts thành mẫu độc lập; không chọn detector theo test.",
                "Raw per-class/confusion/error decomposition: comparison.json; chuẩn hóa: normalization_checks.json."]
        lines += ["", "## Giới hạn", "", *["- " + x for x in self.spec["limitations"]], "",
            "Per-class support, confusion matrices, error decomposition và score-only/final unknown nằm đầy đủ trong comparison.json.",
            "Không suy ra tính mới hoặc ưu thế thống kê từ một seed; không xếp hạng độ khó dataset bằng macro-F1 của các ontology khác nhau.", ""]
        (self.directory / "RESEARCH_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


@contextmanager
def single_gpu_lock():
    """Lock hệ điều hành, tự nhả khi process chết; file lock còn lại KHÔNG là stale lock."""
    path = ROOT / "artifacts" / "external_training.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Một script external khác đang chạy; chạy lần lượt, không song song.") from exc
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def self_test():
    """Fixture CPU/tạm: schema, invalid, dedup, row alignment, split, tên manifest.
    Không fit AE/XGBoost/MLP/novelty, không ghi vào data/models/results của project.
    """
    with tempfile.TemporaryDirectory(prefix=SLUG + "_script_test_") as tmp:
        root = Path(tmp)
        data = root / "input"
        data.mkdir()
        rng = np.random.default_rng(42)
        x = pd.DataFrame({"A": rng.normal(size=120), "B": rng.normal(size=120)})
        y = np.repeat([0, 4, 9], 40) if DATASET == "CIC-UNSW-NB15" else np.repeat(["Benign", "AttackA", "AttackB"], 40)
        extended = pd.concat([x, x.iloc[[0]], pd.DataFrame({"A": [np.inf], "B": [1.]})], ignore_index=True)
        labels = np.concatenate([y, y[:2]])
        if DATASET == "CSE-CIC-IDS2018":
            extended["Timestamp"] = "fixture"
            extended["Label"] = labels
            extended.to_csv(data / "day.csv", index=False)
            (data / "unfinished.csv.part").write_text("fixture")
            try:
                inspect_input(data, enforce=True)
                raise AssertionError("Partial dataset must require consent")
            except ValueError:
                pass
        else:
            extended.to_csv(data / "Data.csv", index=False)
            pd.DataFrame({"Label": labels}).to_csv(data / "Lable.csv", index=False)
        info = inspect_input(data, allow_partial=True, enforce=True)
        audit = audit_input(info, 17)
        assert audit["input_rows"] == 122 and audit["invalid_rows"] == 1 and audit["duplicates"] == 1
        assert sum(c["clean_unique_count"] for c in audit["classes"]) == 120
        assert input_contract(info)["scaler"].startswith("population z-score")
        prepared = root / "prepared"
        report = prepare(info, prepared, 17)
        assert report["samples"] == 120 and report["invalid_rows"] == 1 and report["duplicate_rows_removed"] == 1
        raw = np.load(prepared / "features_raw.npy")
        np.testing.assert_allclose(raw, x.to_numpy(dtype=np.float32))
        ys = np.load(prepared / "attack_label_ids.npy")
        ss = np.load(prepared / "split_ids.npy")
        assert all(np.any((ys == c) & (ss == s)) for c in np.unique(ys) for s in [0, 1, 2])
        from src.research_protocol import require_preprocessing
        from src.model_config import load_model_config
        (root / "configs").mkdir()
        config = _base.read(ROOT / "configs/model_config.json")
        config["experiment"].update(processed_dir=str(prepared), prepared_metadata_dir=str(prepared / "metadata"), dataset_name=DATASET)
        save_json(root / "configs/model.json", config)
        cfg = load_model_config(root / "configs/model.json")
        internal_phase(["scripts/01b_prepare_protocol.py", "--config", str(root / "configs/model.json"), "--run-id", "fixture"])
        arrays, scaled_path, record = require_preprocessing(cfg, "fixture", None)
        assert record["dataset_name"] == DATASET
        arrays.close()
        from src.preprocessing import load_scaler
        scaler = load_scaler(scaled_path.parent / "scaler.joblib")
        np.testing.assert_allclose(scaler.mean_, raw[ss == 0].astype(float).mean(0))
        # Verify CLI dispatch + strict heldout exclusion in scaler ancestry (no model fit).
        heldout = int(np.max(ys))
        internal_phase(["scripts/01b_prepare_protocol.py", "--config", str(root / "configs/model.json"),
                        "--run-id", "fixture_loaco", "--held-out-label-id", str(heldout)])
        loaco_arrays, loaco_path, loaco_record = require_preprocessing(cfg, "fixture_loaco", heldout)
        assert loaco_record["dataset_name"] == DATASET
        loaco_arrays.close()
        loaco_scaler = load_scaler(loaco_path.parent / "scaler.joblib")
        np.testing.assert_allclose(loaco_scaler.mean_, raw[(ss == 0) & (ys != heldout)].astype(float).mean(0))
        if DATASET == "CIC-UNSW-NB15":
            pd.DataFrame({"Label": labels[:-1]}).to_csv(data / "Lable.csv", index=False)
            try:
                list(batches(info, 17))
                raise AssertionError("Misaligned labels accepted")
            except ValueError:
                pass
        else:
            pd.DataFrame({"A": [1.], "C": [2.], "Timestamp": ["fixture"], "Label": ["Benign"]}).to_csv(data / "other.csv", index=False)
            try:
                inspect_input(data, allow_partial=True, enforce=True)
                raise AssertionError("Schema intersection must require consent")
            except ValueError:
                pass
            intersection = inspect_input(data, allow_partial=True, allow_intersection=True, enforce=True)
            assert intersection["feature_names"] == ["A"]
        bad = data / "duplicate.csv"
        bad.write_text("A,A\n1,2\n")
        try:
            header(bad)
            raise AssertionError("Duplicate header accepted")
        except ValueError:
            pass
        # Multi-heldout plan, invalid selection, and leakage column guards.
        fake_y = np.repeat([0, 2, 4, 9], 30)
        fake_s = constrained_stratified_split(fake_y, train_ratio=.7, validation_ratio=.15, test_ratio=.15, random_state=42)
        fake_map = {"0": "BENIGN", "2": "AttackA", "4": "AttackB", "9": "AttackC"}
        cases = plan_heldouts(fake_map, fake_y, fake_s, ["AttackA", "AttackC"], 1)
        assert [c["label_id"] for c in cases] == [2, 9]
        for requested, minimum in [(["BENIGN"], 1), (["missing"], 1), (["AttackA", "AttackA"], 1), (["AttackC"], 500)]:
            try:
                plan_heldouts(fake_map, fake_y, fake_s, requested, minimum)
                raise AssertionError("Invalid heldout plan accepted")
            except ValueError:
                pass
        leaking = root / "leaking"
        leaking.mkdir()
        if DATASET == "CSE-CIC-IDS2018":
            pd.DataFrame({"A": [1], "binary_label": [1], "Timestamp": ["fixture"], "Label": ["AttackA"]}).to_csv(leaking / "day.csv", index=False)
        else:
            pd.DataFrame({"A": [1], "binary_label": [1]}).to_csv(leaking / "Data.csv", index=False)
            pd.DataFrame({"Label": [4]}).to_csv(leaking / "Lable.csv", index=False)
        try:
            inspect_input(leaking)
            raise AssertionError("Target-derived feature accepted")
        except ValueError:
            pass
        print(f"SELF-TEST PASS: {DATASET}; audit/normalization/alignment/LOACO scaler/multi-heldout/leakage guards. No model training.")


def main():
    from src.console import configure_utf8_console
    configure_utf8_console()
    if len(sys.argv) > 1 and sys.argv[1] == "--_phase":
        internal_phase(sys.argv[2:])
        return
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--run", action="store_true", help="Thực sự prepare và train; mặc định chỉ preflight.")
    mode.add_argument("--check-only", action="store_true", help="Chỉ kiểm header/inventory, không fit/ghi artifacts.")
    mode.add_argument("--self-test", action="store_true", help="Kiểm fixture tạm, không training.")
    mode.add_argument("--audit-only", action="store_true", help="Quét toàn bộ cleaning/dedup/class counts; không fit/ghi artifact.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/external" / DATASET)
    parser.add_argument("--run-id", help="Tên mới; tự thêm prefix dataset. Không resume hoặc overwrite.")
    parser.add_argument("--reference-config", type=Path, default=ROOT / "configs/model_config_round1_20261026_s42.json")
    parser.add_argument("--chunksize", type=int, default=100000)
    protocol = parser.add_mutually_exclusive_group()
    protocol.add_argument("--held-out-label", help="Một tên native attack, alias cho danh sách một phần tử.")
    protocol.add_argument("--held-out-labels", nargs="+", help="Các tên native attack chốt trước run; mỗi lớp LOACO riêng.")
    protocol.add_argument("--closed-set-only", action="store_true", help="Chủ động không chạy zero-day; không kết luận unknown.")
    parser.add_argument("--allow-partial-dataset", action="store_true", help="CSE: xác nhận chạy CSV hiện có dù còn tệp nghi tải dở; report gắn partial.")
    parser.add_argument("--allow-schema-intersection", action="store_true", help="CSE: xác nhận giao predictor giữa các ngày, ghi các cột bị loại; không zero-fill.")
    args = parser.parse_args()
    if args.chunksize <= 0:
        parser.error("--chunksize phải dương")
    if args.self_test:
        self_test()
        return
    args.held_out_labels = args.held_out_labels or ([args.held_out_label] if args.held_out_label else [])
    if args.run and not args.held_out_labels and not args.closed_set_only:
        parser.error("Zero-day cần --held-out-labels; nếu chỉ closed-set phải ghi rõ --closed-set-only.")
    if len(set(args.held_out_labels)) != len(args.held_out_labels):
        parser.error("Heldout list bị trùng.")
    info = inspect_input(args.data_dir, args.allow_partial_dataset, args.allow_schema_intersection, enforce=args.run)
    if args.audit_only:
        print(json.dumps(audit_input(info, args.chunksize), ensure_ascii=False, indent=2))
        return
    print(json.dumps({**info, "mode": "RUN" if args.run else "CHECK_ONLY", "primary_stage2": PRIMARY,
        "workflow": "prepare native -> closed-set controls -> independent full LOACO for each preregistered class",
        "input_contract": input_contract(info), "loaco_requested": args.held_out_labels, "reference_config": str(args.reference_config),
        "free_disk_gib": round(shutil.disk_usage(ROOT).free / 1024**3, 2)}, ensure_ascii=False, indent=2))
    if not args.run:
        return
    task = None
    with single_gpu_lock():
        try:
            task = ExternalRound(args, info)
            print("RUN OUTPUT:", task.directory, flush=True)
            task.run()
            print("COMPLETED:", task.directory / "RESEARCH_REPORT.md", flush=True)
        except BaseException as error:
            if task is not None:
                task.state.update(status="failed", error=str(error), ended_utc=datetime.now(timezone.utc).isoformat())
                task.persist()
            traceback.print_exc()
            raise SystemExit(1)


if __name__ == "__main__":
    main()
