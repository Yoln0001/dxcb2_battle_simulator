from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.batch import simulate_batch


def main():
    config = {
        "seed": 42,
        "battle": {"duration": 10, "simulations": 160},
        "target": {"speed": 10000, "hitPoint": 18000, "magicVulnerability": 1.12},
        "characters": [
            {
                "job": "法师",
                "enabled": True,
                "stats": {
                    "constitution": 100,
                    "magic": 1000,
                    "technique": 200,
                    "strength": 100,
                    "speed": 500,
                    "hitRate": 55,
                },
                "equipment": {},
                "skillGroup": "g",
            }
            for _ in range(4)
        ],
    }
    config["characters"][0].update(
        contract="旧日支配者-魔", negativeEffect="群体献祭", skillMultiplier=2
    )
    skill = {
        "name": "火球",
        "job": "法师",
        "damageType": "magic",
        "cooldown": 1.8,
        "hitRate": 30,
        "criticalRate": 20,
        "coefficients": {"magic": 2},
        "effect": {
            "kind": "debuff",
            "type": "burn",
            "duration": 6,
            "applicationRate": 80,
            "baseValue": 1,
            "coefficients": {"technique": 0.25},
        },
    }
    group = {
        "job": "法师",
        "entry": "n",
        "subgroups": [
            {"id": "sub", "nextGroup": "sub", "skills": [{"id": "n", "skillId": "s", "next": ""}]}
        ],
    }
    serial = simulate_batch(config, {}, {"s": skill}, {"g": group}, parallel=False, engine="python")
    progress = []
    parallel = simulate_batch(
        config,
        {},
        {"s": skill},
        {"g": group},
        parallel=True,
        workers=2,
        engine="python",
        progress=lambda n, total: progress.append(n),
    )
    for result in (serial, parallel):
        result.pop("elapsed_seconds")
        result.pop("worker_count")
    assert serial == parallel
    assert progress == list(range(1, 161))
    assert 0 < serial["passed_battles"] < 160
    print(
        "PASS: Windows spawn processes and serial results exactly identical, including mixed passes, quantiles, role/effect means and progress"
    )


if __name__ == "__main__":
    main()
