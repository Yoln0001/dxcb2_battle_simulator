"""技能接口路由，文件存储交给SkillStore。"""
from fastapi import APIRouter, Request

from ..schemas.skills import SkillPayload, SkillLibraryPayload
from ..skills.store import SkillError

router = APIRouter(prefix='/api/skills', tags=['技能库'])

@router.get('', summary='读取全部技能')
def list_skills(request: Request):
    return request.app.state.skill_store.read()

@router.post('', status_code=201, summary='创建技能')
def create_skill(payload: SkillPayload, request: Request):
    return request.app.state.skill_store.save(payload.model_dump())

@router.post('/import', summary='合并导入技能库')
def import_skills(payload: SkillLibraryPayload, request: Request):
    return request.app.state.skill_store.import_library(payload.model_dump())

@router.get('/{skill_id:path}', summary='读取指定技能')
def get_skill(skill_id: str, request: Request):
    skill = next((s for s in request.app.state.skill_store.read()['skills'] if s['id'] == skill_id), None)
    if skill is None:
        raise SkillError('技能不存在', 404)
    return skill

@router.put('/{skill_id:path}', summary='更新指定技能')
def update_skill(skill_id: str, payload: SkillPayload, request: Request):
    return request.app.state.skill_store.save(payload.model_dump(), skill_id)
