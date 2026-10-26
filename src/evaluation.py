from __future__ import annotations

import numpy as np

from src.contracts import finite_vector, probability_matrix, probability_vector


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
    p_attack = probability_vector(p_attack)
    stage2_probabilities = probability_matrix(stage2_probabilities, stage2_class_ids, len(p_attack))
    if not np.isfinite(stage1_threshold) or not 0 <= stage1_threshold <= 1:
        raise ValueError('stage1_threshold phải hữu hạn thuộc [0,1]')
    if (novelty_scores is None) != (novelty_threshold is None):
        raise ValueError('Novelty score và threshold phải được cung cấp cùng nhau')
    if novelty_scores is not None:
        novelty_scores = finite_vector(novelty_scores, 'novelty_scores', len(p_attack))
        if not np.isfinite(novelty_threshold):
            raise ValueError('Novelty threshold không hữu hạn')
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

