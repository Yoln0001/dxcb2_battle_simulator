from pathlib import Path
import sys, random, copy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from backend.skill_groups.validation import validate_group
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle

skill = {
    "name": "Fire",
    "job": "岩浆法师",
    "damageType": "magic",
    "cooldown": 2,
    "coefficients": {"magic": 1},
    "criticalRate": 0,
    "hitRate": 100,
}
skills = {"f": skill}
group = {
    "schemaVersion": 2,
    "id": "g",
    "name": "wait test",
    "job": "岩浆法师",
    "entry": "fire",
    "subgroups": [
        {
            "id": "s",
            "skills": [
                {"id": "fire", "skillId": "f", "next": "wait"},
                {"id": "wait", "skillId": "__wait__", "waitDuration": 2, "next": "end"},
                {"id": "end", "skillId": "f", "next": ""},
            ],
        }
    ],
}
cfg = {
    "battle": {"duration": 10},
    "target": {"hitPoint": 1e9, "speed": 100},
    "characters": [
        {
            "enabled": i == 0,
            "job": "岩浆法师",
            "skillGroup": "g",
            "stats": {"magic": 100, "constitution": 100, "speed": 100},
            "equipment": {},
        }
        for i in range(4)
    ],
}


def check(config, g, expected, equipment={}):
    saved = validate_group(g)
    arrays, _, _ = prepare(config, equipment, skills, {"g": saved})
    for seed in range(3):
        py = SingleBattle(config, equipment, skills, {"g": saved}, seed=seed)
        result = py.run()
        events = [(frame["time"], e) for frame in result["timeline"] for e in frame["events"]]
        starts = [time for time, e in events if e["type"] == "wait_started"]
        releases = [
            time
            for time, e in events
            if e["type"] == "skill_released" and e["skill_name"] == "Fire"
        ]
        assert starts == expected[0] and releases == expected[1], (starts, releases)
        out = battle(*arrays, np.array(random.Random(seed).getstate()[1], dtype=np.uint32))
        assert np.allclose(out[2], result["character_damage"], rtol=1e-10), (
            out[2],
            result["character_damage"],
        )
        assert not any(e["type"] == "equipment_triggered" for _, e in events)


check(cfg, group, ([5.0], [1.5, 7.0]))
first = copy.deepcopy(group)
first["entry"] = "wait"
check(cfg, first, ([1.5], [3.5]))
strike = copy.deepcopy(cfg)
strike["characters"][0]["firstStrike"] = True
check(strike, first, ([0.1], [2.1]))
# Fractional durations complete on the next 0.1s simulation check.
fraction = copy.deepcopy(first)
fraction["subgroups"][0]["skills"][1]["waitDuration"] = 0.25
check(cfg, fraction, ([1.5], [1.8]))
# Support-triggered equipment must not roll while waiting.
equip = {
    "support": {
        "id": "support",
        "name": "Support proc",
        "category": "weapon",
        "startingBuff": {"enabled": False},
        "triggerEnabled": True,
        "triggerEffects": [
            {
                "name": "Buff",
                "triggerType": "none",
                "probability": 100,
                "effect": {
                    "kind": "buff",
                    "type": "magic",
                    "duration": 2,
                    "recipient": "self",
                    "conversions": [
                        {"target": "magic", "enabled": True, "coefficients": {"magic": 1}}
                    ],
                },
            }
        ],
    }
}
with_gear = copy.deepcopy(cfg)
with_gear["characters"][0]["equipment"] = {"weapon": "support"}
check(with_gear, first, ([1.5], [3.5]), equip)
# An immediate-action proc cannot count as CD completion for a wait node.
forced_gear = copy.deepcopy(equip)
forced_gear["support"]["triggerEffects"][0].update(
    triggerType="magic", effect={"kind": "immediateAction"}
)
arrays, _, _ = prepare(with_gear, forced_gear, skills, {"g": validate_group(group)})
py = SingleBattle(with_gear, forced_gear, skills, {"g": validate_group(group)}, seed=1)
result = py.run()
assert [
    f["time"] for f in result["timeline"] for e in f["events"] if e["type"] == "wait_started"
] == [5.0]
out = battle(*arrays, np.array(random.Random(1).getstate()[1], dtype=np.uint32))
assert np.allclose(out[2], result["character_damage"], rtol=1e-10)
# Conditional decision slots may also select a wait in if or else.
conditional = copy.deepcopy(group)
conditional["subgroups"] = [
    {
        "id": "s",
        "conditionsEnabled": True,
        "nextGroup": "s",
        "skills": [
            {
                "id": "fire",
                "skillId": "__wait__",
                "decision": {
                    "cases": [{"kind": "allyHealthBelow", "threshold": 20, "skillId": "f"}],
                    "elseSkillId": "__wait__",
                    "elseWaitDuration": 2,
                },
            }
        ],
    }
]
check(cfg, conditional, ([1.5, 3.5, 5.5, 7.5, 9.5], []))
for duration in (0, -1, float("nan"), 3601):
    invalid = copy.deepcopy(group)
    invalid["subgroups"][0]["skills"][1]["waitDuration"] = duration
    try:
        validate_group(invalid)
    except ValueError:
        pass
    else:
        raise AssertionError(duration)
print(
    "PASS: wait starts after CD, resumes without extra CD, first strike, fractional waits, no equipment procs and compiled parity"
)
