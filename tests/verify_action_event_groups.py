from pathlib import Path
import sys, copy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.skill_groups.validation import validate_group
from engine.runtime.simulation import SingleBattle

skill = {
    "name": "Fire",
    "job": "岩浆法师",
    "damageType": "magic",
    "cooldown": 0,
    "coefficients": {"magic": 1},
    "criticalRate": 0,
    "hitRate": 100,
    "effect": {
        "kind": "debuff",
        "type": "burn",
        "applicationRate": 100,
        "baseValue": 10,
        "duration": 3,
        "coefficients": {},
    },
}
group = validate_group(
    {
        "schemaVersion": 2,
        "id": "g",
        "name": "group",
        "job": "岩浆法师",
        "entry": "n",
        "subgroups": [{"id": "s", "skills": [{"id": "n", "skillId": "fire", "next": "n"}]}],
    }
)
config = {
    "battle": {"duration": 4},
    "target": {"hitPoint": 1e9, "speed": 100},
    "characters": [
        {
            "enabled": i == 0,
            "job": "岩浆法师",
            "skillGroup": "g",
            "stats": {"magic": 100, "constitution": 100, "speed": 100},
            "equipment": {"weapon": "w"} if i == 0 else {},
        }
        for i in range(4)
    ],
}
gear = {
    "w": {
        "id": "w",
        "name": "Weapon",
        "category": "weapon",
        "startingBuff": {"enabled": False},
        "triggerEnabled": True,
        "triggerEffects": [
            {
                "name": "True damage",
                "triggerType": "magic",
                "probability": 100,
                "effect": {"kind": "magicTrueDamage", "coefficients": {"magic": 0.5}},
            }
        ],
    }
}
r = SingleBattle(config, gear, {"fire": skill}, {"g": group}, seed=1).run()
for frame in r["timeline"]:
    actions = [e for e in frame["events"] if e["type"] == "skill_released"]
    for action in actions:
        children = [e for e in frame["events"] if e.get("action_id") == action["action_id"]]
        assert {
            "skill_released",
            "equipment_triggered",
            "skill_damage",
            "target_debuff_applied",
            "equipment_damage",
        } <= set(e["type"] for e in children)
        assert all(e["action_character"] == 1 for e in children)
    assert all("action_id" not in e for e in frame["events"] if e["type"] == "dot_damage")
assert any(e["type"] == "dot_damage" for f in r["timeline"] for e in f["events"])
print(
    "PASS: one action ID includes skill, equipment proc, direct/true damage and burn attachment; later DOT ticks stay independent"
)

# Timeline refs identify the source buff at action time and persist on later DOT ticks.
tracked_gear = copy.deepcopy(gear)
tracked_gear["w"]["effectName"] = "Source boost"
tracked_gear["w"]["startingBuff"] = {
    "enabled": True,
    "target": "magic",
    "recipient": "self",
    "coefficients": {"strength": 0, "magic": 0.1, "technique": 0, "speed": 0},
}
tracked = SingleBattle(config, tracked_gear, {"fire": skill}, {"g": group}, seed=1).run()
for frame in tracked["timeline"]:
    for event in frame["events"]:
        if "action_id" in event or event["type"] == "dot_damage":
            assert any(
                b["name"] == "Source boost"
                and b["source_character"] == 1
                and b["target_character"] == 1
                for b in event["active_buff_refs"]
            ), event
plain = SingleBattle(config, gear, {"fire": skill}, {"g": group}, seed=1).run()
assert all(
    e["active_buff_refs"] == []
    for f in plain["timeline"]
    for e in f["events"]
    if "action_id" in e or e["type"] == "dot_damage"
)
print(
    "PASS: active buff source refs on grouped actions and snapshotted DOT ticks; unbuffed actions have empty refs"
)
