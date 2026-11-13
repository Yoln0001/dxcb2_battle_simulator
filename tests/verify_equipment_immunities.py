from pathlib import Path
import sys, copy, random, tempfile
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.equipment.validation import validate_equipment
from backend.equipment.store import EquipmentStore
from backend.skills.store import SkillError
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from engine.runtime.health import is_negative_immune, reduce_ally_recovery

base = {
    "schemaVersion": 1,
    "id": "e",
    "name": "免疫装备",
    "category": "accessory",
    "weaponJob": "",
    "attackType": "magic",
    "effectName": "",
    "triggerEffectName": "",
    "triggerEnabled": False,
    "startingBuff": {
        "enabled": False,
        "recipient": "self",
        "target": "none",
        "coefficients": dict.fromkeys(["strength", "magic", "technique", "speed"], 0),
    },
    "triggerRate": 0,
    "effect": None,
}
item = validate_equipment(
    {
        **base,
        "negativeImmunities": {
            "immuneBurn": True,
            "immuneStrengthDecay": True,
            "immunePhysicalVulnerability": True,
            "immuneMagicVulnerability": True,
        },
    }
)
second = validate_equipment(
    {
        **base,
        "id": "e2",
        "name": "免疫装备2",
        "negativeImmunities": {
            "immuneTechniqueDecay": True,
            "immuneMagicDecay": True,
            "immuneSpeedDecay": True,
        },
    }
)
with tempfile.TemporaryDirectory() as directory:
    store = EquipmentStore(Path(directory) / "equipment.json")
    saved = store.save(item)["item"]
    assert store.read()["equipment"][0] == saved
    assert store.import_library({"schemaVersion": 1, "equipment": [saved]})["equipment"][0][
        "negativeImmunities"
    ]["immuneBurn"]
for flags in ({"immuneBurn": 1}, {"unknown": True}, []):
    try:
        validate_equipment({**base, "negativeImmunities": flags})
    except SkillError:
        pass
    else:
        raise AssertionError("invalid immunity accepted")
assert not any(validate_equipment(base)["negativeImmunities"].values())
config = {
    "battle": {"duration": 1.5},
    "target": {
        "hitPoint": 1e9,
        "speed": 100,
        "allyHealingReduction": 50,
        "allyLifestealReduction": 50,
        "allyRegenerationReduction": 50,
    },
    "characters": [
        {
            "enabled": i < 2,
            "job": "法师",
            "stats": {
                "magic": 1000,
                "strength": 1,
                "speed": 10000,
                "constitution": 100,
                "magicSingleLifesteal": 10,
            },
            "equipment": {"accessory1": "e", "accessory2": "e2"} if i in (0, 2) else {},
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
for mode in ("healing", "lifesteal"):
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
    py = SingleBattle(config, {"e": item, "e2": second}, {"s": skill}, {"g": group}, seed=3)
    owner, other, disabled = py.state.characters[:3]
    assert (
        is_negative_immune(owner, "burn")
        and is_negative_immune(owner, "techniqueDecay")
        and not is_negative_immune(owner, "stun")
    )
    assert is_negative_immune(owner, "physicalVulnerability") and is_negative_immune(
        owner, "magicVulnerability"
    )
    assert not other.negative_immunities and not disabled.negative_immunities
    assert reduce_ally_recovery(py.state, 100, kind="regeneration", recipient=owner) == 50
    for c in py.state.characters[:2]:
        c.current_hp = 200
        c.stats["hitPoint"] = 200
    py.run()
    assert [c.current_hp for c in py.state.characters[:2]] == [250, 250]
    arrays, _, _ = prepare(config, {"e": item, "e2": second}, {"s": skill}, {"g": group})
    arrays[2][:2, 1] = 200
    arrays[0][:2, 5] = 200
    out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
    assert np.allclose(out[5][:2], [250, 250])
    cfg = copy.deepcopy(config)
    cfg["characters"][0]["equipment"] = {}
    removed = SingleBattle(cfg, {}, {"s": skill}, {"g": group}, seed=3)
    assert not removed.state.characters[0].negative_immunities
    for kind in ("strengthDecay", "magicDecay", "techniqueDecay", "speedDecay"):
        assert is_negative_immune(owner, kind)
    for kind in (
        "weakness",
        "fear",
        "lifeLoss",
        "lifestealReduction",
        "healingReduction",
        "regenerationReduction",
    ):
        assert not is_negative_immune(owner, kind)
    obsolete = validate_equipment(
        {
            **base,
            "negativeImmunities": {
                "immuneSpeedReduction": True,
                "immuneWeakness": True,
                "immuneFear": True,
                "immuneLifeLoss": True,
                "immuneLifestealReduction": True,
                "immuneHealingReduction": True,
                "immuneRegenerationReduction": True,
                "immuneNegativeEffects": True,
            },
        }
    )
    assert not any(obsolete["negativeImmunities"].values())
    assert len(obsolete["negativeImmunities"]) == 12
print(
    "PASS: equipment immunity persistence/import, validation, union, owner-only inheritance, disabled/exchanged gear, distinct stat-decay immunity, obsolete flag migration and recovery Python/Numba parity"
)

from backend.api.bosses import validate_boss_group

for kind in ("strengthDecay", "magicDecay", "techniqueDecay", "speedDecay", "weakness", "fear"):
    group_data = validate_boss_group(
        {
            "skills": [
                {
                    "id": "boss-test",
                    "name": "测试衰减",
                    "effect": {
                        "kind": "debuff",
                        "type": kind,
                        "baseValue": 10,
                        "duration": 5,
                        "applicationRate": 100,
                        "coefficients": dict.fromkeys(
                            ["strength", "magic", "technique", "speed"], 0
                        ),
                    },
                }
            ]
        }
    )
    assert group_data["skills"][0]["effect"]["type"] == kind
print("PASS: Boss stat-decay types remain distinct from weakness and fear after validation")

for trigger in ("receivedPhysical", "receivedMagic"):
    defensive = validate_equipment(
        {
            **base,
            "triggerEnabled": True,
            "triggerEffects": [
                {
                    "name": "受击触发",
                    "triggerType": trigger,
                    "probability": 100,
                    "effect": {"kind": "immediateAction"},
                }
            ],
        }
    )
    assert validate_equipment(defensive) == defensive
    with tempfile.TemporaryDirectory() as directory:
        store = EquipmentStore(Path(directory) / "equipment.json")
        store.save(defensive)
        assert store.read()["equipment"][0]["triggerEffects"][0]["triggerType"] == trigger
    py = SingleBattle(config, {"e": defensive, "e2": second}, {"s": skill}, {"g": group}, seed=3)
    assert not py.procs(py.state.characters[0], skill)
    arrays, _, _ = prepare(config, {"e": defensive, "e2": second}, {"s": skill}, {"g": group})
    out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
    assert not any(out[3])
print(
    "PASS: received physical/magic trigger persistence and isolation from outgoing attacks in Python/Numba"
)

from engine.runtime.amplification import attack_snapshot
from backend.equipment.validation import AMPLIFICATION_ATTRS, AMPLIFICATION_TARGETS

rows = [
    {
        "target": target,
        "enabled": target in ("magic", "armor", "resistance"),
        "coefficients": dict.fromkeys(AMPLIFICATION_ATTRS, 0),
    }
    for target in AMPLIFICATION_TARGETS
]
for row in rows:
    if row["target"] == "magic":
        row["coefficients"].update(armor=2, resistance=3)
    elif row["target"] == "armor":
        row["coefficients"]["magic"] = 0.5
    elif row["target"] == "resistance":
        row["coefficients"]["strength"] = 0.4
amplifier = validate_equipment(
    {
        **base,
        "triggerEnabled": True,
        "triggerEffects": [
            {
                "name": "护甲抗性增幅",
                "triggerType": "magic",
                "probability": 100,
                "effect": {"kind": "amplify", "conversions": rows},
            }
        ],
    }
)
assert validate_equipment(amplifier) == amplifier
cfg = copy.deepcopy(config)
for i, c in enumerate(cfg["characters"]):
    c["enabled"] = i == 0
    c["stats"].update(armor=100, resistance=200)
    c["equipment"] = {"accessory1": "e"} if i == 0 else {}
attack = {
    "job": "法师",
    "name": "测试攻击",
    "damageType": "magic",
    "targeting": "single",
    "cooldown": 0,
    "hitRate": 100,
    "criticalRate": 0,
    "coefficients": {"magic": 1},
    "effect": None,
}
py = SingleBattle(cfg, {"e": amplifier}, {"s": attack}, {"g": group}, seed=3)
snap = attack_snapshot(py.state.characters[0], [amplifier["effect"]])
assert snap["magic"] == 1800 and snap["armor"] == 600 and np.isclose(snap["resistance"], 200.4)
result = py.run()
assert result["total_damage"] == 1800
assert (
    py.state.characters[0].stats["armor"] == 100 and py.state.characters[0].stats["magic"] == 1000
)
arrays, _, _ = prepare(cfg, {"e": amplifier}, {"s": attack}, {"g": group})
out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
assert out[0] == 1800
with tempfile.TemporaryDirectory() as directory:
    store = EquipmentStore(Path(directory) / "equipment.json")
    store.save(amplifier)
    assert (
        store.read()["equipment"][0]["effect"]["conversions"] == amplifier["effect"]["conversions"]
    )
print(
    "PASS: armor/resistance source and destination amplification, simultaneous snapshot, persistence and Python/Numba damage parity"
)
