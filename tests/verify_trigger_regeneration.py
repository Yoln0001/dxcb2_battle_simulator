import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify_boss_combat import fixture, compare
from backend.equipment.validation import validate_equipment
from backend.equipment.store import EquipmentStore
from engine.runtime.boss_simulation import BossBattle

for trigger in ("magic", "receivedPhysical"):
    for recipient in ("self", "allAllies"):
        cfg, eq, sl, gl = fixture()
        cfg["battle"]["duration"] = 8
        cfg["target"]["allyRegenerationReduction"] = 50
        for c in cfg["characters"]:
            c["stats"].update(healingBonus=20, finalHealingBonus=25)
        raw = {
            "schemaVersion": 1,
            "id": "regen",
            "name": "触发回春",
            "category": "accessory",
            "weaponJob": "",
            "attackType": trigger,
            "effectName": "",
            "triggerEffectName": "持续回复",
            "triggerEnabled": True,
            "startingBuff": {
                "enabled": False,
                "recipient": "self",
                "target": "none",
                "coefficients": dict.fromkeys(("strength", "magic", "technique", "speed"), 0),
            },
            "triggerRate": 100,
            "effect": {
                "kind": "buff",
                "type": "regeneration",
                "recipient": recipient,
                "baseValue": 40,
                "duration": 2,
            },
        }
        item = validate_equipment(raw)
        eq["regen"] = item
        for c in cfg["characters"]:
            c["equipment"]["accessory1"] = "regen"
        with tempfile.TemporaryDirectory() as tmp:
            store = EquipmentStore(Path(tmp) / "eq.json")
            store.save(item)
            assert store.read()["equipment"][0]["effect"] == item["effect"]
        out = compare(cfg, eq, sl, gl, seeds=range(2))
        ticks = [
            e for frame in out["timeline"] for e in frame["events"] if e["type"] == "regeneration"
        ]
        assert ticks and all(abs(e["amount"] - 30) < 1e-8 for e in ticks), ticks
print(
    "PASS: triggered regeneration save/reload, self/team, outgoing/received procs, healing bonuses and Boss reduction; Python/njit parity"
)
