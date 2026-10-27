r"""LOACO CICIDS2017: two further held-out classes with validation-only tuning.

Run manually from the project root in VS Code:
    .\.venv\Scripts\python.exe -X utf8 -u -B scripts\11_run_loaco_finetuning.py --study-id loaco_more_v1 --plan
    .\.venv\Scripts\python.exe -X utf8 -u -B scripts\11_run_loaco_finetuning.py --study-id loaco_more_v1 --run

The default outer classes are DoS Hulk (9) and Portscan (25). DDoS (26) from
round2 is historical context, NOT another untouched test. Algorithms, gate,
novelty method and rejection budget remain fixed. Only the declared XGBoost
regularization profile is a hyperparameter candidate. Each candidate refits
the entire known-only chain with a unique run ID. Selection reads only known
validation metrics of that outer LOACO fold; held-out test metrics are NEVER
used for selection. Existing training scripts do write test scores during fit,
so these are exploratory tests, not a pristine blind benchmark.

No data/model/log/result is overwritten, removed or resumed. GPU jobs are
serial and share the external-training lock. --plan is read-only. This script
does not run simply by opening it in VS Code.
"""
from __future__ import annotations

import argparse
import csv
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.model_config import experiment_id, load_model_config
from src.training_utils import save_json


REFERENCE_ROUND = "round2_20261027_fp32_s42"
PROCESSED = ROOT / "data" / "processed" / REFERENCE_ROUND
REFERENCE_CONFIG = ROOT / "configs" / f"model_config_{REFERENCE_ROUND}.json"
REFERENCE_LOCK = ROOT / "results" / "research_rounds" / REFERENCE_ROUND / "protocol_lock.json"
REPRODUCTION_CHECKS = ROOT / "results" / "research_rounds" / REFERENCE_ROUND / "reproduction_checks.json"
MIN_TEST_SUPPORT = 500
FIXED_STAGE1_THRESHOLD = 0.5
FIXED_KNOWN_REJECTION_RATE = 0.05
ESTIMATED_GIB_PER_TRIAL = 1.05  # Measured complete round2 LOACO: 0.976 GiB; estimate, not a guarantee.
RESERVED_GIB = 2.0

# No algorithm switches: AE(16) -> XGBoost(latent) -> XGBoost(latent_only) -> max_probability.
# The second profile tests a predeclared stronger-regularization hypothesis.
PROFILES: dict[str, dict[str, dict[str, float | int]]] = {
    "baseline": {"stage1": {}, "stage2": {}},
    "regularized": {
        "stage1": {"max_depth": 6, "min_child_weight": 8, "reg_lambda": 10.0},
        "stage2": {"max_depth": 6, "min_child_weight": 5, "reg_lambda": 10.0},
    },
}

# Freeze the implementation used by round2, not unrelated external-dataset scripts.
LOCKED_SOURCE_NAMES = (
    "src/artifact_contracts.py", "src/autoencoder.py", "src/calibration.py",
    "src/contracts.py", "src/evaluation.py", "src/metrics.py",
    "src/model_config.py", "src/model_data.py", "src/novelty.py",
    "src/preprocessing.py", "src/research_protocol.py", "src/split_data.py",
    "src/stage1_protocol.py", "src/stage1_xgboost.py", "src/stage2.py",
    "src/training_utils.py", "scripts/01b_prepare_protocol.py",
    "scripts/02_train_autoencoder.py", "scripts/03_train_stage1.py",
    "scripts/04_train_stage2.py", "scripts/05_train_novelty.py",
    "scripts/06_evaluate_pipeline.py",
)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--study-id", required=True, help="Unique prefix; no overwrite or resume.")
    parser.add_argument("--held-out-labels", nargs="+", type=int, default=[9, 25],
                        help="Default: DoS Hulk=9, Portscan=25; each needs >=500 test rows.")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42],
                        help="Training seeds. Phase-2 data split remains fixed at seed 42.")
    parser.add_argument("--profiles", nargs="+", choices=tuple(PROFILES),
                        default=["baseline", "regularized"],
                        help="Same algorithms, predeclared XGBoost hyperparameter profiles.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Read-only feasibility and protocol preview.")
    mode.add_argument("--run", action="store_true", help="Train sequentially; never overwrite/resume.")
    return parser.parse_args()


def checked_sources() -> dict[str, str]:
    expected = read_json(REFERENCE_LOCK)["source_hashes"]
    observed: dict[str, str] = {}
    for relative in LOCKED_SOURCE_NAMES:
        path = ROOT / relative
        key = str(path)
        if key not in expected or not path.is_file():
            raise RuntimeError(f"Missing locked implementation source: {path}")
        actual = digest(path)
        if actual != expected[key]:
            raise RuntimeError(f"Implementation differs from round2; inspect before a new protocol: {path}")
        observed[key] = actual
    return observed


def validate_data(labels: list[int]) -> list[dict[str, Any]]:
    checks = read_json(REPRODUCTION_CHECKS)
    for name, pair in checks.items():
        if pair["new"] != pair["reference"]:
            raise RuntimeError(f"Reference Phase-2 rebuild did not match legacy: {name}")
    for name in ("features_raw.npy", "attack_label_ids.npy", "split_ids.npy"):
        path = PROCESSED / name
        if not path.is_file() or digest(path) != checks[name]["new"]:
            raise RuntimeError(f"Processed data changed after round2: {path}")
    summary: dict[int, dict[str, Any]] = {}
    with (PROCESSED / "split_summary.csv").open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            label = int(row["attack_label_id"])
            record = summary.setdefault(label, {"id": label, "name": row["attack_label"]})
            record[row["split"]] = int(row["count"])
    chosen = []
    for label in labels:
        if label == 0 or label not in summary:
            raise ValueError(f"Held-out ID is not an attack label: {label}")
        record = summary[label]
        if record.get("test", 0) < MIN_TEST_SUPPORT:
            raise ValueError(f"{record['name']} has only {record.get('test', 0)} test rows; need >= {MIN_TEST_SUPPORT}")
        if record.get("train", 0) < MIN_TEST_SUPPORT or record.get("validation", 0) < MIN_TEST_SUPPORT:
            raise ValueError(f"{record['name']} lacks adequate train/validation support: {record}")
        chosen.append(record)
    return chosen


def trial_id(study_id: str, held_out: int, seed: int, profile: str) -> str:
    value = f"{study_id}_h{held_out}_s{seed}_{profile}"
    return experiment_id({"experiment": {"id": value}}, value)


def trial_paths(run_id: str) -> dict[str, Path]:
    return {
        "config": ROOT / "configs" / f"loaco_finetune_{run_id}.json",
        "processed": PROCESSED / "experiments" / run_id,
        "ae_model": ROOT / "models" / "autoencoder" / run_id,
        "s1_model": ROOT / "models" / "stage1" / run_id,
        "s2_model": ROOT / "models" / "stage2" / run_id,
        "novelty_model": ROOT / "models" / "novelty" / run_id,
        "ae_result": ROOT / "results" / "autoencoder" / run_id,
        "s1_result": ROOT / "results" / "stage1" / run_id,
        "s2_result": ROOT / "results" / "stage2" / run_id,
        "novelty_result": ROOT / "results" / "novelty" / run_id,
        "threshold": ROOT / "artifacts" / "thresholds" / run_id,
        "ae_metadata": ROOT / "artifacts" / "metadata" / "autoencoder" / run_id,
        "s1_metadata": ROOT / "artifacts" / "metadata" / "stage1" / run_id,
        "s2_metadata": ROOT / "artifacts" / "metadata" / "stage2" / run_id,
        "novelty_metadata": ROOT / "artifacts" / "metadata" / "novelty" / run_id,
        "evaluation": ROOT / "results" / "pipeline" / (run_id + "_open_mcp"),
    }


def configuration(source: dict[str, Any], run_id: str, seed: int, profile: str) -> dict[str, Any]:
    config = json.loads(json.dumps(source))
    config["experiment"]["id"] = run_id
    config["experiment"]["random_state"] = seed
    config["experiment"]["processed_dir"] = str(PROCESSED)
    config["experiment"]["prepared_metadata_dir"] = str(PROCESSED / "metadata")
    for key, value in PROFILES[profile]["stage1"].items():
        config["stage1"]["xgboost"][key] = value
    for key, value in PROFILES[profile]["stage2"].items():
        config["stage2"]["xgboost"][key] = value
    # These are part of the fixed scientific protocol, not tuning knobs.
    if (config["autoencoder"]["latent_dim"] != 16
            or config["stage1"]["oof_folds"] != 5
            or config["evaluation"]["decision_threshold"] != FIXED_STAGE1_THRESHOLD
            or config["novelty"]["known_rejection_rate"] != FIXED_KNOWN_REJECTION_RATE):
        raise ValueError("AE dimension, OOF folds, gate and rejection budget must match round2")
    return config


def make_plan(args: argparse.Namespace) -> dict[str, Any]:
    if len(args.study_id) > 32:
        raise ValueError("--study-id must be <=32 characters to keep Windows paths short")
    experiment_id({"experiment": {"id": args.study_id}}, args.study_id)
    if len(set(args.held_out_labels)) != len(args.held_out_labels):
        raise ValueError("Duplicate held-out IDs")
    if len(set(args.seeds)) != len(args.seeds) or any(seed < 0 for seed in args.seeds):
        raise ValueError("Seeds must be distinct nonnegative integers")
    if len(set(args.profiles)) != len(args.profiles):
        raise ValueError("Duplicate profiles")
    source = read_json(REFERENCE_CONFIG)
    load_model_config(REFERENCE_CONFIG)
    labels = validate_data(args.held_out_labels)
    hashes = checked_sources()
    trials = []
    for held in args.held_out_labels:
        for seed in args.seeds:
            for profile in args.profiles:
                run_id = trial_id(args.study_id, held, seed, profile)
                configuration(source, run_id, seed, profile)
                trials.append({"run_id": run_id, "held_out": held, "seed": seed, "profile": profile})
    study_dir = ROOT / "results" / "loaco_finetune" / args.study_id
    if study_dir.exists():
        raise FileExistsError(f"Study already exists; no overwrite/resume: {study_dir}")
    for trial in trials:
        for path in trial_paths(trial["run_id"]).values():
            if path.exists():
                raise FileExistsError(f"Trial artifact already exists: {path}")
    free_gib = shutil.disk_usage(ROOT).free / (1024 ** 3)
    needed_gib = RESERVED_GIB + ESTIMATED_GIB_PER_TRIAL * len(trials)
    return {
        "study_id": args.study_id, "reference_round": REFERENCE_ROUND,
        "held_out_classes": labels, "seeds": args.seeds,
        "profiles": {name: PROFILES[name] for name in args.profiles}, "trials": trials,
        "fixed_pipeline": "AE(16) -> XGBoost latent binary gate 0.5 -> XGBoost latent_only multiclass -> max_probability (known validation rejection 0.05)",
        "selection": "within each (held-out, seed), highest Stage2 known-validation macro-F1; ties Stage1 validation F1 then profile order",
        "test_policy": "test/unknown metrics excluded from selection; evaluate only chosen profile per (held-out, seed)",
        "split_policy": "Phase-2 split remains fixed at seed 42; --seeds changes fitting randomness, not the split",
        "source_hashes": hashes, "wrapper_sha256": digest(Path(__file__)),
        "free_gib": round(free_gib, 2),
        "estimated_required_gib": round(needed_gib, 2),
        "disk_warning": "estimate only; no artifacts will be deleted automatically",
        "limitations": ["historical DDoS test already inspected", "candidate training scripts themselves write test scores before selection; selector reads validation fields only", "fixed random split has feature-vector overlap; no time/source-separated evidence", "per-fold best hyperparameters are not one globally validated setting", "zero-day means held-out class simulation, not real-world future attacks"],
    }


class Study:
    def __init__(self, plan: dict[str, Any], source: dict[str, Any]):
        self.plan = plan
        self.directory = ROOT / "results" / "loaco_finetune" / plan["study_id"]
        self.state: dict[str, Any] = {"status": "running", "pid": os.getpid(),
                                     "started_utc": datetime.now(timezone.utc).isoformat(), "steps": []}
        self.source = source
        self.config_hashes: dict[Path, str] = {}

    def persist(self) -> None:
        save_json(self.directory / "status.json", self.state)

    def step(self, name: str, command: list[str]) -> None:
        checked_sources()
        if digest(Path(__file__)) != self.plan["wrapper_sha256"]:
            raise RuntimeError("Finetuning wrapper changed during the study")
        for path, expected in self.config_hashes.items():
            if digest(path) != expected:
                raise RuntimeError(f"Trial config changed during the study: {path}")
        if shutil.disk_usage(ROOT).free < RESERVED_GIB * 1024 ** 3:
            raise RuntimeError(f"Less than {RESERVED_GIB:g} GiB free before {name}; existing artifacts kept")
        log = self.directory / "logs" / f"{len(self.state['steps']):03d}_{name}.log"
        cmd = [sys.executable, "-X", "utf8", "-u", "-B", *command]
        item: dict[str, Any] = {"name": name, "command": cmd, "log": str(log),
                                "status": "running", "started_utc": datetime.now(timezone.utc).isoformat()}
        self.state["steps"].append(item)
        self.state["current_step"] = name
        self.persist()
        print(f"START {name} | {log}", flush=True)
        started = time.perf_counter()
        with log.open("x", encoding="utf-8") as stream:
            child = subprocess.Popen(cmd, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                     env={**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1", "PYTHONHASHSEED": "42"})
            item["child_pid"] = child.pid
            self.persist()
            try:
                while True:
                    try:
                        return_code = child.wait(timeout=60)
                        break
                    except subprocess.TimeoutExpired:
                        # Hashing large arrays can be quiet; this is progress, not a second job.
                        print(f"RUNNING {name}: {time.perf_counter() - started:.0f}s | {log}", flush=True)
            except BaseException as error:
                child.terminate()
                child.wait()
                item.update(returncode=child.returncode, status="interrupted",
                            error=repr(error), ended_utc=datetime.now(timezone.utc).isoformat())
                self.persist()
                raise
        item.update(returncode=return_code, seconds=time.perf_counter() - started,
                    ended_utc=datetime.now(timezone.utc).isoformat(),
                    status="completed" if return_code == 0 else "failed")
        self.persist()
        if return_code:
            raise RuntimeError(f"{name} exited {return_code}; see {log}")
        print(f"DONE {name}: {item['seconds']:.1f}s", flush=True)

    def train_trial(self, trial: dict[str, Any]) -> dict[str, Any]:
        run_id, held, seed, profile = (trial[k] for k in ("run_id", "held_out", "seed", "profile"))
        paths = trial_paths(run_id)
        save_json(paths["config"], configuration(self.source, run_id, seed, profile))
        config_hash = digest(paths["config"])
        self.config_hashes[paths["config"]] = config_hash
        common = ["--config", str(paths["config"]), "--run-id", run_id,
                  "--protocol", "revised_v1", "--held-out-label-id", str(held)]
        # 01b prepares the revised scaler but has no --protocol CLI flag.
        self.step(f"{run_id}_preprocess", ["scripts/01b_prepare_protocol.py",
                                                "--config", str(paths["config"]),
                                                "--run-id", run_id,
                                                "--held-out-label-id", str(held)])
        self.step(f"{run_id}_autoencoder", ["scripts/02_train_autoencoder.py", *common])
        self.step(f"{run_id}_stage1", ["scripts/03_train_stage1.py", *common,
                                       "--model", "xgboost", "--representation", "latent"])
        self.step(f"{run_id}_stage2", ["scripts/04_train_stage2.py", *common,
                                       "--experiment", "latent_only"])
        if digest(paths["config"]) != config_hash:
            raise RuntimeError(f"Config changed while training {run_id}")
        s1 = read_json(paths["s1_result"] / "xgboost_latent" / "metrics.json")
        s2 = read_json(paths["s2_result"] / "latent_only" / "metrics.json")
        result = {**trial, "config": str(paths["config"]), "config_sha256": config_hash,
                  "stage1_validation_f1": float(s1["validation_metrics"]["f1"]),
                  "stage2_validation_macro_f1": float(s2["validation_metrics"]["macro_f1"])}
        if not all(math.isfinite(result[key]) and 0 <= result[key] <= 1
                   for key in ("stage1_validation_f1", "stage2_validation_macro_f1")):
            raise ValueError(f"Invalid validation metrics for {run_id}")
        return result

    def evaluate_selected(self, selected: dict[str, Any]) -> dict[str, Any]:
        run_id, held = selected["run_id"], selected["held_out"]
        paths = trial_paths(run_id)
        config = str(paths["config"])
        p_attack = PROCESSED / "experiments" / run_id / "stage1_xgboost_latent_p_attack_all.npy"
        stage2_result = paths["s2_result"] / "latent_only"
        common = ["--config", config, "--run-id", run_id,
                  "--protocol", "revised_v1", "--held-out-label-id", str(held)]
        self.step(f"{run_id}_novelty", ["scripts/05_train_novelty.py", *common,
                                       "--stage2-result-dir", str(stage2_result),
                                       "--ae-metadata", str(paths["ae_metadata"] / "run.json"),
                                       "--stage1-metadata", str(paths["s1_metadata"] / "xgboost_latent.json"),
                                       "--stage2-metadata", str(paths["s2_metadata"] / "latent_only.json"),
                                       "--methods", "max_probability"])
        novelty_dir = paths["novelty_result"] / f"heldout_{held}" / "latent_only"
        threshold = paths["threshold"] / f"heldout_{held}" / "latent_only" / "max_probability.json"
        self.step(f"{run_id}_evaluation", ["scripts/06_evaluate_pipeline.py", "--config", config,
                                          "--run-id", run_id + "_open_mcp",
                                          "--p-attack-path", str(p_attack),
                                          "--stage2-result-dir", str(stage2_result),
                                          "--held-out-label-id", str(held),
                                          "--novelty-result-dir", str(novelty_dir),
                                          "--novelty-method", "max_probability",
                                          "--novelty-threshold-json", str(threshold)])
        report = read_json(paths["evaluation"] / "metrics.json")
        return {"held_out": held, "seed": selected["seed"], "selected_profile": selected["profile"],
                "run_id": run_id, "validation_stage2_macro_f1": selected["stage2_validation_macro_f1"],
                "final_unknown_metrics": report["final_unknown_metrics"],
                "stage1_test_metrics": report["stage1_test_metrics"],
                "end_to_end_macro_f1": report["end_to_end_metrics"]["macro_f1"],
                "error_decomposition": report["error_decomposition"],
                "metrics_path": str(paths["evaluation"] / "metrics.json")}

    def run(self) -> None:
        self.directory.mkdir(parents=True)
        (self.directory / "logs").mkdir()
        save_json(self.directory / "protocol_lock.json", self.plan)
        self.persist()
        try:
            candidates: list[dict[str, Any]] = []
            selected: list[dict[str, Any]] = []
            for label in self.plan["held_out_classes"]:
                held = label["id"]
                for seed in self.plan["seeds"]:
                    group = []
                    for profile in self.plan["profiles"]:
                        trial = next(item for item in self.plan["trials"]
                                     if item["held_out"] == held and item["seed"] == seed
                                     and item["profile"] == profile)
                        result = self.train_trial(trial)
                        group.append(result)
                        candidates.append(result)
                    winner = max(group, key=lambda item: (item["stage2_validation_macro_f1"],
                                                          item["stage1_validation_f1"],
                                                          -list(self.plan["profiles"]).index(item["profile"])))
                    selection = {"held_out": held, "seed": seed, "criterion": self.plan["selection"],
                                 "test_used_for_selection": False, "candidates": group,
                                 "selected": winner}
                    save_json(self.directory / f"selection_h{held}_s{seed}.json", selection)
                    selected.append(winner)
                    # Only after the immutable selection file exists do we fit novelty and read held-out test metrics.
                    save_json(self.directory / f"evaluation_h{held}_s{seed}.json", self.evaluate_selected(winner))
            evaluations = [read_json(self.directory / f"evaluation_h{x['held_out']}_s{x['seed']}.json")
                           for x in selected]
            save_json(self.directory / "summary.json", {
                "study_id": self.plan["study_id"], "validation_candidates": candidates,
                "selected": selected, "evaluations": evaluations,
                "historical_ddos_reference": str(ROOT / "results/research_rounds" / REFERENCE_ROUND / "comparison.json"),
                "caution": "DDoS historical run is not a new blind test; do not select hyperparameters from held-out test outcomes.",
            })
            self.state.update(status="completed", ended_utc=datetime.now(timezone.utc).isoformat())
            self.persist()
        except BaseException as error:
            self.state.update(status="failed", error=repr(error), ended_utc=datetime.now(timezone.utc).isoformat())
            self.persist()
            traceback.print_exc()
            raise


def exclusive_gpu_lock():
    """Use the same one-byte lock as the external dataset runners on Windows."""
    from contextlib import contextmanager

    @contextmanager
    def acquire():
        path = ROOT / "artifacts" / "external_training.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as stream:
            if path.stat().st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as error:
                    raise RuntimeError("Another external/LOACO training job holds the GPU lock") from error
                try:
                    yield
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                try:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as error:
                    raise RuntimeError("Another external/LOACO training job holds the GPU lock") from error
                try:
                    yield
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    return acquire()


def main() -> None:
    args = parse_args()
    plan = make_plan(args)
    print(json.dumps({key: value for key, value in plan.items() if key != "source_hashes"},
                     ensure_ascii=False, indent=2))
    if args.plan:
        return
    if plan["free_gib"] < plan["estimated_required_gib"]:
        raise RuntimeError("Insufficient D: space for all trials plus safety headroom; free space first, do not delete historical runs automatically")
    with exclusive_gpu_lock():
        # Check collisions and data once more after acquiring the shared lock.
        plan = make_plan(args)
        if plan["free_gib"] < plan["estimated_required_gib"]:
            raise RuntimeError("Free space changed before training")
        Study(plan, read_json(REFERENCE_CONFIG)).run()


if __name__ == "__main__":
    main()
