import sys
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api.equipment_identity import link_rows
from backend.api.library_sets import equipment_catalog
from backend.app import create_app
import tempfile

wiki = {
    "id": "wiki-fixed",
    "name": "original",
    "category": "weapon",
    "weaponJob": "法师",
    "source": {"id": "origin-1", "url": "source-1"},
}
a = {
    "id": "old-a",
    "name": "renamed-a",
    "category": "weapon",
    "weaponJob": "法师",
    "source": {"id": "origin-1"},
    "baseAttributes": {"magic": {"ownedValue": 100}},
}
b = {
    **deepcopy(a),
    "id": "old-b",
    "name": "renamed-b",
    "baseAttributes": {"magic": {"ownedValue": 200}},
}
linked = link_rows([a, b], [wiki])
assert [r["wikiId"] for r in linked] == ["wiki-fixed"] * 2
assert a.get("wikiId") is None and linked[0]["baseAttributes"]["magic"]["ownedValue"] == 100
linked[0]["name"] = "renamed-again"
linked[0].pop("source")
assert link_rows([linked[0]], [wiki])[0]["wikiId"] == "wiki-fixed"


class Store:
    def __init__(self, rows):
        self.rows = rows

    def read(self):
        return {"equipment": deepcopy(self.rows)}


# Same record ID in copied libraries must use the configuration's selected rolls.
import backend.api.library_sets as module

previous = module.store_for
base = Store([{**a, "wikiId": "wiki-fixed"}])
selected = Store([{**b, "id": "old-a", "wikiId": "wiki-fixed"}])
registry = SimpleNamespace(read=lambda: {"libraries": []})
request = SimpleNamespace(
    app=SimpleNamespace(
        state=SimpleNamespace(library_sets=registry, wiki_equipment_store=Store([wiki]))
    )
)
try:
    module.store_for = lambda request, kind, library_id=None: (
        selected if library_id == "copy" else base
    )
    result = {
        row["id"]: row
        for row in equipment_catalog(request, {"librarySelections": {"equipment": "copy"}})
    }
    assert result["old-a"]["baseAttributes"]["magic"]["ownedValue"] == 200
    assert base.rows[0]["baseAttributes"]["magic"]["ownedValue"] == 100
finally:
    module.store_for = previous
print(
    "PASS: source-based and persisted identity survives rename; selected library wins duplicate IDs; source rolls untouched"
)
