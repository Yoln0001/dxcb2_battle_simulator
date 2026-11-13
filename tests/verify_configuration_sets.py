"""Typed configuration libraries preserve legacy records and isolate operations."""

import sys, json, tempfile, copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.configurations.store import ConfigurationStore
from backend.skills.store import SkillError


def config(kind="regular"):
    return {
        "schemaVersion": 1,
        "configurationType": kind,
        "battle": {"duration": 200, "simulations": 100},
        "target": {},
        "characters": [
            {"enabled": True, "firstStrike": False, "stats": {}, "equipment": {}} for _ in range(4)
        ],
    }


with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / "configurations.json"
    legacy = {
        "schemaVersion": 1,
        "activeId": "a",
        "configurations": [
            {"id": "a", "name": "常规旧配置", "configuration": config()},
            {"id": "b", "name": "特殊旧配置", "configuration": config("special")},
        ],
    }
    path.write_text(json.dumps(legacy), encoding="utf-8")
    store = ConfigurationStore(path)
    data = store.read()
    assert data["activeId"] == "a"
    assert [i["libraryId"] for i in data["configurations"]] == [
        "default_regular",
        "default_special",
    ]
    assert [i["configuration"] for i in data["configurations"]] == [
        i["configuration"] for i in legacy["configurations"]
    ]
    library = store.save_library({"name": "实战队伍", "configurationType": "regular"})["library"]
    special = store.save_library({"name": "实战队伍", "configurationType": "special"})["library"]
    saved = store.save(
        {"name": "常规旧配置", "configuration": config(), "libraryId": library["id"]}
    )["item"]
    assert saved["libraryId"] == library["id"]
    try:
        store.save({"name": "混合", "configuration": config("special"), "libraryId": library["id"]})
    except SkillError:
        pass
    else:
        raise AssertionError("cross type accepted")
    copied = store.save_library(
        {
            "name": "队伍备份",
            "configurationType": "regular",
            "copy": True,
            "copyFrom": library["id"],
        }
    )
    backup = [i for i in copied["configurations"] if i["libraryId"] == copied["library"]["id"]]
    assert len(backup) == 1 and backup[0]["id"] != saved["id"]
    assert backup[0]["configuration"] == saved["configuration"]
    store.save_library({"name": "常规默认重命名"}, "default_regular")
    data = store.delete_library(library["id"])
    assert data["activeId"] == ""
    assert any(i["id"] == "a" for i in data["configurations"]) and any(
        i["id"] == backup[0]["id"] for i in data["configurations"]
    )
    try:
        store.delete_library("default_regular")
    except SkillError:
        pass
    else:
        raise AssertionError("default deleted")
    restored = ConfigurationStore(path).read()
    assert any(l["name"] == "常规默认重命名" for l in restored["libraries"])
print(
    "PASS: legacy default assignment, independent typed libraries, copy, scoped names, rename, delete and persistence"
)
