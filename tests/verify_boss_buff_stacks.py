"""Boss self-buff stack caps, expiry and compiled parity."""
import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_boss_combat import fixture,compare
from engine.runtime.boss_simulation import BossBattle
from engine.runtime.compiled.prepare import A
from backend.api.bosses import validate_boss_group
from backend.skills.store import SkillError
for kind in ('magic','regeneration'):
    cfg,eq,sl,gl=fixture();cfg['battle']['duration']=8
    cfg['target']['selectedBoss']['attributes']['magic']=100
    for c in cfg['characters']:c['stats']['constitution']=10000
    skill=cfg['target']['selectedBoss']['skillGroup']['skills'][0];skill['baseValue']=1
    skill['effect']={'kind':'buff','type':kind,'baseValue':10 if kind=='regeneration' else 0,'duration':10,'triggerRate':100,'recipient':'self','skillType':'damage','maxStacks':3,'coefficients':dict.fromkeys(('strength','magic','technique','speed','constitution'),0),'conversions':[{'target':k,'enabled':k=='magic','coefficients':dict.fromkeys(('strength','magic','technique','speed','constitution','hitPoint'),0)} for k in ('strength','magic','technique','speed')]}
    skill['effect']['conversions'][1]['coefficients']['magic']=.1
    py=BossBattle(cfg,eq,sl,gl,seed=3)
    for i,t in enumerate((1.5,3,4.5,6)):
        py.state.time=t;py.boss_periodic();py.boss_action()
        assert py.boss_runtime[3][0,1]==min(i+1,3)
        if kind=='magic':assert py.boss_runtime[0][A['magic']]==100+10*min(i+1,3)
        else:assert py.boss_runtime[1][4]==10*min(i+1,3)
    py.state.time=17;py.boss_periodic()
    assert py.boss_runtime[3][0,1]==0
    if kind=='magic':assert py.boss_runtime[0][A['magic']]==100
    compare(cfg,eq,sl,gl,seeds=range(4))
    for bad_value in (0,1000,1.5,True):
        bad=copy.deepcopy(cfg['target']['selectedBoss']['skillGroup']);bad['skills'][0]['effect']['maxStacks']=bad_value
        try:validate_boss_group(bad)
        except SkillError:pass
        else:raise AssertionError(bad_value)
print('PASS: buff and regeneration stacking, caps, non-compounding own bonus, expiry, validation and njit parity')
