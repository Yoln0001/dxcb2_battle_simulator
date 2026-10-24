"""Conservative conversion of BWIKI descriptions into editable equipment definitions."""
import re
from copy import deepcopy
from ..equipment.validation import validate_equipment
from ..unclassified_equipment.crawler import CATEGORIES
RANGED_ATTRIBUTES={'weaponPower','strength','magic','technique','speed','constitution','armor','resistance'}
ATTRIBUTES={
 '武威':'weaponPower','力量':'strength','魔力':'magic','技巧':'technique','速度':'speed','体质':'constitution',
 '护甲':'armor','抗性':'resistance','暴击率':'criticalRate','命中率':'hitRate','闪避率':'dodgeRate','回复效果':'healingBonus','吸血':'lifesteal',
 '无视护甲':'ignoreArmor','无视抗性':'ignoreResistance','暴击伤害系数':'criticalMultiplier','闪避':'dodge',
 '异常附加率':'abnormalBonus','卸负':'unload','负重':'load','血量':'hitPoint'}
FORMULA={'力量':'strength','魔力':'magic','技巧':'technique','速度':'speed','体质':'constitution','当前生命值':'hitPoint','已损失的生命值':'lostHitPoint','已损失生命值':'lostHitPoint','武器威力':'weaponPower','武威':'weaponPower','护甲':'armor','抗性':'resistance'}
PERCENT={'criticalRate','hitRate','dodgeRate','healingBonus','lifesteal','criticalMultiplier','abnormalBonus','physicalDamage','magicDamage','dotDamage'}
TARGETS=['strength','magic','technique','speed'];NUM=r'\d+(?:\.\d+)?'
def zeros(keys=TARGETS):return dict.fromkeys(keys,0)
def rows(values):
    keys=['strength','magic','technique','speed','constitution','hitPoint','lostHitPoint']
    return [{'target':t,'enabled':t in values,'coefficients':{k:values.get(t,{}).get(k,0) for k in keys}} for t in TARGETS]
def formula(text,percent_target=None):
    result={};remaining=text
    # Longest labels first, so current / lost HP never become an unrelated property.
    for label,key in sorted(FORMULA.items(),key=lambda kv:-len(kv[0])):
        patterns=[(rf'({NUM})%的?{label}',.01),(rf'{label}[×*]({NUM})',1),(rf'({NUM})[×*]{label}',1)]
        for pattern,scale in patterns:
            for match in list(re.finditer(pattern,remaining)):
                result[key]=result.get(key,0)+float(match.group(1))*scale
            remaining=re.sub(pattern,'',remaining)
    if not result:return None
    # Do not silently accept formulas with unmodelled inputs / extra numerical terms.
    remaining=re.sub(r'[提高升同时增幅将的点生命值附加为力量魔力技巧速度体质护甲抗性和+,，（）()。\s]','',remaining)
    if re.search(r'\d|最大|敌方|当前|已损失',remaining):return None
    return result

def attributes(raw):
    result={key:{'label':label,'min':0,'max':0,'value':0,'unit':'%' if key in PERCENT else '', 'source':''} for label,key in ATTRIBUTES.items()}
    unknown=[]
    for text in re.split(r'[，,；;\n]',raw):
        text=text.strip()
        if not text:continue
        label=next((k for k in sorted(ATTRIBUTES,key=len,reverse=True) if text.startswith(k)),None)
        if not label:unknown.append(text);continue
        key=ATTRIBUTES[label];tail=text[len(label):].strip()
        match=re.fullmatch(r'([+-]?\d+(?:\.\d+)?)(?:\s*[-~～]\s*([+-]?\d+(?:\.\d+)?))?\s*(%)?',tail)
        if not match:
            result[key].update(min=None,max=None,value=None,source=text);unknown.append(text);continue
        low=float(match[1]);high=float(match[2]) if match[2] else low
        result[key].update(min=low,max=high,value=low if low==high else None,unit='%' if match[3] else '',source=text)
    if not raw.strip():unknown.append('来源未提供基础属性数值')
    return result,unknown

def classify(raw):
    attrs,issues=attributes(raw['attributes']);category='weapon' if raw['weaponJob'] else raw['category']
    item={'schemaVersion':1,'id':raw['id'].replace('bwiki_','wiki_'),'name':raw['name'],'category':category,'weaponJob':raw['weaponJob'],'attackType':'physical','effectName':'','triggerEffectName':'','triggerEnabled':False,'startingBuff':{'enabled':False,'recipient':'self','coefficients':zeros(),'target':'none'},'triggerRate':0,'effect':None,'triggerEffects':[]}
    definitions=[];passive=[];starting=[];extras=[];text=raw['effects']
    load=re.search(r'负重\+?('+NUM+')',text)
    if load:attrs['load'].update(min=float(load[1]),max=float(load[1]),value=float(load[1]),source=load[0])
    for pattern,label,key in [(r'(?<!/)吸血('+NUM+r')%','吸血（来源未区分单体/群体）','lifesteal'),(r'敌方治疗/吸血/回春效果降低('+NUM+r')%','敌方治疗/吸血/回春效果降低','enemyHealingReduction')]:
        m=re.search(pattern,text)
        if m:extras.append({'key':key,'label':label,'min':float(m[1]),'max':float(m[1]),'unit':'%','source':m[0]})
    matches=list(re.finditer(r'([\u4e00-\u9fffA-Za-z0-9·]+)[：:]',text))
    prefix=text[:matches[0].start()] if matches else text
    # Passive effects are recorded separately, including job-scoped imprints and immunities.
    pieces=[]
    for i,m in enumerate(matches):pieces.append((m[1],text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()))
    if prefix.strip():passive.append({'name':'常驻效果','description':prefix.strip()})
    for name,description in pieces:
        definition={'name':name,'description':description,'timing':'passive','supported':False}
        if name=='辉印':passive.append({'name':name,'description':description});definitions.append(definition);continue
        trigger='physical' if '发动物理攻击' in description else 'magic' if '发动魔法攻击' in description else 'none' if '使用回复技能' in description else None
        start='战斗开始' in description
        if start:definition['timing']='battleStart'
        elif trigger:definition['timing']='action';definition['triggerType']=trigger
        elif '受到物理攻击' in description:definition['timing']='receivePhysical'
        elif '受到魔法攻击' in description:definition['timing']='receiveMagic'
        probability=re.search(rf'({NUM})%的?概率',description)
        probability=float(probability[1]) if probability else 100
        duration=re.search(rf'持续({NUM})秒',description)
        duration=float(duration[1]) if duration else 0
        layers=re.search(r'可叠加(\d+)层',description);layers=int(layers[1]) if layers else 1
        recipient='allAllies' if '我方全体' in description else 'self' if '自身' in description else None
        effect=None
        if start or (trigger is not None and '附加' in description and recipient and '每秒' not in description):
            match=re.search(r'附加([^（(]+)[（(](?:提高|提升)(.+?)[）)]',description)
            if match and recipient:
                expression=match[2];target_label=next((a for a in ('力量','魔力','技巧','速度') if expression.endswith(a) or expression.endswith('点'+a)),None)
                values=formula(expression)
                if target_label and values and all(k in TARGETS for k in values):
                    target=FORMULA[target_label]
                    if start:
                        entry={'name':name,'buffName':match[1].strip(),'enabled':True,'recipient':recipient,'coefficients':{k:values.get(k,0) for k in TARGETS},'target':target};starting.append(entry);definition['parameters']=entry;definition['supported']=True
                    else:effect={'kind':'buff','type':target,'recipient':recipient,'duration':duration,'maxStacks':layers,'conversions':rows({target:values})}
        if trigger and '瞬间' in description:
            same=re.search(r'(?:增幅)(.+?)(?:。|$)',description)
            conversion=re.search(r'(?:将)(.+?)附加为(力量|魔力|技巧|速度)',description)
            values={}
            if conversion:
                terms=formula(conversion[1]);target=FORMULA[conversion[2]]
                if terms and all(k in ['strength','magic','technique','speed','constitution','hitPoint','lostHitPoint'] for k in terms):values[target]=terms
            elif same:
                for value,label in re.findall(rf'({NUM})%的?(力量|魔力|技巧|速度)',same[1]):values[FORMULA[label]]={FORMULA[label]:float(value)/100}
                if re.sub(rf'{NUM}%的?(?:力量|魔力|技巧|速度)|[同时和。\s]', '',same[1]):values={}
            if values:effect={'kind':'amplify','conversions':rows(values)}
        if trigger and '立即执行下次行动' in description:effect={'kind':'immediateAction'}
        if trigger and '真实伤害' in description and trigger!='none':
            expr=re.search(r'造成[（(](.+?)[）)]的?真实伤害',description)
            terms=formula(expr[1]) if expr else None
            if terms and all(k in TARGETS+['weaponPower'] for k in terms):effect={'kind':'physicalTrueDamage' if trigger=='physical' else 'magicTrueDamage','coefficients':{k:terms.get(k,0) for k in TARGETS+['weaponPower']}}
        if trigger and ('附加灼伤' in description or '附加灼烧' in description) and duration and '可叠加' not in description:
            expr=re.search(r'每秒失去(.+?)点生命值',description);terms=formula(expr[1]) if expr else None
            constant=re.fullmatch(NUM,expr[1]) if expr else None
            if constant or terms and all(k in TARGETS for k in terms):effect={'kind':'debuff','type':'burn','baseValue':float(constant[0]) if constant else 0,'duration':duration,'maxStacks':1,'coefficients':{k:(terms or {}).get(k,0) for k in TARGETS}}
        if effect:
            entry={'name':name,'triggerType':trigger,'probability':probability,'effect':effect};item['triggerEffects'].append(entry);definition.update(supported=True,parameters=entry)
        if not definition['supported']:
            parameters={'probability':probability if trigger or definition['timing'].startswith('receive') else None,'duration':duration or None,'maxStacks':layers,'recipient':recipient}
            if '附加为' in description:
                m=re.search(r'将(.+?)附加为(力量|魔力|技巧|速度|护甲|抗性)',description)
                if m:
                    parameters.update(kind='amplify',target=FORMULA[m[2]],coefficients=formula(m[1]))
            elif '附加' in description and ('提高' in description or '提升' in description or '降低' in description):
                m=re.search(r'附加([^（(]+)[（(](?:提高|提升|降低)(.+?)[）)]',description)
                if m:parameters.update(kind='buff' if recipient else 'debuff',buffName=m[1].strip(),formula=m[2],coefficients=formula(m[2]))
            if '每秒回复' in description or '每秒失去' in description:
                m=re.search(r'每秒(?:回复|失去)(.+?)点生命值',description)
                parameters.update(kind='regeneration' if '每秒回复' in description else 'periodicDamage',tickInterval=1,expiresOnIncapacitation='重伤后失效' in description)
                if m:
                    constant=re.fullmatch(NUM,m[1]);parameters.update(baseValue=float(constant[0]) if constant else 0,coefficients={} if constant else formula(m[1]),formula=m[1])
            if '反弹' in description:
                m=re.search(r'反弹('+NUM+r')%',description)
                if m:parameters.update(kind='reflectDamage',ratio=float(m[1])/100)
            if '回复' in description and '每秒' not in description:
                m=re.search(r'回复[（(](.+?)[）)]',description)
                if m:parameters.update(kind='healing',formula=m[1],coefficients=formula(m[1]))
            if '造成' in description and '无属性伤害' in description:parameters.update(kind='untypedDamage',excludedBattles=['遗迹','世界boss'] if '不生效' in description else [])
            if definition['timing']!='passive':definition['parameters']=parameters
            # Never manufacture missing duration, coefficients or unsupported defensive mechanics.
            if definition['timing']!='passive':issues.append(name+'：'+description)
            else:passive.append({'name':name,'description':description})
        definitions.append(definition)
    if starting:
        first=starting[0];item['effectName']=first['name'];item['startingBuff']={k:v for k,v in first.items() if k not in ('name','buffName')}
        if len(starting)>1:issues.append('含多个战斗开始增幅，已在补充窗口分别记录；主表当前显示第一条')
    item['triggerEnabled']=bool(item['triggerEffects'])
    if item['triggerEffects']:
        first=item['triggerEffects'][0];item.update(attackType=first['triggerType'],triggerEffectName=first['name'],triggerRate=first['probability'],effect=first['effect'])
    item=validate_equipment(item)
    for a in extras:
        if a.get('key')=='lifesteal':attrs['lifesteal'].update(min=a['min'],max=a['max'],value=a['min'],source=a.get('source',''))
    item.update(baseAttributes=attrs,extraAttributes=extras,startingEffects=starting,effectDefinitions=definitions,passiveEffects=passive,reviewIssues=issues,classificationStatus='needsReview' if issues else 'converted',source={'id':raw['id'],'category':raw['category'],'url':raw['sourceUrl'],'attributes':raw['attributes'],'effects':text},reviewNotes='')
    return item

def classify_all(records):return [classify(r) for r in records]
