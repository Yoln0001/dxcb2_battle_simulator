from pathlib import Path
import sys,random,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
skills={'f':{'name':'Fire','job':'岩浆法师','damageType':'magic','cooldown':0,'coefficients':{'magic':1},'criticalRate':0,'hitRate':100}}
group={'id':'g','job':'岩浆法师','entry':'f','subgroups':[{'id':'s','nextGroup':'s','skills':[{'id':'f','skillId':'f','next':''}]}]}
config={'battle':{'duration':10},'target':{'hitPoint':1e9,'speed':100,'partyWipe':{'enabled':True,'time':5}},'characters':[{'enabled':True,'job':'岩浆法师','skillGroup':'g','stats':{'magic':100,'constitution':100,'speed':100},'equipment':{}} for i in range(4)]}
def check(cfg,groups,expected,time):
    arrays,_,_=prepare(cfg,{},skills,groups)
    for seed in range(3):
        for timeline in (True,False):
            py=SingleBattle(cfg,{},skills,groups,seed=seed,record_timeline=timeline);ref=py.run()
            assert ref['end_reason']==expected and ref['duration']==time,(ref['end_reason'],ref['duration'])
            out=battle(*arrays,np.array(random.Random(seed).getstate()[1],dtype=np.uint32))
            assert np.allclose(out[2],ref['character_damage'],rtol=1e-10)
            assert np.allclose(out[5],[c.current_hp for c in py.state.characters])
            if expected=='party_defeated':
                assert not any(c.alive for c in py.state.characters)
                if timeline:
                    wipes=[(f['time'],e) for f in ref['timeline'] for e in f['events'] if e['type']=='boss_periodic_kill']
                    assert len(wipes)==1 and wipes[0][0]==time
                    assert not any(e['type']=='skill_released' for f in ref['timeline'] if f['time']>=time for e in f['events'])
check(config,{'g':group},'party_defeated',5)
tie=copy.deepcopy(config);tie['target']['partyWipe']['time']=1.5;check(tie,{'g':group},'party_defeated',1.5)
fraction=copy.deepcopy(config);fraction['target']['partyWipe']['time']=5.01;check(fraction,{'g':group},'party_defeated',5.1)
early=copy.deepcopy(config);early['target']['hitPoint']=1;check(early,{'g':group},'target_defeated',1.5)
disabled=copy.deepcopy(config);disabled['target']['partyWipe']['enabled']=False;check(disabled,{'g':group},'duration',10)
waiting=copy.deepcopy(group);waiting['subgroups'][0]['skills'][0].update(skillId='__wait__',waitDuration=10)
check(config,{'g':waiting},'party_defeated',5)
snapshot=copy.deepcopy(config);snapshot['target']['selectedBoss']={'partyWipe':snapshot['target'].pop('partyWipe')};check(snapshot,{'g':group},'party_defeated',5)
print('PASS: scheduled wipe, same-time priority, fractional time, early Boss defeat, disabled rule, waiting interruption, snapshot and compiled parity')
