"""Sync equipment definitions across existing same-name records, preserving personal rolls."""
from copy import deepcopy
from contextlib import ExitStack
from .library_sets import store_for
from ..equipment.validation import validate_equipment
from ..wiki_equipment.store import WikiEquipmentStore,validate_item,progress
from ..skills.store import SkillError

def definition(item):
    value=deepcopy(item);value.pop('id',None);value.pop('wikiId',None)
    for stat in value.get('baseAttributes',{}).values():stat.pop('ownedValue',None)
    return value

def merged_definition(item,previous):
    value=deepcopy(item);value['id']=previous['id']
    for stat in value.get('baseAttributes',{}).values():stat.pop('ownedValue',None)
    for key,stat in previous.get('baseAttributes',{}).items():
        if 'ownedValue' in stat:
            value.setdefault('baseAttributes',{}).setdefault(key,deepcopy(stat))['ownedValue']=stat['ownedValue']
    return value

def save_synced(request,source,value,update_id=None):
    registry=request.app.state.library_sets
    with registry.lock,ExitStack() as locks:
        stores=[source,request.app.state.equipment_store,request.app.state.wiki_equipment_store]
        stores += [store_for(request,'equipment',lib['id']) for lib in registry.read()['libraries'] if lib['kind']=='equipment']
        stores=list({str(store.path.resolve()):store for store in stores}.values())
        source=next(store for store in stores if store.path.resolve()==source.path.resolve())
        for store in sorted(stores,key=lambda s:str(s.path.resolve())):locks.enter_context(store.lock)
        current=source.read()
        previous=next((row for row in current['equipment'] if row['id']==update_id),None) if update_id else None
        if update_id and previous is None:raise SkillError('装备不存在',404)
        validator=validate_item if isinstance(source,WikiEquipmentStore) else validate_equipment
        item=validator(value,update_id is None)
        from .equipment_identity import link_rows,identity_resolver
        wiki=request.app.state.wiki_equipment_store.read()['equipment']
        item=link_rows([{**item,**({'wikiId':previous['wikiId']} if previous and previous.get('wikiId') else {})}],wiki)[0]
        if update_id and item['id']!=update_id:raise SkillError('路径ID与装备ID不一致')
        if not update_id and any(row['id']==item['id'] for row in current['equipment']):raise SkillError('装备ID已存在，请使用更新接口',409)
        resolve=identity_resolver(wiki)
        shared_changed=previous is None or definition(previous)!=definition(item)
        plans=[];synced=0
        for store in stores:
            data=current if store is source else (store.read() if shared_changed else None)
            if data is None:continue
            changed=False
            if store is source:
                if previous:data['equipment']=[item if row['id']==update_id else row for row in data['equipment']]
                else:
                    if len(data['equipment'])>=5000:raise SkillError('装备库最多5000条')
                    data['equipment'].append(item)
                changed=True
            elif shared_changed:
                for i,row in enumerate(data['equipment']):
                    if resolve(row)==item['wikiId']:
                        candidate=merged_definition(item,row)
                        data['equipment'][i]=(validate_item if isinstance(store,WikiEquipmentStore) else validate_equipment)(candidate)
                        changed=True;synced+=1
            if changed:
                if isinstance(store,WikiEquipmentStore):data['progress']=progress(data['equipment'])
                plans.append((store,data))
        master=request.app.state.wiki_equipment_store
        if not any(row['id']==item['wikiId'] for row in wiki) and source is not master:
            master_data=next((data for store,data in plans if store.path.resolve()==master.path.resolve()),deepcopy(master.read()))
            master_item=deepcopy(item);master_item['id']=item['wikiId']
            for key,stat in master_item.get('baseAttributes',{}).items():
                stat.pop('ownedValue',None);stat.setdefault('label',key)
            master_data['equipment'].append(validate_item(master_item));master_data['progress']=progress(master_data['equipment'])
            plans=[(store,data) for store,data in plans if store.path.resolve()!=master.path.resolve()]+[(master,master_data)]
        # Validate every affected library before any file is replaced.
        originals={str(store.path):store.path.read_bytes() if store.path.exists() else None for store,_ in plans}
        written=[]
        try:
            for store,data in plans:store._write(data);written.append(store)
        except Exception:
            import json
            for store in reversed(written):
                original=originals[str(store.path)]
                if original is None:store.path.unlink(missing_ok=True)
                else:store._write(json.loads(original))
            raise
        return {**next(data for store,data in plans if store is source),'item':item,'syncedEquipmentCount':synced}
