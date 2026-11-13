"""Persistent custom people library."""

import json, uuid
from .library_routes import library_router
from ..library_store import LibraryStore
from ..skills.store import SkillStore, SkillError, text
from ..configurations.special import KEYS, number

ATTRIBUTES = ("strength", "magic", "technique", "speed", "constitution", "armor", "resistance")


def validate_item(payload, item_id=None):
    if not isinstance(payload, dict):
        raise SkillError("人物格式无效")
    name = text(payload.get("name"), "人物名称")
    job = text(payload.get("job"), "职业")
    from ..equipment.jobs import normalize_weapon_job

    normalize_weapon_job(job)
    attrs = payload.get("attributes", {})
    if not isinstance(attrs, dict) or any(k not in ATTRIBUTES for k in attrs):
        raise SkillError("人物属性无效")
    return {
        "id": item_id or str(uuid.uuid4()),
        "name": name,
        "job": job,
        "attributes": {k: number(attrs.get(k, 0)) for k in ATTRIBUTES},
    }


class PeopleStore(LibraryStore):
    key = "people"
    label = "人物"
    validate = staticmethod(validate_item)


router = library_router("people", "人物库")
