from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/unclassified-equipment", tags=["未分类装备库"])


@router.get("")
def list_equipment(request: Request):
    return request.app.state.unclassified_equipment_store.read()


@router.post("/refresh")
def refresh_equipment(payload: dict, request: Request):
    return request.app.state.unclassified_equipment_store.refresh()
