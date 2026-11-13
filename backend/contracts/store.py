"""Editable contract instances; mechanics identified separately from display names."""
import json,uuid
from copy import deepcopy
from ..skills.store import SkillStore,SkillError,text,number,choice
from ..library_store import IdLibraryStore
CATEGORIES=('strength','magic','technique','speed','constitution')
RULES={'狂怒兽神':(3.6,['脆化','污秽','盲目','痴愚']),'饮命者':(6.9,['群体献祭','群体盲目','群体痴愚']),'旧日支配者':(7,['群体献祭']),'炎钢羽神':(1.5,['脆化','污秽','盲目','痴愚']),'饮魂者':(2.5,['群体献祭','群体盲目','群体痴愚'])}
TYPES={'狂怒兽神':'strength','饮命者':'strength','旧日支配者':'strength','炎钢羽神':'technique','饮魂者':'technique'}
RULES.update({'至高妖精': (2.3, ['脆化', '污秽', '盲目', '痴愚']), '饮命者（魔力）': (3.4, ['群体献祭', '群体盲目', '群体痴愚']), '旧日支配者（魔力）': (3.5, ['群体献祭']), '黑雾潜者': (1.3, ['脆化', '污秽', '盲目', '痴愚']), '饮命者（速度）': (1.7, ['群体献祭', '群体盲目', '群体痴愚']), '旧日支配者（速度）': (3.5, ['群体献祭'])})
TYPES.update({'至高妖精': 'magic', '饮命者（魔力）': 'magic', '旧日支配者（魔力）': 'magic', '黑雾潜者': 'speed', '饮命者（速度）': 'speed', '旧日支配者（速度）': 'speed'})

# Constitution contracts currently provide wearing bonuses only.
for name in ('安详女神','吸血伯爵','月之宗主'):
    RULES[name]=(0,['群体脆化','群体盲目','群体污秽','群体痴愚'])
    TYPES[name]='constitution'

def presets():return [dict(id=TYPES[name]+'_'+str(i),name=name,category=TYPES[name],archetype=name,baseBonus=12,multiplier=rule[0],negativeEffect=rule[1][0]) for i,(name,rule) in enumerate(RULES.items())]
def validate_item(data,item_id=None):
    if not isinstance(data,dict):raise SkillError('契约格式无效')
    category=choice(data.get('category'),CATEGORIES,'契约分类')
    archetype=choice(data.get('archetype'),list(RULES),'契约种类')
    if category!=TYPES[archetype]:raise SkillError('契约种类与分类不一致')
    multiplier=number(data.get('multiplier',RULES[archetype][0]),'技能系数')
    if data.get('level')==2:multiplier*=1.2
    bonus=number(data.get('baseBonus',12),'基础属性加成')
    return {'id':text(item_id or data.get('id') or 'contract_'+str(uuid.uuid4()),'契约ID'),'name':text(data.get('name'),'契约名称'),'category':category,'archetype':archetype,'baseBonus':bonus,'multiplier':multiplier,'negativeEffect':choice(data.get('negativeEffect'),RULES[archetype][1],'负面效果')}
class ContractStore(IdLibraryStore):
    key='contracts';label='契约';validate=staticmethod(validate_item)
    def read(self):
        with self.lock:
            if not self.path.exists():return {'schemaVersion':3,'contracts':presets()}
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'))
                rows=[validate_item(i) for i in data['contracts']]
                if self.path.name=='contracts.json' and data.get('schemaVersion',1)<2:
                    existing={i['archetype'] for i in rows};rows.extend(i for i in presets() if TYPES[i['archetype']] in ('magic','speed') and i['archetype'] not in existing)
                if self.path.name=='contracts.json' and data.get('schemaVersion',1)<3:
                    existing={i['archetype'] for i in rows}
                    rows.extend(i for i in presets() if i['category']=='constitution' and i['archetype'] not in existing)
                if len(rows)>5000 or len({i['id'] for i in rows})!=len(rows):raise ValueError()
                return {'schemaVersion':3,'contracts':rows}
            except (ValueError,KeyError,TypeError):raise SkillError('契约库读取失败，原文件未覆盖',500)
