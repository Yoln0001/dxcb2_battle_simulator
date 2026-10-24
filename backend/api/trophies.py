from .library_sets import store_for
"""Persistent custom trophy library."""
import json,uuid
from fastapi import APIRouter,Request
from ..skills.store import SkillStore,SkillError,text
from ..configurations.special import KEYS,number

def validate_item(payload,item_id=None):
    if not isinstance(payload,dict):raise SkillError('战利品格式无效')
    name=text(payload.get('name'),'战利品名称')
    attrs=payload.get('attributes',{})
    if not isinstance(attrs,dict) or any(k not in KEYS+('adventureGoldBonus','adventureSoulBonus') for k in attrs):raise SkillError('战利品属性无效')
    result={'id':item_id or str(uuid.uuid4()),'name':name,'attributes':{k:number(v) for k,v in attrs.items()}}
    if 'firstStrike' in payload:
        if type(payload['firstStrike']) is not bool:raise SkillError('先发制人选项无效')
        result['firstStrike']=payload['firstStrike']
    return result

class TrophyStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':1,'trophies':[]}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schemaVersion')!=1 or not isinstance(data.get('trophies'),list):raise ValueError()
                return {'schemaVersion':1,'trophies':[validate_item(i,i['id']) for i in data['trophies']]}
            except (ValueError,KeyError,TypeError) as e:raise SkillError('战利品库读取失败，原文件未覆盖',500) from e
    def save(self,payload,item_id=None):
        item=validate_item(payload,item_id)
        with self.lock:
            data=self.read();items=data['trophies']
            if item_id and not any(i['id']==item_id for i in items):raise SkillError('战利品不存在',404)
            if any(i['name']==item['name'] and i['id']!=item['id'] for i in items):raise SkillError('战利品名称已存在',409)
            if not item_id and len(items)>=5000:raise SkillError('战利品库最多5000条')
            data['trophies']=[i for i in items if i['id']!=item['id']]+[item];self._write(data)
            return {**data,'item':item}
    def delete(self,item_id):
        with self.lock:
            data=self.read()
            if not any(i['id']==item_id for i in data['trophies']):raise SkillError('战利品不存在',404)
            data['trophies']=[i for i in data['trophies'] if i['id']!=item_id];self._write(data);return data
router=APIRouter(prefix='/api/trophies',tags=['战利品库'])
@router.get('')
def read(request:Request):return store_for(request,'trophies').read()
@router.post('',status_code=201)
def create(payload:dict,request:Request):return store_for(request,'trophies').save(payload)
@router.put('/{item_id}')
def update(item_id:str,payload:dict,request:Request):return store_for(request,'trophies').save(payload,item_id)
@router.delete('/{item_id}')
def delete(item_id:str,request:Request):return store_for(request,'trophies').delete(item_id)
