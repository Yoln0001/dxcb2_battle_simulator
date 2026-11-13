import sys, tempfile, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api.imprints import ImprintStore, presets
from backend.configurations.special import calculate, imprint_for
from backend.skills.store import SkillError

with tempfile.TemporaryDirectory() as d:
    store = ImprintStore(Path(d) / "imprints.json")
    rows = presets()
    base = next(r for r in rows if r["name"] == "战士辉印")
    extra = next(r for r in rows if r["name"] == "剑魔额外辉印")
    assert extra["attributes"]["finalPhysicalDamage"] == 3
    assert all(v == 0 for k, v in extra["attributes"].items() if k != "finalPhysicalDamage")
    values, s = calculate({"selectedImprint": base, "selectedExtraImprint": extra}, {}, [], "剑魔")
    assert values["finalPhysicalDamage"] == 6 and values["finalDotDamage"] == 6
    values2, _ = calculate(s, {}, [], "剑魔")
    assert values2 == values
    legacy = [{k: v for k, v in r.items() if k not in ("scope", "job")} for r in rows]
    for row, original in zip(legacy, rows):
        row["name"] = original["job"] + "辉印"
        row["attributes"] = imprint_for(original["kind"], original["job"])
    store._write({"schemaVersion": 1, "imprints": legacy})
    migrated = store.read()
    assert migrated["imprints"] == rows
    base["attributes"]["finalPhysicalDamage"] = 8
    store.save(base, base["id"])
    assert (
        next(r for r in store.read()["imprints"] if r["id"] == base["id"])["attributes"][
            "finalPhysicalDamage"
        ]
        == 8
    )
    assert (
        next(r for r in store.read()["imprints"] if r["id"] == extra["id"])["attributes"][
            "finalPhysicalDamage"
        ]
        == 3
    )
    values, _ = calculate({"selectedImprint": base, "selectedExtraImprint": extra}, {}, [], "剑魔")
    assert values["finalPhysicalDamage"] == 11
    for action in (
        lambda: store.save(base),
        lambda: store.delete(base["id"]),
        lambda: store.save({**base, "name": "改名"}, base["id"]),
    ):
        try:
            action()
            raise AssertionError("fixed imprint mutation accepted")
        except SkillError:
            pass
    store._write({"schemaVersion": 1, "imprints": []})
    assert len(store.read()["imprints"]) == len(rows)
print(
    "PASS: fixed imprint presets, old combined values migration, additive snapshots, idempotent calculation and numeric-only edits"
)
