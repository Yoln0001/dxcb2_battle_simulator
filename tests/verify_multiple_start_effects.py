from pathlib import Path
import sys,copy,random,tempfile
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.equipment.validation import validate_equipment
from backend.equipment.store import EquipmentStore
from backend.skills.store import SkillError
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
zero=dict.fromkeys(['strength','magic','technique','speed'],0)
def buff(kind='amplify',target='magic',coefs=None,base=0):
 return {'enabled':True,'kind':kind,'recipient':'self','target':target,'coefficients':{**zero,**(coefs or {})},'regeneration':{'baseValue':base,'coefficients':{**zero,'constitution':0,**(coefs or {})}}}
def ally(name,b,enabled=True):return {'side':'ally','name':name,'enabled':enabled,'buff':b}
def enemy(name,kind,value):return {'side':'enemy','name':name,'debuff':{'type':kind,**({ 'dotEnabled':True,'dotDamage':value} if kind=='dot' else {kind:value})}}
base={'schemaVersion':1,'id':'e','name':'混合开战装备','category':'accessory','weaponJob':'','attackType':'magic','effectName':'','triggerEffectName':'','triggerEnabled':False,'startingBuff':{'enabled':False,'recipient':'self','target':'none','coefficients':zero},'triggerRate':0,'effect':None}
entries=[ally('魔力增幅',buff(coefs={'magic':.5})),enemy('物理易伤','physicalVulnerability',12),ally('技巧增幅',buff(target='technique',coefs={'magic':.2})),ally('回春一',buff('regeneration','none',{'magic':.1},5)),enemy('魔法易伤','magicVulnerability',10),ally('回春二',buff('regeneration','none',{'constitution':1},10)),enemy('罚罪一','healingReduction',20),enemy('罚罪二','healingReduction',30),enemy('开战DOT','dot',40),ally('关闭增幅',buff(coefs={'magic':999}),False)]
item=validate_equipment({**base,'battleStartEffects':{'enabled':True,'entries':entries}})
assert len(item['battleStartEffects']['entries'])==10 and validate_equipment(item)==item
with tempfile.TemporaryDirectory() as directory:
 store=EquipmentStore(Path(directory)/'equipment.json');saved=store.save(item)['item'];assert store.read()['equipment'][0]==saved
 store.import_library({'schemaVersion':1,'equipment':[saved]})
legacy={**base,'effectName':'旧增幅','startingBuff':buff(coefs={'magic':.5}),'startingDebuffs':{'enabled':True,'entries':[{'type':'magicVulnerability','magicVulnerability':10,'name':'旧易伤'}]}}
migrated=validate_equipment(legacy);assert [row['side'] for row in migrated['battleStartEffects']['entries']]==['ally','enemy']
config={'battle':{'duration':2},'target':{'hitPoint':1e9,'speed':100},'characters':[{'enabled':i==0,'job':'法师','stats':{'magic':1000,'strength':1,'technique':0,'speed':10000,'constitution':100,'healingBonus':20,'finalHealingBonus':10,'dotDamage':20,'finalDotDamage':10},'equipment':{'accessory1':'e'},'skillGroup':'g'} for i in range(4)]}
group={'job':'法师','entry':'n','subgroups':[{'id':'sub','skills':[{'id':'n','skillId':'__wait__','waitDuration':100,'next':''}]}]}
for enabled in (True,False):
 gear=copy.deepcopy(item);gear['battleStartEffects']['enabled']=enabled;gear=validate_equipment(gear)
 py=SingleBattle(config,{'e':gear},{},{'g':group},seed=3);c=py.state.characters[0]
 assert c.stats['magic']==(1500 if enabled else 1000)
 assert c.stats['technique']==(300 if enabled else 0)
 assert len(c.regeneration_buffs)==(2 if enabled else 0)
 if enabled:
  assert np.isclose(sum(b['amount'] for b in c.regeneration_buffs),349.8)
  assert np.isclose(py.state.target['recoveryMultiplier'],.56)
  assert py.state.target['physicalVulnerability']==1.12 and py.state.target['magicVulnerability']==1.1
 c.current_hp=200;c.stats['hitPoint']=200;result=py.run()
 assert np.isclose(c.current_hp,899.6 if enabled else 200)
 assert np.isclose(result['total_damage'],105.6 if enabled else 0)
 arrays,_,_=prepare(config,{'e':gear},{},{'g':group});arrays[2][0,1]=200;arrays[0][0,5]=200
 out=battle(*arrays,np.array(random.Random(3).getstate()[1],dtype=np.uint32));assert np.isclose(out[5][0],c.current_hp) and np.isclose(out[0],result['total_damage'])
# Defensive opening conversions use the same four source coefficients.
for target in ('armor','resistance'):
 defensive=validate_equipment({**base,'battleStartEffects':{'enabled':True,'entries':[ally('防御增幅',buff(target=target,coefs={'magic':.5}))]}})
 assert validate_equipment(defensive)==defensive
 defensive_config=copy.deepcopy(config);defensive_config['characters'][0]['stats'][target]=100
 py=SingleBattle(defensive_config,{'e':defensive},{},{'g':group},seed=3)
 assert py.state.characters[0].stats[target]==600
 assert py.state.characters[0].buffs[0].attribute==target
 with tempfile.TemporaryDirectory() as directory:
  store=EquipmentStore(Path(directory)/'equipment.json');store.save(defensive)
  assert store.read()['equipment'][0]['battleStartEffects']['entries'][0]['buff']['target']==target
 arrays,_,_=prepare(defensive_config,{'e':defensive},{},{'g':group})
 assert 600 in arrays[0][0]
for bad in ({'enabled':True,'entries':[{'side':'invalid','name':'错误'}]},{'enabled':True,'entries':[{'side':'enemy','debuff':None}]},{'enabled':1,'entries':[]}):
 try:validate_equipment({**base,'battleStartEffects':bad})
 except SkillError:pass
 else:raise AssertionError('invalid opening entry accepted')
print('PASS: multiple ally amplifications/regenerations + enemy debuffs/DOT, names/sides, sequential ally coefficients, entry/global switches, old migration, persistence/import and Python/Numba parity')

for percentages,expected in [([10,20],280),([100],1000),([0],0)]:
 life=validate_equipment({**base,'battleStartEffects':{'enabled':True,'entries':[enemy('生命剥夺','lifeDeprivation',percent) for percent in percentages]}})
 assert validate_equipment(life)==life
 cfg=copy.deepcopy(config);cfg['target'].update(hitPoint=1000,physicalReduction=100,magicReduction=100,dotReduction=100,immuneNegativeEffects=True)
 py=SingleBattle(cfg,{'e':life},{},{'g':group},seed=3)
 assert np.isclose(py.state.target_current_hp,1000-expected)
 result=py.run();assert np.isclose(result['total_damage'],expected) and np.isclose(result['character_damage'][0],expected)
 if expected==1000:assert result['end_reason']=='target_defeated' and py.state.time==0
 arrays,_,_=prepare(cfg,{'e':life},{},{'g':group})
 out=battle(*arrays,np.array(random.Random(3).getstate()[1],dtype=np.uint32));assert np.isclose(out[0],expected) and np.isclose(out[2][0],expected) and bool(out[1])==(expected==1000)
 with tempfile.TemporaryDirectory() as directory:
  store=EquipmentStore(Path(directory)/'equipment.json');store.save(life)
  assert store.read()['equipment'][0]['startingDebuffs']['entries'][0]['lifeDeprivation']==percentages[0]
for percent in (-1,101):
 try:validate_equipment({**base,'battleStartEffects':{'enabled':True,'entries':[enemy('生命剥夺','lifeDeprivation',percent)]}})
 except SkillError:pass
 else:raise AssertionError('invalid deprivation percentage accepted')
print('PASS: current-HP deprivation, sequential percentages, damage attribution, untyped damage, 0/100 percent, persistence and Python/Numba parity')
