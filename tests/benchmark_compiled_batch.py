"""Compare njit to the reference on read-only current libraries."""

from pathlib import Path
import sys, random, time, json
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.batch import simulate_batch
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle


def main():
    root = Path(__file__).resolve().parents[1]
    items = json.loads((root / "data/equipment.json").read_text(encoding="utf-8"))["equipment"]
    skills = json.loads((root / "data/skills.json").read_text(encoding="utf-8"))["skills"]
    groups = json.loads((root / "data/skill_groups.json").read_text(encoding="utf-8"))["groups"]
    eq = {e["id"]: e for e in items}
    sl = {s["id"]: s for s in skills}
    gl = {g["id"]: g for g in groups}
    config = {
        "seed": 345,
        "battle": {"duration": 200, "simulations": 200},
        "target": {
            "hitPoint": 175000000,
            "speed": 43750,
            "resistance": 0,
            "armor": 0,
            "magicVulnerability": 1.12,
            "physicalVulnerability": 1,
            "dotVulnerability": 1,
            "race": "灵体",
        },
        "characters": [],
    }
    for c, gindex in enumerate([2, 4, 0, 1]):
        stats = {
            "constitution": [3916, 3370, 3464, 2967][c],
            "magic": [13121, 12077, 12578, 11523][c],
            "technique": [6074, 6110, 6399, 6502][c],
            "strength": [236, 612, 197, 527][c],
            "speed": [1170, 1099, 1234, 1370][c],
            "weaponPower": [1906, 764, 1969, 798][c],
            "unload": [300, 2300, 300, 800][c],
            "hitRate": [54.5, 53.3, 52.5, 58.5][c],
            "magicDamage": [24.8, 24.8, 26, 24.8][c],
            "finalMagicDamage": [5, 5, 8, 8][c],
            "criticalMultiplier": [27, 17.4, 30, 59][c],
            "abnormalBonus": [70, 20, 0, 0][c],
            "healingBonus": 45,
            "finalHealingBonus": 15,
        }
        positions = [[2, 3, 1, 4, 12], [0, 6, 1, 4, 12], [5, 3, 7, 8, 12], [9, 6, 11, 10, 12]][c]
        config["characters"].append(
            {
                "enabled": True,
                "job": groups[gindex]["job"],
                "stats": stats,
                "equipment": {
                    slot: items[index]["id"]
                    for slot, index in zip(
                        ("weapon", "armor", "accessory1", "accessory2", "stone"), positions
                    )
                },
                "skillGroup": groups[gindex]["id"],
            }
        )
    config["characters"][2].update(
        contract="旧日支配者-魔", negativeEffect="群体献祭", skillMultiplier=5.6
    )
    reference = simulate_batch(config, eq, sl, gl, engine="python", parallel=False)
    compiled = simulate_batch(config, eq, sl, gl, engine="numba", workers=8)
    assert reference["passed_battles"] == compiled["passed_battles"]
    assert np.allclose(reference["sorted_damage"], compiled["sorted_damage"], rtol=1e-10)
    for a, b in zip(reference["characters"], compiled["characters"]):
        assert np.isclose(a["expected_damage"], b["expected_damage"], rtol=1e-10)
        assert a["effects"] == b["effects"]
    print(
        "200 real-library battles: Python",
        round(reference["elapsed_seconds"], 3),
        "njit",
        round(compiled["elapsed_seconds"], 3),
        "seconds, same results",
        flush=True,
    )
    for count in (10000, 100000):
        config["battle"]["simulations"] = count
        result = simulate_batch(config, eq, sl, gl, engine="numba", workers=8)
        print(
            count,
            "real-library battles:",
            round(result["elapsed_seconds"], 3),
            "seconds; pass",
            result["pass_rate"],
            flush=True,
        )


if __name__ == "__main__":
    main()
