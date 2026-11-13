"""Bounded local TAS sessions. No player library is mutated."""

from threading import RLock
from time import monotonic
from uuid import uuid4
from fastapi import APIRouter, Request
from .equipment_identity import battle_catalog
from ..configurations.special import prepare_configuration
from ..skills.store import SkillError
from engine.runtime.tas import TasSession
from engine.runtime.initialization import BattleConfigurationError

router = APIRouter(prefix="/api/battle/tas", tags=["TAS"])


def registry(request):
    return request.app.state.tas_sessions, request.app.state.tas_lock


@router.post("", summary="创建逐0.1秒交互战斗")
def create(payload: dict, request: Request):
    equipment = {i["id"]: i for i in battle_catalog(request, payload)}
    skills = {i["id"]: i for i in request.app.state.skill_store.read()["skills"]}
    groups = {i["id"]: i for i in request.app.state.group_store.read()["groups"]}
    try:
        config = prepare_configuration(payload, list(equipment.values()))
        session = TasSession(config, equipment, skills, groups)
    except BattleConfigurationError as error:
        raise SkillError(str(error)) from error
    sessions, lock = registry(request)
    with lock:
        now = monotonic()
        for key in list(sessions):
            if now - sessions[key][1] > 3600:
                del sessions[key]
        if len(sessions) >= 16:
            raise SkillError("TAS 会话过多，请先关闭已有战斗", 429)
        identifier = uuid4().hex
        sessions[identifier] = (session, now)
        return {"id": identifier, **session.view()}


@router.post("/{identifier}", summary="推进、施法、切换模式或回溯TAS")
def operate(identifier: str, payload: dict, request: Request):
    sessions, lock = registry(request)
    with lock:
        entry = sessions.get(identifier)
        if not entry or monotonic() - entry[1] > 3600:
            sessions.pop(identifier, None)
            raise SkillError("TAS 会话已过期，请重新开始", 404)
        session = entry[0]
        if payload.get("revision") != session.revision:
            raise SkillError("战斗状态已更新，请使用最新状态重试", 409)
        try:
            result = (
                session.seek(payload.get("tick"))
                if payload.get("kind") == "seek"
                else session.operate(payload)
            )
        except BattleConfigurationError as error:
            raise SkillError(str(error)) from error
        sessions[identifier] = (session, monotonic())
        return {"id": identifier, **result}


@router.delete("/{identifier}", summary="关闭TAS会话")
def close(identifier: str, request: Request):
    sessions, lock = registry(request)
    with lock:
        sessions.pop(identifier, None)
    return {"closed": True}
