"""Persistent custom trophy library."""
import json,uuid
from .library_routes import library_router
from ..library_store import LibraryStore
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

class TrophyStore(LibraryStore):
    key='trophies';label='战利品';validate=staticmethod(validate_item)

router=library_router('trophies','战利品库')
