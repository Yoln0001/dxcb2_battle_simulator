from pathlib import Path
import sys,copy,random,tempfile,json
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.contracts.store import presets,ContractStore
from engine.runtime.simulation import SingleBattle
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle
from engine.runtime.contracts import calculate_contract_damage
items=[i for i in presets() if i['category'] in ('magic','speed')];assert len(items)==6
config={'battle':{'duration':28.1},'target':{'hitPoint':1e9,'speed':100},'characters':[{'enabled':True,'job':'寒霜法师','stats':{'magic':100,'strength':100,'technique':100,'speed':100,'constitution':10000},'equipment':{},'skillGroup':'g','contract':'不激活'} for i in range(4)]}
skill={'job':'寒霜法师','name':'无伤害','damageType':'none','healingRecipient':'allAllies','cooldown':0,'hitRate':100,'criticalRate':0,'coefficients':{'magic':10000},'effect':None}
groups={'g':{'job':'寒霜法师','entry':'n','subgroups':[{'id':'sub','skills':[{'id':'n','skillId':'s','next':'n'}]}]}}
for item in items:
    cfg=copy.deepcopy(config);name=item['archetype'].replace('（魔力）','').replace('（速度）','')+('-魔' if item['category']=='magic' else '-速')
    cfg['characters'][0].update(selectedContract=item,contract=name,negativeEffect='群体盲目' if item['archetype'].startswith('饮命者') else '群体献祭' if item['archetype'].startswith('旧日') else '盲目',skillMultiplier=item['multiplier'])
    py=SingleBattle(cfg,{}, {'s':skill},groups,seed=5);result=py.run();events=[e for f in result['timeline'] for e in f['events'] if e['type']=='contract_damage']
    expected=[14.1,28.1] if item['category']=='magic' else [7.1,14.1,21.1,28.1]
    assert [e['time'] for e in events]==expected,(name,events)
    if name.startswith(('至高','黑雾')):assert np.isclose(events[0]['damage'],4*events[1]['damage']),(name,events)
    arrays,_,_=prepare(cfg,{}, {'s':skill},groups);out=battle(*arrays,np.array(random.Random(5).getstate()[1],dtype=np.uint32))
    assert np.isclose(out[0],result['total_damage']),(name,out[0],result['total_damage'])
    if name.startswith('饮命者'):
        state=SingleBattle(cfg,{}, {'s':skill},groups,seed=5).state
        baseline=calculate_contract_damage(state)['damage'];state.target_current_hp=state.target['hitPoint']*.5
        assert np.isclose(calculate_contract_damage(state)['damage'],baseline*1.6)
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'contracts.json';p.write_text(json.dumps({'schemaVersion':1,'contracts':presets()[:5]}),encoding='utf-8');store=ContractStore(p)
    assert len(store.read()['contracts'])==14
    data=store.read();data['contracts']=[i for i in data['contracts'] if i['category']!='speed'];store._write(data)
    assert len(store.read()['contracts'])==11
print('PASS: six magic/speed presets, 0.1-second clock, first burst, missing-health tiers, migration and Python/Numba parity')
