"""FastAPI应用、网页托管和统一错误处理。"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from .api.skills import router
from .api.equipment import router as equipment_router
from .equipment.store import EquipmentStore
from .skill_groups.store import SkillGroupStore
from .api.skill_groups import router as group_router
from .api.battle import router as battle_router
from .skills.store import SkillError, SkillStore

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 5 * 1024 * 1024

def create_app(data_file=None, equipment_file=None, group_file=None, configuration_file=None, unclassified_equipment_file=None, wiki_equipment_file=None, trophy_file=None, people_file=None, stone_file=None, boss_file=None):
    app = FastAPI(title='地下城堡2模拟器接口', version='1.0.0')
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    from .batch_jobs import BatchJobs
    app.state.batch_jobs = BatchJobs()
    from threading import RLock
    from .api.tas import router as tas_router
    app.state.tas_sessions = {}
    app.state.tas_lock = RLock()
    app.include_router(tas_router)
    app.state.skill_store = SkillStore(data_file or ROOT / 'data' / 'skills.json')
    app.state.equipment_store = EquipmentStore(equipment_file or ROOT / 'data' / 'equipment.json')

    app.state.group_store = SkillGroupStore(group_file or ROOT / 'data' / 'skill_groups.json')
    app.state.group_store.skill_store = app.state.skill_store

    @app.middleware('http')
    async def local_requests(request: Request, call_next):
        if request.url.hostname not in {'127.0.0.1', 'localhost'}:
            return JSONResponse({'error': '此接口仅供本机访问'}, status_code=403)
        origin = request.headers.get('origin')
        port = request.url.port or 80
        if origin and origin not in {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}:
            return JSONResponse({'error': '不允许跨站访问接口'}, status_code=403)
        if request.url.path.startswith('/api/') and request.method in {'POST', 'PUT'}:
            if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                return JSONResponse({'error': '请使用application/json'}, status_code=415)
            try:
                length = int(request.headers.get('content-length', '0'))
            except ValueError:
                return JSONResponse({'error': '请求长度无效'}, status_code=400)
            if length > MAX_BODY:
                return JSONResponse({'error': '请求超过5MB'}, status_code=413)
            body = await request.body()
            if not 0 < len(body) <= MAX_BODY:
                return JSONResponse({'error': '请求不能为空或超过5MB'}, status_code=413)
        response = await call_next(request)
        # Development pages and assets must refresh immediately after edits.
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable' if request.url.path.startswith(('/js/','/css/')) and request.query_params.get('v') else 'no-store'
        return response

    @app.exception_handler(SkillError)
    async def skill_error(request, error):
        return JSONResponse({'error': str(error)}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        details = error.errors()
        message = details[0]['msg'] if details else '请求数据无效'
        return JSONResponse({'error': message}, status_code=400)

    @app.exception_handler(OSError)
    async def file_error(request, error):
        return JSONResponse({'error': '文件读写失败，请检查目录权限和磁盘空间'}, status_code=500)

    from .configurations.store import ConfigurationStore
    from .api.configurations import router as configuration_router
    app.state.configuration_store=ConfigurationStore(configuration_file or ROOT / "data" / "configurations.json")
    from .unclassified_equipment.store import UnclassifiedEquipmentStore
    from .api.unclassified_equipment import router as unclassified_router
    app.state.unclassified_equipment_store=UnclassifiedEquipmentStore(unclassified_equipment_file or ROOT / "data" / "unclassified_equipment.json")
    from .wiki_equipment.store import WikiEquipmentStore
    from .api.wiki_equipment import router as wiki_router
    app.state.wiki_equipment_store=WikiEquipmentStore(wiki_equipment_file or ROOT / "data" / "wiki_equipment.json")
    from .api.trophies import TrophyStore,router as trophy_router
    app.state.trophy_store=TrophyStore(trophy_file or ROOT / "data" / "trophies.json")
    from .api.people import PeopleStore,router as people_router
    app.state.people_store=PeopleStore(people_file or ROOT / "data" / "people.json")
    from .api.stones import StoneStore,router as stone_router
    app.state.stone_store=StoneStore(stone_file or ROOT / "data" / "stones.json")
    from .api.bosses import BossStore,router as boss_router
    app.state.boss_store=BossStore(boss_file or app.state.configuration_store.path.parent / "bosses.json")
    app.include_router(boss_router)
    from .contracts.store import ContractStore
    from .api.contracts import router as contract_router
    app.state.contract_store=ContractStore(app.state.configuration_store.path.parent / "contracts.json")
    app.include_router(contract_router)
    from .rings.store import RingStore
    from .api.rings import router as ring_router
    app.state.ring_store=RingStore(app.state.configuration_store.path.parent / "rings.json")
    app.include_router(ring_router)
    from .api.holies import HolyStore,router as holy_router
    from .api.imprints import ImprintStore,router as imprint_router
    app.state.holy_store=HolyStore(app.state.configuration_store.path.parent / 'holies.json')
    app.state.imprint_store=ImprintStore(app.state.configuration_store.path.parent / 'imprints.json')
    app.include_router(holy_router)
    app.include_router(imprint_router)
    from .api.library_sets import LibrarySets,router as library_sets_router
    app.state.library_sets=LibrarySets(app.state.configuration_store.path.parent / "library_sets.json")
    app.include_router(library_sets_router)
    app.include_router(stone_router)
    app.include_router(people_router)
    app.include_router(trophy_router)
    app.include_router(wiki_router)
    app.include_router(unclassified_router)
    app.include_router(configuration_router)
    app.include_router(router)
    app.include_router(equipment_router)
    app.include_router(group_router)
    app.include_router(battle_router)

    @app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT'], include_in_schema=False)
    def unknown_api(path):
        return JSONResponse({'error': '接口不存在'}, status_code=404)

    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(ROOT / 'frontend' / 'index.html')

    app.mount('/', StaticFiles(directory=ROOT / 'frontend', html=True), name='frontend')
    return app
