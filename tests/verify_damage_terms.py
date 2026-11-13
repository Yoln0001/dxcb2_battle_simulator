import sys, math
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.damage import calculate_damage_terms
from engine.runtime.initialization import initialize_battle, BattleConfigurationError
from engine.runtime.amplification import attack_snapshot


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-12), (a, b)


skill = {
    "damageType": "magic",
    "coefficients": {"magic": 4.6, "weaponPower": 1, "hitPoint": 0},
    "criticalRate": 0,
    "raceBonus": {"race": "spirit", "multiplier": 0.5},
}
stats = {
    "magic": 42000,
    "weaponPower": 798,
    "magicDamage": 24.8,
    "criticalRate": 0,
    "technique": 2000,
    "criticalMultiplier": 59,
    "finalMagicDamage": 8,
}
target = {"race": "灵体", "magicVulnerability": 1.12, "physicalVulnerability": 1}
original = deepcopy((stats, skill, target))
result = calculate_damage_terms(stats, skill, target, critical_roll=0.99999)
f = result["factors"]
close(f["skill_damage"], 42000 * 4.6 + 798)
close(f["damage_bonus"], 1.248)
close(f["critical"], 2.09)
close(f["race_bonus"], 1.5)
close(f["imprint"], 1.08)
close(f["target_vulnerability"], 1.12)
close(result["pre_mitigation_damage"], (42000 * 4.6 + 798) * 1.248 * 2.09 * 1.5 * 1.08 * 1.12)
assert result["critical"] and result["critical_rate"]["probability"] == 1
assert (stats, skill, target) == original and len(result["pending_factors"]) == 2
stats["technique"] = 0
result = calculate_damage_terms(stats, skill, target, critical_roll=0)
assert not result["critical"] and result["factors"]["critical"] == 1
stats["technique"] = 600
stats["criticalRate"] = 10
skill["criticalRate"] = 20
result = calculate_damage_terms(stats, skill, target, critical_roll=0.599)
assert result["critical"]
close(result["critical_rate"]["probability"], 0.6)
assert not calculate_damage_terms(stats, skill, target, critical_roll=0.6)["critical"]
target["race"] = "傀儡"
assert calculate_damage_terms(stats, skill, target, critical_roll=0)["factors"]["race_bonus"] == 1
skill["damageType"] = "physical"
skill["coefficients"] = {"strength": 2, "weaponPower": 1}
stats["strength"] = 1000
stats["physicalDamage"] = 20
stats["finalPhysicalDamage"] = 5
target["physicalVulnerability"] = 1.3
f = calculate_damage_terms(stats, skill, target, critical_roll=0.99)["factors"]
close(f["skill_damage"], 2798)
close(f["damage_bonus"], 1.2)
close(f["imprint"], 1.05)
close(f["target_vulnerability"], 1.3)
target["physicalVulnerability"] = 0
assert calculate_damage_terms(stats, skill, target, critical_roll=0)["pre_mitigation_damage"] == 0
skill["damageType"] = "none"
try:
    calculate_damage_terms(stats, skill, target)
except BattleConfigurationError:
    pass
else:
    raise AssertionError("healing must not be treated as damage")
# Attack amplification also increases technique-based critical probability without changing persistent attributes.
config = {
    "characters": [
        {
            "enabled": True,
            "stats": {"magic": 21000, "technique": 1000, "weaponPower": 0},
            "equipment": {},
        }
        for _ in range(4)
    ]
}
state = initialize_battle(config, {})
snapshot = attack_snapshot(
    state.characters[0],
    [
        {
            "kind": "amplify",
            "conversions": [
                {"target": "magic", "enabled": True, "coefficients": {"magic": 1}},
                {"target": "technique", "enabled": True, "coefficients": {"technique": 1}},
            ],
        }
    ],
)
skill = {
    "damageType": "magic",
    "coefficients": {"magic": 4.6},
    "criticalRate": 0,
    "raceBonus": {"race": "none", "multiplier": 0},
}
result = calculate_damage_terms(
    snapshot, skill, {"race": "灵体", "magicVulnerability": 1}, critical_roll=0.99
)
assert result["critical"]
close(result["factors"]["skill_damage"], 42000 * 4.6)
assert (
    state.characters[0].stats["magic"] == 21000 and state.characters[0].stats["technique"] == 1000
)
print(
    "PASS: six factors, percentage units, critical probability boundaries, race matching, attack-time snapshots, physical/magic branches, zero vulnerability and no mutation"
)
