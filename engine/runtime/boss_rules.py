"""Fixed-time Boss mechanics independent of action cooldowns."""

from .initialization import BattleConfigurationError, nonnegative


def party_wipe_time(target):
    selected = target.get("selectedBoss") or {}
    rule = target.get("partyWipe", selected.get("partyWipe"))
    if rule is None:
        return None
    if not isinstance(rule, dict) or type(rule.get("enabled", False)) is not bool:
        raise BattleConfigurationError("定时击杀设置无效")
    if not rule.get("enabled", False):
        return None
    time = nonnegative(rule.get("time"), "击杀间隔")
    if not 0.1 <= time <= 3600:
        raise BattleConfigurationError("击杀间隔应为0.1到3600秒")
    return time


def periodic_kill_strategy(target):
    selected = target.get("selectedBoss") or {}
    rule = target.get("partyWipe", selected.get("partyWipe")) or {}
    strategy = rule.get("strategy", "all")
    if strategy not in ("random", "lowestHp", "highestHp", "all"):
        raise BattleConfigurationError("定时击杀策略无效")
    return strategy
