import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.damage import calculate_burn_damage, calculate_damage, minimum_damage
from engine.runtime.initialization import BattleConfigurationError

stats = {"magic": 1000, "dotDamage": 26, "finalDotDamage": 2}
effect = {"kind": "debuff", "type": "burn", "baseValue": 100, "coefficients": {"magic": 2}}
target = {"dotVulnerability": 1.12, "dotReduction": 25, "armor": 999999}
r = calculate_burn_damage(stats, effect, target)
assert abs(r["final_damage"] - 2100 * 1.26 * 1.02 * 1.12 * 0.75) < 1e-9
assert calculate_burn_damage(stats, effect, {**target, "dotReduction": 100})["final_damage"] == 1
assert (
    calculate_burn_damage(stats, {**effect, "baseValue": 0, "coefficients": {}}, target)[
        "final_damage"
    ]
    == 1
)
for kind, key in [("physical", "physicalReduction"), ("magic", "magicReduction")]:
    skill = {"damageType": kind, "coefficients": {"magic": 0.00001}}
    t = {"physicalVulnerability": 1, "magicVulnerability": 1, "armor": 999999, key: 99}
    assert calculate_damage(stats, skill, t, critical_roll=0.9)["final_damage"] == 1
    assert calculate_damage(stats, skill, {**t, key: 100}, critical_roll=0.9)["final_damage"] == 1
assert minimum_damage(0, 0) == 1
try:
    calculate_burn_damage(stats, effect, {**target, "dotReduction": 101})
    raise AssertionError("invalid reduction accepted")
except BattleConfigurationError:
    pass
print("PASS: burn factors, damage floor for physical/magic/dot and 100% reduction")
