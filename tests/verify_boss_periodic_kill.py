"""Periodic executions select living participants; Python and njit must agree."""
import copy, random, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
from verify_boss_party_wipe import config, skills, group
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from backend.api.bosses import validate_party_wipe
for strategy in ('random','lowestHp','highestHp','all'):
    cfg=copy.deepcopy(config)
    cfg['target']['partyWipe']={'enabled':True,'time':2,'strategy':strategy}
    for i,c in enumerate(cfg['characters']):c['stats']['constitution']=100+i*100
    arrays,_,_=prepare(cfg,{},skills,{'g':group})
    for seed in range(12):
        py=SingleBattle(cfg,{},skills,{'g':group},seed=seed);result=py.run()
        events=[(f['time'],e['target_characters']) for f in result['timeline'] for e in f['events'] if e['type']=='boss_periodic_kill']
        if strategy=='all':assert events==[(2,[1,2,3,4])]
        else:
            assert [t for t,_ in events]==[2,4,6,8]
            order=[indices[0] for _,indices in events]
            assert sorted(order)==[1,2,3,4]
            if strategy=='lowestHp':assert order==[1,2,3,4]
            if strategy=='highestHp':assert order==[4,3,2,1]
        out=battle(*arrays,np.array(random.Random(seed).getstate()[1],dtype=np.uint32))
        assert np.allclose(out[2],result['character_damage'],rtol=1e-10),(strategy,seed,out[2],result['character_damage'])
        assert np.allclose(out[5],[c.current_hp for c in py.state.characters])
    assert validate_party_wipe(cfg['target']['partyWipe'])['strategy']==strategy
# Disabled participants are never selected, even when their HP would win.
cfg['target']['partyWipe']['strategy']='lowestHp';cfg['characters'][0]['enabled']=False
result=SingleBattle(cfg,{},skills,{'g':group},seed=1).run()
assert [e['target_characters'][0] for f in result['timeline'] for e in f['events'] if e['type']=='boss_periodic_kill']==[2,3,4]
print('PASS: periodic executions, all strategies, living participants, backend validation and 48 seeded njit comparisons')

from verify_boss_combat import fixture, compare
from engine.runtime.tas import TasSession
for strategy in ('random','lowestHp','highestHp','all'):
    cfg,eq,sl,gl=fixture()
    cfg['battle']['duration']=10
    cfg['target']['selectedBoss']['skillGroup']['skills'][0]['baseValue']=100
    cfg['target']['partyWipe']={'enabled':True,'time':2,'strategy':strategy}
    compare(cfg,eq,sl,gl,seeds=range(4))
    session=TasSession(cfg,eq,sl,gl)
    for index in range(1,5):session.operate({'kind':'mode','character':index,'mode':'auto'})
    for _ in range(110):
        if session.done:break
        session.operate({'kind':'step'})
    completed=session.view()
    assert any(e['type']=='boss_periodic_kill' for f in session.battle.frames for e in f['events'])
    session.seek(0);session.seek(round(completed['time']*10))
    assert session.view()['snapshot']==completed['snapshot']
    assert session.view()['total_damage']==completed['total_damage']
print('PASS: Boss attacks with periodic kill, njit parity and deterministic TAS rewind')
