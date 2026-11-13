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

base = {
    "schemaVersion": 1,
    "id": "e",
    "name": "回春装备",
    "category": "accessory",
    "weaponJob": "",
    "attackType": "magic",
    "effectName": "回春",
    "triggerEffectName": "",
    "triggerEnabled": False,
    "startingBuff": {
        "enabled": True,
        "kind": "regeneration",
        "recipient": "self",
        "target": "none",
        "coefficients": dict.fromkeys(["strength", "magic", "technique", "speed"], 0),
        "regeneration": {
            "baseValue": 5,
            "coefficients": dict.fromkeys(
                ["strength", "magic", "technique", "speed", "constitution"], 1
            ),
        },
    },
    "triggerRate": 0,
    "effect": None,
}
item = validate_equipment(base)
with tempfile.TemporaryDirectory() as directory:
    store = EquipmentStore(Path(directory) / "equipment.json")
    saved = store.save(item)["item"]
    assert store.read()["equipment"][0] == saved
for change in ({"baseValue": -1}, {"coefficients": {"constitution": -1}}):
    bad = copy.deepcopy(base)
    bad["startingBuff"]["regeneration"].update(change)
    try:
        validate_equipment(bad)
    except SkillError:
        pass
    else:
        raise AssertionError("invalid regeneration accepted")
config = {
    "battle": {"duration": 2},
    "target": {"hitPoint": 1e9, "speed": 100},
    "characters": [
        {
            "enabled": i == 0,
            "job": "法师",
            "stats": {
                "magic": 10,
                "strength": 20,
                "technique": 30,
                "speed": 40,
                "constitution": 100,
                "healingBonus": 20,
                "finalHealingBonus": 10,
            },
            "equipment": {"accessory1": "e"},
            "skillGroup": "g",
        }
        for i in range(4)
    ],
}
group = {
    "job": "法师",
    "entry": "n",
    "subgroups": [
        {
            "id": "sub",
            "skills": [{"id": "n", "skillId": "__wait__", "waitDuration": 100, "next": ""}],
        }
    ],
}
for reduction, immune, expected in [
    (0, False, 741.2),
    (50, False, 470.6),
    (100, False, 200),
    (50, True, 470.6),
]:
    cfg = copy.deepcopy(config)
    cfg["target"]["allyRegenerationReduction"] = reduction
    gear = copy.deepcopy(item)
    gear["negativeImmunities"]["immuneRegenerationReduction"] = immune
    py = SingleBattle(cfg, {"e": gear}, {}, {"g": group}, seed=3)
    owner = py.state.characters[0]
    assert (
        np.isclose(owner.regeneration_buffs[0]["amount"], 270.6)
        and not py.state.characters[1].regeneration_buffs
    )
    owner.current_hp = 200
    owner.stats["hitPoint"] = 200
    result = py.run()
    assert np.isclose(owner.current_hp, expected)
    ticks = [e for e in py.state.events if e["type"] == "regeneration"]
    assert [e["time"] for e in ticks] == [1.0, 2.0]
    arrays, _, _ = prepare(cfg, {"e": gear}, {}, {"g": group})
    arrays[2][0, 1] = 200
    arrays[0][0, 5] = 200
    out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
    assert np.isclose(out[5][0], expected)
# Same-name opening regeneration replaces instead of stacking.
cfg = copy.deepcopy(config)
cfg["characters"][0]["equipment"]["accessory2"] = "e2"
second = copy.deepcopy(item)
second.update(id="e2")
second["startingBuff"]["regeneration"]["baseValue"] = 15
second["battleStartEffects"]["entries"][0]["buff"]["regeneration"]["baseValue"] = 15
py = SingleBattle(cfg, {"e": item, "e2": second}, {}, {"g": group}, seed=3)
assert len(py.state.characters[0].regeneration_buffs) == 1 and np.isclose(
    py.state.characters[0].regeneration_buffs[0]["amount"], 283.8
)
# Sacrifice death at the tick must never be healed back to life.
cfg = copy.deepcopy(config)
cfg["characters"][0].update(contract="旧日支配者-魔", negativeEffect="群体献祭", skillMultiplier=1)
py = SingleBattle(cfg, {"e": item}, {}, {"g": group}, seed=3)
py.state.characters[0].current_hp = 10
py.state.characters[0].stats["hitPoint"] = 10
py.run()
assert (
    not py.state.characters[0].alive
    and py.state.characters[0].current_hp == 0
    and not py.state.characters[0].regeneration_buffs
)
arrays, _, _ = prepare(cfg, {"e": item}, {}, {"g": group})
arrays[2][0, 1] = 10
arrays[0][0, 5] = 10
out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
assert out[5][0] == 0
print(
    "PASS: regeneration five coefficients/base, persistence/limits, 1-second ticks, reduction/obsolete-immunity migration, multiplicative healing bonuses, same-name replacement, death and Python/Numba parity"
)

for healing, imprint, factor in [(0, 0, 1), (20, 0, 1.2), (0, 10, 1.1), (20, 10, 1.32)]:
    cfg = copy.deepcopy(config)
    cfg["characters"][0]["stats"].update(healingBonus=healing, finalHealingBonus=imprint)
    py = SingleBattle(cfg, {"e": item}, {}, {"g": group}, seed=3)
    assert np.isclose(py.state.characters[0].regeneration_buffs[0]["amount"], 205 * factor)
print("PASS: healing and imprint bonuses independently apply and multiply together")

# The starred heart alone ignores outgoing healing bonuses, in both opening formats.
for name in ("肇始之心★", "肇始之心", "其他回春装备"):
    for legacy in (False, True):
        for healing, imprint in ((0, 0), (20, 0), (0, 10), (20, 10)):
            for reduction in (0, 50, 100):
                cfg = copy.deepcopy(config)
                cfg["characters"][0]["stats"].update(
                    healingBonus=healing, finalHealingBonus=imprint
                )
                cfg["target"]["allyRegenerationReduction"] = reduction
                gear = validate_equipment({**copy.deepcopy(base), "name": name})
                if legacy:
                    gear.pop("battleStartEffects", None)
                raw = (
                    205 if name == "肇始之心★" else 205 * (1 + healing / 100) * (1 + imprint / 100)
                )
                expected = 200 + 2 * raw * (1 - reduction / 100)
                py = SingleBattle(cfg, {"e": gear}, {}, {"g": group}, seed=3)
                owner = py.state.characters[0]
                assert np.isclose(owner.regeneration_buffs[0]["amount"], raw), (
                    name,
                    legacy,
                    healing,
                    imprint,
                )
                owner.current_hp = 200
                owner.stats["hitPoint"] = 200
                py.run()
                assert np.isclose(owner.current_hp, expected), (
                    name,
                    reduction,
                    owner.current_hp,
                    expected,
                )
                arrays, _, _ = prepare(cfg, {"e": gear}, {}, {"g": group})
                arrays[2][0, 1] = 200
                arrays[0][0, 5] = 200
                out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
                assert np.isclose(out[5][0], expected), (
                    name,
                    legacy,
                    reduction,
                    out[5][0],
                    expected,
                )
print(
    "PASS: starred heart ignores healing/imprint bonuses; other equipment retains both; all obey Boss regeneration reduction, legacy/bundled formats and Python/njit parity"
)

# Prefixes and effect identity migrate old records to an explicit persistent rule.
for equipment_name, effect_name in [
    ("体体魔魔速技肇始之心★", "肇始之源"),
    ("重命名饰品", "肇始之源"),
]:
    gear = validate_equipment(
        {**copy.deepcopy(base), "name": equipment_name, "effectName": effect_name}
    )
    assert gear["startingBuff"]["regeneration"]["receivesHealingBonuses"] is False
    gear["name"] = "再次随意改名"
    gear["effectName"] = "改名后的回春"
    gear["battleStartEffects"]["entries"][0]["name"] = "改名后的回春"
    gear = validate_equipment(gear)
    assert gear["startingBuff"]["regeneration"]["receivesHealingBonuses"] is False
    with tempfile.TemporaryDirectory() as directory:
        store = EquipmentStore(Path(directory) / "equipment.json")
        store.save(gear)
        gear = store.read()["equipment"][0]
    for reduction in (0, 50, 100):
        cfg = copy.deepcopy(config)
        cfg["target"]["allyRegenerationReduction"] = reduction
        py = SingleBattle(cfg, {"e": gear}, {}, {"g": group}, seed=3)
        owner = py.state.characters[0]
        assert np.isclose(owner.regeneration_buffs[0]["amount"], 205)
        owner.current_hp = 200
        owner.stats["hitPoint"] = 200
        py.run()
        expected = 200 + 410 * (1 - reduction / 100)
        assert np.isclose(owner.current_hp, expected)
        arrays, _, _ = prepare(cfg, {"e": gear}, {}, {"g": group})
        arrays[2][0, 1] = 200
        arrays[0][0, 5] = 200
        out = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
        assert np.isclose(out[5][0], expected)
bad = copy.deepcopy(base)
bad["startingBuff"]["regeneration"]["receivesHealingBonuses"] = "false"
try:
    validate_equipment(bad)
except SkillError:
    pass
else:
    raise AssertionError("nonboolean regeneration setting accepted")
print(
    "PASS: renamed heart and source migrate automatically; explicit rule survives equipment/effect rename, save/reload, Boss reductions and Python/njit simulation"
)
