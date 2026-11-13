import sys, tempfile, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.contracts.store import validate_item, presets, ContractStore

item = validate_item({**presets()[0], "baseBonus": 23.4, "multiplier": 4.75})
assert item["baseBonus"] == 23.4 and item["multiplier"] == 4.75 and "level" not in item
old = validate_item({**presets()[0], "level": 2, "baseBonus": 17, "multiplier": 3.6})
assert abs(old["multiplier"] - 4.32) < 1e-9 and "level" not in old
assert validate_item(old) == old
with tempfile.TemporaryDirectory() as d:
    store = ContractStore(Path(d) / "contracts.json")
    store._write({"schemaVersion": 2, "contracts": [old, item | {"id": "manual"}]})
    saved = store.read()
    store._write(saved)
    assert store.read() == saved
print(
    "PASS: unrestricted manual coefficients and base bonuses, legacy second-level conversion exactly once, persistence without levels"
)
