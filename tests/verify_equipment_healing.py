import sys, random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from backend.equipment.validation import validate_equipment
from backend.skills.store import ATTRS

cfg = {
    "battle": {"duration": 10},
    "target": {"speed": 1000, "hitPoint": 100000000, "magicVulnerability": 1},
    "characters": [
        {
            "job": "法师",
            "enabled": True,
            "stats": {
                "constitution": 100,
                "magic": 100,
                "technique": 0,
                "strength": 1,
                "speed": 1000,
                "healingBonus": 20,
                "finalHealingBonus": 10,
            },
            "equipment": {"accessory1": "e"} if i == 0 else {},
            "skillGroup": "g",
        }
        for i in range(4)
    ],
}
cfg["characters"][0].update(contract="旧日支配者-魔", negativeEffect="群体献祭", skillMultiplier=1)
skills = {
    "s": {
        "name": "火球",
        "job": "法师",
        "damageType": "magic",
        "cooldown": 1,
        "hitRate": 100,
        "criticalRate": 0,
        "coefficients": {"magic": 1},
        "effect": None,
    }
}
groups = {
    "g": {
        "job": "法师",
        "entry": "n",
        "subgroups": [
            {"id": "sub", "nextGroup": "sub", "skills": [{"id": "n", "skillId": "s", "next": ""}]}
        ],
    }
}
item = {
    "schemaVersion": 1,
    "id": "e",
    "name": "装备回血",
    "category": "accessory",
    "weaponJob": "",
    "attackType": "magic",
    "effectName": "",
    "triggerEffectName": "圣灵加护",
    "triggerEnabled": True,
    "startingBuff": {
        "enabled": False,
        "recipient": "self",
        "target": "none",
        "coefficients": dict.fromkeys(["strength", "magic", "technique", "speed"], 0),
    },
    "triggerRate": 100,
    "effect": {
        "kind": "healing",
        "recipient": "allAllies",
        "coefficients": {**dict.fromkeys(ATTRS + ["weaponPower"], 0), "magic": 2},
    },
}
item = validate_equipment(item)
eq = {"e": item}
arrays, _, _ = prepare(cfg, eq, skills, groups)
for seed in range(10):
    py = SingleBattle(cfg, eq, skills, groups, seed=seed)
    ref = py.run()
    out = battle(*arrays, np.array(random.Random(seed).getstate()[1], dtype=np.uint32))
    assert np.allclose(out[5], [c.current_hp for c in py.state.characters])
    assert np.allclose(out[2], ref["character_damage"])
    events = [
        e for e in py.state.events if e["type"] == "healing" and e.get("skill_name") == "圣灵加护"
    ]
    assert events and all(abs(e["amount"] - 264) < 1e-8 for e in events)
print(
    "PASS: equipment group healing, healing bonuses, timeline amount and 10 seeded Python/Numba battles"
)
