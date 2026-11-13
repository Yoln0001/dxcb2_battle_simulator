from pathlib import Path
import copy, random, sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from backend.skills.store import validate_skill, ATTRS, SkillError
from backend.skill_groups.validation import validate_group
from engine.runtime.simulation import SingleBattle
from engine.runtime.targeting import select_target
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle

choices = {
    "lowestHp": 2,
    "highestHp": 3,
    "lowestArmor": 1,
    "highestArmor": 4,
    "lowestResistance": 2,
    "highestResistance": 3,
}
hp = [600, 300, 900, 400]
armor = [5, 20, 10, 30]
resistance = [10, 5, 30, 20]
candidates = [
    SimpleNamespace(
        index=i + 1,
        enabled=True,
        alive=True,
        current_hp=hp[i],
        stats={"armor": armor[i], "resistance": resistance[i]},
        buffs=[],
    )
    for i in range(4)
]
for rule, target in choices.items():
    assert select_target(candidates, rule).index == target
candidates[1].alive = False
assert select_target(candidates, "lowestHp").index == 4
candidates[1].alive = True
candidates[0].buffs = [SimpleNamespace(name="嘲讽")]
assert select_target(candidates, "lowestHp", hostile=True).index == 1
assert select_target(candidates, "lowestHp", hostile=True, ignore_taunt=True).index == 2
assert select_target(candidates, "lowestHp", hostile=False).index == 2
candidates[3].current_hp = 300
assert select_target(candidates, "lowestHp").index == 2

assert (
    select_target(candidates, "random", rng=random.Random(3)).index
    == select_target(candidates, "random", rng=random.Random(3)).index
)
base = {
    "schemaVersion": 1,
    "id": "attack",
    "name": "Attack",
    "job": "岩浆法师",
    "damageType": "magic",
    "cooldown": 1,
    "hitRate": 100,
    "criticalRate": 0,
    "coefficients": {k: 1 if k == "magic" else 0 for k in ATTRS + ["weaponPower"]},
    "raceBonus": {"race": "none", "multiplier": 0},
    "effect": None,
    "targetSelection": "highestHp",
    "ignoreTaunt": True,
}
skill = validate_skill(base)
assert "targetSelection" not in skill and skill["ignoreTaunt"] is True
from engine.runtime.simulation import SkillSequence

raw = {
    "schemaVersion": 2,
    "id": "g",
    "name": "different targets",
    "job": "岩浆法师",
    "entry": "a",
    "subgroups": [
        {
            "id": "s",
            "skills": [
                {"id": "a", "skillId": "attack", "next": "b", "targetSelection": "random"},
                {"id": "b", "skillId": "attack", "next": "a", "targetSelection": "highestArmor"},
            ],
        }
    ],
}
group = validate_group(raw)
seq = SkillSequence(group, {"attack": skill}, "岩浆法师")
assert (
    seq.nodes["a"]["targetSelection"] == "random"
    and seq.nodes["b"]["targetSelection"] == "highestArmor"
)
legacy = copy.deepcopy(raw)
legacy["subgroups"][0]["skills"][0].pop("targetSelection")
assert validate_group(legacy)["subgroups"][0]["skills"][0]["targetSelection"] == "lowestHp"
bad = copy.deepcopy(raw)
bad["subgroups"][0]["skills"][0]["targetSelection"] = "invalid"
try:
    validate_group(bad)
except SkillError:
    pass
else:
    raise AssertionError("invalid group target accepted")
for dtype, targeting in [("none", "single"), ("magic", "all")]:
    definition = {**skill, "damageType": dtype, "targeting": targeting}
    assert (
        SkillSequence(group, {"attack": definition}, "岩浆法师").nodes["a"]["targetSelection"]
        == "default"
    )
conditional = copy.deepcopy(raw)
conditional["subgroups"][0].update(
    conditionsEnabled=True,
    skills=[
        {
            "id": "a",
            "skillId": "attack",
            "decision": {
                "cases": [
                    {
                        "kind": "allyHealthBelow",
                        "threshold": 20,
                        "skillId": "attack",
                        "targetSelection": "highestResistance",
                    }
                ],
                "elseSkillId": "attack",
                "elseTargetSelection": "random",
            },
        }
    ],
)
seq = SkillSequence(validate_group(conditional), {"attack": skill}, "岩浆法师")
assert [n["targetSelection"] for n in seq.nodes.values()] == ["highestResistance", "random"]
config = {
    "battle": {"duration": 6},
    "target": {"hitPoint": 1e9, "speed": 100},
    "characters": [
        {
            "enabled": i == 0,
            "job": "岩浆法师",
            "skillGroup": "g",
            "stats": {"magic": 50, "constitution": 100, "speed": 100},
            "equipment": {},
        }
        for i in range(4)
    ],
}
result = SingleBattle(config, {}, {"attack": skill}, {"g": group}, seed=3).run()
arrays, _, _ = prepare(config, {}, {"attack": skill}, {"g": group})
assert set(arrays[9][:, 8]) == {7, 4}
output = battle(*arrays, np.array(random.Random(3).getstate()[1], dtype=np.uint32))
assert np.allclose(output[2], result["character_damage"])
print(
    "PASS: current-value and seeded random selectors, group node and if/else targets, lowest-HP default, invalid rejection, single-attack restriction and compiled parity"
)
