"""Boss-specific same-member decisions and targeted healing, including njit parity."""
import sys,copy,random,tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.skill_groups.validation import validate_group
from backend.skill_groups.store import SkillGroupStore
from backend.skills.store import SkillError
from engine.runtime.boss_simulation import BossBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from engine.runtime.initialization import BattleConfigurationError
from verify_boss_combat import fixture,compare

cfg,eq,skills,groups=fixture()
job='灵魂贤者'
for c in cfg['characters']:
    c.update(job=job);c['stats'].update(constitution=1000,magic=1000)
skills['s'].update(id='s',job=job,name='摄魂术 Lv.8')
skills['h']={**skills['s'],'id':'h','name':'魂体重塑 Lv.8','damageType':'none','cooldown':0,'healingRecipient':'self','effect':{'kind':'buff','type':'regeneration','recipient':'healingTargets','triggerRate':100,'baseValue':0,'duration':4,'coefficients':{'magic':.8}}}
boss=cfg['target']['selectedBoss'];boss.update(id='phantom',name='圣者的幻影')
boss['skillGroup']['skills'][0].update(name='生命萃取',damageType='magic',baseValue=100,cooldown=2.1,effect={'kind':'debuff','type':'lifeLoss','baseValue':120,'duration':8,'applicationRate':1000,'coefficients':dict.fromkeys(('strength','magic','technique','speed'),0)})
# Normal source graph preserves each skill's target strategy.
for sub in boss['skillGroup']['subgroups']:
    for n in sub['skills']:n['targetSelection']='random'
case={'kind':'memberStatus','includeSelf':True,'requiredDebuff':{'type':'lifeLoss','skillId':'hit','skillName':'生命萃取'},'absentBuff':{'type':'regeneration','skillId':'h','skillName':'魂体重塑 Lv.8'},'skillId':'h','targetSelection':'matchedMember'}
g=validate_group({'schemaVersion':2,'id':'g','name':'图52专用','job':job,'scope':{'kind':'boss','bossId':'phantom','bossName':'圣者的幻影','libraryId':'','libraryName':'默认Boss库'},'entry':'n','subgroups':[{'id':'sub','nextGroup':'sub','conditionsEnabled':True,'skills':[{'id':'n','skillId':'s','decision':{'cases':[case],'elseSkillId':'s'}}]}]})
groups={'g':g,'attack':{'job':job,'entry':'a','subgroups':[{'id':'attacks','nextGroup':'attacks','skills':[{'id':'a','skillId':'s'}]}]}}
for c in cfg['characters'][1:]:c['skillGroup']='attack'
assert validate_group(g)==g
with tempfile.TemporaryDirectory() as d:
    store=SkillGroupStore(Path(d)/'groups.json');store.save(g);assert store.read()['groups'][0]==g
print('PASS: scene and status conditions survive save/reload',flush=True)
py=BossBattle(cfg,{},skills,groups,seed=1)
py.state.time=1.5
# Member 3 is lowest overall, but only member 2 has the required status.
for c,hp in zip(py.state.characters,[9000,8000,100,9500]):c.current_hp=hp;c.stats['hitPoint']=hp
py.boss_runtime[4][1,7]=[1,9,2.5,120,-1,0,0]
assert [c.index for c in py.matching_members(case,1)]==[2]
py.action(1)
heals=[e for e in py.state.events if e['type']=='healing'];assert heals[-1]['target_character']==2,heals
assert py.state.characters[1].regeneration_buffs and not py.state.characters[2].regeneration_buffs
assert not py.matching_members(case,1)
# The healer may also be the target; dead/disabled members are excluded.
py.boss_runtime[4][0,7]=[1,9,2.5,120,-1,0,0]
assert [c.index for c in py.matching_members(case,1)]==[1]
assert not py.matching_members({**case,'includeSelf':False},1)
py.state.characters[0].alive=False;assert not py.matching_members(case,1)
py.state.characters[0].alive=True;py.boss_runtime[4][0,7,5]=1
assert not py.matching_members(case,1)
print('PASS: same member, correct target, existing regeneration, self, source skill and death checks',flush=True)
wrong=copy.deepcopy(cfg);wrong['target']['selectedBoss']['id']='other'
try:BossBattle(wrong,{},skills,groups,seed=1)
except BattleConfigurationError:pass
else:raise AssertionError('Wrong Boss scene accepted')
malformed=copy.deepcopy(g);malformed['scope']={'kind':'general'}
try:validate_group(malformed)
except SkillError:pass
else:raise AssertionError('Source-specific condition accepted without Boss')
cfg['battle']['duration']=30
ref=compare(cfg,{},skills,groups,seeds=range(12))
releases=[e['skill_name'] for frame in ref['timeline'] for e in frame['events'] if e['type']=='skill_released' and e['character']==1]
assert '魂体重塑 Lv.8' in releases and '摄魂术 Lv.8' in releases,releases
print('PASS: Python/njit Boss-targeted decisions, healing, regeneration expiry and damage parity across 12 seeds',flush=True)

# Reaction elapses during CD; an unrecognized status leads to an ordinary attack.
delayed=copy.deepcopy(g)
dc=delayed['subgroups'][0]['skills'][0]['decision']['cases'][0]
dc.update(recognitionDelay=.3,operationDelay=.3)
delayed=validate_group(delayed)
py=BossBattle(cfg,{},skills,{**groups,'g':delayed},seed=1)
py.state.time=1.5
py.boss_runtime[4][1,7]=[1,9,2.4,120,-1,0,1.4]
py.action(1)
assert [e for e in py.state.events if e['type']=='skill_released'][-1]['skill_name']=='摄魂术 Lv.8'
py.state.time=3.0;py.action(1)
assert py.operating[1]==(3.3,2)
assert py.state.characters[0].last_action_at==1.5
count=len([e for e in py.state.events if e['type']=='skill_released'])
py.state.time=3.2;py.action(1)
assert len([e for e in py.state.events if e['type']=='skill_released'])==count
py.state.time=3.3;py.action(1)
assert [e for e in py.state.events if e['type']=='healing'][-1]['target_character']==2
assert py.state.characters[0].last_action_at==3.3 and py.state.characters[0].next_action_at==4.8
# If the debuff was recognized before CD readiness, only the operation time remains.
py=BossBattle(cfg,{},skills,{**groups,'g':delayed},seed=1);py.state.time=1.5
py.boss_runtime[4][1,7]=[1,9,2.0,120,-1,0,1.0]
py.action(1);assert py.operating[1]==(1.8,2)
py.state.time=1.8;py.action(1)
assert any(e['type']=='healing' and e['time']==1.8 for e in py.state.events)
# Selected target is locked while operating; death cancels rather than retargets.
py=BossBattle(cfg,{},skills,{**groups,'g':delayed},seed=1);py.state.time=1.5
py.boss_runtime[4][1,7]=[1,9,2.0,120,-1,0,1.0];py.action(1)
py.state.characters[1].alive=False;py.state.characters[1].current_hp=0
py.state.time=1.8;py.action(1)
assert not any(e['type']=='healing' for e in py.state.events)
assert any(e['type']=='operation_cancelled' for e in py.state.events)
print('PASS: reaction/CD overlap, extra attack before recognition, locked operation, actual-release CD start and dead-target cancellation',flush=True)
for recognition in (0,.3,3.0):
 for operation in (0,.3,.7):
  candidate=copy.deepcopy(g);candidate['subgroups'][0]['skills'][0]['decision']['cases'][0].update(recognitionDelay=recognition,operationDelay=operation)
  candidate=validate_group(candidate)
  ref=compare(cfg,{},skills,{**groups,'g':candidate},seeds=range(5))
  if operation:
   events=[e for frame in ref['timeline'] for e in frame['events']]
   for e in [e for e in events if e['type']=='operation_started']:
    assert not any(a['type']=='skill_released' and a['character']==e['character'] and e['time']<=a['time']<e['ends_at'] for a in events)
# Refresh/stacks preserve the first continuous application timestamp.
refresh_cfg=copy.deepcopy(cfg);refresh_cfg['battle']['duration']=4.6
refresh_skill=refresh_cfg['target']['selectedBoss']['skillGroup']['skills'][0]
refresh_skill.update(cooldown=0,targeting='all');refresh_skill['effect'].update(duration=20,maxStacks=3)
py=BossBattle(refresh_cfg,{},skills,groups,seed=2);py.run()
assert all(np.isclose(row[6],1.5) for row in py.boss_runtime[4][:,7])
for field,value in [('recognitionDelay',-.1),('operationDelay',True),('operationDelay',.15),('recognitionDelay',3600.1)]:
 bad=copy.deepcopy(g);bad['subgroups'][0]['skills'][0]['decision']['cases'][0][field]=value
 try:validate_group(bad)
 except SkillError:pass
 else:raise AssertionError((field,value))
with tempfile.TemporaryDirectory() as d:
 store=SkillGroupStore(Path(d)/'groups.json');store.save(delayed)
 assert store.read()['groups'][0]['subgroups'][0]['skills'][0]['decision']['cases'][0]['operationDelay']==.3
print('PASS: configurable delays save/reload and validation; refresh does not reset reaction; 45 delayed Python/njit battles agree',flush=True)

# Boss attacks continue during a long operation and may kill its locked target.
death_cfg=copy.deepcopy(cfg)
for c in death_cfg['characters']:c['stats']['constitution']=200
death_cfg['characters'][1]['stats']['constitution']=150
bs=death_cfg['target']['selectedBoss']['skillGroup']['skills'][0]
bs.update(baseValue=5000);bs['effect']['baseValue']=0
for sub in death_cfg['target']['selectedBoss']['skillGroup']['subgroups']:
 for node in sub['skills']:node['targetSelection']='lowestHp'
long_group=copy.deepcopy(delayed);long_group['subgroups'][0]['skills'][0]['decision']['cases'][0]['operationDelay']=5.0
ref=compare(death_cfg,{},skills,{**groups,'g':long_group},seeds=range(5))
assert any(e['type']=='operation_cancelled' for frame in ref['timeline'] for e in frame['events'])
print('PASS: Boss continues attacking during operation; locked target death cancels with Python/njit parity',flush=True)
