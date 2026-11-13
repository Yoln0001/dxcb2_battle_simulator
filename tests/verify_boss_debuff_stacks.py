"""Boss debuff stacking, expiry restoration, validation and njit parity."""

import sys, copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_boss_combat import fixture, compare
from engine.runtime.boss_simulation import BossBattle
from backend.api.bosses import validate_boss_group
from backend.skills.store import SkillError

for kind in ("burn", "lifeLoss", "weakness", "magicDecay", "slow", "stun"):
    cfg, eq, sl, gl = fixture()
    cfg["battle"]["duration"] = 8
    for c in cfg["characters"]:
        c["stats"].update(strength=100, constitution=10000, physicalBlock=0)
    skill = cfg["target"]["selectedBoss"]["skillGroup"]["skills"][0]
    skill.update(baseValue=0, targeting="all")
    skill["effect"] = {
        "kind": "debuff",
        "type": kind,
        "baseValue": 10,
        "duration": 10,
        "applicationRate": 1000,
        "coefficients": dict.fromkeys(("strength", "magic", "technique", "speed"), 0),
        "maxStacks": 3,
    }
    py = BossBattle(cfg, eq, sl, gl, seed=3)
    for i, t in enumerate((1.5, 3, 4.5, 6)):
        py.state.time = t
        py.boss_periodic()
        py.boss_action()
        row = py.boss_runtime[4][
            0,
            (
                "burn",
                "bleeding",
                "plague",
                "slow",
                "stun",
                "weakness",
                "fear",
                "lifeLoss",
                "strengthDecay",
                "magicDecay",
                "techniqueDecay",
                "speedDecay",
            ).index(kind),
        ]
        assert row[0] == min(i + 1, 3), (kind, row)
        if kind in ("burn", "lifeLoss"):
            assert row[3] == 10 * min(i + 1, 3)
        if kind == "weakness":
            assert py.state.characters[0].stats["strength"] == 100 - 10 * min(i + 1, 3)
        if kind == "magicDecay":
            assert py.state.characters[0].stats["magic"] == 100 - 10 * min(i + 1, 3)
    py.state.time = 17
    py.boss_periodic()
    # Drain delayed DOT ticks before expiry; attribute effects restore immediately.
    if kind == "weakness":
        assert py.state.characters[0].stats["strength"] == 100
    if kind == "magicDecay":
        assert py.state.characters[0].stats["magic"] == 100
    compare(cfg, eq, sl, gl, seeds=range(3))
    for invalid in (0, 1000, 1.5, True):
        bad = copy.deepcopy(cfg["target"]["selectedBoss"]["skillGroup"])
        bad["skills"][0]["effect"]["maxStacks"] = invalid
        try:
            validate_boss_group(bad)
        except SkillError:
            pass
        else:
            raise AssertionError(invalid)
print(
    "PASS: stacking caps, DOT damage, attribute restoration, stun, validation and 18 seeded njit comparisons"
)
