from .library_sets import store_for
from .equipment_sync import save_synced, saved_response
from fastapi import APIRouter, Request
from ..schemas.equipment import EquipmentPayload, EquipmentLibraryPayload
from ..skills.store import SkillError

router = APIRouter(prefix="/api/equipment", tags=["装备库"])


@router.get("", summary="读取装备库")
def list_equipment(request: Request):
    from .equipment_identity import library_view

    return library_view(request)


@router.get("/team", summary="按百科身份读取当前库装备数值")
def team_equipment(request: Request):
    from .equipment_identity import library_view

    return library_view(request, canonical=True)


@router.post("", status_code=201, summary="创建装备")
def create_equipment(payload: EquipmentPayload, request: Request):
    return saved_response(
        request, save_synced(request, store_for(request, "equipment"), payload.model_dump())
    )


@router.post("/import", summary="合并导入装备库")
def import_equipment(payload: EquipmentLibraryPayload, request: Request):
    return store_for(request, "equipment").import_library(payload.model_dump())


@router.get("/{item_id:path}", summary="读取装备")
def get_equipment(item_id: str, request: Request):
    item = next(
        (
            item
            for item in store_for(request, "equipment").read()["equipment"]
            if item["id"] == item_id
        ),
        None,
    )
    if item is None:
        raise SkillError("装备不存在", 404)
    return item


@router.put("/{item_id:path}", summary="修改装备")
def update_equipment(item_id: str, payload: EquipmentPayload, request: Request):
    return saved_response(
        request,
        save_synced(request, store_for(request, "equipment"), payload.model_dump(), item_id),
    )


@router.delete("/{item_id}")
def delete_equipment(item_id: str, request: Request):
    return store_for(request, "equipment").delete(item_id)
