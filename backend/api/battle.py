"""战斗接口：开战初始化、单次模拟、批量模拟任务。"""

from contextlib import contextmanager

from fastapi import APIRouter, Request

from .equipment_identity import battle_catalog
from ..skills.store import SkillError
from ..configurations.special import prepare_configuration as prepare_panel
from engine.runtime.initialization import initialize_battle, BattleConfigurationError


def prepare_configuration(payload, library):
    from copy import deepcopy

    payload = deepcopy(payload)
    rows = payload.get("characters", [])
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise BattleConfigurationError("角色配置数量无效")
    if sum(c.get("enabled", True) for c in rows) > 4:
        raise BattleConfigurationError("最多4名角色参战")
    if len(rows) != 4:
        rows = [c for c in rows if c.get("enabled", True)]
        while len(rows) < 4:
            rows.append(
                {
                    "name": "空位",
                    "enabled": False,
                    "firstStrike": False,
                    "stats": {},
                    "equipment": {},
                    "contract": "不激活",
                    "job": "",
                    "skillGroup": "",
                }
            )
        payload["characters"] = rows
    return prepare_panel(payload, library)


def equipment_library(request, payload):
    return {item["id"]: item for item in battle_catalog(request, payload)}


def battle_libraries(request, payload):
    """本次请求可用的装备、技能和技能组，均按ID索引。"""
    equipment = equipment_library(request, payload)
    skills = {item["id"]: item for item in request.app.state.skill_store.read()["skills"]}
    groups = {item["id"]: item for item in request.app.state.group_store.read()["groups"]}
    return equipment, skills, groups


@contextmanager
def configuration_errors(status=400):
    """把引擎的配置错误转成接口错误响应。"""
    try:
        yield
    except BattleConfigurationError as error:
        raise SkillError(str(error), status) from error


def has_boss_attacks(payload):
    """所选Boss设置了技能组时模拟包含Boss攻击，否则Boss只作为受击目标（与TAS的判断一致）。"""
    target = payload.get("target")
    target = target if isinstance(target, dict) else {}
    selected = target.get("selectedBoss")
    selected = selected if isinstance(selected, dict) else {}
    group = selected.get("skillGroup") or target.get("skillGroup")
    return isinstance(group, dict) and bool(group.get("entry") and group.get("subgroups"))


router = APIRouter(prefix="/api/battle", tags=["战斗"])


@router.post("/initialize", summary="计算开战装备增幅并返回角色buff记录")
def initialize(payload: dict, request: Request):
    library = equipment_library(request, payload)
    with configuration_errors():
        payload = prepare_configuration(payload, list(library.values()))
        return initialize_battle(payload, library).to_dict()


# “-with-boss”是合并前的旧路径，保留为别名，行为与新路径完全相同。
@router.post("/simulate-single-with-boss", include_in_schema=False)
@router.post(
    "/simulate-single",
    summary="以0.1秒步进执行单次模拟并返回时间表及状态快照；所选Boss有技能组时包含Boss攻击",
)
def simulate(payload: dict, request: Request):
    equipment, skills, groups = battle_libraries(request, payload)
    with configuration_errors():
        payload = prepare_configuration(payload, list(equipment.values()))
        boss_attacks = has_boss_attacks(payload)
        if boss_attacks:
            # Boss战斗依赖Numba模块，只在需要时导入，普通模拟不受影响。
            from engine.runtime.boss_simulation import BossBattle as battle_class
        else:
            from engine.runtime.simulation import SingleBattle as battle_class
        result = battle_class(payload, equipment, skills, groups, seed=payload.get("seed")).run()
        result["boss_attacks"] = boss_attacks
        return result


@router.post("/simulate-batch-with-boss", include_in_schema=False)
@router.post(
    "/simulate-batch",
    summary="启动批量模拟并返回任务编号；所选Boss有技能组时包含Boss攻击",
)
def start_batch(payload: dict, request: Request):
    equipment, skills, groups = battle_libraries(request, payload)
    with configuration_errors():
        payload = prepare_configuration(payload, list(equipment.values()))
        return request.app.state.batch_jobs.start(
            payload, equipment, skills, groups, boss_attacks=has_boss_attacks(payload)
        )


@router.get("/batch/{job_id}", summary="查看批量模拟进度和统计结果")
def batch_status(job_id: str, request: Request):
    with configuration_errors(404):
        return request.app.state.batch_jobs.get(job_id)


@router.post("/batch/{job_id}/cancel", summary="取消批量模拟")
def cancel_batch(job_id: str, request: Request):
    with configuration_errors(404):
        return request.app.state.batch_jobs.cancel(job_id)
