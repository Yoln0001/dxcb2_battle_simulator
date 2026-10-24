"""Stable encyclopedia identity, separate from a library record and personal rolls."""
from copy import deepcopy


def identity_resolver(wiki):
    by_id={row['id']:row for row in wiki}
    sources={'id':{},'url':{}};names={}
    def add(index,key,item):
        if key in index:index[key]=None
        else:index[key]=item
    for item in wiki:
        for key,index in sources.items():
            value=item.get('source',{}).get(key)
            if value:add(index,value,item)
        add(names,(item['name'].strip(),item['category'],item.get('weaponJob','')),item)
    def resolve(row):
        match=by_id.get(row.get('wikiId')) or by_id.get(row['id'])
        if match is None:
            for key,index in sources.items():
                match=index.get(row.get('source',{}).get(key))
                if match:break
        if match is None:match=names.get((row['name'].strip(),row['category'],row.get('weaponJob','')))
        return match['id'] if match else row.get('wikiId') or row['id']
    return resolve


def link_rows(rows, wiki):
    resolve=identity_resolver(wiki)
    result=[]
    for original in rows:
        row=deepcopy(original);row['wikiId']=resolve(original);result.append(row)
    return result


def identity_catalog(request):
    """Include retained old files only to translate legacy wearing IDs, never their rolls."""
    from .library_sets import equipment_catalog
    from ..equipment.store import EquipmentStore
    rows=equipment_catalog(request)
    registry=request.app.state.library_sets
    known={item['id'] for item in registry.read()['libraries'] if item['kind']=='equipment'}
    wiki=request.app.state.wiki_equipment_store.read()['equipment']
    for path in (registry.path.parent/'player_libraries'/'equipment').glob('*.json'):
        if path.stem in known:continue
        try:rows+=link_rows(EquipmentStore(path).read()['equipment'],wiki)
        except ValueError:continue
    return rows


def library_view(request, canonical=False):
    from .library_sets import store_for, equipment_catalog
    rows = link_rows(store_for(request, 'equipment').read()['equipment'], request.app.state.wiki_equipment_store.read()['equipment'])
    aliases = {}
    for item in identity_catalog(request):
        aliases.setdefault(item['wikiId'], set()).add(item['id'])
    for row in rows:
        row['identityAliases'] = sorted(aliases.get(row['wikiId'], set()) | {row['id'], row['wikiId']})
    if canonical:
        for row in rows:
            row['libraryRecordId']=row['id'];row['id']=row['wikiId']
    return {'schemaVersion': 1, 'equipment': rows}


def battle_catalog(request,config):
    from .library_sets import store_for
    wiki=request.app.state.wiki_equipment_store.read()['equipment']
    selected=link_rows(store_for(request,'equipment',config.get('librarySelections',{}).get('equipment','')).read()['equipment'],wiki)
    by_identity={row['wikiId']:row for row in selected}
    result={}
    for old in identity_catalog(request):
        row=by_identity.get(old['wikiId'])
        if row:result[old['id']]={**deepcopy(row),'id':old['id']}
    for row in selected:result[row['wikiId']]={**deepcopy(row),'libraryRecordId':row['id'],'id':row['wikiId']}
    return list(result.values())
