from .library_sets import store_for
from .equipment_identity import battle_catalog
from fastapi import APIRouter, Request
from ..configurations.special import prepare_configuration
from ..configurations.store import validate_config
from ..skills.store import SkillError
from copy import deepcopy


def calculated_payload(payload, request):
    payload = dict(payload)
    config = validate_config(payload.get("configuration"))
    for kind, library_id in config.get("librarySelections", {}).items():
        store_for(request, kind, library_id)
    payload["configuration"] = prepare_configuration(
        config,
        battle_catalog(request, config) if config.get("configurationType") == "special" else [],
        allow_incomplete=True,
    )
    return payload


router = APIRouter(prefix="/api/configurations", tags=["配置库"])


@router.get("")
def list_configurations(request: Request):
    return request.app.state.configuration_store.read()


@router.post("", status_code=201)
def create_configuration(payload: dict, request: Request):
    return request.app.state.configuration_store.save(calculated_payload(payload, request))


@router.post("/libraries", status_code=201)
def create_library(payload: dict, request: Request):
    return request.app.state.configuration_store.save_library(payload)


@router.put("/libraries/{library_id}")
def rename_library(library_id: str, payload: dict, request: Request):
    return request.app.state.configuration_store.save_library(payload, library_id)


@router.delete("/libraries/{library_id}")
def delete_library(library_id: str, request: Request):
    return request.app.state.configuration_store.delete_library(library_id)


@router.put("/{item_id}/name")
def rename_configuration(item_id: str, payload: dict, request: Request):
    return request.app.state.configuration_store.rename(item_id, payload)


@router.put("/{item_id}")
def update_configuration(item_id: str, payload: dict, request: Request):
    return request.app.state.configuration_store.save(calculated_payload(payload, request), item_id)


@router.post("/{item_id}/activate")
def activate_configuration(item_id: str, payload: dict, request: Request):
    return request.app.state.configuration_store.activate(item_id)


@router.delete("/{item_id}")
def delete_configuration(item_id: str, request: Request):
    return request.app.state.configuration_store.delete(item_id)


@router.post("/{item_id}/copy-regular", status_code=201)
def copy_regular(item_id: str, payload: dict, request: Request):
    store = request.app.state.configuration_store
    source = next((i for i in store.read()["configurations"] if i["id"] == item_id), None)
    if source is None:
        raise SkillError("配置不存在", 404)
    if source["configuration"].get("configurationType") != "special":
        raise SkillError("请选择特殊配置")
    config = deepcopy(source["configuration"])
    config = prepare_configuration(config, battle_catalog(request, config))
    config["configurationType"] = "regular"
    for character in config["characters"]:
        sources = character.pop("specialSources", {})
        character["ringPanelIncluded"] = bool(character.get("selectedRing"))
        character["ringBattleMultipliers"] = deepcopy(sources.get("ringBattleMultipliers", {}))
        character["ringPanelBonuses"] = deepcopy(sources.get("ringPanelBonuses", {}))
        character.pop("panelCalculationError", None)
        # Wearing bonuses are already baked into the editable panel. Preserve active
        # contract mechanics through its explicit name, negative and multiplier.
        character["selectedContract"] = None
    return store.save(
        {
            "name": payload.get("name", source["name"] + "（常规）"),
            "configuration": validate_config(config),
            "libraryId": payload.get("libraryId", "default_regular"),
            "activate": False,
        }
    )
