"""Separate editable encyclopedia equipment library; custom equipment is never overwritten."""
import json,math
from copy import deepcopy
from ..skills.store import SkillStore,SkillError
from ..equipment.validation import validate_equipment
from .classifier import ATTRIBUTES,RANGED_ATTRIBUTES
EXTRA_KEYS=['crystal','baseAttributes','extraAttributes','startingEffects','effectDefinitions','passiveEffects','reviewIssues','classificationStatus','source','reviewNotes']
def normalize_fixed(stat):
    numbers=[stat.get(field) for field in ('value','min','max') if stat.get(field) is not None]
    if any(type(n) not in (int,float) or not math.isfinite(n) for n in numbers):raise SkillError('固定属性数值无效')
    if numbers and any(n!=numbers[0] for n in numbers):raise SkillError(stat.get('label','属性')+'是固定属性，不能填写不同的上下限')
    stat['value']=stat['min']=stat['max']=numbers[0] if numbers else None

def validate_item(value,generate_id=False):
    item=validate_equipment(value,generate_id)
    for key in EXTRA_KEYS:
        if key in value:item[key]=deepcopy(value[key])
    if not isinstance(item.get('baseAttributes',{}),dict):raise SkillError('装备基础属性格式无效')
    for key,stat in item.get('baseAttributes',{}).items():
        if not isinstance(stat,dict) or not isinstance(stat.get('label'),str):raise SkillError('属性名称无效')
        for field in ('min','max','value'):
            n=stat.get(field)
            if n is not None and (type(n) not in (int,float) or not math.isfinite(n)):raise SkillError('属性数值必须是有限数字或空值')
        if stat.get('min') is not None and stat.get('max') is not None and stat['min']>stat['max']:raise SkillError('属性最小值不能超过最大值')
        if key not in RANGED_ATTRIBUTES:normalize_fixed(stat)
    for key in ('extraAttributes','startingEffects','effectDefinitions','passiveEffects','reviewIssues'):
        if key in item and (not isinstance(item[key],list) or len(item[key])>300):raise SkillError('补充资料列表无效')
    if 'source' in item and not isinstance(item['source'],dict):raise SkillError('来源资料格式无效')
    for stat in item.get('extraAttributes',[]):
        if not isinstance(stat,dict) or not isinstance(stat.get('label'),str) or not stat['label'].strip():raise SkillError('补充属性名称无效')
        for field in ('min','max'):
            n=stat.get(field)
            if n is not None and (type(n) not in (int,float) or not math.isfinite(n)):raise SkillError('补充属性数值无效')
        if stat.get('min') is not None and stat.get('max') is not None and stat['min']>stat['max']:raise SkillError('补充属性最小值不能超过最大值')
        normalize_fixed(stat)
    if item.get('classificationStatus','needsReview') not in ('converted','needsReview','reviewed'):raise SkillError('整理状态无效')
    return item

def progress(items):
    result={};total={'total':len(items),'converted':0,'needsReview':0,'reviewed':0}
    for item in items:
        category=item.get('source',{}).get('category') or item['category']
        row=result.setdefault(category,{'total':0,'converted':0,'needsReview':0,'reviewed':0})
        status=item.get('classificationStatus','needsReview');row['total']+=1;row[status]+=1;total[status]+=1
    return {'total':total,'categories':result}
class WikiEquipmentStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':1,'equipment':[],'progress':progress([])}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schemaVersion')!=1 or not isinstance(data.get('equipment'),list):raise ValueError()
                items=[validate_item(i) for i in data['equipment']]
                return {**data,'equipment':items,'progress':progress(items)}
            except (ValueError,TypeError,KeyError) as error:raise SkillError('百科装备库无法读取，原文件未覆盖',500) from error
    def save(self,value,item_id=None):
        item=validate_item(value,item_id is None)
        if item_id and item['id']!=item_id:raise SkillError('装备ID不一致')
        with self.lock:
            data=self.read();index=next((i for i,x in enumerate(data['equipment']) if x['id']==item['id']),None)
            if item_id and index is None:raise SkillError('百科装备不存在',404)
            if not item_id and index is not None:raise SkillError('装备已存在，请保存修改',409)
            if index is None:data['equipment'].append(item)
            else:data['equipment'][index]=item
            data['progress']=progress(data['equipment']);self._write(data);return {**data,'item':item}
    def delete(self,item_id):
        with self.lock:
            data=self.read()
            item=next((i for i in data['equipment'] if i['id']==item_id),None)
            if item is None:raise SkillError('装备不存在',404)
            data['equipment']=[i for i in data['equipment'] if i['id']!=item_id]
            source_id=item.get('source',{}).get('id')
            if source_id:data['deletedSourceIds']=list(dict.fromkeys(data.get('deletedSourceIds',[])+[source_id]))
            data['progress']=progress(data['equipment'])
            self._write(data)
            return data

    def import_library(self,payload):
        if payload.get('schemaVersion',1)!=1 or not isinstance(payload.get('equipment'),list) or len(payload['equipment'])>5000:raise SkillError('百科装备库格式无效或超过5000条')
        items=[validate_item(i) for i in payload['equipment']]
        if len({i['id'] for i in items})!=len(items):raise SkillError('装备ID重复')
        with self.lock:
            data=self.read();by_id={i['id']:i for i in data['equipment']}
            for item in items:
                if item['id'] in by_id and by_id[item['id']]!=item:raise SkillError('同ID内容不同，未覆盖：'+item['name'],409)
                by_id[item['id']]=item
            data.update(equipment=list(by_id.values()),progress=progress(list(by_id.values())));self._write(data);return data
    def classify_missing(self,raw_items):
        from .classifier import classify
        with self.lock:
            data=self.read();ids={i.get('source',{}).get('id') for i in data['equipment']}|set(data.get('deletedSourceIds',[]));added=0
            for raw in raw_items:
                if raw['id'] not in ids:data['equipment'].append(classify(raw));added+=1
            data['progress']=progress(data['equipment']);self._write(data);return {**data,'added':added}
