from pathlib import Path
import sys, copy, random
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.simulation import simulate_single, SingleBattle
from engine.runtime.cooldowns import check_action_ready, current_action_deadline
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle

stats = {
    "strength": 200,
    "speed": 99,
    "constitution": 100,
    "magic": 1000,
    "technique": 0,
    "hitRate": 100,
}
config = {
    "battle": {"duration": 12},
    "target": {"hitPoint": 1e9, "speed": 100, "magicVulnerability": 1, "resistance": 0},
    "characters": [
        {
            "name": str(i),
            "job": "寒霜法师",
            "enabled": i < 2,
            "firstStrike": i == 0,
            "stats": copy.deepcopy(stats),
            "equipment": {},
            "skillGroup": "g",
        }
        for i in range(4)
    ],
}
skills = {
    "s": {
        "id": "s",
        "name": "冰锥术",
        "job": "寒霜法师",
        "damageType": "magic",
        "cooldown": 1.5,
        "hitRate": 0,
        "coefficients": {"magic": 1},
        "effect": None,
    }
}
groups = {
    "g": {
        "id": "g",
        "job": "寒霜法师",
        "entry": "n",
        "subgroups": [
            {"id": "sub", "nextGroup": "sub", "skills": [{"id": "n", "skillId": "s", "next": ""}]}
        ],
    }
}
result = simulate_single(config, {}, skills, groups, seed=77)
for index, expected in [(1, [0.1, 5.1, 10.1]), (2, [3.5, 8.5])]:
    times = [
        f["time"]
        for f in result["timeline"]
        if any(e["type"] == "skill_released" and e["character"] == index for e in f["events"])
    ]
    assert times == expected, (index, times)
state = SingleBattle(config, {}, skills, groups, seed=77).state
c = state.characters[0]
assert (
    current_action_deadline(c) == 0.1
    and not check_action_ready(c, 0)["ready"]
    and check_action_ready(c, 0.1)["ready"]
)
c.stats["strength"] = 99999
assert current_action_deadline(c) == 0.1
arrays, _, _ = prepare(config, {}, skills, groups)
for seed in range(10):
    py = SingleBattle(config, {}, skills, groups, seed=seed, record_timeline=False).run()
    compiled = battle(*arrays, np.array(random.Random(seed).getstate()[1], dtype=np.uint32))
    assert np.allclose(compiled[2], py["character_damage"]) and np.isclose(
        compiled[0], py["total_damage"]
    )
print(
    "PASS: first strike at 0.1s, normal first action, subsequent cooldowns and seeded compiled parity"
)
