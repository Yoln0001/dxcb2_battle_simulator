from pathlib import Path
import sys,copy,random
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.contracts.store import presets
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
config={'battle':{'duration':29.1},'target':{'hitPoint':1e9,'speed':100},'characters':[{'enabled':i==0,'job':'寒霜法师','stats':{'magic':100,'strength':1,'technique':100,'speed':10000,'constitution':10000,'dotDamage':10,'finalDotDamage':20},'equipment':{},'skillGroup':'g','contract':'不激活'} for i in range(4)]}
skill={'job':'寒霜法师','name':'旧灼烧','damageType':'magic','cooldown':0,'hitRate':100,'criticalRate':0,'coefficients':{'magic':0},'effect':{'kind':'debuff','type':'burn','applicationRate':100,'baseValue':999,'duration':60,'coefficients':{}}}
groups={'g':{'job':'寒霜法师','entry':'n','subgroups':[{'id':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]}}
for item in [i for i in presets() if i['category']=='technique']:
    cfg=copy.deepcopy(config);cfg['characters'][0].update(selectedContract=item,contract=item['archetype']+'-技',negativeEffect='盲目' if item['archetype']=='炎钢羽神' else '群体盲目',skillMultiplier=item['multiplier'])
    py=SingleBattle(cfg,{}, {'s':skill},groups,seed=5);result=py.run();events=[e for f in result['timeline'] for e in f['events']]
    trigger=[e for e in events if e['type']=='contract_dot_applied'];assert [e['time'] for e in trigger]==[14.1,28.1],trigger
    dots=[e for e in events if e['type']=='dot_damage']
    assert not any(14.1<=e['time']<15.1 for e in dots),dots
    assert [e['time'] for e in dots if e['time']>=14.1]==[15.1,29.1],dots
    new=[e for e in dots if e['time']>=14.1];expected=112*item['multiplier']*1.1*1.2
    assert np.isclose(new[0]['damage'],expected*(4 if item['archetype']=='炎钢羽神' else 1)),new
    assert np.isclose(new[1]['damage'],expected),new
    arrays,_,_=prepare(cfg,{}, {'s':skill},groups);out=battle(*arrays,np.array(random.Random(5).getstate()[1],dtype=np.uint32))
    assert np.isclose(out[0],result['total_damage']),(out[0],result['total_damage'])
print('PASS: 14-second technique contracts, first tick +1 second, ordinary burn replacement, one-second duration, first burst, DOT bonuses and Python/Numba parity')
