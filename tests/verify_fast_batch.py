from pathlib import Path
import sys, copy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.simulation import SingleBattle

stats = {
    "constitution": 100,
    "magic": 1000,
    "technique": 300,
    "strength": 200,
    "speed": 999,
    "hitRate": 55,
}
config = {
    "battle": {"duration": 30},
    "target": {"hitPoint": 75000, "speed": 5000, "resistance": 100, "magicVulnerability": 1.12},
    "characters": [
        {
            "job": "法师",
            "enabled": True,
            "stats": copy.deepcopy(stats),
            "equipment": {},
            "skillGroup": "g",
        }
        for _ in range(4)
    ],
}
config["characters"][0].update(
    contract="旧日支配者-魔", negativeEffect="群体献祭", skillMultiplier=2
)
conversions = [
    {"target": "strength", "enabled": True, "coefficients": {"strength": 0.2}},
    {"target": "technique", "enabled": True, "coefficients": {"magic": 0.1}},
]
skills = {
    "hit": {
        "name": "火球Lv.7",
        "job": "法师",
        "damageType": "magic",
        "cooldown": -1.5,
        "hitRate": 30,
        "criticalRate": 20,
        "coefficients": {"magic": 3},
        "effect": {
            "kind": "debuff",
            "type": "burn",
            "duration": 6,
            "applicationRate": 80,
            "baseValue": 1,
            "coefficients": {"technique": 0.25},
        },
    },
    "heal": {
        "name": "凝神静气Lv.7",
        "job": "法师",
        "damageType": "none",
        "cooldown": -1,
        "coefficients": {"magic": 0.1},
        "effect": {
            "kind": "buff",
            "type": "strength",
            "duration": 0.35,
            "triggerRate": 75,
            "recipient": "allAllies",
            "conversions": conversions,
            "baseValue": 0,
        },
    },
}
groups = {
    "g": {
        "job": "法师",
        "entry": "a",
        "subgroups": [
            {
                "id": "sub",
                "nextGroup": "sub",
                "skills": [
                    {"id": "a", "skillId": "hit", "next": ""},
                    {"id": "b", "skillId": "heal", "next": ""},
                ],
            }
        ],
    }
}
item = {
    "id": "quick",
    "name": "装备",
    "category": "accessory",
    "startingBuff": {"enabled": False},
    "triggerEnabled": True,
    "triggerEffects": [
        {
            "name": "连击",
            "triggerType": "magic",
            "probability": 50,
            "effect": {"kind": "immediateAction"},
        }
    ],
}
for c in config["characters"]:
    c["equipment"] = {"accessory1": "quick"}
for seed in range(50):
    scenario = copy.deepcopy(config)
    scenario_skills = copy.deepcopy(skills)
    if seed % 2:
        scenario["target"]["hitPoint"] = 2000000
        scenario_skills["heal"]["coefficients"] = {"magic": 0.01}
    slow = SingleBattle(scenario, {"quick": item}, scenario_skills, groups, seed=seed).run()
    fast_battle = SingleBattle(
        scenario, {"quick": item}, scenario_skills, groups, seed=seed, record_timeline=False
    )
    fast = fast_battle.run()
    for key in [
        "total_damage",
        "end_reason",
        "duration",
        "character_damage",
        "effect_counts",
        "warnings",
    ]:
        assert slow[key] == fast[key], (seed, key)
    for old, new in zip(slow["final_state"]["characters"], fast_battle.state.characters):
        assert (
            old["stats"] == new.stats
            and old["alive"] == new.alive
            and old["current_hp"] == new.current_hp
        )
print(
    "PASS: 50 seeds fast/0.1s reference identical: pass outcome, damage, proc counts, burn, buffs, dynamic cooldown, contract, sacrifice and death"
)
