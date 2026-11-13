"""Numeric Boss graph, attacks and status effects for the opt-in combat kernel."""

import math
import numpy as np
from numba import njit
from .rng import uniform, below
from .prepare import A, ATTRS, TARGET_SELECTIONS
from ..initialization import BattleConfigurationError, nonnegative

KINDS = (
    "burn",
    "bleeding",
    "plague",
    "slow",
    "stun",
    "weakness",
    "fear",
    "lifeLoss",
    "strengthDecay",
    "magicDecay",
    "techniqueDecay",
    "speedDecay",
    "armorDecay",
    "resistanceDecay",
)
CONDITIONS = {
    "always": 0,
    "bossHealthBelow": 1,
    "bossHealthAbove": 2,
    "enemyHealthBelow": 3,
    "noEnemyHealthBelow": 4,
    "timeAtLeast": 5,
}


def tables(config, characters, group=None):
    from backend.api.bosses import validate_boss_group
    from backend.skills.store import SkillError

    target = config["target"]
    selected = target.get("selectedBoss") or {}
    if not isinstance(selected, dict):
        raise BattleConfigurationError("所选Boss格式无效")
    if not isinstance(selected.get("attributes", {}), dict) or not isinstance(
        target.get("attributes", {}), dict
    ):
        raise BattleConfigurationError("Boss属性格式无效")
    try:
        if group is None:
            group = validate_boss_group(selected.get("skillGroup", target.get("skillGroup")))
    except SkillError as error:
        raise BattleConfigurationError(str(error)) from error
    if not group["entry"]:
        raise BattleConfigurationError("包含Boss攻击的模拟需要先为所选Boss设置技能组")
    source = np.zeros(len(ATTRS))
    attrs = {**selected.get("attributes", {}), **target.get("attributes", {})}
    for key in ATTRS:
        source[A[key]] = nonnegative(attrs.get(key, target.get(key, 0)), "Boss " + key)
    source[A["hitPoint"]] = target.get("hitPoint", source[A["hitPoint"]])
    skills = group["skills"]
    ids = {s["id"]: i for i, s in enumerate(skills)}
    meta = np.zeros((len(skills), 18))
    coefs = np.zeros((len(skills), len(ATTRS)))
    con = np.zeros((len(skills), len(ATTRS), len(ATTRS)))
    linear = coefs.copy()
    for i, s in enumerate(skills):
        effect = s.get("effect") or {}
        kind = (
            0
            if not effect
            else 2
            if effect["kind"] == "debuff"
            else 3
            if effect["type"] == "regeneration"
            else 1
        )
        meta[i, :13] = [
            {"physical": 0, "magic": 1, "none": 2}[s["damageType"]],
            s["cooldown"],
            s["baseValue"],
            s["hitRate"],
            s["criticalRate"],
            int(s["targeting"] == "all"),
            kind,
            KINDS.index(effect["type"]) if kind == 2 else A.get(effect.get("type"), -1),
            effect.get("baseValue", 0),
            effect.get("duration", 0),
            effect.get("applicationRate", effect.get("triggerRate", 100)),
            int(s.get("ignoreTaunt", False)),
            int(
                effect.get("recipient") != "singleAlly"
                and (effect.get("recipient") != "healingTargets" or s["damageType"] == "none")
            ),
        ]
        meta[i, 17] = effect.get("maxStacks", 1)
        # Boss skills have no racial damage bonus; keep neutral factors in the array layout.
        meta[i, 13:17] = 1.0
        for k, v in s["coefficients"].items():
            coefs[i, A[k]] = v
        for k, v in effect.get("coefficients", {}).items():
            linear[i, A[k]] = v
        for row in effect.get("conversions", []):
            if row["enabled"]:
                for k, v in row["coefficients"].items():
                    con[i, A[row["target"]], A[k]] = v
                if row["target"] == effect["type"]:
                    linear[i, A[row["target"]]] = effect.get("baseValue", 0)
    flat = [(g, n) for g in group["subgroups"] for n in g["skills"]]
    nodes = np.zeros((len(flat), 12))
    node_ids = {n["id"]: i for i, (_, n) in enumerate(flat)}
    group_first = {g["id"]: node_ids[g["skills"][0]["id"]] for g in group["subgroups"]}
    choices = []
    for i, (g, n) in enumerate(flat):
        following = (
            node_ids[g["skills"][g["skills"].index(n) + 1]["id"]]
            if g["skills"].index(n) + 1 < len(g["skills"])
            else group_first.get(g.get("nextGroup"), -1)
        )
        condition = n.get("releaseCondition") or {"kind": "always"}
        mode = {"sequential": 0, "conditional": 1, "random": 2}[g["type"]]
        begin = len(choices)
        for sid in n.get("skillIds", []):
            choices.append(
                [
                    ids[sid],
                    node_ids.get(n["skillJumps"].get(sid), following),
                    TARGET_SELECTIONS[n["skillTargets"][sid]],
                ]
            )
        nodes[i] = [
            mode,
            group_first[g["id"]],
            group_first[g["id"]] + len(g["skills"]),
            begin,
            len(choices),
            ids.get(n.get("skillId"), -1),
            node_ids.get(n.get("next"), following),
            TARGET_SELECTIONS[n["targetSelection"]],
            CONDITIONS[condition["kind"]],
            condition.get("threshold", 0),
            n.get("waitDuration", 1),
            following,
        ]
    immunity = np.zeros((4, len(KINDS)), np.int64)
    taunt = np.zeros(4, np.int64)
    keys = {
        "burn": "immuneBurn",
        "bleeding": "immuneBleeding",
        "plague": "immunePlague",
        "stun": "immuneStun",
        "strengthDecay": "immuneStrengthDecay",
        "magicDecay": "immuneMagicDecay",
        "techniqueDecay": "immuneTechniqueDecay",
        "speedDecay": "immuneSpeedDecay",
        "armorDecay": "immuneArmorDecay",
        "resistanceDecay": "immuneResistanceDecay",
    }
    for c, character in enumerate(characters):
        for k, key in keys.items():
            immunity[c, KINDS.index(k)] = bool(character.negative_immunities.get(key))
        taunt[c] = int(any(b.name == "嘲讽" for b in character.buffs))
    entry = np.array([node_ids[group["entry"]]], np.int64)
    return (
        source,
        meta,
        coefs,
        con,
        linear,
        nodes,
        np.array(choices, dtype=np.float64).reshape((-1, 3)),
        immunity,
        taunt,
        entry,
    )


@njit(cache=True)
def dot(left, right):
    value = 0.0
    for i in range(len(left)):
        value += left[i] * right[i]
    return value


@njit(cache=True)
def initial_state(data):
    source, meta, coefs, con, linear, nodes, choices, immunity, taunt, entry = data
    # node, last release, previous skill CD, wait deadline, regeneration amount/next/expiry
    clock = np.array([float(entry[0]), 0.0, 0.0, -1.0, 0.0, 1.0, -1.0])
    return (
        source.copy(),
        clock,
        np.zeros((len(meta), len(source))),
        np.column_stack((np.full(len(meta), -1.0), np.zeros(len(meta)))),
        np.zeros((4, len(KINDS), 7)),
    )


@njit(cache=True)
def cooldown(source, skill):
    r = max(source[0] - source[18], 1) / (source[3] + 1) * 10
    near = round(r)
    if abs(r - near) < 1e-12:
        r = float(near)
    return max(0.5, round(1.5 + skill + min(3.0, math.floor(r) / 10), 12))


@njit(cache=True)
def deadline(runtime, target_debuffs=None):
    source, clock, deltas, expires, status = runtime
    effective = source.copy()
    if target_debuffs is not None:
        for k, a in ((3, 3), (5, 0), (6, 2)):
            if target_debuffs[k, 0]:
                effective[a] = max(1.0, effective[a] - target_debuffs[k, 5])
    return clock[3] if clock[3] >= 0 else round(clock[1] + cooldown(effective, clock[2]), 12)


@njit(cache=True)
def periodic(time, stats, hp, maximum, alive, runtime):
    source, clock, deltas, expires, status = runtime
    damage = np.zeros(4)
    for s in range(len(expires)):
        if expires[s, 0] >= 0 and expires[s, 0] <= time:
            source[:] = np.maximum(0.0, source - deltas[s])
            deltas[s, :] = 0
            expires[s, 0] = -1
            expires[s, 1] = 0
    if clock[4] > 0 and clock[5] <= time and (clock[6] < 0 or clock[5] <= clock[6]):
        clock[5] = round(clock[5] + 1, 12)
        # Boss regeneration is returned to the caller through a separate amount.
        heal = clock[4]
    else:
        heal = 0.0
    for c in range(4):
        for k in range(status.shape[1]):
            row = status[c, k]
            if not row[0]:
                continue
            if k in (0, 7) and row[2] <= time and row[2] <= row[1] and alive[c]:
                value = max(
                    1.0,
                    row[3] * (1 - stats[c, 41] / 100) * (stats[c, 42] if stats[c, 42] > 0 else 1.0),
                )
                hp[c] = max(0.0, hp[c] - value)
                stats[c, 5] = hp[c]
                damage[c] += value
                row[2] = round(row[2] + 1, 12)
            if row[1] <= time and not (k in (0, 7) and row[2] <= row[1]):
                if row[4] >= 0:
                    stats[c, int(row[4])] += row[3]
                row[0] = 0
            if hp[c] <= 0:
                alive[c] = 0
    return damage, heal


@njit(cache=True)
def blocked(c, runtime):
    return runtime[4][c, 4, 0] > 0


@njit(cache=True)
def act(
    time,
    target_hp,
    target,
    stats,
    hp,
    maximum,
    alive,
    target_debuffs,
    data,
    runtime,
    rng,
    received=None,
):
    source, clock, deltas, expires, status = runtime
    _, meta, coefs, con, linear, nodes, choices, immunity, taunt, entry = data
    # Fixed output: released skill, selected skill node, target hit flags and incoming damage.
    hits = np.zeros(4, np.int64)
    amounts = np.zeros(4)
    effects = np.full(4, -1, np.int64)
    triggers = np.full(4, -1, np.int64)
    if (
        clock[0] < 0
        or target_hp <= 0
        or time < deadline(runtime, target_debuffs)
        or target_debuffs[4, 0] > 0
    ):
        return -1, hits, amounts, effects, target_hp, triggers
    if clock[3] >= 0:
        clock[3] = -1
        clock[0] = nodes[int(clock[0]), 6]
        if clock[0] < 0:
            return -1, hits, amounts, effects, target_hp, triggers
    node = int(clock[0])
    mode = int(nodes[node, 0])
    if mode == 1:
        for candidate in range(int(nodes[node, 1]), int(nodes[node, 2])):
            condition = int(nodes[candidate, 8])
            threshold = nodes[candidate, 9]
            low = False
            for c in range(4):
                if alive[c] and maximum[c] > 0 and hp[c] / maximum[c] * 100 < threshold:
                    low = True
            percent = target_hp / target[0] * 100
            if (
                condition == 0
                or condition == 1
                and percent < threshold
                or condition == 2
                and percent > threshold
                or condition == 3
                and low
                or condition == 4
                and not low
                or condition == 5
                and time >= threshold
            ):
                node = candidate
                break
    clock[0] = node
    skill = int(nodes[node, 5])
    following = int(nodes[node, 6])
    selection = int(nodes[node, 7])
    if mode == 2:
        n = int(nodes[node, 4] - nodes[node, 3])
        chosen = np.int64(nodes[node, 3]) + (np.int64(below(rng, n)) if n > 1 else np.int64(0))
        skill = int(choices[chosen, 0])
        following = int(choices[chosen, 1])
        selection = int(choices[chosen, 2])
    if skill < 0:
        clock[3] = round(time + nodes[node, 10], 12)
        return -2, hits, amounts, effects, target_hp, triggers
    attack = source.copy()
    attack[5] = target_hp
    for k, a in ((3, 3), (5, 0), (6, 2)):
        if target_debuffs[k, 0]:
            attack[a] = max(1.0, attack[a] - target_debuffs[k, 5])
    row = meta[skill]
    dtype = int(row[0])
    targets = np.zeros(4, np.int64)
    if dtype < 2:
        if row[5]:
            targets[:] = alive
        else:
            chosen = -1
            has_taunt = False
            if not row[11]:
                for c in range(4):
                    if alive[c] and taunt[c]:
                        has_taunt = True
            candidates = np.zeros(4, np.int64)
            n = 0
            attribute = 5 if selection <= 2 or selection == 7 else 27 if selection <= 4 else 28
            highest = selection in (2, 4, 6)
            for c in range(4):
                if not alive[c] or has_taunt and not taunt[c]:
                    continue
                candidates[n] = c
                n += 1
                if (
                    chosen < 0
                    or selection != 0
                    and selection != 7
                    and (
                        stats[c, attribute] > stats[chosen, attribute]
                        if highest
                        else stats[c, attribute] < stats[chosen, attribute]
                    )
                ):
                    chosen = c
            if selection == 7 and n > 1:
                chosen = np.int64(candidates[np.int64(below(rng, n))])
            if chosen >= 0:
                targets[chosen] = 1
    base = row[2] + dot(attack, coefs[skill])
    if dtype == 2:
        target_hp = min(
            target[0],
            target_hp + base * (1 + attack[20] / 100) * (1 + attack[21] / 100) * target[19],
        )
    for c in range(4):
        if not targets[c]:
            continue
        chance = min(
            1.0,
            max(
                0.0,
                (row[3] + attack[8] - stats[c, 31] + attack[2] / max(1.0, stats[c, 3]) * 30) / 100,
            ),
        )
        if uniform(rng) >= chance:
            continue
        hits[c] = 1
        defense_stats = stats[c].copy()
        if received is not None:
            proc, ranges, emeta, econ = received
            for p in range(ranges[c, 0], ranges[c, 1]):
                if int(proc[p, 0]) == 10 + dtype and uniform(rng) < proc[p, 1] / 100:
                    triggers[c] = p
                    eid = int(proc[p, 2])
                    if emeta[eid, 0] == 2:
                        original = defense_stats.copy()
                        original[22] = maximum[c] - hp[c]
                        for a in range(len(original)):
                            defense_stats[a] += dot(original, econ[eid, a])
                    break
        critical = uniform(rng) < min(1.0, (row[4] + attack[7] + attack[2] / 20) / 100)
        crit = 1.5 + attack[19] / 100 if critical else 1.0
        defense = max(0.0, defense_stats[27 + dtype] - attack[9 + dtype])
        mult = defense_stats[36 + dtype] if defense_stats[36 + dtype] > 0 else 1.0
        value = max(
            1.0,
            (
                base
                * (1 + attack[12 + dtype] / 100)
                * (1 + attack[15 + dtype] / 100)
                * crit
                * row[13 + c]
                * 50
                / (50 + defense)
                * mult
                * (1 - defense_stats[39 + dtype] / 100)
            )
            - defense_stats[34 + dtype],
        )
        amounts[c] = value
        hp[c] = max(0.0, hp[c] - value)
        stats[c, 5] = hp[c]
        life = attack[23 + dtype + 2 * int(row[5])]
        target_hp = min(target[0], target_hp + value * life / 100 * target[19])
        if row[6] == 2:
            k = int(row[7])
            if not immunity[c, k] and uniform(rng) < min(
                1.0, max(0.0, (row[10] + attack[11] - stats[c, 28] / 10) / 100)
            ):
                old = status[c, k]
                if old[0] and old[4] >= 0:
                    stats[c, int(old[4])] += old[3]
                stacks = min(row[17], old[0] + 1)
                next_tick = old[2] if old[0] and row[17] > 1 else round(time + 1, 12)
                value = row[8] + dot(attack, linear[skill])
                attribute = -1
                if k in (0, 7):
                    value = (
                        max(1.0, value * (1 + attack[14] / 100) * (1 + attack[17] / 100)) * stacks
                    )
                elif k in (3, 5, 6, 8, 9, 10, 11, 12, 13):
                    attribute = (
                        27
                        if k == 12
                        else 28
                        if k == 13
                        else 3
                        if k in (3, 11)
                        else 0
                        if k in (5, 8)
                        else 2
                        if k in (6, 10)
                        else 1
                    )
                    value = min(max(0.0, stats[c, attribute] - 1.0), value * stacks)
                    stats[c, attribute] -= value
                first_applied = old[6] if old[0] and old[5] == skill else time
                status[c, k] = np.array(
                    [
                        stacks,
                        round(time + row[9], 12),
                        next_tick,
                        value,
                        float(attribute),
                        float(skill),
                        first_applied,
                    ]
                )
                effects[c] = k
    if row[6] in (1, 3) and row[12] and uniform(rng) < row[10] / 100:
        stacks = min(row[17], expires[skill, 1] + 1)
        expires[skill, 1] = stacks
        expires[skill, 0] = round(time + row[9], 12) if row[9] > 0 else math.inf
        if row[6] == 3:
            clock[4] = (
                (row[8] + dot(attack, linear[skill]))
                * (1 + attack[20] / 100)
                * (1 + attack[21] / 100)
                * target[19]
                * stacks
            )
            clock[5] = round(time + 1, 12)
            clock[6] = round(time + row[9], 12) if row[9] > 0 else -1
        else:
            source[:] = np.maximum(0.0, source - deltas[skill])
            deltas[skill, :] = 0
            for a in range(len(source)):
                deltas[skill, a] = (dot(source, con[skill, a]) + linear[skill, a]) * stacks
            source[:] += deltas[skill]
    clock[0] = following
    clock[1] = time
    clock[2] = row[1]
    return skill, hits, amounts, effects, target_hp, triggers
