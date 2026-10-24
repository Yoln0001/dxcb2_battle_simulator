from .library_sets import store_for
"""Persistent custom trophy library."""
import json,uuid
from fastapi import APIRouter,Request
from ..skills.store import SkillStore,SkillError,text
from ..configurations.special import KEYS,number

ATTRIBUTES=('strength','magic','technique','speed','constitution','armor','resistance')
def validate_item(payload,item_id=None):
    if not isinstance(payload,dict):raise SkillError('人物格式无效')
    name=text(payload.get('name'),'人物名称');job=text(payload.get('job'),'职业')
    from ..equipment.jobs import normalize_weapon_job
    normalize_weapon_job(job)
    attrs=payload.get('attributes',{})
    if not isinstance(attrs,dict) or any(k not in ATTRIBUTES for k in attrs):raise SkillError('人物属性无效')
    return {'id':item_id or str(uuid.uuid4()),'name':name,'job':job,'attributes':{k:number(attrs.get(k,0)) for k in ATTRIBUTES}}

class PeopleStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':1,'people':[]}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schemaVersion')!=1 or not isinstance(data.get('people'),list):raise ValueError()
                return {'schemaVersion':1,'people':[validate_item(i,i['id']) for i in data['people']]}
            except (ValueError,KeyError,TypeError) as e:raise SkillError('人物库读取失败，原文件未覆盖',500) from e
    def save(self,payload,item_id=None):
        item=validate_item(payload,item_id)
        with self.lock:
            data=self.read();items=data['people']
            if item_id and not any(i['id']==item_id for i in items):raise SkillError('人物不存在',404)
            if any(i['name']==item['name'] and i['id']!=item['id'] for i in items):raise SkillError('人物名称已存在',409)
            if not item_id and len(items)>=5000:raise SkillError('人物库最多5000条')
            data['people']=[i for i in items if i['id']!=item['id']]+[item];self._write(data)
            return {**data,'item':item}
    def delete(self,item_id):
        with self.lock:
            data=self.read()
            if not any(i['id']==item_id for i in data['people']):raise SkillError('人物不存在',404)
            data['people']=[i for i in data['people'] if i['id']!=item_id];self._write(data);return data
router=APIRouter(prefix='/api/people',tags=['人物库'])
@router.get('')
def read(request:Request):return store_for(request,'people').read()
@router.post('',status_code=201)
def create(payload:dict,request:Request):return store_for(request,'people').save(payload)
@router.put('/{item_id}')
def update(item_id:str,payload:dict,request:Request):return store_for(request,'people').save(payload,item_id)
@router.delete('/{item_id}')
def delete(item_id:str,request:Request):return store_for(request,'people').delete(item_id)
