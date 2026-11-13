"""各条目库共用的增删改查路由；按请求中的library参数选择默认库或玩家库。"""
from fastapi import APIRouter, Request

from .library_sets import store_for


def library_router(kind, tag=None):
    router = APIRouter(prefix='/api/' + kind, tags=[tag] if tag else None)

    @router.get('')
    def read(request: Request):
        return store_for(request, kind).read()

    @router.post('', status_code=201)
    def create(payload: dict, request: Request):
        return store_for(request, kind).save(payload)

    @router.put('/{item_id}')
    def update(item_id: str, payload: dict, request: Request):
        return store_for(request, kind).save(payload, item_id)

    @router.delete('/{item_id}')
    def delete(item_id: str, request: Request):
        return store_for(request, kind).delete(item_id)

    return router
