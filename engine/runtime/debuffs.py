"""Skill debuff application, after the skill hit result is known."""

import random
from .initialization import nonnegative, BattleConfigurationError


def check_skill_debuff_application(source_stats, effect, target, *, hit, roll=None, rng=None):
    """Returns eligibility only; does not apply, stack or tick the debuff.

    Percentage = skill application rate + panel rate - resistance / 10.
    The caller supplies the actual skill hit result, avoiding a second hit roll.
    """
    if type(hit) is not bool:
        raise BattleConfigurationError("技能命中结果必须为布尔值")
    if not isinstance(effect, dict) or effect.get("kind") != "debuff":
        raise BattleConfigurationError("需要技能负面特效配置")
    skill_rate = nonnegative(effect.get("applicationRate", 0), "技能异常附加率")
    panel_rate = nonnegative(source_stats.get("abnormalBonus", 0), "面板异常附加率")
    resistance = nonnegative(target.get("resistance", 0), "目标抗性")
    raw_percent = skill_rate + panel_rate - resistance / 10
    probability = min(1.0, max(0.0, raw_percent / 100))
    if not hit:
        return {
            "hit": False,
            "applied": False,
            "raw_percent": raw_percent,
            "probability": probability,
            "roll": None,
            "reason": "miss",
        }
    if roll is None:
        roll = (rng or random).random()
    roll = nonnegative(roll, "异常附加随机值")
    if roll >= 1:
        raise BattleConfigurationError("异常附加随机值必须处于[0,1)")
    applied = roll < probability
    return {
        "hit": True,
        "applied": applied,
        "raw_percent": raw_percent,
        "probability": probability,
        "roll": roll,
        "reason": "applied" if applied else "application_failed",
    }
