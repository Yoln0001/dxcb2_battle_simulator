"""Survival statistics agree across ordinary and Boss batch engines."""
import sys,copy,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_boss_combat import fixture
from engine.runtime.batch import simulate_batch
from engine.runtime.boss_simulation import BossBattle
from engine.runtime.simulation import SingleBattle

cfg,eq,skills,groups=fixture()
cfg['battle'].update(duration=1.5,simulations=64)
def verify(config,expected=None,boss_attacks=True):
    rng=random.Random(config['seed']);alive=passed=0;members=[0]*4
    for _ in range(config['battle']['simulations']):
        b=(BossBattle if boss_attacks else SingleBattle)(config,eq,skills,groups,seed=rng.randrange(2**53),record_timeline=False);b.run()
        survivors=b.survival_at_all_kill if b.survival_at_all_kill is not None else [c.enabled and c.alive for c in b.state.characters]
        alive+=all(survivors)
        for i,value in enumerate(survivors):members[i]+=int(value)
        passed+=b.state.target_current_hp<=0
    if expected is not None:assert alive==expected,(alive,expected)
    for engine,parallel,workers in [('python',False,1),('numba',False,1),('numba',True,2)]:
        out=simulate_batch(config,eq,skills,groups,boss_attacks=boss_attacks,engine=engine,parallel=parallel,workers=workers)
        assert out['all_alive_battles']==alive,(engine,out['all_alive_battles'],alive)
        assert out['all_alive_rate']==alive/config['battle']['simulations']*100
        assert out['passed_battles']==passed
        for i,c in enumerate(out['characters']):
            assert c['survived_battles']==members[i]
            assert c['survival_rate']==(members[i]/config['battle']['simulations']*100 if c['enabled'] else None)
    return alive
verify(cfg,64) # Survive timeout without defeating the Boss.
mixed=copy.deepcopy(cfg)
mixed['target']['selectedBoss']['skillGroup']['skills'][0].update(baseValue=100000,hitRate=50,targeting='all')
assert 0<verify(mixed)<64
wipe=copy.deepcopy(mixed);wipe['target']['selectedBoss']['skillGroup']['skills'][0]['hitRate']=100
verify(wipe,0)
disabled=copy.deepcopy(cfg);disabled['characters'][0]['enabled']=False
verify(disabled,0)
win=copy.deepcopy(cfg);win['target']['hitPoint']=1
verify(win,64)
# Full-party execution is a deadline, but earlier deaths and targeted kills count.
execution=copy.deepcopy(cfg);execution['target']['partyWipe']={'enabled':True,'time':1.5,'strategy':'all'}
b=BossBattle(execution,eq,skills,groups,seed=1);b.run();assert not any(c.alive for c in b.state.characters);assert all(b.survival_at_all_kill)
verify(execution,64)
earlier=copy.deepcopy(mixed);earlier['battle']['duration']=3;earlier['target']['partyWipe']={'enabled':True,'time':3,'strategy':'all'}
assert 0<verify(earlier)<64
targeted=copy.deepcopy(execution);targeted['target']['partyWipe']['strategy']='random'
verify(targeted,0)
early_wipe=copy.deepcopy(wipe);early_wipe['battle']['duration']=3;early_wipe['target']['partyWipe']={'enabled':True,'time':3,'strategy':'all'}
verify(early_wipe,0)
verify(cfg,64,boss_attacks=False)
verify(disabled,0,boss_attacks=False)
verify(execution,64,boss_attacks=False)
verify(targeted,0,boss_attacks=False)
from backend.rings.store import presets
sacrifice=copy.deepcopy(cfg);sacrifice['battle']['duration']=20;sacrifice['target']['hitPoint']=1e12
sacrifice['characters'][0]['selectedRing']={**next(r for r in presets() if r['kind']=='fire'),'restriction':'sacrifice','mainValue':0,'secondaryValue':0}
verify(sacrifice,0,boss_attacks=False)
sacrifice['target']['partyWipe']={'enabled':True,'time':15,'strategy':'all'}
verify(sacrifice,0,boss_attacks=False)
print('PASS: ordinary/Boss Python and njit survival parity; full-party cutoff, individual kills, sacrifice, disabled, timeout and victory',flush=True)
