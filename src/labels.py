from __future__ import annotations

import re

import pandas as pd


BENIGN_LABEL = "BENIGN"
ATTEMPTED_SUFFIX = " - Attempted"


def normalize_label(value: object) -> str:
    """Normalize whitespace without merging or relabeling attack classes."""
    if pd.isna(value):
        raise ValueError("Label cannot be missing")
    return re.sub(r"\s+", " ", str(value)).strip()


def is_attempted_label(label: str) -> bool:
    return normalize_label(label).casefold().endswith(ATTEMPTED_SUFFIX.casefold())


def parent_attack_label(label: str) -> str:
    normalized = normalize_label(label)
    if is_attempted_label(normalized):
        return normalized[: -len(ATTEMPTED_SUFFIX)]
    return normalized


def attack_family(label: str) -> str:
    """Create an additional family label while preserving the exact label."""
    normalized = parent_attack_label(label)
    folded = normalized.casefold()
    if folded == BENIGN_LABEL.casefold():
        return "BENIGN"
    if "ddos" in folded:
        return "DDOS"
    if folded.startswith("dos ") or "heartbleed" in folded:
        return "DOS"
    if "patator" in folded or "brute force" in folded:
        return "BRUTE_FORCE"
    if "web attack" in folded or "xss" in folded or "sql injection" in folded:
        return "WEB_ATTACK"
    if "portscan" in folded or "port scan" in folded:
        return "PORT_SCAN"
    if "infiltration" in folded:
        return "INFILTRATION"
    if "botnet" in folded or folded == "bot":
        return "BOTNET"
    return "OTHER_ATTACK"


def add_label_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if "Label" not in frame.columns:
        raise KeyError("Required label column 'Label' is missing")
    result = frame.copy()
    result["attack_label_raw"] = result["Label"].astype(str)
    result["attack_label_normalized"] = result["Label"].map(normalize_label)
    result["binary_label"] = (
        result["attack_label_normalized"].str.casefold() != BENIGN_LABEL.casefold()
    ).astype("int8")
    result["is_attempted"] = result["attack_label_normalized"].map(is_attempted_label).astype("int8")
    result["attack_family"] = result["attack_label_normalized"].map(attack_family)
    return result
