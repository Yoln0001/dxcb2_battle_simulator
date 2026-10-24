from pathlib import Path
import sys,random,ast,time
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.compiled.prepare import prepare
from engine.runtime.compiled.kernel import battle,chunk
from engine.runtime.compiled.rng import uniform,shuffle
from engine.runtime.simulation import SingleBattle

def fixture():
    tree=ast.parse((Path(__file__).parent/'benchmark_batch.py').read_text(encoding='utf-8'))
    main=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    body=[]
    for node in main.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='result' for t in node.targets):break
        body.append(node)
    namespace={};exec(compile(ast.Module(body=body,type_ignores=[]),'fixture','exec'),namespace)
    return namespace['config'],{},namespace['skills'],namespace['groups']

def main():
    rng=random.Random(123);state=np.array(rng.getstate()[1],dtype=np.uint32)
    for _ in range(5000):assert uniform(state)==rng.random()
    for n in range(1,40):
        actual=np.arange(n,dtype=np.float64).reshape(-1,1);expected=list(range(n));shuffle(state,actual,n);rng.shuffle(expected);assert actual[:,0].tolist()==expected
    print('PASS: CPython-compatible MT19937 and shuffle',flush=True)
    config,equipment,skills,groups=fixture();arrays,keys,warnings=prepare(config,equipment,skills,groups)
    started=time.perf_counter()
    for seed in range(30):
        py=SingleBattle(config,equipment,skills,groups,seed=seed,record_timeline=False);reference=py.run()
        state=np.array(random.Random(seed).getstate()[1],dtype=np.uint32)
        result=battle(*arrays,state)
        assert np.allclose(result[2],reference['character_damage'],rtol=1e-10,atol=1e-6),(seed,result[2],reference['character_damage'])
        assert np.isclose(result[0],reference['total_damage'],rtol=1e-10),(seed,result[0],reference['total_damage'])
        assert result[1]==(py.state.target_current_hp<=0)
        assert np.allclose(result[5],[c.current_hp for c in py.state.characters],rtol=1e-10)
    print('PASS: 30 seeded rich battles: damage, health and pass match; compile+check',round(time.perf_counter()-started,3),flush=True)
    # Dynamic cooldown, fractional expiry, immediate actions and deaths.
    tree=ast.parse((Path(__file__).parent/'verify_fast_batch.py').read_text(encoding='utf-8'))
    statements=[]
    for node in tree.body:
        if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and node.target.id=='seed':break
        if not isinstance(node,(ast.Import,ast.ImportFrom)):statements.append(node)
    import copy
    ns={'copy':copy,'sys':sys,'Path':Path,'__file__':str(Path(__file__))};exec(compile(ast.Module(body=statements,type_ignores=[]),'dynamic_fixture','exec'),ns)
    for low_heal in (False,True):
        cfg=copy.deepcopy(ns['config']);lib=copy.deepcopy(ns['skills'])
        if low_heal:cfg['target']['hitPoint']=2000000;lib['heal']['coefficients']={'magic':.01}
        arr,proc_keys,_=prepare(cfg,{'quick':ns['item']},lib,ns['groups'])
        for seed in range(30):
            py=SingleBattle(cfg,{'quick':ns['item']},lib,ns['groups'],seed=seed,record_timeline=False);ref=py.run()
            out=battle(*arr,np.array(random.Random(seed).getstate()[1],dtype=np.uint32))
            assert np.allclose(out[2],ref['character_damage'],rtol=1e-10),(low_heal,seed,out[2],ref['character_damage'])
            assert out[1]==(py.state.target_current_hp<=0)
            assert np.allclose(out[5],[c.current_hp for c in py.state.characters],rtol=1e-10)
            assert out[6].tolist()==[int(c.enabled and c.alive) for c in py.state.characters]
            for c in range(4):
                expected=sum(e['count'] for e in ref['effect_counts'][c])
                assert sum(out[3][p] for p,key in enumerate(proc_keys) if key[0]==c)==expected
    print('PASS: 60 dynamic cooldown/expiry/immediate/death battles',flush=True)
    # Read current saved libraries without modifying them; exercise real equipment and graphs.
    import json
    root=Path(__file__).resolve().parents[1]
    items=json.loads((root/'data/equipment.json').read_text(encoding='utf-8'))['equipment']
    saved_skills=json.loads((root/'data/skills.json').read_text(encoding='utf-8'))['skills']
    saved_groups=json.loads((root/'data/skill_groups.json').read_text(encoding='utf-8'))['groups']
    if len(items)>=13 and len(saved_groups)>=5:
        eq={e['id']:e for e in items};sl={s['id']:s for s in saved_skills};gl={g['id']:g for g in saved_groups}
        cfg={'battle':{'duration':200},'target':{'hitPoint':175000000,'speed':43750,'resistance':0,'armor':0,'magicVulnerability':1.12,'physicalVulnerability':1,'dotVulnerability':1,'race':'灵体'},'characters':[]}
        for c,gindex in enumerate([2,4,0,1]):
            stats={'constitution':[3916,3370,3464,2967][c],'magic':[13121,12077,12578,11523][c],'technique':[6074,6110,6399,6502][c],'strength':[236,612,197,527][c],'speed':[1170,1099,1234,1370][c],'weaponPower':[1906,764,1969,798][c],'unload':[300,2300,300,800][c],'hitRate':[54.5,53.3,52.5,58.5][c],'magicDamage':[24.8,24.8,26,24.8][c],'finalMagicDamage':[5,5,8,8][c],'criticalMultiplier':[27,17.4,30,59][c],'abnormalBonus':[70,20,0,0][c],'healingBonus':45,'finalHealingBonus':15}
            positions=[[2,3,1,4,12],[0,6,1,4,12],[5,3,7,8,12],[9,6,11,10,12]][c]
            row={'enabled':True,'job':saved_groups[gindex]['job'],'stats':stats,'equipment':{},'skillGroup':saved_groups[gindex]['id']}
            from backend.equipment.jobs import JOB_FAMILIES
            for slot,index in zip(('weapon','armor','accessory1','accessory2','stone'),positions):
                category='accessory' if slot.startswith('accessory') else slot
                eligible=[e for e in items if e['id'] not in row['equipment'].values() and e['category']==category and (slot!='weapon' or not e.get('weaponJob') or e['weaponJob']==JOB_FAMILIES[row['job']])]
                preferred=items[index]
                row['equipment'][slot]=preferred['id'] if preferred in eligible else (eligible[0]['id'] if eligible else '')
            cfg['characters'].append(row)
        cfg['characters'][2].update(contract='旧日支配者-魔',negativeEffect='群体献祭',skillMultiplier=5.6)
        arr,pk,_=prepare(cfg,eq,sl,gl)
        for seed in range(100):
            py=SingleBattle(cfg,eq,sl,gl,seed=seed,record_timeline=False);ref=py.run()
            out=battle(*arr,np.array(random.Random(seed).getstate()[1],dtype=np.uint32))
            assert np.allclose(out[2],ref['character_damage'],rtol=1e-10),(seed,out[2],ref['character_damage'])
            assert out[1]==(py.state.target_current_hp<=0)
            assert np.allclose(out[5],[c.current_hp for c in py.state.characters],rtol=1e-10)
            expected={(c,e['slot'],e['equipment_id'],e['name'],e['trigger_type'],e['kind']):e['count'] for c,rows in enumerate(ref['effect_counts']) for e in rows}
            for p,key in enumerate(pk):assert out[3][p]==expected.get(key,0),(seed,key,out[3][p],expected.get(key,0))
        print('PASS: 100 seeded battles from saved skill/equipment/group libraries, including conditional jumps',flush=True)
    states=np.array([random.Random(i).getstate()[1] for i in range(16)],dtype=np.uint32)
    chunk(*arrays,states)
    print('PASS: parallel njit chunk compiled',flush=True)
    from engine.runtime.batch import simulate_batch
    cfg={'seed':42,'battle':{'duration':10,'simulations':200},'target':{'speed':10000,'hitPoint':18000,'magicVulnerability':1.12},'characters':[{'job':'法师','enabled':True,'stats':{'constitution':100,'magic':1000,'technique':200,'strength':100,'speed':500,'hitRate':55},'equipment':{},'skillGroup':'g'} for _ in range(4)]}
    cfg['characters'][0].update(contract='旧日支配者-魔',negativeEffect='群体献祭',skillMultiplier=2)
    skill={'name':'火球','job':'法师','damageType':'magic','cooldown':1.8,'hitRate':30,'criticalRate':20,'coefficients':{'magic':2},'effect':{'kind':'debuff','type':'burn','duration':6,'applicationRate':80,'baseValue':1,'coefficients':{'technique':.25}}}
    group={'job':'法师','entry':'n','subgroups':[{'id':'sub','nextGroup':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]}
    eq={};sl={'s':skill};gl={'g':group}
    ref=simulate_batch(cfg,eq,sl,gl,engine='python',parallel=False)
    out=simulate_batch(cfg,eq,sl,gl,engine='numba',workers=4)
    assert 0<ref['passed_battles']<200
    assert out['passed_battles']==ref['passed_battles']
    assert np.allclose(out['sorted_damage'],ref['sorted_damage'],rtol=1e-10)
    for a,b in zip(out['characters'],ref['characters']):
        assert np.isclose(a['expected_damage'],b['expected_damage'],rtol=1e-10)
        assert a['effects']==b['effects']
    print('PASS: 200 mixed-pass batch has identical pass count and consistent damage/effect statistics',flush=True)

if __name__=='__main__':main()
