"""Choose a living combatant from current values; equal values use slot order."""

from .initialization import BattleConfigurationError

RULES = {
    "lowestHp": ("hitPoint", False),
    "highestHp": ("hitPoint", True),
    "lowestArmor": ("armor", False),
    "highestArmor": ("armor", True),
    "lowestResistance": ("resistance", False),
    "highestResistance": ("resistance", True),
}


def select_target(
    candidates, rule="default", *, default_index=None, hostile=False, ignore_taunt=False, rng=None
):
    living = [c for c in candidates if c.enabled and c.alive]
    if not living:
        return None
    if hostile and not ignore_taunt:
        taunting = [
            c
            for c in living
            if getattr(c, "taunting", False)
            or any(getattr(b, "name", "") == "嘲讽" for b in getattr(c, "buffs", []))
        ]
        if taunting:
            living = taunting
    if rule == "random":
        import random

        ordered = sorted(living, key=lambda c: c.index)
        return ordered[0] if len(ordered) == 1 else (rng or random).choice(ordered)
    if rule == "default":
        return next(
            (c for c in living if c.index == default_index), min(living, key=lambda c: c.index)
        )
    if rule not in RULES:
        raise BattleConfigurationError("释放对象选项无效")
    attribute, highest = RULES[rule]

    def value(c):
        return c.current_hp if attribute == "hitPoint" else c.stats.get(attribute, 0)

    return min(living, key=lambda c: ((-value(c) if highest else value(c)), c.index))
