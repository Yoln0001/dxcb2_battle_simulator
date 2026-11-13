"""Seeded Python/njit parity for every ring pair, restriction and gain; no data writes."""

from pathlib import Path
import sys, copy, random, time
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.rings.store import presets, RESTRICTIONS, GAINS
from engine.runtime.compiled.prepare import prepare, A
from engine.runtime.compiled.kernel import battle
from engine.runtime.simulation import SingleBattle
from engine.runtime.batch import simulate_batch
from verify_compiled_core import fixture


def check(config, equipment, skills, groups, seeds=(1, 17)):
    arrays, keys, _ = prepare(config, equipment, skills, groups)
    for seed in seeds:
        py = SingleBattle(config, equipment, skills, groups, seed=seed, record_timeline=False)
        ref = py.run()
        out = battle(*arrays, np.array(random.Random(seed).getstate()[1], dtype=np.uint32))
        assert np.allclose(out[2], ref["character_damage"], rtol=1e-10, atol=1e-6), (
            seed,
            out[2],
            ref["character_damage"],
        )
        assert out[1] == (py.state.target_current_hp <= 0)
        assert np.allclose(out[5], [c.current_hp for c in py.state.characters], rtol=1e-10)
        assert out[6].tolist() == [int(c.enabled and c.alive) for c in py.state.characters]
        for c, character in enumerate(py.state.characters):
            for key in (
                "strength",
                "magic",
                "technique",
                "speed",
                "constitution",
                "physicalDamage",
                "magicDamage",
                "dotDamage",
                "hitRate",
                "abnormalBonus",
                "healingBonus",
                "dodgeRate",
                "physicalBlock",
                "magicBlock",
                "physicalTakenMultiplier",
                "magicTakenMultiplier",
                "ringRecoveryMultiplier",
            ):
                assert np.isclose(out[4][c, A[key]], character.stats.get(key, 0), rtol=1e-10), (
                    seed,
                    c,
                    key,
                    out[4][c, A[key]],
                    character.stats.get(key, 0),
                )
        for c in range(4):
            expected = sum(e["count"] for e in ref["effect_counts"][c])
            assert sum(out[3][p] for p, key in enumerate(keys) if key[0] == c) == expected
    return arrays


def main():
    config, equipment, skills, groups = fixture()
    config["battle"]["duration"] = 32
    config["target"]["hitPoint"] = 1e12
    # All 12 base pairs, every legal restriction/gain, both enemy/party count branches.
    cases = 0
    started = time.perf_counter()
    for preset in presets():
        for restriction in RESTRICTIONS[preset["kind"]]:
            for gain in GAINS[preset["kind"]]:
                for party, enemies in ((4, 1), (2, 2)):
                    cfg = copy.deepcopy(config)
                    cfg["target"]["enemyCount"] = enemies
                    ring = {
                        **preset,
                        "restriction": restriction,
                        "gain": gain,
                        "gainValue": 12.3,
                        "mainValue": 100,
                        "secondaryValue": 50,
                    }
                    for i, c in enumerate(cfg["characters"]):
                        c["enabled"] = i < party
                        c["selectedRing"] = ring if i < party else None
                    check(cfg, equipment, skills, groups)
                    cases += 1
    print(
        "PASS:",
        cases * 2,
        "seeded battles across all ring pairs/restrictions/gains; damage, stats, HP, deaths and proc counts",
        flush=True,
    )
    # Unequal deaths change missing-party stacks; full-health gain toggles around healing.
    cfg = copy.deepcopy(config)
    cfg["battle"]["duration"] = 35
    ring_by_kind = {r["kind"]: r for r in presets()}
    cfg["characters"][0]["selectedRing"] = {
        **ring_by_kind["fire"],
        "restriction": "sacrifice",
        "gainValue": 10,
    }
    cfg["characters"][1]["selectedRing"] = {
        **ring_by_kind["sky"],
        "restriction": "missingParty",
        "gainValue": 10,
    }
    cfg["characters"][2]["selectedRing"] = {
        **ring_by_kind["earth"],
        "restriction": "fullHealth",
        "gain": "doubleBlock",
        "gainValue": 125,
    }
    cfg["characters"][3]["selectedRing"] = {
        **ring_by_kind["water"],
        "restriction": "missingParty",
        "gain": "healingBonus",
        "gainValue": 10,
    }
    weak = copy.deepcopy(skills)
    weak["heal"]["coefficients"] = {"magic": 0.001}
    check(cfg, equipment, weak, groups, seeds=range(12))
    # Pollution combines with target recovery reduction, skill lifesteal and regeneration.
    cfg = copy.deepcopy(config)
    cfg["target"].update(
        allyHealingReduction=20, allyLifestealReduction=15, allyRegenerationReduction=25
    )
    for c in cfg["characters"]:
        c["selectedRing"] = {**ring_by_kind["fire"], "restriction": "polluted", "gainValue": 10}
    healing = copy.deepcopy(skills)
    healing["fire"]["lifesteal"] = 15
    healing["heal"]["effect"] = {
        "kind": "buff",
        "type": "regeneration",
        "recipient": "healingTargets",
        "baseValue": 10,
        "duration": 3,
        "triggerRate": 100,
        "coefficients": {"magic": 0.01},
    }
    healing["heal"]["healingRecipient"] = "allAllies"
    check(cfg, equipment, healing, groups, seeds=range(12))
    cfg["battle"]["simulations"] = 50
    python = simulate_batch(cfg, equipment, healing, groups, parallel=False, engine="python")
    compiled = simulate_batch(
        cfg, equipment, healing, groups, parallel=True, workers=2, engine="numba"
    )
    assert compiled["engine"] == "numba_njit"
    assert python["passed_battles"] == compiled["passed_battles"]
    assert np.allclose(python["sorted_damage"], compiled["sorted_damage"], rtol=1e-10)
    assert python["warnings"] == compiled["warnings"]
    # Target kill / scheduled wipe preserve DOT-before-sacrifice priority.
    for hp, wipe in ((200000, None), (1e12, 8)):
        cfg = copy.deepcopy(config)
        cfg["target"]["hitPoint"] = hp
        if wipe is not None:
            cfg["target"]["partyWipe"] = {"enabled": True, "time": wipe}
        for c in cfg["characters"]:
            c["selectedRing"] = {
                **ring_by_kind["fire"],
                "restriction": "sacrifice",
                "gainValue": 10,
            }
        check(cfg, equipment, skills, groups, seeds=range(6))
    equipment = {
        "ring_test": {
            "id": "ring_test",
            "name": "域之环叠加测试",
            "category": "accessory",
            "effectName": "开战回春",
            "startingBuff": {
                "enabled": True,
                "kind": "regeneration",
                "recipient": "self",
                "target": "none",
                "coefficients": dict.fromkeys(("strength", "magic", "technique", "speed"), 0),
                "regeneration": {"baseValue": 300, "coefficients": {}},
            },
            "triggerEnabled": True,
            "triggerEffects": [
                {
                    "name": "属性转换",
                    "triggerType": "magic",
                    "probability": 65,
                    "effect": {
                        "kind": "amplify",
                        "duration": 3,
                        "conversions": [
                            {
                                "target": "magic",
                                "enabled": True,
                                "coefficients": {"magic": 0.2, "armor": 0.1},
                            }
                        ],
                    },
                }
            ],
        }
    }
    cfg = copy.deepcopy(config)
    for c in cfg["characters"]:
        c["equipment"]["accessory1"] = "ring_test"
    for c, r in zip(
        cfg["characters"],
        (
            {**ring_by_kind["fire"], "restriction": "sacrifice", "gainValue": 12},
            {**ring_by_kind["fire"], "restriction": "polluted", "gainValue": 15},
            {
                **ring_by_kind["earth"],
                "restriction": "fullHealth",
                "gain": "doubleBlock",
                "gainValue": 100,
            },
            {
                **ring_by_kind["water"],
                "restriction": "missingParty",
                "gain": "healingBonus",
                "gainValue": 10,
            },
        ),
    ):
        c["selectedRing"] = r
    check(cfg, equipment, skills, groups, seeds=range(20))
    print(
        "PASS: dynamic deaths/full health, pollution with healing/lifesteal/regeneration, compiled batch parity and termination",
        flush=True,
    )
    # Report warm timings separately from first compilation.
    cfg["battle"]["simulations"] = 1000
    cfg["battle"]["duration"] = 200
    cfg["target"].pop("partyWipe", None)
    fast = simulate_batch(cfg, equipment, skills, groups, workers=2, engine="numba")
    print(
        "Warm 1000 ring battles:",
        round(fast["elapsed_seconds"], 3),
        "s; engine:",
        fast["engine"],
        flush=True,
    )
    print("Suite elapsed:", round(time.perf_counter() - started, 3), "s", flush=True)


if __name__ == "__main__":
    main()
