from pathlib import Path
import sys, copy, random, tempfile
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api.bosses import BossStore, validate_item
from backend.skills.store import SkillError
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from engine.runtime.health import reduce_ally_recovery

keys = ["allyLifestealReduction", "allyHealingReduction", "allyRegenerationReduction"]
record = {
    "name": "ReductionBoss",
    "attributes": {"constitution": 100},
    "targetRules": dict(zip(keys, [20, 30, 40])),
}
with tempfile.TemporaryDirectory() as directory:
    store = BossStore(Path(directory) / "bosses.json")
    saved = store.save(record)["item"]
    assert store.read()["bosses"][0] == saved
    assert [saved["targetRules"][k] for k in keys] == [20, 30, 40]
assert all(validate_item({"name": "LegacyBoss"})["targetRules"][k] == 0 for k in keys)
for key in keys:
    try:
        validate_item({**record, "targetRules": {key: 101}})
    except SkillError:
        pass
    else:
        raise AssertionError("percentage >100 accepted")
config = {
    "battle": {"duration": 1.5},
    "target": {"hitPoint": 1e9, "speed": 100, **dict(zip(keys, [20, 30, 40]))},
    "characters": [
        {
            "enabled": i == 0,
            "job": "法师",
            "stats": {
                "magic": 1000,
                "strength": 1,
                "speed": 10000,
                "constitution": 100,
                "magicSingleLifesteal": 10,
            },
            "equipment": {},
            "skillGroup": "g",
        }
        for i in range(4)
    ],
}
group = {
    "job": "法师",
    "entry": "n",
    "subgroups": [{"id": "sub", "skills": [{"id": "n", "skillId": "s", "next": ""}]}],
}
for mode, expected in [("lifesteal", 280), ("healing", 270), ("equipment", 340)]:
    skill = {
        "job": "法师",
        "name": "测试技能",
        "damageType": "none" if mode == "healing" else "magic",
        "targeting": "single",
        "cooldown": 0,
        "hitRate": 100,
        "criticalRate": 0,
        "coefficients": {"magic": 0.1 if mode == "healing" else 1},
        "effect": None,
    }
    cfg = copy.deepcopy(config)
    equipment = {}
    if mode == "equipment":
        cfg["characters"][0]["stats"]["magicSingleLifesteal"] = 0
        cfg["characters"][0]["equipment"] = {"weapon": "gear"}
        equipment = {
            "gear": {
                "id": "gear",
                "name": "HealGear",
                "category": "weapon",
                "startingBuff": {"enabled": False},
                "triggerEnabled": True,
                "triggerEffects": [
                    {
                        "name": "回血",
                        "triggerType": "magic",
                        "probability": 100,
                        "effect": {
                            "kind": "healing",
                            "recipient": "self",
                            "coefficients": {"magic": 0.2},
                        },
                    }
                ],
            }
        }
    py = SingleBattle(cfg, equipment, {"s": skill}, {"g": group}, seed=3)
    assert reduce_ally_recovery(py.state, 100, kind="regeneration") == 60
    py.state.characters[0].current_hp = 200
    py.state.characters[0].stats["hitPoint"] = 200
    py.run()
    assert abs(py.state.characters[0].current_hp - expected) < 1e-8, (
        mode,
        py.state.characters[0].current_hp,
    )
    arrays, _, _ = prepare(cfg, equipment, {"s": skill}, {"g": group})
    arrays[2][0, 1] = 200
    arrays[0][0, 5] = 200
    out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
    assert np.isclose(out[5][0], expected), (mode, out[5])
print(
    "PASS: three percentages saved, old defaults, limits, separate lifesteal/healing/equipment reductions and Python/Numba parity; regeneration multiplier"
)
