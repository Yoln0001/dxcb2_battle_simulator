from pathlib import Path
import sys, random, copy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle


def main():
    config = {
        "battle": {"duration": 1.5},
        "target": {
            "hitPoint": 1e9,
            "speed": 100,
            "physicalVulnerability": 1,
            "magicVulnerability": 1,
        },
        "characters": [
            {
                "enabled": i == 0,
                "job": "寒霜法师",
                "stats": {"magic": 1000, "strength": 1000, "speed": 10000, "constitution": 100},
                "equipment": {"weapon": "gear"},
                "skillGroup": "g",
            }
            for i in range(4)
        ],
    }
    group = {
        "job": "寒霜法师",
        "entry": "n",
        "subgroups": [{"id": "sub", "skills": [{"id": "n", "skillId": "s", "next": ""}]}],
    }
    for dtype in ("magic", "physical"):
        for scope in ("single", "all"):
            key = dtype + ("Area" if scope == "all" else "Single") + "Lifesteal"
            for mode in (
                "matching",
                "wrong-type",
                "wrong-scope",
                "miss",
                "cap",
                "skill-only",
                "skill-plus-panel",
                "skill-miss",
                "skill-reduced",
            ):
                cfg = copy.deepcopy(config)
                chosen = (
                    key
                    if mode not in ("wrong-type", "wrong-scope")
                    else (
                        ("physical" if dtype == "magic" else "magic")
                        + ("Area" if scope == "all" else "Single")
                        + "Lifesteal"
                        if mode == "wrong-type"
                        else dtype + ("Single" if scope == "all" else "Area") + "Lifesteal"
                    )
                )
                cfg["characters"][0]["stats"][chosen] = 10
                if mode in ("miss", "skill-miss"):
                    cfg["target"]["dodgeRate"] = 100
                if mode in ("skill-only", "skill-miss", "skill-reduced"):
                    cfg["characters"][0]["stats"][key] = 0
                if mode == "skill-reduced":
                    cfg["target"]["allyLifestealReduction"] = 50
                skill = {
                    "job": "寒霜法师",
                    "name": "测试技能",
                    "damageType": dtype,
                    "targeting": scope,
                    "cooldown": 0,
                    "hitRate": 100,
                    "criticalRate": 0,
                    "coefficients": {"magic" if dtype == "magic" else "strength": 1},
                    "effect": None,
                }
                if mode.startswith("skill-"):
                    skill["lifesteal"] = 15
                gear = {
                    "id": "gear",
                    "name": "真伤装备",
                    "category": "weapon",
                    "startingBuff": {"enabled": False},
                    "triggerEnabled": True,
                    "triggerEffects": [
                        {
                            "name": "装备真伤",
                            "triggerType": dtype,
                            "probability": 100,
                            "effect": {"kind": dtype + "TrueDamage", "coefficients": {"magic": 5}},
                        }
                    ],
                }
                initial_hp = 990 if mode == "cap" else 200
                py = SingleBattle(cfg, {"gear": gear}, {"s": skill}, {"g": group}, seed=3)
                py.state.characters[0].current_hp = initial_hp
                py.state.characters[0].stats["hitPoint"] = initial_hp
                result = py.run()
                events = [e for f in result["timeline"] for e in f["events"]]
                steals = [e for e in events if e["type"] == "lifesteal"]
                expected = (
                    1000
                    if mode == "cap"
                    else 300
                    if mode == "matching"
                    else {
                        "skill-only": 350,
                        "skill-plus-panel": 450,
                        "skill-miss": 200,
                        "skill-reduced": 275,
                    }.get(mode, 200)
                )
                assert py.state.characters[0].current_hp == expected, (dtype, scope, mode, events)
                if steals:
                    assert (
                        steals[0]["amount"]
                        == (
                            {"skill-only": 150, "skill-plus-panel": 250, "skill-reduced": 75}.get(
                                mode, 100
                            )
                        )
                        and steals[0]["effective_amount"] == expected - initial_hp
                    )
                assert any(e["type"] == "equipment_damage" and e["damage"] == 5000 for e in events)
                assert bool(steals) == (
                    mode in ("matching", "cap", "skill-only", "skill-plus-panel", "skill-reduced")
                )
                arrays, _, _ = prepare(cfg, {"gear": gear}, {"s": skill}, {"g": group})
                arrays[2][0, 1] = initial_hp
                arrays[0][0, 5] = initial_hp
                out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
                assert np.isclose(out[5][0], expected), (dtype, scope, mode, out[5])
                assert np.allclose(out[2], result["character_damage"])
    print(
        "PASS: four lifesteal types, scope/type filtering, miss rejection, equipment exclusion, health cap and njit parity"
    )


if __name__ == "__main__":
    main()
