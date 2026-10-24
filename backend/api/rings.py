from fastapi import APIRouter,Request
from .library_sets import store_for
from ..rings.store import validate_item
from ..skills.store import SkillError
router=APIRouter(prefix='/api/rings')
@router.get('')
def read(request:Request):return store_for(request,'rings').read()
@router.post('',status_code=201)
def create(payload:dict,request:Request):return save(payload,request)
@router.put('/{item_id}')
def update(item_id:str,payload:dict,request:Request):return save(payload,request,item_id)
def save(payload,request,item_id=None):
    store=store_for(request,'rings');item=validate_item(payload,item_id)
    with store.lock:
        data=store.read();index=next((n for n,i in enumerate(data['rings']) if i['id']==item['id']),None)
        if item_id and index is None:raise SkillError('域之环不存在',404)
        if not item_id and index is not None:raise SkillError('域之环ID已存在',409)
        if index is None:data['rings'].append(item)
        else:data['rings'][index]=item
        store._write(data);return {**data,'item':item}
@router.delete('/{item_id}')
def delete(item_id:str,request:Request):
    store=store_for(request,'rings')
    with store.lock:
        data=store.read();rows=[i for i in data['rings'] if i['id']!=item_id]
        if len(rows)==len(data['rings']):raise SkillError('域之环不存在',404)
        data['rings']=rows;store._write(data);return data
