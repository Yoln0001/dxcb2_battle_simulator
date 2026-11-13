from pathlib import Path
import sys, copy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.simulation import simulate_single

stats = {
    "strength": 0,
    "speed": 99,
    "constitution": 100,
    "magic": 1000,
    "technique": 0,
    "hitRate": 100,
    "magicDamage": 0,
}
config = {
    "battle": {"duration": 16.5},
    "target": {
        "hitPoint": 10000000,
        "race": "傀儡",
        "armor": 999999,
        "resistance": 0,
        "magicVulnerability": 1,
        "physicalVulnerability": 1,
        "dotVulnerability": 1,
    },
    "characters": [
        {
            "name": f"角色 {i + 1}",
            "job": "寒霜法师",
            "enabled": True,
            "stats": copy.deepcopy(stats),
            "equipment": {},
            "skillGroup": "g",
        }
        for i in range(4)
    ],
}
skill = {
    "id": "s",
    "name": "冰锥术",
    "job": "寒霜法师",
    "damageType": "magic",
    "cooldown": 1.5,
    "hitRate": 0,
    "coefficients": {"magic": 1},
    "effect": None,
}
group = {
    "id": "g",
    "job": "寒霜法师",
    "entry": "n",
    "subgroups": [
        {"id": "sub", "nextGroup": "sub", "skills": [{"id": "n", "skillId": "s", "next": ""}]}
    ],
}
lib = {"s": skill}
groups = {"g": group}
before = copy.deepcopy(config)
a = simulate_single(config, {}, lib, groups, seed=77, rules={"hit_confirmed": True})
b = simulate_single(config, {}, lib, groups, seed=77, rules={"hit_confirmed": True})
assert a == b and config == before
assert [f["time"] for f in a["timeline"]] == [0, 1.5, 4.5, 7.5, 10.5, 13.5, 16.5]
assert sum(e["type"] == "skill_released" for f in a["timeline"] for e in f["events"]) == 24
assert a["total_damage"] == 24000
assert all(len(f["snapshot"]["characters"]) == 4 for f in a["timeline"])
assert a["timeline"][0]["snapshot"]["characters"][0]["last_action_at"] is None
assert a["timeline"][1]["snapshot"]["characters"][0]["last_action_at"] == 1.5
# Per-node jump takes precedence over subgroup end; no jump ends execution.
g = copy.deepcopy(group)
g["subgroups"][0]["skills"] = [
    {"id": "n", "skillId": "s", "next": "n2"},
    {"id": "n2", "skillId": "s", "next": ""},
]
g["subgroups"][0]["nextGroup"] = ""
c = simulate_single(config, {}, lib, {"g": g}, seed=77)
assert sum(e["type"] == "skill_released" for f in c["timeline"] for e in f["events"]) == 8
# Recovery triggers persistent equipment stacks, refreshed without compounding old delta.
heal = {
    **skill,
    "damageType": "none",
    "name": "凝神静气",
    "coefficients": {"magic": 0.1},
    "cooldown": 0,
    "effect": {
        "kind": "buff",
        "type": "technique",
        "duration": 15,
        "baseValue": 5,
        "recipient": "allAllies",
        "triggerRate": 100,
        "conversions": [{"target": "technique", "enabled": True, "coefficients": {"magic": 0.1}}],
    },
}
item = {
    "id": "heart",
    "category": "accessory",
    "name": "影兽之心",
    "startingBuff": {"enabled": False},
    "triggerEnabled": True,
    "triggerEffects": [
        {
            "name": "影兽buff",
            "triggerType": "none",
            "probability": 100,
            "effect": {
                "kind": "buff",
                "type": "magic",
                "recipient": "self",
                "duration": 99,
                "maxStacks": 5,
                "conversions": [
                    {"target": "magic", "enabled": True, "coefficients": {"magic": 0.12}}
                ],
            },
        }
    ],
}
cfg = copy.deepcopy(config)
cfg["battle"]["duration"] = 3
cfg["characters"][0]["equipment"] = {"accessory1": "heart"}
for row in cfg["characters"][1:]:
    row["enabled"] = False
r = simulate_single(cfg, {"heart": item}, {"s": heal}, groups, seed=3, rules={"healing": True})
assert r["final_state"]["characters"][0]["stats"]["magic"] == 1240
assert r["timeline"][1]["snapshot"]["characters"][0]["stats"]["magic"] == 1120
assert r["final_state"]["characters"][0]["buffs"][0]["stacks"] == 2
heals = [e for f in r["timeline"] for e in f["events"] if e["type"] == "healing"]
assert [e["amount"] for e in heals] == [100, 112]
first_events = r["timeline"][1]["events"]
heal_pos = next(i for i, e in enumerate(first_events) if e["type"] == "healing")
assert all(i > heal_pos for i, e in enumerate(first_events) if e["type"] == "buff_applied")

# A contract tick shares a frame with an owner action; sacrifice is always first.
cfg = copy.deepcopy(config)
cfg["battle"]["duration"] = 14.1
cfg["characters"][0].update(contract="旧日支配者-魔", negativeEffect="群体献祭", skillMultiplier=2)
for row in cfg["characters"]:
    row["stats"]["strength"] = 260
    row["stats"]["speed"] = 99
s = {**skill, "cooldown": -1.6}
r = simulate_single(cfg, {}, {"s": s}, groups, seed=9)
tick = next(f for f in r["timeline"] if f["time"] == 14.1)
assert any(e["type"] == "contract_damage" for e in tick["events"])
frame = next(f for f in r["timeline"] if f["time"] == 10)
assert [e["type"] for e in frame["events"][:4]] == ["sacrifice_tick"] * 4
assert len({f["time"] for f in r["timeline"]}) == len(r["timeline"])
# Burn ticks use application snapshot and refresh expiry.
cfg = copy.deepcopy(config)
cfg["battle"]["duration"] = 3.5
for row in cfg["characters"][1:]:
    row["enabled"] = False
burn = {
    **skill,
    "effect": {
        "kind": "debuff",
        "type": "burn",
        "duration": 2,
        "applicationRate": 100,
        "baseValue": 0,
        "coefficients": {"magic": 0.1},
    },
}
r = simulate_single(
    cfg, {}, {"s": burn}, groups, seed=3, rules={"burn_ticks": True, "hit_confirmed": True}
)
assert any(e["type"] == "dot_damage" for f in r["timeline"] for e in f["events"])
assert r["timeline"][0]["snapshot"]["target_debuffs"] == []
print(
    "PASS: seeded 0.1s timeline, graph flow, idle omission, independent snapshots, damage, buffs, sacrifice priority, contract and burn"
)

# A six-second burn always ticks six times, including exactly at expiry.
cfg = copy.deepcopy(config)
cfg["battle"]["duration"] = 8
for row in cfg["characters"][1:]:
    row["enabled"] = False
one = copy.deepcopy(group)
one["subgroups"][0]["nextGroup"] = ""
burn["effect"]["duration"] = 6
for seed in range(10):
    r = simulate_single(cfg, {}, {"s": burn}, {"g": one}, seed=seed)
    ticks = [
        f["time"] for f in r["timeline"] if any(e["type"] == "dot_damage" for e in f["events"])
    ]
    assert ticks == [2.5, 3.5, 4.5, 5.5, 6.5, 7.5], ticks
    assert not r["final_state"]["target_debuffs"]
# True damage ignores armor, resistance, crit and race, but retains the five factors.
from engine.runtime.damage import calculate_equipment_damage

r = calculate_equipment_damage(
    {"magic": 100, "magicDamage": 26, "finalMagicDamage": 8},
    {"coefficients": {"magic": 2}},
    {"resistance": 999999, "magicVulnerability": 1.12, "magicReduction": 25},
    "magic",
)
assert abs(r["final_damage"] - 200 * 1.26 * 1.08 * 1.12 * 0.75) < 1e-8
# Immediate action overrides even a large ordinary cooldown to 0.5s.
item = {
    "id": "quick",
    "category": "accessory",
    "name": "连击装备",
    "startingBuff": {"enabled": False},
    "triggerEnabled": True,
    "triggerEffects": [
        {
            "name": "连击",
            "triggerType": "magic",
            "probability": 100,
            "effect": {"kind": "immediateAction"},
        }
    ],
}
cfg["battle"]["duration"] = 3
cfg["characters"][0]["equipment"] = {"accessory1": "quick"}
r = simulate_single(cfg, {"quick": item}, {"s": {**skill, "cooldown": 99}}, groups, seed=2)
assert [
    f["time"] for f in r["timeline"] if any(e["type"] == "skill_released" for e in f["events"])
] == [1.5, 2, 2.5, 3]
print(
    "PASS: six burn ticks at inclusive expiry across seeds, five-factor equipment damage and forced 0.5s actions"
)

from engine.runtime.damage import calculate_hit_chance

chance = calculate_hit_chance(
    {"technique": 4375, "hitRate": 58.5}, {"hitRate": 41}, {"speed": 43750, "dodgeRate": 10}
)
assert abs(chance["technique_percent"] - 3) < 1e-9
assert abs(chance["probability"] - 0.925) < 1e-9
cfg = copy.deepcopy(config)
cfg["battle"]["duration"] = 1.5
for row in cfg["characters"][1:]:
    row["enabled"] = False
cfg["characters"][0]["contract"] = "旧日支配者-魔"
cfg["characters"][0]["negativeEffect"] = "群体献祭"
cfg["characters"][0]["stats"].update(healingBonus=26, finalHealingBonus=8)
healing = {**heal, "coefficients": {"magic": 0.01}, "effect": None}
r = simulate_single(cfg, {}, {"s": healing}, groups, seed=3)
heal_event = next(e for f in r["timeline"] for e in f["events"] if e["type"] == "healing")
assert abs(heal_event["amount"] - 10 * 1.26 * 1.08) < 1e-9
# Whole-team healing applies caster factors and skips disabled teammates.
team_config = copy.deepcopy(cfg)
for row in team_config["characters"][1:]:
    row["enabled"] = True
team_config["characters"][3]["enabled"] = False
team_heal = {**healing, "healingRecipient": "allAllies"}
team_result = simulate_single(team_config, {}, {"s": team_heal}, groups, seed=3)
team_events = [
    e
    for f in team_result["timeline"]
    for e in f["events"]
    if e["type"] == "healing" and e["character"] == 1
]
assert [e["target_character"] for e in team_events] == [1, 2, 3]
assert all(abs(e["amount"] - 10 * 1.26 * 1.08) < 1e-9 for e in team_events)
# Log calculated healing even when it exceeds missing health.
overheal = {**healing, "coefficients": {"magic": 10}, "healingRecipient": "allAllies"}
over_result = simulate_single(team_config, {}, {"s": overheal}, groups, seed=3)
over_events = [
    e
    for f in over_result["timeline"]
    for e in f["events"]
    if e["type"] == "healing" and e["character"] == 1
]
assert all(abs(e["amount"] - 10000 * 1.26 * 1.08) < 1e-9 for e in over_events)
assert all(e["effective_amount"] == 50 for e in over_events)
assert all(c["current_hp"] <= c["maximum_hp"] for c in over_result["final_state"]["characters"])
# Effect damage type is independent of the skill's trigger type.
item = {
    "id": "true",
    "category": "accessory",
    "name": "真伤装备",
    "startingBuff": {"enabled": False},
    "triggerEnabled": True,
    "triggerEffects": [
        {
            "name": "物理真伤",
            "triggerType": "magic",
            "probability": 100,
            "effect": {"kind": "physicalTrueDamage", "coefficients": {"magic": 1}},
        }
    ],
}
cfg["characters"][0]["equipment"] = {"accessory1": "true"}
cfg["target"].update(physicalReduction=50, magicReduction=0)
r = simulate_single(cfg, {"true": item}, {"s": skill}, groups, seed=3)
e = next(e for f in r["timeline"] for e in f["events"] if e["type"] == "equipment_damage")
assert e["damage_type"] == "physical" and e["damage"] == 500
print(
    "PASS: technique/target-speed hit chance, healing percentages, explicit true damage type independent of trigger"
)

# A guaranteed skill miss does not prevent an already-triggered true-damage effect.
cfg["characters"][0]["stats"]["hitRate"] = 0
cfg["characters"][0]["stats"]["technique"] = 0
miss_skill = {**skill, "hitRate": 0}
for kind, damage_type in [("physicalTrueDamage", "physical"), ("magicTrueDamage", "magic")]:
    item["triggerEffects"][0]["effect"]["kind"] = kind
    result = simulate_single(cfg, {"true": item}, {"s": miss_skill}, groups, seed=3)
    events = [e for f in result["timeline"] for e in f["events"]]
    assert any(e["type"] == "skill_missed" for e in events)
    assert not any(e["type"] == "skill_damage" for e in events)
    damage_event = next(e for e in events if e["type"] == "equipment_damage")
    assert damage_event["damage_type"] == damage_type and damage_event["damage"] > 0
    assert result["total_damage"] == damage_event["damage"]
print("PASS: physical and magic equipment true damage still land when the skill misses")

# Same-timestamp character actions always follow slot order, regardless of seed.
for seed in range(20):
    result = simulate_single(config, {}, lib, groups, seed=seed)
    for frame in result["timeline"]:
        actors = [e["character"] for e in frame["events"] if e["type"] == "skill_released"]
        assert actors == sorted(actors), (seed, frame["time"], actors)
print("PASS: same-timestamp actions follow character 1/2/3/4 across random seeds")

# Buff expiry and contract ticks cannot split the ordered action block.
for seed in range(40):
    cfg = __import__("copy").deepcopy(config)
    cfg["characters"][0].update(contract="旧日支配者-魔", negativeEffect="无", skillMultiplier=1)
    for c in cfg["characters"]:
        c["stats"]["strength"] = 260
        c["stats"]["speed"] = 99
    cfg["battle"]["duration"] = 14.1
    block_skill = {
        **skill,
        "cooldown": -1.6,
        "effect": {
            "kind": "buff",
            "type": "technique",
            "duration": 3.5,
            "baseValue": 0,
            "recipient": "allAllies",
            "triggerRate": 100,
            "conversions": [
                {"target": "technique", "enabled": True, "coefficients": {"magic": 0.1}}
            ],
        },
    }
    result = simulate_single(cfg, {}, {"s": block_skill}, groups, seed=seed)
    for frame in result["timeline"]:
        events = frame["events"]
        positions = [i for i, e in enumerate(events) if e["type"] == "skill_released"]
        if len(positions) > 1:
            assert not any(
                e["type"] in ["buff_expired", "contract_damage"]
                for e in events[positions[0] : positions[-1] + 1]
            ), (seed, frame["time"])
print(
    "PASS: character action block remains contiguous; buff expirations and contracts occur only before/after it"
)

# Different casters/skill levels overwrite one shared burn, restarting its clock.
from engine.runtime.simulation import SingleBattle

cfg = __import__("copy").deepcopy(config)
battle = SingleBattle(cfg, {}, lib, groups, seed=1)
effect = {
    "kind": "debuff",
    "type": "burn",
    "duration": 6,
    "applicationRate": 100,
    "baseValue": 0,
    "coefficients": {"magic": 0.1},
}
battle.state.time = 15.3
battle.apply_debuff(
    battle.state.characters[0], "炎爆术Lv.8·灼烧", effect, {"magic": 1000, "abnormalBonus": 0}
)
assert battle.boss_debuffs["灼烧"]["next_tick_at"] == 16.3
battle.state.time = 16.4
battle.apply_debuff(
    battle.state.characters[1], "炎爆术Lv.7·灼烧", effect, {"magic": 2000, "abnormalBonus": 0}
)
assert len(battle.boss_debuffs) == 1
burn_state = battle.boss_debuffs["灼烧"]
assert burn_state["character"] == 2 and burn_state["source_stats"]["magic"] == 2000
assert burn_state["next_tick_at"] == 17.4 and burn_state["expires_at"] == 22.4
assert burn_state["stacks"] == 1
print(
    "PASS: burn shared across casters and skill names; replacement resets damage snapshot and tick/expiry clock"
)

# A target debuff is replacement even when an imported equipment defines maxStacks.
effect["maxStacks"] = 5
battle.state.time = 17
battle.apply_debuff(
    battle.state.characters[0], "另一施法者", effect, {"magic": 3000}, equipment=True
)
assert len(battle.boss_debuffs) == 1 and battle.boss_debuffs["灼烧"]["stacks"] == 1
# Different levels share one buff name; later caster replaces the prior delta.
cfg = __import__("copy").deepcopy(config)
cfg["battle"]["duration"] = 1.5
buff_effect = {
    "kind": "buff",
    "type": "technique",
    "duration": 15,
    "baseValue": 0,
    "recipient": "allAllies",
    "triggerRate": 100,
    "conversions": [{"target": "technique", "enabled": True, "coefficients": {"magic": 0.1}}],
}
skills_map = {}
groups_map = {}
for i, c in enumerate(cfg["characters"]):
    c["stats"].update(magic=(i + 1) * 1000, technique=100)
    c["skillGroup"] = "g" + str(i)
    key = "s" + str(i)
    skills_map[key] = {
        **skill,
        "name": "静气凝神Lv." + str(i + 7),
        "damageType": "none",
        "effect": buff_effect,
    }
    groups_map[c["skillGroup"]] = {
        "job": c["job"],
        "entry": "n",
        "subgroups": [
            {"id": "sub", "nextGroup": "", "skills": [{"id": "n", "skillId": key, "next": ""}]}
        ],
    }
result = simulate_single(cfg, {}, skills_map, groups_map, seed=1)
for c in result["final_state"]["characters"]:
    buffs = [b for b in c["buffs"] if b["name"] == "静气凝神"]
    assert len(buffs) == 1 and buffs[0]["source_character"] == 4 and buffs[0]["stacks"] == 1
    assert c["stats"]["technique"] == 500
print(
    "PASS: target debuffs never stack; cross-caster skill buff levels share one name and replace old deltas"
)
