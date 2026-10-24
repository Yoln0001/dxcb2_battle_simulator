from pathlib import Path
import copy, random, runpy, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from backend.skills.store import validate_skill, ATTRS, TARGETS
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
fixture=runpy.run_path(str(Path(__file__).with_name('verify_action_event_groups.py')))
config=copy.deepcopy(fixture['config']);config['target']['attributes']={'strength':100,'technique':80}
config['characters'][0]['equipment']={}
groups={'g':fixture['group']}
for kind,attribute,name in [('weakness','strength','虚弱'),('fear','technique','恐惧')]:
    skill=copy.deepcopy(fixture['skill'])
    skill.update(schemaVersion=1,id='fire',raceBonus={'race':'none','multiplier':0})
    skill['coefficients']={k:100 if k=='magic' else 0 for k in ATTRS+['weaponPower']}
    skill['effect']={'kind':'debuff','type':kind,'applicationRate':100,'baseValue':10,'duration':1,'coefficients':{k:.2 if k=='magic' else 0 for k in TARGETS}}
    skill=validate_skill(skill)
    skills={'fire':skill}
    engine=SingleBattle(config,{},skills,groups,seed=1)
    source=engine.state.characters[0]
    engine.apply_debuff(source,'Test',skill['effect'],source.stats)
    assert engine.state.target['attributes'][attribute]==config['target']['attributes'][attribute]-30
    weaker=copy.deepcopy(skill['effect']);weaker['baseValue']=5;weaker['coefficients']=dict.fromkeys(TARGETS,0)
    engine.apply_debuff(source,'Replacement',weaker,source.stats)
    assert len(engine.boss_debuffs)==1 and engine.state.target['attributes'][attribute]==config['target']['attributes'][attribute]-5
    enormous=copy.deepcopy(weaker);enormous['baseValue']=1000
    engine.apply_debuff(source,'Clamp',enormous,source.stats)
    assert engine.state.target['attributes'][attribute]==1
    result=engine.run()
    expired=next(f for f in result['timeline'] if f['time']==1)
    assert expired['snapshot']['target_attributes'][attribute]==config['target']['attributes'][attribute]
    assert config['target']['attributes']=={'strength':100,'technique':80}
    for immunity in ('immuneNegativeEffects','immuneWeakness' if kind=='weakness' else 'immuneFear'):
        cfg=copy.deepcopy(config);cfg['target'][immunity]=True
        immune=SingleBattle(cfg,{},skills,groups,seed=1)
        immune.apply_debuff(immune.state.characters[0],'Immune',skill['effect'],immune.state.characters[0].stats)
        assert not immune.boss_debuffs
    result=SingleBattle(config,{},skills,groups,seed=1).run()
    applied=next(e for f in result['timeline'] for e in f['events'] if e['type']=='target_debuff_applied')
    assert applied['name']==name and applied['attribute']==attribute and applied['amount']==30
    arrays,_,_=prepare(config,{},skills,groups)
    output=battle(*arrays,np.array(random.Random(1).getstate()[1],dtype=np.uint32))
    assert np.allclose(output[2],result['character_damage'])
print('PASS: weakness/fear validation, formula, overwrite, minimum-one clamp, expiry restoration, immunity, snapshots and compiled parity')
