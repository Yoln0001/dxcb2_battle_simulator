"""Named independent player libraries with atomic snapshot copies."""
import uuid
import math
from copy import deepcopy
from fastapi import APIRouter,Request
from ..skills.store import SkillStore,SkillError,text
KINDS={'holies':('holy_store','holies'),'imprints':('imprint_store','imprints'),'rings':('ring_store','rings'),'contracts':('contract_store','contracts'),'bosses':('boss_store','bosses'),'equipment':('equipment_store','equipment'),'stones':('stone_store','stones'),'people':('people_store','people'),'trophies':('trophy_store','trophies')}
class LibrarySets(SkillStore):
    def read(self):
        import json
        with self.lock:
            if not self.path.exists():return {'schemaVersion':1,'libraries':[]}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(data.get('libraries'),list):raise ValueError()
                return data
            except (ValueError,TypeError):raise SkillError('玩家库索引读取失败，原文件未覆盖',500)
    def get(self,kind,item_id):
        item=next((i for i in self.read()['libraries'] if i['kind']==kind and i['id']==item_id),None)
        if not item:raise SkillError('所选库不存在',404)
        return item

def store_for(request,kind,library_id=None):
    if kind not in KINDS:raise SkillError('库类型无效')
    base=getattr(request.app.state,KINDS[kind][0]);library_id=library_id if library_id is not None else request.query_params.get('library','')
    if not library_id:return base
    request.app.state.library_sets.get(kind,library_id)
    return type(base)(request.app.state.library_sets.path.parent/'player_libraries'/kind/(library_id+'.json'))
def equipment_catalog(request,config=None):
    result=store_for(request,'equipment','').read()['equipment']
    for lib in request.app.state.library_sets.read()['libraries']:
        if lib['kind']=='equipment':result+=store_for(request,'equipment',lib['id']).read()['equipment']
    from .equipment_identity import link_rows
    wiki=request.app.state.wiki_equipment_store.read()['equipment']
    result=link_rows(result,wiki)
    if config is not None:
        selected=link_rows(store_for(request,'equipment',config.get('librarySelections',{}).get('equipment','')).read()['equipment'],wiki)
        result += selected
    return result
def apply_equipment_copy_percentages(rows, percentages):
    if not isinstance(percentages,dict) or set(percentages)-{'main','other','defense'}:
        raise SkillError('装备属性百分比设置无效')
    for value in percentages.values():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=100:
            raise SkillError('装备属性百分比必须为0～100之间的数值')
    for row in rows:
        for attr in ('strength','magic','technique','speed','constitution','weaponPower','armor','resistance'):
            percent=percentages.get('defense' if attr in ('armor','resistance') else 'main' if attr==row.get('mainAttribute') else 'other')
            stat=row.get('baseAttributes',{}).get(attr)
            if percent is None or not isinstance(stat,dict):continue
            low,high=stat.get('min'),stat.get('max')
            if low is None or high is None:continue
            stat['ownedValue']=round(low+(high-low)*percent/100,8)

router=APIRouter(prefix='/api/library-sets')
@router.get('/equipment/catalog')
def catalog(request:Request):return {'schemaVersion':1,'equipment':equipment_catalog(request)}
@router.get('/{kind}')
def read(kind:str,request:Request):
    if kind not in KINDS:raise SkillError('库类型无效')
    data=request.app.state.library_sets.read()
    return {'libraries':[i for i in data['libraries'] if i['kind']==kind], 'displayNames':data.get('displayNames',{}).get(kind,{})}
@router.post('/{kind}',status_code=201)
def create(kind:str,payload:dict,request:Request):
    if kind not in KINDS:raise SkillError('库类型无效')
    registry=request.app.state.library_sets;name=text(payload.get('name'),'库名称')
    with registry.lock:
        data=registry.read()
        if name in data.get('displayNames',{}).get(kind,{}).values() or any(i['kind']==kind and i['name']==name for i in data['libraries']):raise SkillError('库名称已存在',409)
        if len(data['libraries'])>=200:raise SkillError('最多创建200个玩家库')
        item={'id':str(uuid.uuid4()),'kind':kind,'name':name};key=KINDS[kind][1]
        rows=deepcopy(store_for(request,kind,payload.get('copyFrom','')).read()[key]) if payload.get('copy') else []
        if kind=='equipment' and payload.get('copy') and 'attributePercentages' in payload:
            apply_equipment_copy_percentages(rows,payload['attributePercentages'])
        if kind=='equipment':
            from .equipment_identity import link_rows
            rows=link_rows(rows,request.app.state.wiki_equipment_store.read()['equipment'])
        else:
            for row in rows:row['id']=kind+'_'+str(uuid.uuid4())
        base=getattr(request.app.state,KINDS[kind][0]);target=type(base)(registry.path.parent/'player_libraries'/kind/(item['id']+'.json'))
        target._write({'schemaVersion':1,key:rows});data['libraries'].append(item);registry._write(data)
        return {'libraries':[i for i in data['libraries'] if i['kind']==kind],'item':item}

def editable_equipment_store(request,library_id):
    if library_id=='__wiki__':return request.app.state.wiki_equipment_store
    return store_for(request,'equipment','' if library_id=='__default__' else library_id)

def equipment_percentages(rows):
    values={key:[] for key in ('main','other','defense')}
    for row in rows:
        for attr in ('strength','magic','technique','speed','constitution','weaponPower','armor','resistance'):
            stat=row.get('baseAttributes',{}).get(attr,{})
            low,high,owned=stat.get('min'),stat.get('max'),stat.get('ownedValue')
            if low is None or high is None or low==high:continue
            key='defense' if attr in ('armor','resistance') else 'main' if attr==row.get('mainAttribute') else 'other'
            values[key].append(None if owned is None else round((owned-low)/(high-low)*100,6))
    return {key:rows[0] for key,rows in values.items() if rows and rows[0] is not None and 0<=rows[0]<=100 and all(v==rows[0] for v in rows)}

@router.get('/{kind}/{library_id}')
def edit_options(kind:str,library_id:str,request:Request):
    if kind!='equipment':raise SkillError('库类型无效')
    return {'attributePercentages':equipment_percentages(editable_equipment_store(request,library_id).read()['equipment'])}

@router.put('/{kind}/{library_id}')
def rename(kind:str,library_id:str,payload:dict,request:Request):
    if kind not in KINDS:raise SkillError('库类型无效')
    registry=request.app.state.library_sets;name=text(payload.get('name'),'库名称')
    with registry.lock:
        data=registry.read()
        special=library_id in ('__default__','__wiki__')
        if library_id=='__wiki__' and kind!='equipment':raise SkillError('所选库不存在',404)
        if not special:registry.get(kind,library_id)
        names=data.setdefault('displayNames',{}).setdefault(kind,{})
        if any(i['kind']==kind and i['id']!=library_id and i['name']==name for i in data['libraries']) or any(key!=library_id and value==name for key,value in names.items()):raise SkillError('库名称已存在',409)
        if special:names[library_id]=name
        else:next(i for i in data['libraries'] if i['kind']==kind and i['id']==library_id)['name']=name
        if 'attributePercentages' in payload:
            if kind!='equipment':raise SkillError('仅装备库可修改属性百分比')
            store=editable_equipment_store(request,library_id)
            with store.lock:
                original=store.read();updated=deepcopy(original)
                apply_equipment_copy_percentages(updated['equipment'],payload['attributePercentages'])
                store._write(updated)
                try:registry._write(data)
                except Exception:
                    store._write(original)
                    raise
        else:registry._write(data)
        return {'libraries':[i for i in data['libraries'] if i['kind']==kind],'displayNames':names}

@router.delete('/{kind}/{library_id}')
def delete(kind:str,library_id:str,request:Request):
    if kind not in KINDS:raise SkillError('库类型无效')
    registry=request.app.state.library_sets
    with registry.lock:
        registry.get(kind,library_id);data=registry.read()
        data['libraries']=[i for i in data['libraries'] if not (i['kind']==kind and i['id']==library_id)]
        # Remove the registry entry atomically; keep the detached data file for recovery.
        registry._write(data)
        return {'libraries':[i for i in data['libraries'] if i['kind']==kind]}
