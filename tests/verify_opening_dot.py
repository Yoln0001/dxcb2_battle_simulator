from pathlib import Path
import sys, copy, random

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from backend.equipment.validation import validate_equipment
from backend.skill_groups.validation import validate_group
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle

gear = {
    "a": {
        "schemaVersion": 1,
        "id": "a",
        "name": "DOT gear",
        "category": "armor",
        "weaponJob": "",
        "attackType": "physical",
        "effectName": "",
        "triggerEnabled": False,
        "startingBuff": {
            "enabled": False,
            "target": "none",
            "recipient": "self",
            "coefficients": dict.fromkeys(["strength", "magic", "technique", "speed"], 0),
        },
        "triggerRate": 0,
        "effect": None,
        "triggerEffects": [],
        "startingDebuffs": {
            "enabled": True,
            "name": "腐蚀",
            "physicalVulnerability": 0,
            "magicVulnerability": 0,
            "dotEnabled": True,
            "dotDamage": 100,
        },
    }
}
gear["a"] = validate_equipment(gear["a"])
group = validate_group(
    {
        "schemaVersion": 2,
        "id": "g",
        "name": "wait",
        "job": "岩浆法师",
        "entry": "wait",
        "subgroups": [
            {
                "id": "s",
                "skills": [
                    {"id": "wait", "skillId": "__wait__", "waitDuration": 300, "next": "wait"}
                ],
            }
        ],
    }
)
cfg = {
    "battle": {"duration": 205},
    "target": {"hitPoint": 1e9, "speed": 100, "partyWipe": {"enabled": True, "time": 200}},
    "characters": [
        {
            "enabled": i == 0,
            "job": "岩浆法师",
            "skillGroup": "g",
            "stats": {
                "magic": 100,
                "constitution": 100,
                "speed": 100,
                "dotDamage": 20,
                "finalDotDamage": 50,
            },
            "equipment": {"armor": "a"} if i == 0 else {},
        }
        for i in range(4)
    ],
}


def check(config, equipment, expected):
    outputs = []
    for timeline in (True, False):
        r = SingleBattle(
            config, equipment, {}, {"g": group}, seed=2, record_timeline=timeline
        ).run()
        outputs.append(r)
        assert np.isclose(r["total_damage"], expected), (r["total_damage"], expected)
    arrays, _, _ = prepare(config, equipment, {}, {"g": group})
    out = battle(*arrays, np.array(random.Random(2).getstate()[1], dtype=np.uint32))
    assert np.allclose(out[2], outputs[0]["character_damage"])
    return outputs[0]


r = check(cfg, gear, 200 * 180)
assert r["end_reason"] == "party_defeated"
frame = next(f for f in r["timeline"] if f["time"] == 200)
assert [e["type"] for e in frame["events"]][:2] == ["dot_damage", "boss_periodic_kill"]
assert len([e for f in r["timeline"] for e in f["events"] if e["type"] == "dot_damage"]) == 200
# Same name replaces across characters; final owner's damage bonuses apply.
multi = copy.deepcopy(cfg)
multi["characters"][1]["enabled"] = True
multi["characters"][1]["equipment"] = {"armor": "a"}
multi["characters"][1]["stats"]["dotDamage"] = 0
r = check(multi, gear, 200 * 150)
assert r["character_damage"][0] == 0 and r["character_damage"][1] == 30000
# A lethal DOT at 200 wins before the wipe; zero outgoing actions occur at that time.
lethal = copy.deepcopy(cfg)
lethal["target"]["hitPoint"] = 36000
assert check(lethal, gear, 36000)["end_reason"] == "target_defeated"
reduced = copy.deepcopy(cfg)
reduced["target"]["dotReduction"] = 50
check(reduced, gear, 18000)
print(
    "PASS: named opening DOT, one-second ticks, owner DOT/imprint bonuses, same-name overwrite, reductions, tick-before-wipe at 200, lethal DOT priority and compiled/fast parity"
)

# Multiple opening entries: different names coexist, same names replace within the item.
multiple = copy.deepcopy(gear)
multiple["a"]["startingDebuffs"]["entries"] = [
    {"name": "腐蚀", "dotEnabled": True, "dotDamage": 100, "physicalVulnerability": 20},
    {"name": "燃蚀", "dotEnabled": True, "dotDamage": 50, "magicVulnerability": 10},
    {"name": "腐蚀", "dotEnabled": True, "dotDamage": 25, "physicalVulnerability": 5},
]
r = check(cfg, multiple, 200 * 135)
dots = [b for b in r["final_state"]["target_debuffs"] if b["type"] == "openingDot"]
assert len(dots) == 2
assert sorted(b["damage"] for b in dots) == [45, 90]
state = SingleBattle(cfg, multiple, {}, {"g": group}, seed=2).state
assert state.target["physicalVulnerability"] == 1.05 and state.target["magicVulnerability"] == 1.1
print("PASS: multiple debuffs per equipment, coexistence and same-type/name overwrite")
