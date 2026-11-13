"""Persistent custom stone library."""

import json, uuid
from .library_routes import library_router
from ..library_store import LibraryStore
from ..skills.store import SkillStore, SkillError, text
from ..configurations.special import KEYS, number

TYPES = ("暴君之石", "古精灵之石", "乌鸦之石", "猎神者之石", "巨龙之石", "唯一魔石")
ATTRIBUTES = ("strength", "magic", "technique", "speed", "constitution", "hitRate")


def validate_item(payload, item_id=None):
    if not isinstance(payload, dict):
        raise SkillError("魔石格式无效")
    name = text(payload.get("name"), "魔石名称")
    kind = payload.get("kind")
    if kind not in TYPES:
        raise SkillError("魔石种类无效")
    attrs = payload.get("attributes", {})
    if not isinstance(attrs, dict) or any(k not in ATTRIBUTES for k in attrs):
        raise SkillError("魔石属性无效")
    return {
        "id": item_id or str(uuid.uuid4()),
        "name": name,
        "kind": kind,
        "attributes": {k: number(attrs.get(k, 0)) for k in ATTRIBUTES},
    }


class StoneStore(LibraryStore):
    key = "stones"
    label = "魔石"
    validate = staticmethod(validate_item)


router = library_router("stones", "魔石库")
