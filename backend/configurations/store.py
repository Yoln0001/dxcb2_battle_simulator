"""Named team configurations, stored atomically on the server."""
import json
import uuid
from copy import deepcopy
from ..skills.store import SkillStore, SkillError, text, number

def validate_config(config):
    if not isinstance(config,dict) or config.get('schemaVersion')!=1 or not isinstance(config.get('characters'),list) or not 1<=len(config['characters'])<=100:
        raise SkillError('配置必须包含1至100个角色')
    if config.get('configurationType','regular') not in ('regular','special'):raise SkillError('配置分类无效')
    if sum(c.get('enabled') is True for c in config['characters'] if isinstance(c,dict))>4:raise SkillError('最多4名角色参战')
    if 'librarySelections' in config:
        selections=config['librarySelections']
        if not isinstance(selections,dict) or any(k not in ('equipment','stones','people','trophies','bosses','contracts','rings','holies','imprints') for k in selections):raise SkillError('配置库选择格式无效')
        for value in selections.values():text(value,'库ID',False)
    battle=config.get('battle');target=config.get('target')
    if not isinstance(battle,dict) or not isinstance(target,dict):raise SkillError('战斗及目标配置无效')
    if number(battle.get('duration'),'战斗时长',3600)<.1:raise SkillError('战斗时长至少0.1秒')
    count=number(battle.get('simulations'),'模拟次数',1000000)
    if count<1 or int(count)!=count:raise SkillError('模拟次数必须为正整数')
    for value in target.values():
        if isinstance(value,(int,float)) and not isinstance(value,bool):number(value,'目标属性')
    for c in config['characters']:
        if not isinstance(c,dict) or not isinstance(c.get('stats'),dict) or not isinstance(c.get('equipment'),dict):raise SkillError('角色配置无效')
        for k in ('enabled','firstStrike'):
            if type(c.get(k)) is not bool:raise SkillError('参战设置无效')
        for k in ('name','job','skillGroup','contract','negativeEffect'):text(c.get(k,''),k,False)
        for value in c['stats'].values():number(value,'面板属性')
        for value in c['equipment'].values():text(value,'装备',False)
        number(c.get('skillMultiplier',1),'技能倍率')
        if type(c.get('ringPanelIncluded',False)) is not bool:raise SkillError('域之环面板标记无效')
        bonuses=c.get('ringPanelBonuses',{})
        if not isinstance(bonuses,dict) or any(k not in ('physicalDamage','magicDamage','dotDamage','hitRate','abnormalBonus','healingBonus','dodgeRate','physicalBlock','magicBlock') for k in bonuses):raise SkillError('域之环面板增益无效')
        for value in bonuses.values():number(value,'域之环面板增益')
        multipliers=c.get('ringBattleMultipliers',{})
        if not isinstance(multipliers,dict) or any(k not in ('strength','magic','technique','speed','constitution') for k in multipliers):raise SkillError('域之环属性倍率无效')
        for value in multipliers.values():number(value,'域之环属性倍率')
        if c.get('selectedRing'):
            from ..rings.store import validate_item as validate_ring
            validate_ring(c['selectedRing'])
        if c.get('selectedContract'):
            from ..contracts.store import validate_item
            validate_item(c['selectedContract'])
    if sum(c.get('enabled',True) and c.get('contract','不激活')!='不激活' for c in config['characters'])>1:raise SkillError('契约只能由一个角色开启')
    return migrate_ring_panel(config)

def migrate_ring_panel(config):
    """Keep fixed ring attributes on the panel and dynamic gains in battle."""
    result=deepcopy(config)
    if result.get('configurationType','regular')!='regular':return result
    from ..rings.store import validate_item as validate_ring,base_values
    for character in result['characters']:
        ring=character.get('selectedRing')
        if not ring:continue
        stats=character['stats']
        if character.get('ringPanelIncluded'):
            for key,value in character.get('ringPanelBonuses',{}).items():
                stats[key]=max(0,stats.get(key,0)-value)
        else:
            multipliers=character.get('ringBattleMultipliers',{})
            for key,value in base_values(validate_ring(ring)).items():
                stats[key]=stats.get(key,0)+value*multipliers.get(key,1)
        character['ringPanelBonuses']={}
        character['ringPanelIncluded']=True
    return result

class ConfigurationStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():data={'schemaVersion':1,'configurations':[],'activeId':''}
            else:
                data=None
            if data is not None:return self.with_libraries(data)
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('schemaVersion')!=1 or not isinstance(data.get('configurations'),list):raise ValueError()
                changed=False
                for item in data['configurations']:
                    text(item['id'],'配置ID');text(item['name'],'配置名称')
                    config=validate_config(item['configuration'])
                    changed=changed or config!=item['configuration']
                    item['configuration']=config
                data=self.with_libraries(data)
                if changed:
                    from shutil import copy2
                    backup=self.path.parent/'backups'/(self.path.stem+'.before-ring-panel-migration-'+uuid.uuid4().hex+'.json')
                    backup.parent.mkdir(parents=True,exist_ok=True)
                    copy2(self.path,backup)
                    self._write(data)
                return data
            except (ValueError,KeyError,TypeError) as error:raise SkillError('配置库无法读取，原文件未覆盖',500) from error
    @staticmethod
    def with_libraries(data):
        libraries=data.setdefault('libraries',[])
        for kind,label in [('regular','默认常规配置库'),('special','默认特殊配置库')]:
            default='default_'+kind
            if not any(l['id']==default for l in libraries):libraries.append({'id':default,'name':label,'configurationType':kind,'default':True})
        for item in data['configurations']:
            item.setdefault('libraryId','default_'+item['configuration'].get('configurationType','regular'))
            lib=next((l for l in libraries if l['id']==item['libraryId']),None)
            if not lib or lib['configurationType']!=item['configuration'].get('configurationType','regular'):raise SkillError('配置所属库无效',500)
        return data

    def save_library(self,payload,library_id=None):
        name=text(payload.get('name'),'库名称')
        with self.lock:
            data=self.read();libraries=data['libraries']
            original=next((l for l in libraries if l['id']==library_id),None)
            if library_id and not original:raise SkillError('配置库不存在',404)
            kind=original['configurationType'] if original else payload.get('configurationType')
            if kind not in ('regular','special'):raise SkillError('请先选择配置类型')
            if any(l['configurationType']==kind and l['id']!=library_id and l['name']==name for l in libraries):raise SkillError('库名称已存在',409)
            if original:original['name']=name;item=original
            else:
                if len(libraries)>=200:raise SkillError('最多创建200个配置库')
                item={'id':'library_'+uuid.uuid4().hex,'name':name,'configurationType':kind,'default':False}
                if payload.get('copy'):
                    source=next((l for l in libraries if l['id']==payload.get('copyFrom')),None)
                    if not source or source['configurationType']!=kind:raise SkillError('复制来源库类型不匹配')
                    if len(data['configurations'])+sum(row['libraryId']==source['id'] for row in data['configurations'])>5000:raise SkillError('配置库最多5000条')
                    for row in list(data['configurations']):
                        if row['libraryId']==source['id']:
                            copied=deepcopy(row);copied.update(id='config_'+uuid.uuid4().hex,libraryId=item['id']);data['configurations'].append(copied)
                libraries.append(item)
            self._write(data);return {**data,'library':deepcopy(item)}

    def delete_library(self,library_id):
        with self.lock:
            data=self.read();item=next((l for l in data['libraries'] if l['id']==library_id),None)
            if not item:raise SkillError('配置库不存在',404)
            if item.get('default'):raise SkillError('默认配置库不可删除')
            removed={i['id'] for i in data['configurations'] if i['libraryId']==library_id}
            data['configurations']=[i for i in data['configurations'] if i['id'] not in removed]
            data['libraries']=[l for l in data['libraries'] if l['id']!=library_id]
            if data.get('activeId') in removed:data['activeId']=''
            data['initialized']=True;self._write(data);return data

    def save(self,payload,item_id=None):
        name=text(payload.get('name'),'配置名称');config=validate_config(payload.get('configuration'))
        with self.lock:
            data=self.read();items=data['configurations']
            item=next((c for c in items if c['id']==item_id),None)
            if item_id and item is None:raise SkillError('配置不存在',404)
            library_id=payload.get('libraryId',item.get('libraryId') if item else 'default_'+config.get('configurationType','regular'))
            library=next((l for l in data['libraries'] if l['id']==library_id),None)
            if not library or library['configurationType']!=config.get('configurationType','regular'):raise SkillError('配置与所属库类型不匹配')
            if any(c['libraryId']==library_id and c['id']!=item_id and c['name']==name for c in items):raise SkillError('配置名称已存在',409)
            if item is None:
                if len(items)>=5000:raise SkillError('配置库最多5000条')
                item={'id':'config_'+uuid.uuid4().hex};items.append(item)
            item.update(name=name,configuration=config,libraryId=library_id);
            if payload.get('activate',True):data['activeId']=item['id']
            self._write(data)
            return {**data,'item':deepcopy(item)}
    def rename(self,item_id,payload):
        name=text(payload.get('name'),'配置名称')
        with self.lock:
            data=self.read();items=data['configurations']
            item=next((c for c in items if c['id']==item_id),None)
            if item is None:raise SkillError('配置不存在',404)
            if any(c['libraryId']==item['libraryId'] and c['id']!=item_id and c['name']==name for c in items):raise SkillError('配置名称已存在',409)
            item['name']=name;self._write(data)
            return {**data,'item':deepcopy(item)}

    def activate(self,item_id):
        with self.lock:
            data=self.read();item=next((c for c in data['configurations'] if c['id']==item_id),None)
            if not item:raise SkillError('配置不存在',404)
            data['activeId']=item_id;self._write(data);return {'item':deepcopy(item)}

    def delete(self,item_id):
        with self.lock:
            data=self.read()
            if not any(c['id']==item_id for c in data['configurations']):raise SkillError('配置不存在',404)
            data['configurations']=[c for c in data['configurations'] if c['id']!=item_id]
            if data.get('activeId')==item_id:data['activeId']=''
            data['initialized']=True
            self._write(data)
            return data
