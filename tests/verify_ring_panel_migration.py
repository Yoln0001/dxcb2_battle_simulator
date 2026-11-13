import copy, json, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.configurations.store import ConfigurationStore, validate_config
from backend.rings.store import presets
from engine.runtime.initialization import initialize_battle

ring = next(r for r in presets() if r["kind"] == "fire")
ring = {
    **ring,
    "mainAttribute": "magic",
    "secondaryAttribute": "magic",
    "mainValue": 750,
    "secondaryValue": 500,
    "gainValue": 13,
}
c = {
    "schemaVersion": 1,
    "configurationType": "regular",
    "battle": {"duration": 10, "simulations": 10},
    "target": {},
    "characters": [],
}
for i in range(4):
    c["characters"].append(
        {
            "name": str(i),
            "job": "",
            "skillGroup": "",
            "enabled": True,
            "firstStrike": False,
            "stats": {"magic": 3000, "constitution": 1000, "physicalDamage": 20, "magicDamage": 20},
            "equipment": {},
            "contract": "不激活",
            "negativeEffect": "无",
            "selectedRing": ring,
            "ringPanelIncluded": True,
            "ringPanelBonuses": {"physicalDamage": 13, "magicDamage": 13},
            "ringBattleMultipliers": {"magic": 1.2},
        }
    )
original = copy.deepcopy(c)
before = initialize_battle(c, {})
after_config = validate_config(c)
assert c == original and validate_config(after_config) == after_config
assert after_config["characters"][0]["stats"]["magic"] == 3000
assert after_config["characters"][0]["stats"]["magicDamage"] == 7
outside = copy.deepcopy(after_config)
for character in outside["characters"]:
    character["ringPanelIncluded"] = False
    character["stats"]["magic"] -= 1500
assert validate_config(outside) == after_config
after = initialize_battle(after_config, {})
for a, b in zip(before.characters, after.characters):
    assert a.stats == b.stats and a.maximum_hp == b.maximum_hp and a.current_hp == b.current_hp
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "configurations.json"
    data = {
        "schemaVersion": 1,
        "activeId": "keep",
        "configurations": [{"id": "keep", "name": "旧常规", "configuration": c}],
    }
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    store = ConfigurationStore(path)
    first = store.read()
    raw = path.read_bytes()
    assert first["activeId"] == "keep" and first["configurations"][0]["name"] == "旧常规"
    assert first["configurations"][0]["configuration"] == after_config
    backups = list((path.parent / "backups").glob("*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8")) == data
    assert store.read() == first and path.read_bytes() == raw
    assert len(list((path.parent / "backups").glob("*.json"))) == 1
print(
    "PASS: legacy panel migration preserves opening state, combines duplicate attributes, keeps identity/active selection, backs up once, and is idempotent"
)
