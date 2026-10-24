from pathlib import Path
import sys,random,copy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from backend.skills.store import validate_skill

base={'schemaVersion':1,'id':'s','name':'回春测试 Lv.8','job':'寒霜法师','damageType':'none','cooldown':0,'hitRate':0,'criticalRate':0,'coefficients':dict.fromkeys(['strength','magic','technique','speed','constitution','hitPoint','weaponPower'],0),'raceBonus':{'race':'none','multiplier':0},'effect':{'kind':'buff','type':'regeneration','triggerRate':100,'recipient':'healingTargets','skillType':'support','baseValue':10,'duration':2,'coefficients':{'strength':0,'magic':.2,'technique':0,'speed':0,'constitution':0}}}
base['coefficients']['magic']=.1
config={'battle':{'duration':4.5},'target':{'hitPoint':1e9,'speed':100,'allyHealingReduction':50,'allyRegenerationReduction':50},'characters':[{'enabled':i<2,'job':'寒霜法师','stats':{'magic':100,'strength':1,'speed':10000,'constitution':100,'healingBonus':20,'finalHealingBonus':10},'equipment':{},'skillGroup':'g' if i==0 else 'w'} for i in range(4)]}
groups={'g':{'job':'寒霜法师','entry':'n','subgroups':[{'id':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]},'w':{'job':'寒霜法师','entry':'wait','subgroups':[{'id':'sub','skills':[{'id':'wait','skillId':'__wait__','waitDuration':60,'next':''}]}]}}
for scope in ('self','allAllies'):
    for recipient in ('healingTargets','self','singleAlly','allAllies'):
        skill=validate_skill({**base,'healingRecipient':scope,'effect':{**base['effect'],'recipient':recipient}})
        py=SingleBattle(config,{}, {'s':skill},groups,seed=3)
        for c,hp in zip(py.state.characters,[800,100,0,0]):c.current_hp=hp;c.stats['hitPoint']=hp
        result=py.run();events=[e for f in result['timeline'] for e in f['events']]
        heals=[e for e in events if e['type']=='healing'];regen=[e for e in events if e['type']=='regeneration']
        assert [e['target_character'] for e in heals]==([2] if scope=='self' else [1,2]),heals
        targets=[1,2] if recipient=='allAllies' or recipient=='healingTargets' and scope=='allAllies' else [1] if recipient=='self' else [2]
        assert [e['target_character'] for e in events if e['type']=='regeneration_applied']==targets
        assert len(regen)==2*len(targets) and all(e['time'] in (2.5,3.5) and np.isclose(e['amount'],19.8) for e in regen),regen
        arrays,_,_=prepare(config,{}, {'s':skill},groups)
        arrays[2][:,1]=[800,100,0,0];arrays[0][:,5]=[800,100,0,0]
        out=battle(*arrays,np.array(random.Random(3).getstate()[1],dtype=np.uint32))
        assert np.allclose(out[5],[c.current_hp for c in py.state.characters]),(scope,recipient,out[5],py.state.characters)
print('PASS: single/group healing targets, matching buff recipients, regeneration coefficients, recovery bonuses, penalties, expiry and Python/Numba parity')

for scope in ('self','allAllies'):
    effect={'kind':'buff','type':'technique','triggerRate':100,'recipient':'healingTargets','skillType':'support','baseValue':10,'duration':2,'conversions':[{'target':k,'enabled':k=='technique','coefficients':dict.fromkeys(['strength','magic','technique','speed','constitution','hitPoint'],0)} for k in ('strength','magic','technique','speed')]}
    skill=validate_skill({**base,'healingRecipient':scope,'effect':effect})
    py=SingleBattle(config,{}, {'s':skill},groups,seed=3)
    for c,hp in zip(py.state.characters,[800,100,0,0]):c.current_hp=hp;c.stats['hitPoint']=hp
    result=py.run();events=[e for f in result['timeline'] for e in f['events']]
    buffs=[e for e in events if e['type']=='buff_applied']
    assert [e['target_character'] for e in buffs]==([2] if scope=='self' else [1,2]),buffs
    arrays,_,_=prepare(config,{}, {'s':skill},groups);arrays[2][:,1]=[800,100,0,0];arrays[0][:,5]=[800,100,0,0]
    out=battle(*arrays,np.array(random.Random(3).getstate()[1],dtype=np.uint32))
    assert np.allclose(out[5],[c.current_hp for c in py.state.characters])
    assert np.allclose(out[4][:,2],[c.stats.get('technique',0) for c in py.state.characters])
print('PASS: attribute buffs follow actual single/group healing recipients and expire in both engines')
