from .library_sets import store_for
"""Persistent custom trophy library."""
import json,uuid
from fastapi import APIRouter,Request
from ..skills.store import SkillStore,SkillError,text
from ..configurations.special import KEYS,number

from ..configurations.special import HOLY,IMPRINT,imprint_for
from ..equipment.jobs import JOB_FAMILIES
TYPES=tuple(HOLY)
ATTRIBUTES=('strength', 'magic', 'technique', 'speed', 'constitution')
# The supplied holy table has separate minor/major columns (level 60 is 82/162).
HOLY_LEVELS={20:(10,20),30:(21,42),40:(36,72),50:(55,110),60:(82,162),70:(115,230),80:(158,316),90:(214,428),100:(280,560)}
HOLY_WEIGHTS={
    '战士':{'strength':1,'technique':1,'speed':1,'constitution':2},
    '野蛮人':{'strength':2,'speed':2,'constitution':1},
    '火枪手':{'strength':1,'technique':2,'speed':1,'constitution':1},
    '潜行者':{'technique':2,'speed':2,'constitution':1},
    '法师':{'magic':2,'technique':2,'constitution':1},
    '圣职':{'magic':2,'technique':1,'constitution':2},
}
# Each entry is one level in the repeating 30-level solar obelisk cycle.
OBELISK_CYCLE=[
 ('圣职','technique',20),('法师','magic',30),('野蛮人','strength',30),('战士','constitution',20),('潜行者','technique',30),('火枪手','technique',30),
 ('圣职','magic',30),('法师','technique',30),('野蛮人','technique',20),('战士','strength',30),('潜行者','speed',30),('火枪手','strength',30),
 ('圣职','technique',20),('法师','magic',20),('野蛮人','strength',20),('战士','constitution',20),('潜行者','strength',20),('火枪手','constitution',20),
 ('圣职','magic',20),('法师','constitution',20),('野蛮人','constitution',20),('战士','technique',30),('潜行者','technique',20),('火枪手','technique',20),
 ('圣职','constitution',30),('法师','technique',20),('野蛮人','speed',30),('战士','speed',20),('潜行者','constitution',20),('火枪手','speed',20),
]

def level_attributes(kind,holy_level,obelisk_level):
    if type(holy_level) is not int or holy_level not in HOLY_LEVELS:raise SkillError('圣迹等级请选择表中的20至100级档位')
    if type(obelisk_level) is not int or obelisk_level<0:raise SkillError('日冕尖碑等级必须为非负整数')
    minor,major=HOLY_LEVELS[holy_level]
    holy={k:(minor if HOLY_WEIGHTS[kind].get(k)==1 else major if HOLY_WEIGHTS[kind].get(k)==2 else 0) for k in ATTRIBUTES}
    obelisk=dict.fromkeys(ATTRIBUTES,0);cycles,remainder=divmod(obelisk_level,30)
    for index,(family,key,value) in enumerate(OBELISK_CYCLE):
        if family==kind:obelisk[key]+=value*(cycles+(index<remainder))
    return {'holy':holy,'obelisk':obelisk,'total':{k:holy[k]+obelisk[k] for k in ATTRIBUTES}}

def presets():
    return [dict(id='holy_'+str(i),name=job+'圣迹',kind=job,holyLevel=100,obeliskLevel=600,attributes=level_attributes(job,100,600)['total']) for i,job in enumerate(HOLY)]

def validate_item(payload,item_id=None):
    if not isinstance(payload,dict):raise SkillError('圣迹格式无效')
    name=text(payload.get('name'),'圣迹名称');kind=payload.get('kind')
    if kind not in TYPES:raise SkillError('圣迹种类无效')
    attrs=payload.get('attributes',{})
    if not isinstance(attrs,dict) or any(k not in ATTRIBUTES for k in attrs):raise SkillError('圣迹属性无效')
    result={'id':item_id or str(uuid.uuid4()),'name':name,'kind':kind,'attributes':{k:number(attrs.get(k,0)) for k in ATTRIBUTES}}
    if 'holyLevel' in payload or 'obeliskLevel' in payload:
        levels=level_attributes(kind,payload.get('holyLevel'),payload.get('obeliskLevel'))
        result.update(holyLevel=payload['holyLevel'],obeliskLevel=payload['obeliskLevel'],attributes=levels['total'])
    elif result['attributes']==level_attributes(kind,100,600)['total']:
        result.update(holyLevel=100,obeliskLevel=600)
    return result

class HolyStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':1,'holies':presets()}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schemaVersion')!=1 or not isinstance(data.get('holies'),list):raise ValueError()
                rows=[validate_item(i,i['id']) for i in data['holies']]
                fixed=[];extras=list(data.get('legacyHolies',[]))
                for default in presets():
                    matching=[i for i in rows if i['kind']==default['kind']]
                    item=matching[0] if matching else default
                    fixed.append({**item,'name':default['name']});extras.extend(matching[1:])
                result={'schemaVersion':1,'holies':fixed}
                if extras:result['legacyHolies']=extras
                return result
            except (ValueError,KeyError,TypeError) as e:raise SkillError('圣迹库读取失败，原文件未覆盖',500) from e
    def save(self,payload,item_id=None):
        if not item_id:raise SkillError('圣迹固定为每大类职业一种，不可新增',405)
        if 'holyLevel' not in payload or 'obeliskLevel' not in payload:raise SkillError('请填写圣迹等级和日冕尖碑等级')
        item=validate_item(payload,item_id)
        with self.lock:
            data=self.read();original=next((i for i in data['holies'] if i['id']==item_id),None)
            if not original:raise SkillError('圣迹不存在',404)
            if item['kind']!=original['kind'] or item['name']!=original['name']:raise SkillError('圣迹名称和职业固定，只能修改等级')
            data['holies']=[item if i['id']==item_id else i for i in data['holies']];self._write(data)
            return {**data,'item':item}
    def delete(self,item_id):
        raise SkillError('圣迹固定为每大类职业一种，不可删除',405)
router=APIRouter(prefix='/api/holies',tags=['圣迹库'])
@router.get('')
def read(request:Request):return store_for(request,'holies').read()
@router.post('',status_code=201)
def create(payload:dict,request:Request):return store_for(request,'holies').save(payload)
@router.put('/{item_id}')
def update(item_id:str,payload:dict,request:Request):return store_for(request,'holies').save(payload,item_id)
@router.delete('/{item_id}')
def delete(item_id:str,request:Request):return store_for(request,'holies').delete(item_id)
