"""Fixed imprint library: preset entries, attribute values editable."""
import json,uuid
from .library_routes import library_router
from ..skills.store import SkillStore,SkillError,text
from ..configurations.special import KEYS,number

from ..configurations.special import HOLY,IMPRINT,imprint_for
from ..equipment.jobs import JOB_FAMILIES
TYPES=tuple(HOLY)
ATTRIBUTES=('finalPhysicalDamage', 'finalMagicDamage', 'finalDotDamage', 'finalHealingBonus', 'hitRate', 'criticalRate', 'abnormalBonus')
def presets():
    rows=[]
    for i,(job,family) in enumerate({**{k:k for k in HOLY},**JOB_FAMILIES}.items()):
        if family not in HOLY:continue
        base=job==family
        values=imprint_for(family,job)
        if not base:values={k:values[k]-imprint_for(family,family)[k] for k in ATTRIBUTES}
        rows.append(dict(id='imprint_'+str(i),name=job+('辉印' if base else '额外辉印'),kind=family,scope='base' if base else 'extra',job=job,attributes=values))
    return rows

def validate_item(payload,item_id=None):
    if not isinstance(payload,dict):raise SkillError('辉印格式无效')
    name=text(payload.get('name'),'辉印名称');kind=payload.get('kind')
    if kind not in TYPES:raise SkillError('辉印种类无效')
    attrs=payload.get('attributes',{})
    if not isinstance(attrs,dict) or any(k not in ATTRIBUTES for k in attrs):raise SkillError('辉印属性无效')
    result={'id':item_id or str(uuid.uuid4()),'name':name,'kind':kind,'attributes':{k:number(attrs.get(k,0)) for k in ATTRIBUTES}}
    if payload.get('scope') in ('base','extra'):result.update(scope=payload['scope'],job=text(payload.get('job'),'辉印职业'))
    return result

class ImprintStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':2,'imprints':presets()}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schemaVersion') not in (1,2) or not isinstance(data.get('imprints'),list):raise ValueError()
                rows=[validate_item(i,i['id']) for i in data['imprints']]
                fixed=[];used=set();legacy=list(data.get('legacyImprints',[]))
                for default in presets():
                    names=(default['name'],default['job']+'辉印')
                    item=next((r for r in rows if r['name'] in names and r['kind']==default['kind'] and r['id'] not in used),None)
                    if item:
                        used.add(item['id']);values=item['attributes']
                        if data['schemaVersion']==1 and default['scope']=='extra' and item.get('scope')!='extra':
                            base=imprint_for(default['kind'],default['kind'])
                            values={k:max(0,values[k]-base[k]) for k in ATTRIBUTES}
                        fixed.append({**default,'id':item['id'],'attributes':values})
                    else:fixed.append(default)
                legacy.extend(r for r in rows if r['id'] not in used)
                result={'schemaVersion':2,'imprints':fixed}
                if legacy:result['legacyImprints']=legacy
                return result
            except (ValueError,KeyError,TypeError) as e:raise SkillError('辉印库读取失败，原文件未覆盖',500) from e
    def save(self,payload,item_id=None):
        if not item_id:raise SkillError('辉印为固定条目，不可新增',405)
        item=validate_item(payload,item_id)
        with self.lock:
            data=self.read();original=next((i for i in data['imprints'] if i['id']==item_id),None)
            if not original:raise SkillError('辉印不存在',404)
            if any(item.get(k)!=original.get(k) for k in ('name','kind','scope','job')):raise SkillError('辉印名称和职业固定，只能修改属性数值')
            data['imprints']=[item if i['id']==item_id else i for i in data['imprints']];self._write(data)
            return {**data,'item':item}
    def delete(self,item_id):
        raise SkillError('辉印为固定条目，不可删除',405)
router=library_router('imprints','辉印库')
