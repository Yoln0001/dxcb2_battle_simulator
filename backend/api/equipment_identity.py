"""Stable encyclopedia identity, separate from a library record and personal rolls."""

from copy import deepcopy


def identity_resolver(wiki):
    by_id = {row["id"]: row for row in wiki}
    sources = {"id": {}, "url": {}}
    names = {}

    def add(index, key, item):
        if key in index:
            index[key] = None
        else:
            index[key] = item

    for item in wiki:
        for key, index in sources.items():
            value = item.get("source", {}).get(key)
            if value:
                add(index, value, item)
        add(names, (item["name"].strip(), item["category"], item.get("weaponJob", "")), item)

    def resolve(row):
        match = by_id.get(row.get("wikiId")) or by_id.get(row["id"])
        if match is None:
            for key, index in sources.items():
                match = index.get(row.get("source", {}).get(key))
                if match:
                    break
        if match is None:
            match = names.get((row["name"].strip(), row["category"], row.get("weaponJob", "")))
        return match["id"] if match else row.get("wikiId") or row["id"]

    return resolve


def link_rows(rows, wiki):
    resolve = identity_resolver(wiki)
    result = []
    for original in rows:
        row = deepcopy(original)
        row["wikiId"] = resolve(original)
        result.append(row)
    return result


def link_fresh(rows, resolve):
    """给刚从库里读出的行就地补上wikiId。库的read()每次返回独立副本，无需再复制。"""
    for row in rows:
        row["wikiId"] = resolve(row)
    return rows


def identity_pairs(request, resolve):
    """全部装备库中每条记录的(库内ID, 百科身份)，顺序为默认库、各玩家库、已移除库的残留文件。

    残留文件只用来翻译旧的穿戴ID，不提供数值。这里只取ID，不复制装备内容。
    """
    from .library_sets import store_for
    from ..equipment.store import EquipmentStore

    registry = request.app.state.library_sets
    known = [item["id"] for item in registry.read()["libraries"] if item["kind"] == "equipment"]
    rows = store_for(request, "equipment", "").read()["equipment"]
    for library_id in known:
        rows += store_for(request, "equipment", library_id).read()["equipment"]
    pairs = [(row["id"], resolve(row)) for row in rows]
    for path in (registry.path.parent / "player_libraries" / "equipment").glob("*.json"):
        if path.stem in known:
            continue
        try:
            retained = EquipmentStore(path).read()["equipment"]
            pairs += [(row["id"], resolve(row)) for row in retained]
        except ValueError:
            continue
    return pairs


def library_view(request, canonical=False):
    from .library_sets import store_for

    resolve = identity_resolver(request.app.state.wiki_equipment_store.read()["equipment"])
    rows = link_fresh(store_for(request, "equipment").read()["equipment"], resolve)
    aliases = {}
    for record_id, wiki_id in identity_pairs(request, resolve):
        aliases.setdefault(wiki_id, set()).add(record_id)
    for row in rows:
        row["identityAliases"] = sorted(
            aliases.get(row["wikiId"], set()) | {row["id"], row["wikiId"]}
        )
    if canonical:
        for row in rows:
            row["libraryRecordId"] = row["id"]
            row["id"] = row["wikiId"]
    return {"schemaVersion": 1, "equipment": rows}


def battle_catalog(request, config):
    from .library_sets import store_for

    resolve = identity_resolver(request.app.state.wiki_equipment_store.read()["equipment"])
    selected = link_fresh(
        store_for(
            request, "equipment", config.get("librarySelections", {}).get("equipment", "")
        ).read()["equipment"],
        resolve,
    )
    by_identity = {row["wikiId"]: row for row in selected}
    # 先只确定每个ID最终对应哪一行（同一ID后者覆盖前者，位置保持首次出现处），
    # 再各复制一次；各库ID统一时，同一件装备不必按库的数量重复复制。
    plan = {}
    for record_id, wiki_id in identity_pairs(request, resolve):
        if wiki_id in by_identity:
            plan[record_id] = (by_identity[wiki_id], None)
    for row in selected:
        plan[row["wikiId"]] = (row, row["id"])
    result = []
    for key, (row, library_record_id) in plan.items():
        item = deepcopy(row)
        if library_record_id is not None:
            item["libraryRecordId"] = library_record_id
        item["id"] = key
        result.append(item)
    return result
