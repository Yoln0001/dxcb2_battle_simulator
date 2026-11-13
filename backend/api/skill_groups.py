from fastapi import APIRouter, Request
from ..skills.store import SkillError

router = APIRouter(prefix="/api/skill-groups", tags=["技能组库"])


@router.get("")
def list_groups(request: Request):
    return request.app.state.group_store.read()


@router.post("", status_code=201)
def create_group(payload: dict, request: Request):
    return request.app.state.group_store.save(payload)


@router.put("/{item_id}")
def update_group(item_id: str, payload: dict, request: Request):
    return request.app.state.group_store.save(payload, item_id)


@router.delete("/{item_id}")
def delete_group(item_id: str, request: Request):
    return request.app.state.group_store.delete(item_id)
