import sys, copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_boss_combat import fixture, compare
from engine.runtime.boss_simulation import BossBattle
from backend.api.bosses import validate_boss_group
from engine.runtime.compiled.boss import KINDS

for kind, attribute, flag in [
    ("armorDecay", "armor", "immuneArmorDecay"),
    ("resistanceDecay", "resistance", "immuneResistanceDecay"),
]:
    cfg, eq, sl, gl = fixture()
    skill = cfg["target"]["selectedBoss"]["skillGroup"]["skills"][0]
    skill.update(
        baseValue=0,
        targeting="all",
        effect={
            "kind": "debuff",
            "type": kind,
            "baseValue": 10,
            "duration": 2,
            "applicationRate": 1000,
            "coefficients": dict.fromkeys(("strength", "magic", "technique", "speed"), 0),
            "maxStacks": 1,
        },
    )
    cfg["target"]["selectedBoss"]["skillGroup"] = validate_boss_group(
        cfg["target"]["selectedBoss"]["skillGroup"]
    )
    item = {
        "id": "immune",
        "name": "免疫",
        "category": "accessory",
        "startingBuff": {"enabled": False},
        "triggerEnabled": False,
        "negativeImmunities": {flag: True},
    }
    eq["immune"] = item
    cfg["characters"][0]["equipment"]["accessory1"] = "immune"
    battle = BossBattle(cfg, eq, sl, gl, seed=1)
    initial = [c.stats[attribute] for c in battle.state.characters]
    battle.state.time = 1.5
    battle.boss_action()
    assert battle.state.characters[0].stats[attribute] == initial[0]
    assert battle.state.characters[1].stats[attribute] == initial[1] - 10
    assert battle.boss_runtime[4][0, KINDS.index(kind), 0] == 0
    battle.state.time = 3.5
    battle.boss_periodic()
    assert [c.stats[attribute] for c in battle.state.characters] == initial
    compare(cfg, eq, sl, gl, seeds=range(2))
print(
    "PASS: armor/resistance decay immunity, unprotected decay, expiry restoration and Python/njit parity"
)
