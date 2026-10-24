from .library_sets import store_for
"""Persistent custom trophy library."""
import json,uuid
from fastapi import APIRouter,Request
from ..skills.store import SkillStore,SkillError,text
from ..configurations.special import KEYS,number

TYPES=('暴君之石','古精灵之石','乌鸦之石','猎神者之石','巨龙之石','唯一魔石')
ATTRIBUTES=('strength','magic','technique','speed','constitution','hitRate')
def validate_item(payload,item_id=None):
    if not isinstance(payload,dict):raise SkillError('魔石格式无效')
    name=text(payload.get('name'),'魔石名称');kind=payload.get('kind')
    if kind not in TYPES:raise SkillError('魔石种类无效')
    attrs=payload.get('attributes',{})
    if not isinstance(attrs,dict) or any(k not in ATTRIBUTES for k in attrs):raise SkillError('魔石属性无效')
    return {'id':item_id or str(uuid.uuid4()),'name':name,'kind':kind,'attributes':{k:number(attrs.get(k,0)) for k in ATTRIBUTES}}

class StoneStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':1,'stones':[]}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schemaVersion')!=1 or not isinstance(data.get('stones'),list):raise ValueError()
                return {'schemaVersion':1,'stones':[validate_item(i,i['id']) for i in data['stones']]}
            except (ValueError,KeyError,TypeError) as e:raise SkillError('魔石库读取失败，原文件未覆盖',500) from e
    def save(self,payload,item_id=None):
        item=validate_item(payload,item_id)
        with self.lock:
            data=self.read();items=data['stones']
            if item_id and not any(i['id']==item_id for i in items):raise SkillError('魔石不存在',404)
            if any(i['name']==item['name'] and i['id']!=item['id'] for i in items):raise SkillError('魔石名称已存在',409)
            if not item_id and len(items)>=5000:raise SkillError('魔石库最多5000条')
            data['stones']=[i for i in items if i['id']!=item['id']]+[item];self._write(data)
            return {**data,'item':item}
    def delete(self,item_id):
        with self.lock:
            data=self.read()
            if not any(i['id']==item_id for i in data['stones']):raise SkillError('魔石不存在',404)
            data['stones']=[i for i in data['stones'] if i['id']!=item_id];self._write(data);return data
router=APIRouter(prefix='/api/stones',tags=['魔石库'])
@router.get('')
def read(request:Request):return store_for(request,'stones').read()
@router.post('',status_code=201)
def create(payload:dict,request:Request):return store_for(request,'stones').save(payload)
@router.put('/{item_id}')
def update(item_id:str,payload:dict,request:Request):return store_for(request,'stones').save(payload,item_id)
@router.delete('/{item_id}')
def delete(item_id:str,request:Request):return store_for(request,'stones').delete(item_id)
