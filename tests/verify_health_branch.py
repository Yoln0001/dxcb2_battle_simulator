from pathlib import Path
import sys,random,copy
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.skill_groups.validation import validate_group
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle

def main():
    group={'schemaVersion':2,'id':'g','name':'血量条件','job':'岩浆法师','entry':'fire','subgroups':[{'id':'sub','nextGroup':'sub','healthBranch':{'kind':'allyHealthBelow','threshold':20,'whenTrue':'heal','whenFalse':'fire'},'skills':[{'id':'fire','skillId':'f','next':'fire'},{'id':'heal','skillId':'h','next':'fire'}]}]}
    saved=validate_group(group);assert saved['subgroups'][0]['healthBranch']==group['subgroups'][0]['healthBranch']
    # New editor shape: each skill carries its own release condition, top-down priority.
    group['subgroups'][0].pop('healthBranch')
    group['subgroups'][0]['conditionsEnabled']=True
    group['subgroups'][0]['skills'].reverse()
    group['subgroups'][0]['skills'][0]['releaseCondition']={'kind':'allyHealthBelow','threshold':20}
    group['subgroups'][0]['skills'][1]['releaseCondition']={'kind':'always','threshold':20}
    saved=validate_group(group)
    assert saved['subgroups'][0]['conditionsEnabled']
    base={'job':'岩浆法师','hitRate':100,'criticalRate':0,'cooldown':-1.5,'coefficients':{'magic':1},'effect':None}
    skills={'f':dict(base,name='火球术',damageType='magic'),'h':dict(base,name='静气凝神',damageType='none',healingRecipient='allAllies')}
    config={'battle':{'duration':1.5},'target':{'hitPoint':100000,'speed':100,'magicVulnerability':1},'characters':[{'enabled':i<2,'job':'岩浆法师','stats':{'magic':1000,'speed':100,'constitution':100},'equipment':{},'skillGroup':'g'} for i in range(4)]}
    for ally_hp,enabled,expected in [(1000,True,'火球术'),(200,True,'火球术'),(199,True,'静气凝神'),(0,True,'火球术'),(199,False,'火球术')]:
        cfg=copy.deepcopy(config);cfg['characters'][1]['enabled']=enabled
        for seed in range(5):
            py=SingleBattle(cfg,{},skills,{'g':saved},seed=seed)
            py.state.characters[0].current_hp=50;py.state.characters[0].stats['hitPoint']=50
            py.state.characters[1].current_hp=ally_hp;py.state.characters[1].stats['hitPoint']=ally_hp
            ref=py.run();released=next(e for frame in ref['timeline'] for e in frame['events'] if e['type']=='skill_released' and e['character']==1)
            assert released['skill_name']==expected,(ally_hp,enabled,released)
            arrays,_,_=prepare(cfg,{},skills,{'g':saved});arrays[2][0,1]=50;arrays[0][0,5]=50;arrays[2][1,1]=ally_hp;arrays[0][1,5]=ally_hp
            out=battle(*arrays,np.array(random.Random(seed).getstate()[1],dtype=np.uint32))
            assert np.allclose(out[2],ref['character_damage'])
            assert np.allclose(out[5],[c.current_hp for c in py.state.characters])
    # Recheck every action: sacrifice takes an ally below 20%, healing switches back.
    cfg=copy.deepcopy(config);cfg['battle']['duration']=19
    cfg['characters'][0].update(contract='旧日支配者-魔',negativeEffect='群体献祭',skillMultiplier=1)
    cfg['target']['hitPoint']=1e9
    py=SingleBattle(cfg,{},skills,{'g':saved},seed=9);ref=py.run()
    releases=[(frame['time'],e['skill_name']) for frame in ref['timeline'] for e in frame['events'] if e['type']=='skill_released' and e['character']==1]
    assert any(name=='静气凝神' for _,name in releases)
    position=next(i for i,(_,name) in enumerate(releases) if name=='静气凝神')
    assert releases[position+1][1]=='火球术'
    arrays,_,_=prepare(cfg,{},skills,{'g':saved});out=battle(*arrays,np.array(random.Random(9).getstate()[1],dtype=np.uint32))
    assert np.allclose(out[2],ref['character_damage'],rtol=1e-10)
    assert np.allclose(out[5],[c.current_hp for c in py.state.characters])
    empty=copy.deepcopy(saved)
    empty['subgroups'][0]['skills'][1]['releaseCondition']={'kind':'never','threshold':20}
    py=SingleBattle(config,{},skills,{'g':empty},seed=1);ref=py.run()
    assert not any(e['type']=='skill_released' for f in ref['timeline'] for e in f['events'])
    arr,_,_=prepare(config,{},skills,{'g':empty});out=battle(*arr,np.array(random.Random(1).getstate()[1],dtype=np.uint32))
    assert out[0]==0
    print('PASS: branch save, strict threshold, self/dead/disabled exclusion, per-action recheck and njit parity')
if __name__=='__main__':main()
