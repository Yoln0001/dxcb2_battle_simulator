from pathlib import Path
import sys, math

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.initialization import initialize_battle, BattleConfigurationError
from engine.runtime.contracts import calculate_contract_damage, resolve_contract_tick
from engine.runtime.buffs import apply_named_buff, expire_buffs

config = {
    "target": {
        "hitPoint": 10000000,
        "magicVulnerability": 1.12,
        "magicReduction": 25,
        "armor": 99999,
        "resistance": 99999,
    },
    "characters": [
        {
            "name": f"角色{i + 1}",
            "enabled": True,
            "stats": {
                "magic": 10000,
                "magicDamage": 26 if i == 0 else 999,
                "finalMagicDamage": 8 if i == 0 else 999,
                "criticalRate": 100,
                "criticalMultiplier": 999,
                "constitution": 1000,
            },
            "equipment": {},
            "contract": "旧日支配者-魔" if i == 0 else "不激活",
            "negativeEffect": "无",
            "skillMultiplier": 5.6,
        }
        for i in range(4)
    ],
}
state = initialize_battle(config, {})
assert state.contract.next_tick_at == 14.1
expected = 40000 * 5.6 * 1.26 * 1.08 * 1.12 * 0.75
r = calculate_contract_damage(state)
assert math.isclose(r["damage"], expected)
assert r["factors"]["magic_reduction"] == 0.75
try:
    resolve_contract_tick(state)
except BattleConfigurationError:
    pass
else:
    raise AssertionError("must not trigger before 14 seconds")
apply_named_buff(
    state,
    name="魔力buff",
    source_index=2,
    target_indices=[2],
    conversions={"magic": {"magic": 1}},
    now=1,
    duration=20,
)
expire_buffs(state, 14.1)
r = resolve_contract_tick(state)
assert r["total_magic"] == 50000
assert state.contract.next_tick_at == 28.1
assert math.isclose(state.target_current_hp, 10000000 - r["damage"])
expire_buffs(state, 28.1)
r2 = resolve_contract_tick(state)
assert r2["total_magic"] == 40000
assert state.contract.next_tick_at == 42.1
assert math.isclose(state.contract.total_damage, r["damage"] + r2["damage"])
config["characters"][3]["enabled"] = False
state = initialize_battle(config, {})
assert calculate_contract_damage(state)["total_magic"] == 30000
state.target["magicReduction"] = 100
assert calculate_contract_damage(state)["damage"] == 1
print(
    "PASS: 14/28/42 timing, current team magic with buff expiry, owner-only bonus/imprint, target vulnerability/reduction, no armor/crit/race, target HP and independent total"
)

from engine.runtime.contracts import resolve_contract_action_tie
from copy import deepcopy

config["characters"][3]["enabled"] = True
base = initialize_battle(config, {})
expire_buffs(base, 14.1)


def owner_action(state):
    apply_named_buff(
        state,
        name="同刻魔力增幅",
        source_index=1,
        target_indices=[1],
        conversions={"magic": {"magic": 1}},
        now=state.time,
    )


first = deepcopy(base)
second = deepcopy(base)
a = resolve_contract_action_tie(first, owner_action, roll=0.49)
b = resolve_contract_action_tie(second, owner_action, roll=0.5)
assert a["total_magic"] == 50000 and b["total_magic"] == 40000
assert first.characters[0].stats["magic"] == second.characters[0].stats["magic"] == 20000
assert first.contract.next_tick_at == second.contract.next_tick_at == 28.1
assert next(e for e in first.events if e["type"] == "contract_action_tie")["order"] == [
    "owner_action",
    "contract",
]
print(
    "PASS: 0.1s clock offset, 14.1/28.1/42.1s schedule and deterministic 50% tie branches using before/after magic"
)
