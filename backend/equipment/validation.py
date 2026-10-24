"""装备定义校验；实际触发及战斗结算由后续战斗引擎处理。"""
import uuid
from .jobs import normalize_weapon_job

from ..skills.store import ATTRS, TARGETS, SkillError, choice, coefficients, number, text

BUFF_TARGETS=TARGETS+['constitution','armor','resistance']
AMPLIFICATION_ATTRS = ATTRS + ['lostHitPoint','armor','resistance']
AMPLIFICATION_TARGETS = TARGETS + ['armor','resistance']

def conversions(value, keys=ATTRS, targets=TARGETS):
    if not isinstance(value, list) or len(value) not in (4,len(targets)):
        raise SkillError('属性转化需要4行')
    result = []
    for target in targets:
        matches = [row for row in value if isinstance(row, dict) and row.get('target') == target]
        if not matches and target not in TARGETS:
            result.append({'target':target,'enabled':False,'coefficients':dict.fromkeys(keys,0)});continue
        if len(matches) != 1 or type(matches[0].get('enabled')) is not bool:
            raise SkillError('转化目标或开关无效')
        row = matches[0]
        result.append({'target': target, 'enabled': row['enabled'], 'coefficients': coefficients(dict(row.get('coefficients') or {}, lostHitPoint=(row.get('coefficients') or {}).get('lostHitPoint', 0),armor=(row.get('coefficients') or {}).get('armor',0),resistance=(row.get('coefficients') or {}).get('resistance',0)), keys) if row['enabled'] else dict.fromkeys(keys, 0)})
    return result

def enabled_flag(value, label):
    if type(value) is not bool:
        raise SkillError(label + '开关无效')
    return value

def layers(value):
    if type(value) is not int or not 1 <= value <= 999:
        raise SkillError('层数必须为1～999的整数')
    return value

def validate_single_equipment(data, generate_id=False):
    if not isinstance(data, dict) or type(data.get('schemaVersion')) is not int or data['schemaVersion'] != 1:
        raise SkillError('装备版本无效')
    item_id = data.get('id')
    if generate_id and (item_id is None or item_id == ''):
        item_id = 'equipment_' + str(uuid.uuid4())
    category = choice(data.get('category'), ['weapon', 'armor', 'accessory', 'stone'], '装备类型')
    starting = data.get('startingBuff')
    if not isinstance(starting, dict):
        raise SkillError('开战增幅格式无效')
    result = {'schemaVersion': 1, 'id': text(item_id, '装备ID'), 'name': text(data.get('name'), '装备名称'),
              'category': category, 'weaponJob': normalize_weapon_job(data.get('weaponJob')) if category == 'weapon' else '',
              'attackType': choice(data.get('attackType'), ['physical', 'magic', 'none', 'receivedPhysical', 'receivedMagic'], '触发类型'),
              'effectName': text(data.get('effectName'), '战斗开始特效名称', False),
              'triggerEffectName': text(data.get('triggerEffectName', ''), '特效名称', False),
              'triggerEnabled': enabled_flag(data.get('triggerEnabled', data.get('effect') is not None), '触发特效'),
              'startingBuff': {'enabled': enabled_flag(starting.get('enabled', bool(data.get('effectName')) or any(isinstance(v, (int, float)) and v > 0 for v in (starting.get('coefficients') or {}).values())), '战斗开始增幅'), 'recipient': choice(starting.get('recipient'), ['self', 'allAllies', 'singleAlly'], '开始buff对象'),
                               'coefficients': coefficients(starting.get('coefficients'), TARGETS),
                               'target': choice(starting.get('target'), ['none'] + TARGETS + ['armor','resistance'], '开战转化目标')},
              'triggerRate': number(data.get('triggerRate'), '触发概率', 100), 'effect': None}
    result['startingBuff']['kind']=choice(starting.get('kind','amplify'),['amplify','regeneration'],'开始buff特效类型')
    regen=starting.get('regeneration',{})
    if not isinstance(regen,dict):raise SkillError('开战回春格式无效')
    regen_keys=TARGETS+['constitution']
    raw_coefs=regen.get('coefficients',{})
    if not isinstance(raw_coefs,dict):raise SkillError('回春系数格式无效')
    result['startingBuff']['regeneration']={'receivesHealingBonuses':enabled_flag(regen.get('receivesHealingBonuses',not ('肇始之心★' in result['name'] or result['effectName']=='肇始之源')),'回春回复加成'),'baseValue':number(regen.get('baseValue',0),'回春基础数值'),'coefficients':coefficients({**dict.fromkeys(regen_keys,0),**raw_coefs},regen_keys)}
    if 'effect' not in data:
        raise SkillError('无特效时effect应为null')
    effect = data['effect']
    if effect is not None:
        if not isinstance(effect, dict):
            raise SkillError('装备特效格式无效')
        kind = effect.get('kind')
        if kind == 'amplify':
            result['effect'] = {'kind': kind, 'conversions': conversions(effect.get('conversions'), AMPLIFICATION_ATTRS, AMPLIFICATION_TARGETS)}
        elif kind in ('trueDamage', 'physicalTrueDamage', 'magicTrueDamage'):
            if kind == 'trueDamage':
                kind = 'magicTrueDamage' if data.get('attackType') in ('magic','receivedMagic') else 'physicalTrueDamage'
            result['effect'] = {'kind': kind, 'coefficients': coefficients(effect.get('coefficients'), TARGETS + ['weaponPower'])}
        elif kind == 'immediateAction':
            result['effect'] = {'kind': kind}
        elif kind == 'debuff':
            result['effect'] = {'kind': kind, 'type': choice(effect.get('type'), ['bleeding', 'plague', 'burn', 'slow', 'stun', 'weakness', 'fear', 'lifeLoss'], 'debuff类型'),
                                'baseValue': number(effect.get('baseValue'), '基础值'), 'duration': number(effect.get('duration'), '持续时间'),
                                'maxStacks': layers(effect.get('maxStacks')), 'coefficients': coefficients(effect.get('coefficients'), TARGETS)}
        elif kind == 'healing':
            result['effect']={'kind':kind,'recipient':choice(effect.get('recipient'),['self','allAllies','singleAlly'],'回复对象'),'coefficients':coefficients(effect.get('coefficients'),ATTRS+['weaponPower'])}
        elif kind == 'buff' and effect.get('type')=='regeneration':
            result['effect']={'kind':'buff','type':'regeneration','recipient':choice(effect.get('recipient','self'),['self','allAllies'],'回春对象'),'baseValue':number(effect.get('baseValue',0),'回春基础值'),'duration':number(effect.get('duration',0),'持续时间'),'coefficients':{},'conversions':[],'maxStacks':1}
        elif kind == 'buff':
            result['effect'] = {'kind': kind, 'type': choice(effect.get('type'), BUFF_TARGETS, 'buff类型'),
                                'recipient': choice(effect.get('recipient'), ['self', 'allAllies', 'singleAlly'], 'buff对象'),
                                'duration': number(effect.get('duration'), '持续时间'), 'maxStacks': layers(effect.get('maxStacks')),
                                'conversions': conversions(effect.get('conversions'),targets=BUFF_TARGETS)}
        else:
            raise SkillError('装备特效类型无效')
    return result

def validate_equipment(data, generate_id=False):
    if not isinstance(data, dict):
        raise SkillError('装备格式无效')
    entries = data.get('triggerEffects')
    if 'triggerEffects' not in data:
        entries = [{'name': data.get('triggerEffectName', ''), 'triggerType': data.get('attackType'), 'probability': data.get('triggerRate'), 'effect': data.get('effect')}]
    if not isinstance(entries, list) or len(entries) > 50:
        raise SkillError('触发特效列表无效（最多50条）')
    triggers = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SkillError('触发特效格式无效')
        item = validate_single_equipment(dict(data, attackType=entry.get('triggerType'), triggerEffectName=entry.get('name'), triggerRate=entry.get('probability'), effect=entry.get('effect')), generate_id)
        triggers.append({'name': item['triggerEffectName'], 'triggerType': item['attackType'], 'probability': item['triggerRate'], 'effect': item['effect']})
    first = triggers[0] if triggers else {'name': '', 'triggerType': 'physical', 'probability': 0, 'effect': None}
    result = validate_single_equipment(dict(data, attackType=first['triggerType'], triggerEffectName=first['name'], triggerRate=first['probability'], effect=first['effect']), generate_id)
    if data.get('wikiId'):result['wikiId']=text(data['wikiId'],'百科装备身份')
    result['mainAttribute']=choice(data.get('mainAttribute',''),['','strength','magic','technique','speed','constitution'],'主属性')
    result['triggerEffects'] = triggers
    from copy import deepcopy
    labels={'weaponPower':'武威','strength':'力量','magic':'魔力','technique':'技巧','speed':'速度','constitution':'体质','armor':'护甲','resistance':'抗性','criticalRate':'暴击率','hitRate':'命中率','dodgeRate':'闪避率','healingBonus':'回复效果','lifesteal':'吸血','ignoreArmor':'无视护甲','ignoreResistance':'无视抗性','criticalMultiplier':'暴击伤害系数','dodge':'闪避','abnormalBonus':'异常附加率','unload':'卸负','load':'负重'}
    stats=deepcopy(data.get('baseAttributes',{}))
    if not isinstance(stats,dict):raise SkillError('装备基础属性格式无效')
    import math
    ranged={'weaponPower','strength','magic','technique','speed','constitution','armor','resistance'}
    if 'lifesteal' not in stats:
        value=sum(a.get('value',a.get('min',0)) or 0 for a in data.get('extraAttributes',[]) if isinstance(a,dict) and a.get('key')=='lifesteal')
        stats['lifesteal']={'label':'吸血','min':value,'max':value,'value':value,'unit':'%'}
    for key,label in labels.items():stats.setdefault(key,{'label':label,'min':0,'max':0,'value':0,'unit':'%' if key in {'criticalRate','hitRate','dodgeRate','healingBonus','lifesteal','criticalMultiplier','abnormalBonus'} else ''})
    for key,stat in stats.items():
        if not isinstance(stat,dict):raise SkillError('装备基础属性格式无效')
        values=[stat.get(f) for f in ('min','max','value','ownedValue') if stat.get(f) is not None]
        if any(type(n) not in (int,float) or not math.isfinite(n) for n in values):raise SkillError('属性数值无效')
        if key in {'physicalVulnerability','magicVulnerability'}:
            if any(n<0 for n in values):raise SkillError('易伤百分比不能为负数')
            stat['unit']='%'
        if key not in ranged:
            if values and any(n!=values[0] for n in values):raise SkillError('固定属性不能填写不同的上下限')
            stat['min']=stat['max']=stat['value']=values[0] if values else None
        elif stat.get('min') is not None and stat.get('max') is not None and stat['min']>stat['max']:raise SkillError('属性最小值不能超过最大值')
    opening=data.get('startingDebuffs')
    if opening is None:
        legacy={key:(stats.get(key,{}).get('value') if stats.get(key,{}).get('value') is not None else stats.get(key,{}).get('min')) or 0 for key in ('physicalVulnerability','magicVulnerability')}
        opening={'enabled':any(legacy.values()),**legacy}
    if not isinstance(opening,dict):raise SkillError('开战敌方debuff格式无效')
    entries=opening.get('entries',[opening])
    if not isinstance(entries,list) or len(entries)>50:raise SkillError('开战敌方debuff最多50条')
    rows=[]
    for row in entries:
        if not isinstance(row,dict):raise SkillError('开战敌方debuff格式无效')
        name=text(row.get('name',''),'开战敌方debuff名称',False)
        values={'physicalVulnerability':number(row.get('physicalVulnerability',0),'物理易伤百分比'),
            'magicVulnerability':number(row.get('magicVulnerability',0),'魔法易伤百分比'),
            'dot':number(row.get('dotDamage',0),'DOT每秒基础伤害'),
            'healingReduction':number(row.get('healingReduction',0),'回复/吸血效果降低',100),
            'lifeDeprivation':number(row.get('lifeDeprivation',0),'敌方当前生命值百分比',100)}
        dot_on=enabled_flag(row.get('dotEnabled',False),'开战DOT')
        if 'type' in row:
            kinds=[choice(row['type'],list(values),'开战debuff类型')]
        else:
            kinds=[key for key,value in values.items() if (dot_on if key=='dot' else value>0)] or ['physicalVulnerability']
        for kind in kinds:
            rows.append({'name':name,'type':kind,'dotEnabled':kind=='dot',
                'dotDamage':values['dot'] if kind=='dot' else 0,
                **{key:values[key] if kind==key else 0 for key in ('physicalVulnerability','magicVulnerability','healingReduction','lifeDeprivation')}})
    if len(rows)>50:raise SkillError('拆分后开战敌方debuff超过50条')
    result['startingDebuffs']={'enabled':enabled_flag(opening.get('enabled',False),'开战敌方debuff'),'entries':rows,**(rows[0] if rows else {})}
    for key in ('physicalVulnerability','magicVulnerability'):stats.pop(key,None)
    immunities=data.get('negativeImmunities',{})
    immunity_keys=('immuneBleeding', 'immunePlague', 'immuneBurn', 'immuneStun', 'immunePhysicalVulnerability', 'immuneMagicVulnerability', 'immuneStrengthDecay', 'immuneMagicDecay', 'immuneTechniqueDecay', 'immuneSpeedDecay', 'immuneArmorDecay', 'immuneResistanceDecay')
    if not isinstance(immunities,dict) or any(k not in immunity_keys and k not in ('immuneSpeedReduction', 'immuneWeakness', 'immuneFear', 'immuneLifeLoss', 'immuneLifestealReduction', 'immuneHealingReduction', 'immuneRegenerationReduction', 'immuneNegativeEffects') for k in immunities):raise SkillError('装备负面免疫格式无效')
    result['negativeImmunities']={k:enabled_flag(immunities.get(k,False),'装备负面免疫') for k in immunity_keys}
    result['baseAttributes']=stats
    crystal=data.get('crystal',{'enabled':False,'attributes':{}})
    if not isinstance(crystal,dict) or type(crystal.get('enabled')) is not bool or not isinstance(crystal.get('attributes',{}),dict):raise SkillError('晶络格式无效')
    crystal_stats={key:crystal.get('attributes',{}).get(key,0) for key in ('strength','magic','technique','speed','constitution')}
    if any(type(n) not in (int,float) or not math.isfinite(n) for n in crystal_stats.values()):raise SkillError('晶络属性数值无效')
    result['crystal']={'enabled':crystal['enabled'],'attributes':crystal_stats}
    for key in ['extraAttributes','startingEffects','effectDefinitions','passiveEffects','reviewIssues','classificationStatus','source','reviewNotes']:
        if key in data:result[key]=deepcopy(data[key])
    bundle=data.get('battleStartEffects')
    if 'battleStartEffects' in data:
        if not isinstance(bundle,dict) or not isinstance(bundle.get('entries'),list) or len(bundle['entries'])>100:raise SkillError('战斗开始效果最多100条')
        enabled=enabled_flag(bundle.get('enabled',False),'战斗开始效果');entries=[]
        for row in bundle['entries']:
            if not isinstance(row,dict):raise SkillError('战斗开始效果格式无效')
            side=choice(row.get('side'),['ally','enemy'],'施加阵营');name=text(row.get('name',''),'战斗开始特效名称',False);on=enabled_flag(row.get('enabled',True),'开战效果条目')
            if side=='ally':
                buff=validate_single_equipment({**data,'effectName':name,'startingBuff':row.get('buff'),'effect':None},generate_id)['startingBuff']
                entries.append({'side':side,'name':name,'enabled':on,'buff':buff})
            else:
                debuff=row.get('debuff')
                if not isinstance(debuff,dict):raise SkillError('开战敌方debuff格式无效')
                old={k:v for k,v in data.items() if k!='battleStartEffects'}
                normalized=validate_equipment({**old,'startingDebuffs':{'enabled':True,'entries':[{**debuff,'name':name}]}},generate_id)['startingDebuffs']['entries']
                if len(normalized)!=1:raise SkillError('每条敌方开战效果只能选择一种debuff')
                entries.append({'side':side,'name':name,'enabled':on,'debuff':normalized[0]})
        if sum(row['side']=='enemy' for row in entries)>50:raise SkillError('开战敌方debuff最多50条')
        result['battleStartEffects']={'enabled':enabled,'entries':entries}
    else:
        ally_configured=result['startingBuff']['enabled'] or result['effectName'] or result['startingBuff']['kind']=='regeneration' or result['startingBuff']['target']!='none' or any(result['startingBuff']['coefficients'].values())
        enemy_configured=[row for row in result['startingDebuffs']['entries'] if result['startingDebuffs']['enabled'] or row['name'] or row['dotEnabled'] or any(row[key] for key in ('physicalVulnerability','magicVulnerability','healingReduction','lifeDeprivation'))]
        result['battleStartEffects']={'enabled':result['startingBuff']['enabled'] or result['startingDebuffs']['enabled'],'entries':
            ([{'side':'ally','name':result['effectName'],'enabled':result['startingBuff']['enabled'],'buff':deepcopy(result['startingBuff'])}] if ally_configured else [])+
            [{'side':'enemy','name':row['name'],'enabled':result['startingDebuffs']['enabled'],'debuff':deepcopy(row)} for row in enemy_configured]}
    bundle=result['battleStartEffects'];ally=next((row for row in bundle['entries'] if row['side']=='ally' and row['enabled']),None)
    if ally:result['effectName']=ally['name'];result['startingBuff']={**deepcopy(ally['buff']),'enabled':bundle['enabled']}
    else:result['startingBuff']['enabled']=False
    enemy=[{**deepcopy(row['debuff']),'name':row['name']} for row in bundle['entries'] if row['side']=='enemy' and row['enabled']]
    result['startingDebuffs']={'enabled':bundle['enabled'] and bool(enemy),'entries':enemy,**(enemy[0] if enemy else {})}
    return result

def validate_library(data):
    if not isinstance(data, dict) or data.get('schemaVersion') != 1 or not isinstance(data.get('equipment'), list) or len(data['equipment']) > 5000:
        raise SkillError('装备库格式无效或超过5000条')
    items = [validate_equipment(item) for item in data['equipment']]
    if len({item['id'] for item in items}) != len(items):
        raise SkillError('装备ID重复')
    return {'schemaVersion': 1, 'equipment': items}
