from fastapi import APIRouter, Request
from .equipment_sync import save_synced

router = APIRouter(prefix="/api/wiki-equipment", tags=["百科装备库"])


@router.get("")
def read(request: Request):
    return request.app.state.wiki_equipment_store.read()


@router.post("", status_code=201)
def create(payload: dict, request: Request):
    return save_synced(request, request.app.state.wiki_equipment_store, payload)


@router.put("/{item_id}")
def update(item_id: str, payload: dict, request: Request):
    return save_synced(request, request.app.state.wiki_equipment_store, payload, item_id)


@router.post("/import")
def import_library(payload: dict, request: Request):
    return request.app.state.wiki_equipment_store.import_library(payload)


@router.post("/classify")
def classify_missing(payload: dict, request: Request):
    return request.app.state.wiki_equipment_store.classify_missing(
        request.app.state.unclassified_equipment_store.read()["equipment"]
    )


@router.post("/{item_id}/promote")
def promote(item_id: str, payload: dict, request: Request):
    from ..skills.store import SkillError
    from copy import deepcopy

    wiki = request.app.state.wiki_equipment_store
    custom = request.app.state.equipment_store
    with wiki.lock, custom.lock:
        item = next((i for i in wiki.read()["equipment"] if i["id"] == item_id), None)
        if item is None:
            raise SkillError("百科装备不存在", 404)
        item = deepcopy(item)
        existing = next(
            (i for i in custom.read()["equipment"] if i["name"].strip() == item["name"].strip()),
            None,
        )
        item["id"] = existing["id"] if existing else item["id"]
        result = custom.save(item, item["id"] if existing else None)
        return {**result, "replaced": existing is not None}


@router.delete("/{item_id}")
def delete_equipment(item_id: str, request: Request):
    return request.app.state.wiki_equipment_store.delete(item_id)
