from __future__ import annotations

import numpy as np


UNKNOWN_ATTACK_ID = -1


def compose_pipeline_predictions(
    p_attack: np.ndarray,
    stage2_probabilities: np.ndarray,
    stage2_class_ids: np.ndarray,
    novelty_scores: np.ndarray | None,
    novelty_threshold: float | None,
    stage1_threshold: float,
) -> np.ndarray:
    """Ghép Stage 1 -> Stage 2 -> novelty thành nhãn cuối cùng theo thứ tự test."""
    p_attack = np.asarray(p_attack)
    if len(p_attack) != len(stage2_probabilities):
        raise ValueError("Stage 1 và Stage 2 phải có cùng số dòng test")
    output = np.zeros(len(p_attack), dtype=np.int32)  # 0 = BENIGN
    attack_mask = p_attack >= stage1_threshold
    stage2_positions = np.argmax(stage2_probabilities, axis=1)
    output[attack_mask] = np.asarray(stage2_class_ids, dtype=np.int32)[stage2_positions[attack_mask]]
    if novelty_scores is not None:
        if novelty_threshold is None:
            raise ValueError("Có novelty_scores nhưng thiếu novelty_threshold")
        unknown_mask = attack_mask & (np.asarray(novelty_scores) >= novelty_threshold)
        output[unknown_mask] = UNKNOWN_ATTACK_ID
    return output

