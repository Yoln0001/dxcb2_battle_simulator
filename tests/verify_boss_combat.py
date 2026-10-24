"""Opt-in Boss attacks: hand-calculated cases, timeline/njit parity and speed comparison."""
import sys,copy,random,time
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.boss_simulation import BossBattle
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from engine.runtime.batch import simulate_batch
from backend.api.bosses import validate_boss_group


def fixture():
    skill={'id':'hit','name':'Boss物理攻击','damageType':'physical','targeting':'single','cooldown':0,'baseValue':1000,'hitRate':100,'criticalRate':0,'coefficients':{},'effect':None}
    group=validate_boss_group({'skills':[skill]})
    boss={'attributes':{'strength':100,'speed':10000,'technique':0},'skillGroup':group}
    cfg={'seed':123,'battle':{'duration':5,'simulations':10},'target':{'hitPoint':1e9,'speed':10000,'selectedBoss':boss},'characters':[{'enabled':True,'job':'法师','stats':{'constitution':100,'magic':100,'strength':1,'technique':0,'speed':10000,'hitRate':100,'armor':50,'resistance':150,'physicalBlock':100},'equipment':{},'skillGroup':'g'} for _ in range(4)]}
    skills={'s':{'name':'我方攻击','job':'法师','damageType':'magic','cooldown':0,'hitRate':100,'criticalRate':0,'coefficients':{'magic':1},'effect':None}}
    groups={'g':{'job':'法师','entry':'n','subgroups':[{'id':'sub','nextGroup':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]}}
    return cfg,{},skills,groups


def compare(cfg,eq,sl,gl,seeds=range(8)):
    arrays,keys,warnings,data=prepare(cfg,eq,sl,gl,boss_attacks=True)
    for seed in seeds:
        py=BossBattle(cfg,eq,sl,gl,seed=seed);ref=py.run()
        out=battle(*arrays,np.array(random.Random(seed).getstate()[1],np.uint32),data)
        assert np.allclose(out[2],ref['character_damage'],rtol=1e-10),(seed,out[2],ref['character_damage'])
        assert np.allclose(out[5],[c.current_hp for c in py.state.characters],rtol=1e-10),(seed,out[5],[c.current_hp for c in py.state.characters])
        assert out[6].tolist()==[int(c.enabled and c.alive) for c in py.state.characters]
        assert out[1]==(py.state.target_current_hp<=0)
        expected={(c,e['slot'],e['equipment_id'],e['name'],e['trigger_type'],e['kind']):e['count'] for c,rows in enumerate(ref['effect_counts']) for e in rows}
        for p,key in enumerate(keys):assert out[3][p]==expected.get(key,0),(seed,key,out[3][p],expected.get(key,0))
    return ref


def main():
    cfg,eq,sl,gl=fixture()
    ref=compare(cfg,eq,sl,gl)
    damage=[e['damage'] for f in ref['timeline'] for e in f['events'] if e['type']=='boss_skill_damage']
    assert damage==[400,400,400],damage
    assert not any(e['type'].startswith('boss_skill') for f in SingleBattle(cfg,eq,sl,gl,seed=1).run()['timeline'] for e in f['events'])
    print('PASS: hand-calculated physical damage/armor/block/death; old engine has no Boss attacks',flush=True)
    # Every supported incoming status; each uses the same DOT interval/overwrite convention.
    kinds=('burn','bleeding','plague','slow','stun','weakness','fear','lifeLoss','strengthDecay','magicDecay','techniqueDecay','speedDecay')
    for kind in kinds:
        scenario=copy.deepcopy(cfg);scenario['battle']['duration']=8
        skill=scenario['target']['selectedBoss']['skillGroup']['skills'][0]
        skill.update(damageType='magic',baseValue=100,targeting='all',effect={'kind':'debuff','type':kind,'baseValue':10,'duration':2,'applicationRate':1000,'coefficients':dict.fromkeys(('strength','magic','technique','speed'),0)})
        compare(scenario,eq,sl,gl)
    # Random candidates each retain their own jumps and targeting; conditions and waits.
    scenario=copy.deepcopy(cfg);group=scenario['target']['selectedBoss']['skillGroup'];group['skills'].append({**group['skills'][0],'id':'magic','name':'魔法','damageType':'magic'})
    group.update(entry='r',subgroups=[{'id':'random','type':'random','skills':[{'id':'r','skillIds':['hit','magic'],'skillJumps':{'hit':'w','magic':'c'},'skillTargets':{'hit':'highestHp','magic':'random'}}]},
        {'id':'wait','nextGroup':'condition','skills':[{'id':'w','skillId':'__wait__','waitDuration':.5}]},
        {'id':'condition','type':'conditional','nextGroup':'random','skills':[{'id':'c','skillId':'hit','releaseCondition':{'kind':'timeAtLeast','threshold':3}},{'id':'else','skillId':'magic','releaseCondition':{'kind':'always'}}]}])
    scenario['target']['selectedBoss']['skillGroup']=validate_boss_group(group);scenario['battle']['duration']=12
    compare(scenario,eq,sl,gl,seeds=range(20))
    # Surviving recipients trigger received-attack effects; fatal damage cannot resurrect.
    for kind in ('buff','physicalTrueDamage','healing','immediateAction','debuff'):
        scenario=copy.deepcopy(cfg);scenario['target']['selectedBoss']['skillGroup']['skills'][0]['baseValue']=300
        effect={'kind':kind,'duration':2,'type':'magic','baseValue':0,'recipient':'self','maxStacks':1,'coefficients':{'magic':.2},'conversions':[{'target':'magic','enabled':True,'coefficients':{'magic':.1}}]}
        if kind=='debuff':effect.update(type='weakness',applicationRate=100)
        item={'id':'e','name':'受击装备','category':'accessory','startingBuff':{'enabled':False},'triggerEnabled':True,'triggerEffects':[{'name':'受击','triggerType':'receivedPhysical','probability':100,'effect':effect}]}
        for c in scenario['characters']:c['equipment']={'accessory1':'e'}
        compare(scenario,{'e':item},sl,gl)
    # Incoming amplification increases armor for this hit, without persisting it.
    scenario=copy.deepcopy(cfg);scenario['battle']['duration']=1.5
    amp={'id':'shield','name':'守护','category':'accessory','startingBuff':{'enabled':False},'triggerEnabled':True,'triggerEffects':[{'name':'受击护甲','triggerType':'receivedPhysical','probability':100,'effect':{'kind':'amplify','conversions':[{'target':'armor','enabled':True,'coefficients':{'armor':1}}]}}]}
    scenario['characters'][0]['equipment']={'accessory1':'shield'}
    result=compare(scenario,{'shield':amp},sl,gl)
    incoming=[e['damage'] for f in result['timeline'] for e in f['events'] if e['type']=='boss_skill_damage']
    assert np.allclose(incoming,[1000/3-100]),incoming
    # Immunity to explicit strength decay does not confer immunity to weakness.
    item={'id':'immune','name':'免疫','category':'accessory','startingBuff':{'enabled':False},'triggerEnabled':False,'negativeImmunities':{'immuneStrengthDecay':True}}
    for kind in ('strengthDecay','weakness'):
        scenario=copy.deepcopy(cfg);scenario['battle']['duration']=1.5
        scenario['characters'][0]['equipment']={'accessory1':'immune'};scenario['characters'][0]['stats']['strength']=100
        scenario['target']['selectedBoss']['skillGroup']['skills'][0]['effect']={'kind':'debuff','type':kind,'baseValue':20,'duration':10,'applicationRate':1000,'coefficients':dict.fromkeys(('strength','magic','technique','speed'),0)}
        py=BossBattle(scenario,{'immune':item},sl,gl,seed=3);py.run()
        assert py.state.characters[0].stats['strength']==(100 if kind=='strengthDecay' else 80)
        compare(scenario,{'immune':item},sl,gl)
    # Boss self buffs, direct healing, regeneration and lifesteal.
    for mode in ('buff','regeneration','healing','lifesteal'):
        scenario=copy.deepcopy(cfg);scenario['battle']['duration']=10
        skill=scenario['target']['selectedBoss']['skillGroup']['skills'][0];skill['baseValue']=10
        if mode=='healing':skill.update(damageType='none',baseValue=300)
        elif mode=='lifesteal':scenario['target']['selectedBoss']['attributes']['physicalSingleLifesteal']=50
        elif mode=='buff':skill['effect']={'kind':'buff','type':'strength','baseValue':5,'duration':2,'triggerRate':100,'recipient':'self','skillType':'damage','conversions':[{'target':k,'enabled':k=='strength','coefficients':dict.fromkeys(('strength','magic','technique','speed','constitution','hitPoint'),.1 if k=='strength' else 0)} for k in ('strength','magic','technique','speed')]}
        else:skill['effect']={'kind':'buff','type':'regeneration','baseValue':25,'duration':3,'triggerRate':100,'recipient':'self','skillType':'damage','coefficients':dict.fromkeys(('strength','magic','technique','speed','constitution'),0)}
        compare(scenario,eq,sl,gl)
    # Ring fragile/full-health/sacrifice and contract timing remain live during attacks.
    from backend.rings.store import presets
    scenario=copy.deepcopy(cfg);scenario['battle']['duration']=16
    kinds={r['kind']:r for r in presets()}
    for c,r in zip(scenario['characters'],({**kinds['fire'],'restriction':'fragile','gainValue':10},{**kinds['fire'],'restriction':'polluted','gainValue':10},{**kinds['earth'],'restriction':'fullHealth','gain':'doubleBlock','gainValue':50},{**kinds['fire'],'restriction':'sacrifice','gainValue':10})):
        c['selectedRing']=r
    compare(scenario,eq,sl,gl)
    # Ally stun prevents Boss release until expiration; party wipe retains priority.
    scenario=copy.deepcopy(cfg);scenario['characters'][0]['firstStrike']=True
    lib=copy.deepcopy(sl);lib['s']['effect']={'kind':'debuff','type':'stun','baseValue':0,'duration':10,'applicationRate':1000,'coefficients':{}}
    compare(scenario,eq,lib,gl)
    scenario['target']['partyWipe']={'enabled':True,'time':1.5};result=compare(scenario,eq,sl,gl)
    assert not any(e['type']=='boss_skill_released' for f in result['timeline'] for e in f['events'])
    # An owner killed before its queued same-tick contract must not release it.
    scenario=copy.deepcopy(cfg);scenario['battle']['duration']=14.1
    scenario['characters'][0].update(contract='旧日支配者-魔',negativeEffect='无',skillMultiplier=1)
    group=scenario['target']['selectedBoss']['skillGroup'];poke={**group['skills'][0],'baseValue':1,'cooldown':11.1}
    kill={**poke,'id':'kill','name':'击杀佩戴者','baseValue':100000}
    group.update(skills=[poke,kill],entry='killnode',subgroups=[{'id':'condition','type':'conditional','nextGroup':'condition','skills':[{'id':'killnode','skillId':'kill','releaseCondition':{'kind':'timeAtLeast','threshold':14}},{'id':'poke','skillId':'hit','releaseCondition':{'kind':'always'}}]}])
    scenario['target']['selectedBoss']['skillGroup']=validate_boss_group(group)
    compare(scenario,eq,sl,gl,seeds=range(20))
    print('PASS: all incoming statuses, random/conditional/wait graph and received equipment effects',flush=True)
    cfg['battle'].update(duration=100,simulations=1000);cfg['target']['selectedBoss']['skillGroup']['skills'][0]['baseValue']=1
    # Compile both specializations before timing.
    warm=copy.deepcopy(cfg);warm['battle']['simulations']=1
    simulate_batch(warm,eq,sl,gl,workers=4);simulate_batch(warm,eq,sl,gl,workers=4,boss_attacks=True)
    samples=[]
    for enabled in (False,True):
        value=simulate_batch(cfg,eq,sl,gl,workers=4,boss_attacks=enabled,engine='numba');samples.append(value['elapsed_seconds'])
        assert value['engine']=='numba_njit'
    print('1000 warm battles baseline / Boss:',samples,'ratio:',round(samples[1]/samples[0],2),flush=True)

def verify_no_racial_bonus():
    from engine.runtime.compiled.boss import tables
    cfg,eq,sl,gl=fixture()
    group=cfg['target']['selectedBoss']['skillGroup']
    group['skills'][0]['raceBonus']={'race':'human','multiplier':99}
    cleaned=validate_boss_group(group)
    assert cleaned['skills'][0]['raceBonus']=={'race':'none','multiplier':0}
    meta=tables(cfg,BossBattle(cfg,eq,sl,gl,seed=123).state.characters,group)[1]
    assert np.all(meta[:,13:17]==1)
    boosted=BossBattle(cfg,eq,sl,gl,seed=123);boosted.run()
    group['skills'][0]['raceBonus']={'race':'none','multiplier':0}
    ordinary=BossBattle(cfg,eq,sl,gl,seed=123);ordinary.run()
    assert [c.current_hp for c in boosted.state.characters]==[c.current_hp for c in ordinary.state.characters]
    print('PASS: legacy Boss racial bonuses neutralized in validation, compiled factors and timeline damage')

if __name__=='__main__':
    main()
    verify_no_racial_bonus()

