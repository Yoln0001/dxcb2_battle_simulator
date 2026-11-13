import sys, json, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.configurations.special import calculate, prepare_configuration
from backend.configurations.store import ConfigurationStore

sources = {
    "day10": {"magic": 1000, "strength": 200},
    "contract": {"magic": 10},
    "stone": {"magic": 20},
    "holy": {"magic": 100},
    "ring": {"magic": 50, "magicDamage": 8},
    "trophies": {"magic": 30, "magicDamage": 7, "hitRate": 5},
    "saturation": {"weapon": {"magic": 25, "weaponPower": 60}},
}
gear = [
    {
        "id": "e",
        "name": "杖",
        "baseAttributes": {
            "magic": {"min": 100, "max": 300},
            "weaponPower": {"min": 10, "max": 20},
            "magicDamage": {"value": 12},
            "hitRate": {"value": -4},
        },
        "crystal": {"enabled": True, "attributes": {"magic": 5}},
    }
]
stats, normalized = calculate(sources, {"weapon": "e"}, gear)
assert (
    stats["magic"] == 3087.5
    and stats["weaponPower"] == 16
    and stats["hitRate"] == 1
    and stats["magicDamage"] == 19
    and stats["strength"] == 340
)
c = {
    "name": "角色",
    "enabled": True,
    "firstStrike": False,
    "job": "寒霜法师",
    "skillGroup": "",
    "contract": "不激活",
    "negativeEffect": "无",
    "skillMultiplier": 1,
    "equipment": {"weapon": "e"},
    "stats": {"magic": 1},
    "specialSources": sources,
}
config = {
    "schemaVersion": 1,
    "configurationType": "special",
    "battle": {"duration": 200, "simulations": 100},
    "target": {},
    "characters": [c] * 4,
}
result = prepare_configuration(config, gear)
assert (
    result["characters"][0]["stats"]["magic"] == 3087.5
    and config["characters"][0]["stats"]["magic"] == 1
)
with tempfile.TemporaryDirectory() as temp:
    store = ConfigurationStore(Path(temp) / "config.json")
    saved = store.save({"name": "特殊配置", "configuration": result})["item"]
    restored = store.read()["configurations"][0]
    assert (
        restored == saved
        and restored["configuration"]["characters"][0]["specialSources"]["day10"]
        == normalized["day10"]
        and restored["configuration"]["characters"][0]["stats"]["finalMagicDamage"] == 8
    )
    copy = store.save({"name": "特殊副本", "configuration": result})["item"]
    copy["configuration"]["characters"][0]["specialSources"]["day10"]["magic"] = 1
    assert store.read()["configurations"][0] == saved
print("PASS: special panel formula, source persistence, independent copy and input preservation")

for job, expected in [
    ("寒霜法师", {"magic": 1560, "technique": 1560, "constitution": 680}),
    ("圣龙将军", {"strength": 880, "technique": 880, "speed": 680, "constitution": 1360}),
]:
    values, src = calculate({}, {}, [], job)
    assert all(values[k] == v for k, v in expected.items())
values, src = calculate({"holy": {"magic": 123}, "holyCustom": True}, {}, [], "寒霜法师")
assert values["magic"] == 123
print("PASS: profession holy defaults and explicit manual override")

values, _ = calculate({"stone": {"hitRate": 12.5}, "trophies": {"hitRate": 8}}, {}, [])
assert values["hitRate"] == 20.5

values, src = calculate({}, {}, [], "寒霜法师")
assert (
    values["finalMagicDamage"] == 8
    and values["finalDotDamage"] == 2
    and values["finalHealingBonus"] == 15
    and values["hitRate"] == 5
    and values["criticalRate"] == 5
    and values["abnormalBonus"] == 20
)
values, _ = calculate({"imprintCustom": True, "imprint": {"hitRate": 12}}, {}, [], "寒霜法师")
assert values["hitRate"] == 12
print("PASS: class and subclass imprints, additive panel stats and manual overrides")

values, _ = calculate(
    {}, {"weapon": "v"}, [{"id": "v", "baseAttributes": {"lifesteal": {"value": 5}}}]
)
assert all(
    values[k] == 5
    for k in (
        "physicalSingleLifesteal",
        "physicalAreaLifesteal",
        "magicSingleLifesteal",
        "magicAreaLifesteal",
    )
)

from copy import deepcopy

exact = deepcopy(sources)
exact["saturation"]["weapon"]["magic"] = {"mode": "value", "value": 200}
values, restored = calculate(exact, {"weapon": "e"}, gear)
assert values["magic"] == 3152.5 and restored["saturation"]["weapon"]["magic"] == {
    "mode": "value",
    "value": 200,
}
for n in (99, 301, float("nan")):
    exact["saturation"]["weapon"]["magic"]["value"] = n
    try:
        calculate(exact, {"weapon": "e"}, gear)
    except Exception:
        pass
    else:
        raise AssertionError("out of range accepted")
print("PASS: exact equipment values persist and reject out-of-range inputs")

values, _ = calculate(
    {},
    {"weapon": "owned"},
    [
        {
            "id": "owned",
            "name": "my staff",
            "baseAttributes": {"magic": {"min": 100, "max": 300, "ownedValue": 180}},
        }
    ],
)
assert values["magic"] == 180
from backend.equipment.validation import validate_equipment
import json

item = json.loads(
    (Path(__file__).resolve().parents[1] / "data/equipment.json").read_text(encoding="utf-8")
)["equipment"][0]
item["baseAttributes"]["magic"] = {"label": "magic", "min": 100, "max": 300, "ownedValue": 180}
assert validate_equipment(item)["baseAttributes"]["magic"]["ownedValue"] == 180
item["baseAttributes"]["magic"]["ownedValue"] = 301
assert validate_equipment(item)["baseAttributes"]["magic"]["ownedValue"] == 301
print("PASS: personal equipment value fallback, preservation after shared range changes")

config_person = {
    "configurationType": "special",
    "characters": [
        {
            "job": "寒霜法师",
            "equipment": {},
            "specialSources": {
                "selectedPerson": {
                    "id": "p",
                    "name": "法师",
                    "job": "寒霜法师",
                    "attributes": {"magic": 100, "armor": 25, "resistance": 30},
                }
            },
        }
    ],
}
prepared = prepare_configuration(config_person, [])
assert (
    prepared["characters"][0]["stats"]["magic"] == 1730
    and prepared["characters"][0]["stats"]["armor"] == 42.5
    and prepared["characters"][0]["stats"]["resistance"] == 51
)
print("PASS: selected person snapshot supplies five dimensions and armor/resistance")

values, _ = calculate(
    {"gearPercentEnabled": False, "saturation": {"weapon": {"magic": 100}}},
    {"weapon": "owned"},
    [
        {
            "id": "owned",
            "name": "staff",
            "baseAttributes": {"magic": {"min": 100, "max": 300, "ownedValue": 180}},
        }
    ],
)
assert values["magic"] == 180
print("PASS: disabled percentage ignores local overrides and uses equipment library personal value")

for trophies, expected in [
    ([], False),
    ([{"id": "t", "name": "先发战利品", "attributes": {}, "firstStrike": True}], True),
    ([{"id": "t", "name": "普通战利品", "attributes": {}, "firstStrike": False}], False),
]:
    config = {
        "configurationType": "special",
        "characters": [
            {
                "job": "寒霜法师",
                "equipment": {},
                "firstStrike": True,
                "specialSources": {"selectedTrophies": trophies},
            }
        ],
    }
    assert prepare_configuration(config, [])["characters"][0]["firstStrike"] is expected
print("PASS: special first strike derives only from selected trophies, ignoring stale manual flags")

from backend.contracts.store import presets as contract_presets
from backend.rings.store import presets as ring_presets

contract = next(i for i in contract_presets() if i["category"] == "magic")
ring = next(i for i in ring_presets() if i["kind"] == "water" and i["mainAttribute"] == "magic")
legacy = {
    "day10": {"magic": 100},
    "contract": {"magic": 99},
    "ring": {"magic": 999, "magicDamage": 88},
}
values, _ = calculate(legacy, {}, [])
assert values["magic"] == 170 and values["magicDamage"] == 0
wearing = {**legacy, "selectedContract": contract, "selectedRing": ring}
values, _ = calculate(wearing, {}, [])
assert values["magic"] == round(170 * 1.12 + 750, 8)
removed = {**wearing, "selectedContract": None, "selectedRing": None}
values, _ = calculate(removed, {}, [])
assert values["magic"] == 170
conf = {
    "configurationType": "special",
    "characters": [
        {
            "equipment": {},
            "selectedRing": None,
            "selectedContract": None,
            "contract": "旧日支配者-魔",
            "specialSources": wearing,
        }
    ],
}
prepared = prepare_configuration(conf, [])["characters"][0]
assert (
    prepared["stats"]["magic"] == 170
    and prepared["selectedRing"] is None
    and prepared["selectedContract"] is None
)
assert (
    prepared["specialSources"]["selectedRing"] is None
    and prepared["specialSources"]["selectedContract"] is None
    and prepared["contract"] == "不激活"
)
again = prepare_configuration({"configurationType": "special", "characters": [prepared]}, [])[
    "characters"
][0]
assert again["stats"] == prepared["stats"]
assert legacy["contract"]["magic"] == 99 and legacy["ring"]["magic"] == 999
print(
    "PASS: old manual contract/ring values excluded; selected wear counted once; removal clears stale snapshots and activation"
)

# A saved weapon from the previous profession must not contribute to the new role.
from backend.skills.store import SkillError

wrong_weapon = {
    "id": "old_mage_weapon",
    "name": "霜语",
    "weaponJob": "法师",
    "baseAttributes": {"speed": {"min": 10, "max": 10}},
}
try:
    calculate({}, {"weapon": wrong_weapon["id"]}, [wrong_weapon], "夜魇")
    raise AssertionError("previous profession weapon accepted")
except SkillError as exc:
    assert "职业不符" in str(exc)
assert calculate({}, {"weapon": wrong_weapon["id"]}, [wrong_weapon], "寒霜法师")[0]["speed"] == 10
print("PASS: special panel rejects previous profession weapons and accepts compatible weapons")

# Constitution contract bonuses apply once, before flat holy/equipment bonuses.
for body in (i for i in contract_presets() if i["category"] == "constitution"):
    src = {
        "day10": {"constitution": 1000, "magic": 200},
        "holy": {"constitution": 100},
        "selectedContract": body,
    }
    values, _ = calculate(src, {}, [])
    assert values["constitution"] == 2004 and values["magic"] == 340, values
    src["selectedContract"] = {**body, "baseBonus": 20}
    assert calculate(src, {}, [])[0]["constitution"] == 2140
print("PASS: all three constitution contracts supply editable wearing bonuses exactly once")
