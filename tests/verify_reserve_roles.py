import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.configurations.store import ConfigurationStore, validate_config
from backend.api.battle import prepare_configuration

rows = [
    dict(
        name=str(i),
        enabled=i < 4,
        firstStrike=False,
        job="",
        skillGroup="",
        stats={},
        equipment={},
        contract="不激活",
        negativeEffect="无",
    )
    for i in range(6)
]
c = dict(
    schemaVersion=1,
    configurationType="regular",
    battle=dict(duration=10, simulations=10),
    target={},
    characters=rows,
)
with tempfile.TemporaryDirectory() as tmp:
    store = ConfigurationStore(Path(tmp) / "config.json")
    store.save({"name": "备选", "configuration": c})
    assert len(store.read()["configurations"][0]["configuration"]["characters"]) == 6
c["characters"][0]["enabled"] = False
c["characters"][5]["enabled"] = True
assert [i["name"] for i in prepare_configuration(c, [])["characters"]] == ["1", "2", "3", "5"]
assert len(c["characters"]) == 6
c["characters"][0]["enabled"] = True
for fn in (validate_config, lambda c: prepare_configuration(c, [])):
    try:
        fn(c)
    except ValueError:
        pass
    else:
        raise AssertionError("fifth participant accepted")
for row in c["characters"]:
    row["enabled"] = False
assert len(prepare_configuration(c, [])["characters"]) == 4
print("PASS: reserve persistence, selection/order, four-participant limit and empty slots")
