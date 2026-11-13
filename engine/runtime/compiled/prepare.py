"""Translate a validated configuration into immutable numeric tables once per batch."""

import re
import numpy as np
from ..simulation import SingleBattle
from ..damage import RACES
from ..initialization import BattleConfigurationError

ATTRS = [
    "strength",
    "magic",
    "technique",
    "speed",
    "constitution",
    "hitPoint",
    "weaponPower",
    "criticalRate",
    "hitRate",
    "ignoreArmor",
    "ignoreResistance",
    "abnormalBonus",
    "physicalDamage",
    "magicDamage",
    "dotDamage",
    "finalPhysicalDamage",
    "finalMagicDamage",
    "finalDotDamage",
    "unload",
    "criticalMultiplier",
    "healingBonus",
    "finalHealingBonus",
    "lostHitPoint",
    "physicalSingleLifesteal",
    "magicSingleLifesteal",
    "physicalAreaLifesteal",
    "magicAreaLifesteal",
    "armor",
    "resistance",
    "contractCooldown",
    "contractHitPenalty",
    "dodgeRate",
    "dodge",
    "load",
    "physicalBlock",
    "magicBlock",
    "physicalTakenMultiplier",
    "magicTakenMultiplier",
    "ringRecoveryMultiplier",
    "physicalReduction",
    "magicReduction",
    "dotReduction",
    "dotTakenMultiplier",
    "contractRecoveryMultiplier",
]
A = {name: i for i, name in enumerate(ATTRS)}
KINDS = {
    "buff": 1,
    "amplify": 2,
    "physicalTrueDamage": 3,
    "magicTrueDamage": 4,
    "immediateAction": 5,
    "debuff": 6,
    "healing": 7,
    "regeneration": 8,
}
DEBUFFS = {
    "burn": 0,
    "bleeding": 1,
    "plague": 2,
    "slow": 3,
    "stun": 4,
    "weakness": 5,
    "fear": 6,
    "lifeLoss": 7,
}
TYPES = {"physical": 0, "magic": 1, "none": 2, "receivedPhysical": 10, "receivedMagic": 11}
TARGET_SELECTIONS = {
    name: i
    for i, name in enumerate(
        (
            "default",
            "lowestHp",
            "highestHp",
            "lowestArmor",
            "highestArmor",
            "lowestResistance",
            "highestResistance",
            "random",
        )
    )
}


class UnsupportedConfiguration(ValueError):
    pass


def prepare(config, equipment, skills, groups, *, boss_attacks=False):
    battle_class = SingleBattle
    if boss_attacks:
        from ..boss_simulation import BossBattle

        battle_class = BossBattle
    battle = battle_class(
        config, equipment, skills, groups, seed=config.get("seed"), record_timeline=False
    )
    names = {}

    def name_id(name):
        if name not in names:
            names[name] = len(names)
        return names[name]

    emeta = []
    econ = []
    ebase = []
    elinear = []
    warnings = set(battle.warnings)

    def vector(values):
        result = np.zeros(len(ATTRS))
        for key, value in values.items():
            if value and key not in A:
                raise UnsupportedConfiguration("未知属性：" + key)
            if not np.isfinite(value) or value < 0:
                raise BattleConfigurationError("属性系数必须为有限非负数")
            if key in A:
                result[A[key]] = value
        return result

    def effect_id(effect, name, trigger_type=0, allow_single=False):
        if not effect:
            return -1
        kind = (
            "regeneration"
            if effect.get("type") == "regeneration" and effect["kind"] == "buff"
            else effect["kind"]
        )
        if kind == "trueDamage":
            kind = "physicalTrueDamage" if trigger_type in (0, 10) else "magicTrueDamage"
        if kind not in KINDS:
            raise UnsupportedConfiguration("未知装备特效：" + kind)
        recipient = effect.get("recipient", "self")
        if recipient not in ("self", "allAllies") and not (
            recipient in ("singleAlly", "healingTargets") and allow_single
        ):
            raise UnsupportedConfiguration("不支持未指定队友的特效")
        meta = np.zeros(9)
        meta[0] = KINDS[kind]
        meta[1] = name_id(name)
        meta[2] = int(recipient == "allAllies")
        meta[3] = A.get(effect.get("type"), -1)
        meta[4] = float(effect.get("duration") or 0)
        meta[5] = effect.get("maxStacks", 1)
        meta[6] = effect.get("triggerRate", 100)
        meta[7] = DEBUFFS.get(effect.get("type"), -1)
        meta[8] = effect.get("applicationRate", 100)
        con = np.zeros((len(ATTRS), len(ATTRS)))
        base = np.zeros(len(ATTRS))
        linear = vector(effect.get("coefficients", {}))
        if kind in ("buff", "amplify"):
            enabled = False
            enabled_targets = set()
            for row in effect.get("conversions", []):
                if row["enabled"]:
                    enabled = True
                    if row["target"] not in A:
                        raise UnsupportedConfiguration("未知转化属性")
                    enabled_targets.add(A[row["target"]])
                    con[A[row["target"]]] = vector(row["coefficients"])
            if kind == "buff" and not enabled:
                raise BattleConfigurationError("buff没有启用任何属性增幅")
            if kind == "buff" and int(meta[3]) in enabled_targets:
                base[int(meta[3])] = effect.get("baseValue", 0)
        elif kind == "regeneration":
            base[0] = effect.get("baseValue", 0)
        elif kind == "debuff":
            if meta[7] < 0:
                raise UnsupportedConfiguration("未知负面效果")
            base[0] = effect.get("baseValue", 0)
            if effect["type"] in ("bleeding", "plague"):
                warnings.add("流血和瘟疫伤害规则尚未指定，暂只记录附加和到期。")
        index = len(emeta)
        emeta.append(meta)
        econ.append(con)
        ebase.append(base)
        elinear.append(linear)
        return index

    # Each equipped row has a stable proc index, preserving slot/row priority.
    proc = []
    proc_keys = []
    ranges = np.zeros((4, 2), dtype=np.int64)
    proc_map = {}
    for i, c in enumerate(battle.state.characters):
        ranges[i, 0] = len(proc)
        if c.enabled:
            for slot in ("weapon", "armor", "accessory1", "accessory2", "stone"):
                item = equipment.get(c.equipment.get(slot))
                if not item or not item.get("triggerEnabled"):
                    continue
                for row_index, row in enumerate(item.get("triggerEffects", [])):
                    if not row.get("effect"):
                        continue
                    dtype = TYPES[row["triggerType"]]
                    eid = effect_id(row["effect"], row["name"] or item["name"], dtype)
                    proc_map[(i, item["id"], row_index, row.get("name", ""))] = len(proc)
                    proc_map.setdefault(
                        (i, "name", item["name"], row_index, row.get("name", "")), len(proc)
                    )
                    proc.append([dtype, row["probability"], eid])
                    proc_keys.append(
                        (
                            i,
                            slot,
                            item["id"],
                            row["name"] or item["name"],
                            row["triggerType"],
                            row["effect"]["kind"],
                        )
                    )
        ranges[i, 1] = len(proc)
    smeta = []
    scoef = []
    skill_ids = {}

    def skill_id(skill_id, wait_duration=1, target_selection="lowestHp"):
        if skill_id == "__wait__":
            key = (skill_id, wait_duration)
            if key not in skill_ids:
                skill_ids[key] = len(smeta)
                smeta.append([3, wait_duration, 0, 0, 1, 0, -1, 0, 0, 0, 0, 0])
                scoef.append(np.zeros(len(ATTRS)))
            return skill_ids[key]
        key = (skill_id, target_selection)
        if key in skill_ids:
            return skill_ids[key]
        skill = skills[skill_id]
        dtype = TYPES[skill["damageType"]]
        bonus = skill.get("raceBonus", {})
        br = RACES.get(bonus.get("race"), bonus.get("race"))
        tr = RACES.get(config["target"].get("race"), config["target"].get("race"))
        race = 1 + bonus.get("multiplier", 0) if br and br != "none" and br == tr else 1
        name = re.sub(r"\s*lv\.?\s*\d+\s*$", "", skill["name"], flags=re.IGNORECASE).strip()
        selection = (
            TARGET_SELECTIONS.get(target_selection)
            if dtype < 2 and skill.get("targeting", "single") == "single"
            else 0
        )
        if selection is None:
            raise BattleConfigurationError("释放对象选项无效")
        effect = skill.get("effect")
        if effect and effect.get("recipient") == "healingTargets":
            effect = {
                **effect,
                "recipient": "allAllies"
                if dtype == 2 and skill.get("healingRecipient") == "allAllies"
                else "healingTargets",
            }
        eid = effect_id(effect, name, allow_single=True)
        idx = len(smeta)
        skill_ids[key] = idx
        smeta.append(
            [
                dtype,
                skill.get("cooldown", 0),
                skill.get("hitRate", 0),
                skill.get("criticalRate", 0),
                race,
                int(skill.get("healingRecipient", "self") == "allAllies"),
                eid,
                int(skill.get("targeting", "single") == "all"),
                selection,
                skill.get("lifesteal", 0),
                int(bool(effect and effect.get("recipient") == "healingTargets")),
                int(bool(effect and effect.get("recipient") == "singleAlly")),
            ]
        )
        scoef.append(vector(skill.get("coefficients", {})))
        if dtype != 2 and config["target"].get("speed", 43750) <= 0:
            raise BattleConfigurationError("攻击命中计算要求目标速度大于0")
        return idx

    nodes = []
    entries = np.full(4, -1, dtype=np.int64)
    for i, row in enumerate(config["characters"]):
        if not row["enabled"]:
            continue
        seq = battle.sequences[i + 1]
        group = seq.group
        flat = [n for g in group["subgroups"] for n in g["skills"]]
        offset = len(nodes)
        ids = {n["id"]: offset + j for j, n in enumerate(flat)}
        entries[i] = ids[seq.current]
        membership = {n["id"]: g for g in group["subgroups"] for n in g["skills"]}
        for n in flat:
            cond = n.get("jumpCondition")
            condition = -1
            if cond:
                key = (
                    (
                        i,
                        "name",
                        cond["equipmentName"],
                        cond["effectIndex"],
                        cond.get("effectName", ""),
                    )
                    if cond.get("equipmentName")
                    else (i, cond["equipmentId"], cond["effectIndex"], cond.get("effectName", ""))
                )
                condition = proc_map.get(key, -2)
            branch = seq.branches.get(n["id"])
            subgroup = membership[n["id"]]
            release = n.get("releaseCondition") or {"kind": "always", "threshold": 20}
            kinds = {
                "always": 0,
                "allyHealthBelow": 1,
                "noAllyHealthBelow": 2,
                "never": 3,
                "memberStatus": 4,
            }
            negative = release.get("requiredDebuff")
            positive = release.get("absentBuff")
            status_kind = -1
            source_skill = -1
            buff_id = -1
            buff_type = -1
            if negative:
                from .boss import KINDS as BOSS_KINDS

                status_kind = BOSS_KINDS.index(negative["type"])
                source_skill = next(
                    (
                        j
                        for j, s in enumerate(getattr(battle, "boss_group", {}).get("skills", []))
                        if s["id"] == negative["skillId"]
                    ),
                    -1,
                )
            if positive:
                buff_id = name_id(
                    re.sub(
                        r"\s*lv\.?\s*\d+\s*$", "", positive["skillName"], flags=re.IGNORECASE
                    ).strip()
                )
                buff_type = -2 if positive["type"] == "regeneration" else A[positive["type"]]

            nodes.append(
                [
                    skill_id(
                        n["skillId"], n.get("waitDuration", 1), n.get("targetSelection", "lowestHp")
                    ),
                    ids.get(seq.following[n["id"]], -1),
                    ids.get(seq.fallback[n["id"]], -1),
                    condition,
                    branch["threshold"] if branch else -1,
                    ids.get(branch["whenTrue"], -1) if branch else -1,
                    ids.get(branch["whenFalse"], -1) if branch else -1,
                    ids[subgroup["skills"][0]["id"]] if subgroup.get("conditionsEnabled") else -1,
                    ids[subgroup["skills"][-1]["id"]] + 1,
                    kinds[release["kind"]],
                    release.get("threshold", 20),
                    status_kind,
                    source_skill,
                    buff_id,
                    buff_type,
                    int(release.get("includeSelf", True)),
                    int(n.get("targetSelection") == "matchedMember"),
                    release.get("recognitionDelay", 0),
                    release.get("operationDelay", 0),
                ]
            )
    initial = np.zeros((4, len(ATTRS)))
    enabled = np.zeros(4, dtype=np.int64)
    health = np.zeros((4, 6))
    for i, c in enumerate(battle.state.characters):
        enabled[i] = c.enabled
        for key, value in c.stats.items():
            if key in A:
                initial[i, A[key]] = value
        from ..health import reduce_ally_recovery

        health[i] = [
            c.maximum_hp or 0,
            c.current_hp or 0,
            *[
                reduce_ally_recovery(battle.state, 1, kind=kind, recipient=c)
                for kind in ("lifesteal", "healing", "regeneration")
            ],
            0,
        ]
        for buff in c.buffs:
            name_id(buff.name)
        for buff in c.regeneration_buffs:
            name_id(buff["name"])
    # Per-character ring: restriction, gain columns, value, applied amount, next tick, enemy count.
    # Base attributes and recovery penalties are already included by SingleBattle initialization.
    rings = np.zeros((4, 7))
    rings[:, 0] = -1
    rings[:, 1:3] = -1
    restrictions = {
        "none": 0,
        "twoEnemies": 1,
        "missingParty": 2,
        "fullHealth": 3,
        "fragile": 4,
        "polluted": 5,
        "sacrifice": 6,
    }
    for i, c in enumerate(battle.state.characters):
        item = c.domain_ring
        if not item or not c.enabled:
            continue
        gain = item["gain"]
        keys = (
            ["physicalBlock", "magicBlock"]
            if gain == "doubleBlock"
            else ["physicalDamage", "magicDamage"]
            if gain == "physicalMagicDamage"
            else [gain]
        )
        rings[i] = [
            restrictions[item["restriction"]],
            A[keys[0]],
            A[keys[1]] if len(keys) > 1 else -1,
            item["gainValue"],
            c.ring_gain_amount,
            c.ring_next_tick,
            battle.state.target.get("enemyCount", 1),
        ]
    # Opening buffs may share names; replacements subtract all recorded deltas.
    if not names:
        name_id("__empty__")
    initial_regen = np.zeros((4, len(names), 4))
    for i, c in enumerate(battle.state.characters):
        for buff in c.regeneration_buffs:
            initial_regen[i, names[buff["name"]]] = [
                buff["amount"],
                buff["next_tick_at"],
                float("inf"),
                1,
            ]
    opening = np.zeros((4, len(names), len(ATTRS)))
    opening_active = np.zeros((4, len(names)), dtype=np.int64)
    opening_order = np.zeros((4, len(names)), dtype=np.int64)
    counter = 0
    for i, c in enumerate(battle.state.characters):
        for buff in c.buffs:
            b = names[buff.name]
            opening[i, b, A[buff.attribute]] += buff.amount
            opening_active[i, b] = 1
            counter += 1
            opening_order[i, b] = counter
    t = battle.state.target
    target = np.array(
        [
            t.get("hitPoint", 0),
            t.get("armor", 0),
            t.get("resistance", 0),
            t.get("speed", 43750),
            t.get("dodgeRate", 0),
            t.get("physicalVulnerability", 1),
            t.get("magicVulnerability", 1),
            t.get("dotVulnerability", 1),
            t.get("physicalReduction", 0),
            t.get("magicReduction", 0),
            t.get("dotReduction", 0),
            t.get("allyLifestealReduction", 0),
            t.get("allyHealingReduction", 0),
            t.get("allyRegenerationReduction", 0),
        ],
        dtype=np.float64,
    )
    if np.any(target[8:14] > 100):
        raise BattleConfigurationError("目标减伤必须处于0到100%")
    target = np.concatenate(
        (
            target,
            np.array(
                [
                    battle.state.target_current_hp
                    if battle.state.target_current_hp is not None
                    else target[0],
                    *battle.character_damage,
                ],
                dtype=np.float64,
            ),
        )
    )
    immune = np.array(
        [
            bool(t.get("immuneNegativeEffects") or t.get(key))
            for key in (
                "immuneBurn",
                "immuneBleeding",
                "immunePlague",
                "immuneSpeedReduction",
                "immuneStun",
                "immuneWeakness",
                "immuneFear",
                "immuneLifeLoss",
            )
        ],
        dtype=np.int64,
    )
    contract = battle.state.contract
    owner = contract.owner_index - 1 if contract else -1
    sacrifice = any(c.debuffs for c in battle.state.characters)
    settings = np.array(
        [
            battle.duration,
            owner,
            contract.skill_multiplier if contract else 0,
            int(sacrifice),
            *[int(c.first_strike) for c in battle.state.characters],
            battle.party_wipe_at if battle.party_wipe_at is not None else -1,
            contract.interval if contract else 14,
            contract.next_tick_at if contract else 14.1,
            {
                "旧日支配者-魔": 0,
                "狂怒兽神-力": 1,
                "饮命者-力": 2,
                "旧日支配者-力": 3,
                "炎钢羽神-技": 4,
                "饮魂者-技": 5,
                "至高妖精-魔": 6,
                "饮命者-魔": 7,
                "黑雾潜者-速": 8,
                "饮命者-速": 9,
                "旧日支配者-速": 10,
            }.get(contract.name, 0)
            if contract
            else 0,
            {"all": 0, "random": 1, "lowestHp": 2, "highestHp": 3}[battle.kill_strategy],
            *[
                v
                for b in battle.state.target.get("equipmentDotDebuffs", [])
                for v in (b["character"] - 1, b["damage"])
            ],
        ],
        dtype=np.float64,
    )

    def table(rows, width):
        return np.array(rows, dtype=np.float64).reshape((-1, width))

    arrays = (
        initial,
        enabled,
        health,
        opening,
        opening_active,
        opening_order,
        target,
        immune,
        settings,
        table(smeta, 12),
        table(scoef, len(ATTRS)),
        np.array(nodes, dtype=np.float64).reshape((-1, 19)),
        entries,
        table(proc, 3),
        ranges,
        table(emeta, 9),
        np.array(econ, dtype=np.float64).reshape((-1, len(ATTRS), len(ATTRS))),
        table(ebase, len(ATTRS)),
        table(elinear, len(ATTRS)),
        initial_regen,
        rings,
    )
    if boss_attacks:
        arrays = list(arrays)
        arrays[6] = np.append(arrays[6], battle.state.target.get("recoveryMultiplier", 1))
        arrays = tuple(arrays)
        return arrays, proc_keys, sorted(warnings), battle.boss_tables
    return arrays, proc_keys, sorted(warnings)
