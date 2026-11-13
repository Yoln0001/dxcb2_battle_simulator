from pathlib import Path
import sys, copy, random, tempfile
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.contracts.store import presets, validate_item, ContractStore, RULES
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from engine.runtime.contracts import calculate_contract_damage
from engine.runtime.cooldowns import action_cooldown
from engine.runtime.health import reduce_ally_recovery
from engine.runtime.initialization import initialize_battle, BattleConfigurationError

base = {
    "battle": {"duration": 56.1},
    "target": {"hitPoint": 1e9, "speed": 100, "physicalReduction": 0, "magicReduction": 0},
    "characters": [
        {
            "enabled": True,
            "job": "寒霜法师",
            "stats": {
                "magic": 100,
                "strength": 100,
                "speed": 10000,
                "constitution": 1000,
                "hitRate": 50,
            },
            "equipment": {},
            "skillGroup": "g",
            "contract": "不激活",
        }
        for _ in range(4)
    ],
}
skill = {
    "id": "s",
    "name": "群体治疗",
    "job": "寒霜法师",
    "damageType": "none",
    "healingRecipient": "allAllies",
    "cooldown": 0,
    "coefficients": {"magic": 10000},
    "effect": None,
}
groups = {
    "g": {
        "job": "寒霜法师",
        "entry": "n",
        "subgroups": [{"id": "sub", "skills": [{"id": "n", "skillId": "s", "next": "n"}]}],
    }
}
for item in [i for i in presets() if i["category"] == "strength"]:
    for negative in RULES[item["archetype"]][1]:
        cfg = copy.deepcopy(base)
        owner = cfg["characters"][0]
        owner.update(
            selectedContract=item,
            contract=item["archetype"] + "-力",
            negativeEffect=negative,
            skillMultiplier=item["multiplier"],
        )
        py = SingleBattle(cfg, {}, {"s": skill}, groups, seed=4)
        assert np.isclose(py.state.characters[0].stats["strength"], 112)
        if negative == "污秽":
            assert np.isclose(
                reduce_ally_recovery(
                    py.state, 100, recipient=py.state.characters[0], kind="regeneration"
                ),
                70,
            )
        if negative == "痴愚":
            assert np.isclose(action_cooldown(py.state.characters[0], 0)["total"], 1.8)
        if negative == "盲目":
            assert py.state.characters[0].stats["hitRate"] == 45
        if negative == "群体盲目":
            assert all(c.stats["hitRate"] == 47 for c in py.state.characters)
        if negative == "群体痴愚":
            assert all(np.isclose(action_cooldown(c, 0)["total"], 1.6) for c in py.state.characters)
        if negative == "脆化":
            assert py.state.characters[0].stats["physicalTakenMultiplier"] == 1.3
        result = py.run()
        events = [
            e for f in result["timeline"] for e in f["events"] if e["type"] == "contract_damage"
        ]
        assert [e["time"] for e in events] == [28.1, 56.1], events
        if item["archetype"] == "狂怒兽神":
            assert np.isclose(events[0]["damage"], events[1]["damage"] * 4)
        if item["archetype"] == "旧日支配者":
            assert (
                np.isclose(events[0]["damage"], (112 + 300) * 7) and events[0]["targeting"] == "all"
            )
        arrays, _, _ = prepare(cfg, {}, {"s": skill}, groups)
        out = battle(*arrays, np.array(random.Random(4).getstate()[1], dtype=np.uint32))
        assert np.isclose(out[0], result["total_damage"]), (
            item,
            negative,
            out[0],
            result["total_damage"],
        )
        assert np.allclose(out[5], [c.current_hp for c in py.state.characters]), (
            item,
            negative,
            out[5],
        )
item = presets()[1]
cfg = copy.deepcopy(base)
cfg["characters"][0].update(
    contract="饮命者-力", selectedContract=item, skillMultiplier=6.9, negativeEffect="群体盲目"
)
state = initialize_battle(cfg, {})
for lost, multiple in ((0, 1), (0.2499, 1), (0.25, 1.3), (0.5, 1.6), (0.75, 1.9)):
    state.target_current_hp = 1e9 * (1 - lost)
    assert np.isclose(calculate_contract_damage(state)["damage"], 112 * 6.9 * multiple)
# Worn inactive contracts still give attributes, four identical contracts are allowed.
cfg = copy.deepcopy(base)
for c in cfg["characters"]:
    c["selectedContract"] = presets()[0]
state = initialize_battle(cfg, {})
assert state.contract is None and all(
    np.isclose(c.stats["strength"], 112) for c in state.characters
)
cfg["characters"][0]["contract"] = cfg["characters"][1]["contract"] = "狂怒兽神-力"
try:
    initialize_battle(cfg, {})
except BattleConfigurationError:
    pass
else:
    raise AssertionError("multiple activated contracts accepted")
with tempfile.TemporaryDirectory() as d:
    store = ContractStore(Path(d) / "contracts.json")
    assert len(store.read()["contracts"]) == 14
    item = validate_item({**presets()[0], "level": 2, "baseBonus": 18})
    store._write({"schemaVersion": 1, "contracts": [item]})
    assert store.read()["contracts"][0]["baseBonus"] == 18
print(
    "PASS: strength contract presets, persistence, worn/active separation, initial burst, loss thresholds, team strength, negative effects, single activation and Python/Numba parity"
)

from engine.runtime.damage import calculate_hit_chance

cfg = copy.deepcopy(base)
cfg["characters"][0].update(contract="狂怒兽神-力", negativeEffect="盲目", skillMultiplier=3.6)
cfg["characters"][0]["stats"]["hitRate"] = 0
state = initialize_battle(cfg, {})
assert (
    calculate_hit_chance(state.characters[0].stats, {"hitRate": 50}, {"speed": 100})["raw_percent"]
    == 45
)
print("PASS: contract blindness still subtracts its full percentage when panel hit rate is zero")
