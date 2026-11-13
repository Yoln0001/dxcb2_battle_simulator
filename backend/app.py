"""FastAPI应用、网页托管和统一错误处理。"""

from pathlib import Path
from threading import RLock

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from .api.battle import router as battle_router
from .api.bosses import BossStore, router as boss_router
from .api.configurations import router as configuration_router
from .api.contracts import router as contract_router
from .api.equipment import router as equipment_router
from .api.holies import HolyStore, router as holy_router
from .api.imprints import ImprintStore, router as imprint_router
from .api.library_sets import LibrarySets, router as library_sets_router
from .api.people import PeopleStore, router as people_router
from .api.rings import router as ring_router
from .api.skill_groups import router as group_router
from .api.skills import router as skill_router
from .api.stones import StoneStore, router as stone_router
from .api.tas import router as tas_router
from .api.trophies import TrophyStore, router as trophy_router
from .api.unclassified_equipment import router as unclassified_router
from .api.wiki_equipment import router as wiki_router
from .batch_jobs import BatchJobs
from .configurations.store import ConfigurationStore
from .contracts.store import ContractStore
from .equipment.store import EquipmentStore
from .rings.store import RingStore
from .skill_groups.store import SkillGroupStore
from .skills.store import SkillError, SkillStore
from .unclassified_equipment.store import UnclassifiedEquipmentStore
from .wiki_equipment.store import WikiEquipmentStore

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MAX_BODY = 5 * 1024 * 1024

# 路由按此顺序注册；FastAPI按注册顺序匹配，调整前请确认路径没有重叠。
ROUTERS = (
    tas_router,
    boss_router,
    contract_router,
    ring_router,
    holy_router,
    imprint_router,
    library_sets_router,
    stone_router,
    people_router,
    trophy_router,
    wiki_router,
    unclassified_router,
    configuration_router,
    skill_router,
    equipment_router,
    group_router,
    battle_router,
)


def create_stores(
    state,
    data_file=None,
    equipment_file=None,
    group_file=None,
    configuration_file=None,
    unclassified_equipment_file=None,
    wiki_equipment_file=None,
    trophy_file=None,
    people_file=None,
    stone_file=None,
    boss_file=None,
):
    """建立各数据库；未指定路径的库使用data目录下的默认文件。"""
    state.skill_store = SkillStore(data_file or DATA / "skills.json")
    state.equipment_store = EquipmentStore(equipment_file or DATA / "equipment.json")
    state.group_store = SkillGroupStore(group_file or DATA / "skill_groups.json")
    state.group_store.skill_store = state.skill_store
    state.configuration_store = ConfigurationStore(
        configuration_file or DATA / "configurations.json"
    )
    state.unclassified_equipment_store = UnclassifiedEquipmentStore(
        unclassified_equipment_file or DATA / "unclassified_equipment.json"
    )
    state.wiki_equipment_store = WikiEquipmentStore(
        wiki_equipment_file or DATA / "wiki_equipment.json"
    )
    state.trophy_store = TrophyStore(trophy_file or DATA / "trophies.json")
    state.people_store = PeopleStore(people_file or DATA / "people.json")
    state.stone_store = StoneStore(stone_file or DATA / "stones.json")
    # 以下各库与配置库放在同一目录，测试只需替换配置文件路径即可整体隔离。
    folder = state.configuration_store.path.parent
    state.boss_store = BossStore(boss_file or folder / "bosses.json")
    state.contract_store = ContractStore(folder / "contracts.json")
    state.ring_store = RingStore(folder / "rings.json")
    state.holy_store = HolyStore(folder / "holies.json")
    state.imprint_store = ImprintStore(folder / "imprints.json")
    state.library_sets = LibrarySets(folder / "library_sets.json")


def create_app(
    data_file=None,
    equipment_file=None,
    group_file=None,
    configuration_file=None,
    unclassified_equipment_file=None,
    wiki_equipment_file=None,
    trophy_file=None,
    people_file=None,
    stone_file=None,
    boss_file=None,
):
    app = FastAPI(title="地下城堡2模拟器接口", version="1.0.0")
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.state.batch_jobs = BatchJobs()
    app.state.tas_sessions = {}
    app.state.tas_lock = RLock()
    create_stores(
        app.state,
        data_file,
        equipment_file,
        group_file,
        configuration_file,
        unclassified_equipment_file,
        wiki_equipment_file,
        trophy_file,
        people_file,
        stone_file,
        boss_file,
    )

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        if request.url.hostname not in {"127.0.0.1", "localhost"}:
            return JSONResponse({"error": "此接口仅供本机访问"}, status_code=403)
        origin = request.headers.get("origin")
        port = request.url.port or 80
        if origin and origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
            return JSONResponse({"error": "不允许跨站访问接口"}, status_code=403)
        if request.url.path.startswith("/api/") and request.method in {"POST", "PUT"}:
            if (
                request.headers.get("content-type", "").split(";")[0].strip().lower()
                != "application/json"
            ):
                return JSONResponse({"error": "请使用application/json"}, status_code=415)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"error": "请求长度无效"}, status_code=400)
            if length > MAX_BODY:
                return JSONResponse({"error": "请求超过5MB"}, status_code=413)
            body = await request.body()
            if not 0 < len(body) <= MAX_BODY:
                return JSONResponse({"error": "请求不能为空或超过5MB"}, status_code=413)
        response = await call_next(request)
        # Development pages and assets must refresh immediately after edits.
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if request.url.path.startswith(("/js/", "/css/")) and request.query_params.get("v")
            else "no-store"
        )
        return response

    @app.exception_handler(SkillError)
    async def skill_error(request, error):
        return JSONResponse({"error": str(error)}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = error.errors()
        message = details[0]["msg"] if details else "请求数据无效"
        return JSONResponse({"error": message}, status_code=400)

    @app.exception_handler(OSError)
    async def file_error(request, error):
        return JSONResponse({"error": "文件读写失败，请检查目录权限和磁盘空间"}, status_code=500)

    for router in ROUTERS:
        app.include_router(router)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT"], include_in_schema=False)
    def unknown_api(path):
        return JSONResponse({"error": "接口不存在"}, status_code=404)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "frontend" / "index.html")

    app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
    return app
