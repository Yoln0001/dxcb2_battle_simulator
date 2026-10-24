"""Domain rings: independent base pairs and fixed restriction/gain combinations."""
import json,uuid
from ..skills.store import SkillStore,SkillError,text,number,choice
ATTRIBUTES=('strength','magic','technique','speed','constitution')
# Existing field names and presets are retained for saved configuration compatibility.
PAIRS={'sky':[('technique','speed'),('technique','strength'),('technique','magic')],'water':[('technique','constitution'),('magic','constitution'),('magic','technique')],'fire':[('strength','technique'),('magic','technique'),('speed','technique')],'earth':[('constitution','magic'),('constitution','strength'),('constitution','technique')]}
RESTRICTIONS={'sky':['twoEnemies','missingParty','none'],'water':['twoEnemies','missingParty','none'],'fire':['fragile','polluted','sacrifice'],'earth':['twoEnemies','fullHealth','missingParty','none']}
GAINS={'sky':['physicalMagicDamage','dotDamage','hitRate'],'water':['abnormalBonus','healingBonus','dodgeRate'],'fire':['physicalMagicDamage','dotDamage','hitRate'],'earth':['physicalBlock','magicBlock','doubleBlock']}
def gain_value(item):return item['gainValue']
def base_values(item):
    values={}
    for attribute,amount in ((item['mainAttribute'],item['mainValue']),(item['secondaryAttribute'],item['secondaryValue'])):
        values[attribute]=values.get(attribute,0)+amount
    return values
def initial_gain_values(item,party_size=4,enemy_count=1):
    stacks=1
    if item['restriction']=='twoEnemies':stacks=int(enemy_count>=2)
    elif item['restriction']=='missingParty':stacks=max(0,4-party_size)
    keys=['physicalDamage','magicDamage'] if item['gain']=='physicalMagicDamage' else ['physicalBlock','magicBlock'] if item['gain']=='doubleBlock' else [item['gain']]
    return {k:item['gainValue']*stacks for k in keys}

def validate_item(data,item_id=None):
    if not isinstance(data,dict):raise SkillError('域之环格式无效')
    kind=choice(data.get('kind'),list(PAIRS),'域之环种类');main=data.get('mainAttribute');secondary=data.get('secondaryAttribute')
    main=choice(main,ATTRIBUTES,'属性一');secondary=choice(secondary,ATTRIBUTES,'属性二')
    gain=data.get('gain')
    if gain in ('physicalDamage','magicDamage'):gain='physicalMagicDamage'
    level=data.get('level',50)
    if type(level) is not int or not 1<=level<=50:raise SkillError('域之环等级应为1～50')
    return dict(id=text(item_id or data.get('id') or 'ring_'+str(uuid.uuid4()),'域之环ID'),name=text(data.get('name'),'域之环名称'),kind=kind,level=level,mainAttribute=main,secondaryAttribute=secondary,mainValue=number(data.get('mainValue',750),'属性一数值'),secondaryValue=number(data.get('secondaryValue',500),'属性二数值'),restriction=choice(data.get('restriction'),RESTRICTIONS[kind],'限制条件'),gain=choice(gain,GAINS[kind],'增益'),gainValue=number(data.get('gainValue',0),'增益数值'))
def presets():
    return [validate_item(dict(id=kind+'_'+str(i),name={'sky':'空之环','water':'水之环','fire':'炎之环','earth':'地之环'}[kind]+' · '+str(i+1),kind=kind,level=50,mainAttribute=main,secondaryAttribute=sub,mainValue=750,secondaryValue=500,restriction='fragile' if kind=='fire' else 'none',gain=GAINS[kind][0],gainValue=0)) for kind,pairs in PAIRS.items() for i,(main,sub) in enumerate(pairs)]
class RingStore(SkillStore):
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':1,'rings':presets()}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'));rows=[validate_item(i) for i in data['rings']]
                if len(rows)>5000 or len({i['id'] for i in rows})!=len(rows):raise ValueError()
                return {'schemaVersion':1,'rings':rows}
            except (ValueError,KeyError,TypeError):raise SkillError('域之环库读取失败，原文件未覆盖',500)
