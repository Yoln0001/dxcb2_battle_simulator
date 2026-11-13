"""装备特效计算；保留原脚本的随机调用顺序和概率。"""

import numpy as np
from numba import njit
from .equipment import (
    BERSERKER_START_MULTIPLIER_1,
    BERSERKER_START_MULTIPLIER_2,
    BERSERKER_FIRST_CHANCE,
    BERSERKER_SECOND_CONDITIONAL_CHANCE,
    BERSERKER_FIRST_STRENGTH_MULTIPLIER,
    BERSERKER_FIRST_HP_RATIO,
    BERSERKER_FALLBACK_STRENGTH_MULTIPLIER,
    BERSERKER_FALLBACK_TECHNIQUE_RATIO,
    BERSERKER_NORMAL_COOLDOWN,
    BERSERKER_COMBO_COOLDOWN,
)


@njit
def berserker_start_strength(strength):
    return strength * BERSERKER_START_MULTIPLIER_1 * BERSERKER_START_MULTIPLIER_2


@njit
def holy_lancer_team_technique(technique, source_technique):
    return technique + source_technique * 0.45


@njit
def berserker_attack_effect(strength, technique, hit_point):
    if np.random.random() < BERSERKER_FIRST_CHANCE:
        return (
            strength * BERSERKER_FIRST_STRENGTH_MULTIPLIER + hit_point * BERSERKER_FIRST_HP_RATIO,
            technique,
            BERSERKER_NORMAL_COOLDOWN,
        )
    elif np.random.random() < BERSERKER_SECOND_CONDITIONAL_CHANCE:
        return strength, technique, BERSERKER_COMBO_COOLDOWN
    else:
        return (
            strength * BERSERKER_FALLBACK_STRENGTH_MULTIPLIER
            + technique * BERSERKER_FALLBACK_TECHNIQUE_RATIO,
            technique,
            BERSERKER_NORMAL_COOLDOWN,
        )
