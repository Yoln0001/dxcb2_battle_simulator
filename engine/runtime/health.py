"""Irreversible death state shared by all battle events."""


def mark_deaths(state, now=None):
    now = state.time if now is None else now
    for c in state.characters:
        if c.enabled and c.alive and c.current_hp is not None and c.current_hp <= 0:
            c.alive = False
            c.regeneration_buffs = []
            c.current_hp = 0.0
            c.stats["hitPoint"] = 0.0
            state.events.append(
                {"time": now, "type": "character_died", "character": c.index, "job": c.job}
            )
            if state.contract and state.contract.active and state.contract.owner_index == c.index:
                state.contract.active = False
                state.events.append(
                    {
                        "time": now,
                        "type": "contract_disabled",
                        "character": c.index,
                        "name": state.contract.name,
                    }
                )


def apply_enemy_recovery(state, amount, *, kind="healing"):
    """Shared enemy healing/lifesteal settlement, after normal outgoing bonuses."""
    from .initialization import nonnegative, BattleConfigurationError

    if kind not in ("healing", "lifesteal"):
        raise BattleConfigurationError("敌方回复类型无效")
    raw = nonnegative(amount, "敌方回复量")
    multiplier = nonnegative(state.target.get("recoveryMultiplier", 1), "敌方回复倍率")
    if multiplier > 1:
        raise BattleConfigurationError("敌方回复倍率不能大于1")
    reduced = raw * multiplier
    maximum = nonnegative(state.target.get("hitPoint", 0), "敌方最大血量")
    before = state.target_current_hp
    if before is None:
        raise BattleConfigurationError("敌方当前血量未设置")
    # Dead targets cannot recover or resurrect.
    effective = min(max(0, maximum - before), reduced) if before > 0 else 0.0
    state.target_current_hp = before + effective
    state.events.append(
        {
            "time": state.time,
            "type": "enemy_" + kind,
            "amount": reduced,
            "effective_amount": effective,
            "original_amount": raw,
            "recovery_multiplier": multiplier,
        }
    )
    return effective


def reduce_ally_recovery(state, amount, *, kind="healing", recipient=None):
    """Apply the enemy's separate team-wide recovery penalties."""
    from .initialization import nonnegative, BattleConfigurationError

    keys = {
        "healing": "allyHealingReduction",
        "lifesteal": "allyLifestealReduction",
        "regeneration": "allyRegenerationReduction",
    }
    if kind not in keys:
        raise BattleConfigurationError("己方回复类型无效")
    reduction = nonnegative(state.target.get(keys[kind], 0), "己方回复降低比例")
    if reduction > 100:
        raise BattleConfigurationError("己方回复降低比例不能超过100%")
    return (
        nonnegative(amount, "己方回复量")
        * (1 - reduction / 100)
        * (
            recipient.stats.get("contractRecoveryMultiplier", 1)
            * recipient.stats.get("ringRecoveryMultiplier", 1)
            if recipient is not None
            else 1
        )
    )


def is_negative_immune(character, kind):
    keys = {
        "physicalVulnerability": "immunePhysicalVulnerability",
        "magicVulnerability": "immuneMagicVulnerability",
        "bleeding": "immuneBleeding",
        "plague": "immunePlague",
        "burn": "immuneBurn",
        "stun": "immuneStun",
        "strengthDecay": "immuneStrengthDecay",
        "magicDecay": "immuneMagicDecay",
        "techniqueDecay": "immuneTechniqueDecay",
        "speedDecay": "immuneSpeedDecay",
        "armorDecay": "immuneArmorDecay",
        "resistanceDecay": "immuneResistanceDecay",
    }
    return bool(character.negative_immunities.get(keys.get(kind, "")))
