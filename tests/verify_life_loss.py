from pathlib import Path
import copy,random,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from backend.skills.store import validate_skill, ATTRS, TARGETS
from backend.skill_groups.validation import validate_group
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
skill=validate_skill({'schemaVersion':1,'id':'loss','name':'Life loss','job':'岩浆法师','damageType':'magic','cooldown':0,'hitRate':100,'criticalRate':0,'raceBonus':{'race':'none','multiplier':0},'coefficients':{k:1 if k=='magic' else 0 for k in ATTRS+['weaponPower']},'effect':{'kind':'debuff','type':'lifeLoss','applicationRate':100,'baseValue':100,'duration':3,'coefficients':dict.fromkeys(TARGETS,0)}})
group=validate_group({'schemaVersion':2,'id':'g','name':'one cast','job':'岩浆法师','entry':'cast','subgroups':[{'id':'s','skills':[{'id':'cast','skillId':'loss','next':'wait'},{'id':'wait','skillId':'__wait__','waitDuration':300,'next':'wait'}]}]})
config={'battle':{'duration':5},'target':{'hitPoint':1e9,'speed':100},'characters':[{'enabled':i==0,'job':'岩浆法师','skillGroup':'g','stats':{'magic':100,'constitution':100,'speed':100,'dotDamage':20,'finalDotDamage':50},'equipment':{}} for i in range(4)]}
def check(cfg,skills):
 result=SingleBattle(cfg,{},skills,{'g':group},seed=3).run()
 fast=SingleBattle(cfg,{},skills,{'g':group},seed=3,record_timeline=False).run()
 arrays,_,_=prepare(cfg,{},skills,{'g':group})
 output=battle(*arrays,np.array(random.Random(3).getstate()[1],dtype=np.uint32))
 assert np.allclose(output[2],result['character_damage'])
 assert result['total_damage']==fast['total_damage']
 return result
result=check(config,{'loss':skill})
ticks=[(f['time'],e) for f in result['timeline'] for e in f['events'] if e['type']=='dot_damage']
assert [t for t,e in ticks]==[2.5,3.5,4.5]
assert all(e['name']=='生命流失' and np.isclose(e['damage'],180) for t,e in ticks)
assert any(e['type']=='target_debuff_expired' and e['name']=='生命流失' for f in result['timeline'] for e in f['events'])
assert np.isclose(result['total_damage'],640)
# Tick wins over a wipe occurring at exactly the first tick's timestamp.
wipe=copy.deepcopy(config);wipe['target']['partyWipe']={'enabled':True,'time':2.5}
result=check(wipe,{'loss':skill})
assert result['end_reason']=='party_defeated' and np.isclose(result['total_damage'],280)
frame=next(f for f in result['timeline'] if f['time']==2.5)
assert [e['type'] for e in frame['events']][:2]==['dot_damage','boss_periodic_kill']
# Same type replaces; burn and life loss remain independent.
engine=SingleBattle(config,{}, {'loss':skill},{'g':group},seed=3)
c=engine.state.characters[0];effect=skill['effect']
engine.apply_debuff(c,'First',effect,c.stats)
engine.state.time=.5
engine.apply_debuff(c,'Refresh',effect,c.stats)
assert len(engine.boss_debuffs)==1 and engine.boss_debuffs['生命流失']['next_tick_at']==1.5
burn=copy.deepcopy(effect);burn['type']='burn'
engine.apply_debuff(c,'Burn',burn,c.stats)
assert set(engine.boss_debuffs)=={'生命流失','灼烧'}
for key in ('immuneLifeLoss','immuneNegativeEffects'):
 immune=copy.deepcopy(config);immune['target'][key]=True
 result=check(immune,{'loss':skill})
 assert not any(e['type']=='dot_damage' for f in result['timeline'] for e in f['events'])
print('PASS: life loss starts one second after cast, ticks each second through expiry, DOT/imprint bonuses, overwrite, coexistence, immunity, tick-before-wipe and compiled parity')
