import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api.holies import (
    HolyStore,
    HOLY_LEVELS,
    TYPES,
    level_attributes,
    presets,
    validate_item,
)
from backend.configurations.special import HOLY, calculate
from backend.skills.store import SkillError

for kind in TYPES:
    expected = {
        k: HOLY[kind].get(k, 0) for k in ("strength", "magic", "technique", "speed", "constitution")
    }
    assert level_attributes(kind, 100, 600)["total"] == expected, kind
assert level_attributes("战士", 60, 0)["total"]["strength"] == 82
assert level_attributes("战士", 60, 0)["total"]["constitution"] == 162
assert level_attributes("圣职", 20, 30)["obelisk"] == dict(
    strength=0, magic=50, technique=40, speed=0, constitution=30
)
assert level_attributes("圣职", 20, 31)["obelisk"]["technique"] == 60
with tempfile.TemporaryDirectory() as d:
    store = HolyStore(Path(d) / "holies.json")
    row = presets()[0]
    row.update(holyLevel=50, obeliskLevel=31, attributes={"strength": 99999})
    saved = store.save(row, row["id"])["item"]
    assert saved["attributes"] == level_attributes("战士", 50, 31)["total"]
    assert store.read()["holies"][0] == saved
    stats, s = calculate({"selectedHoly": saved}, {}, [], "剑魔")
    for k, v in saved["attributes"].items():
        assert stats[k] == v
    stats2, _ = calculate(s, {}, [], "剑魔")
    assert stats2 == stats
    legacy = {k: v for k, v in row.items() if k not in ("holyLevel", "obeliskLevel")}
    store._write({"schemaVersion": 1, "holies": [legacy]})
    retained = store.read()["holies"][0]
    assert retained["attributes"]["strength"] == 99999 and "holyLevel" not in retained
    for h, o in [(65, 0), (100, -1), (100, 1.5), (True, 0), (100, True)]:
        try:
            validate_item({**row, "holyLevel": h, "obeliskLevel": o})
            raise AssertionError("invalid levels accepted")
        except SkillError:
            pass
print(
    "PASS: max-level totals equal old six-profession values; exact table, 30-level cycle, persistence, authoritative levels, legacy preservation and panel snapshots"
)
