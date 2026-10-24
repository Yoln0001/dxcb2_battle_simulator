import sys,copy,tempfile
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import create_app
from backend.api.configurations import copy_regular
from backend.configurations.special import prepare_configuration
from backend.contracts.store import presets as contracts
from backend.rings.store import presets as rings
from engine.runtime.initialization import initialize_battle
from backend.skills.store import SkillError
with tempfile.TemporaryDirectory() as directory:
    app=create_app(configuration_file=Path(directory)/'configurations.json',equipment_file=Path(directory)/'equipment.json')
    contract=next(c for c in contracts() if c['archetype']=='饮命者')
    ring={**next(r for r in rings() if r['kind']=='fire'),'mainAttribute':'magic','secondaryAttribute':'constitution','mainValue':800,'secondaryValue':450,'gainValue':21.2}
    config={'schemaVersion':1,'configurationType':'special','battle':{'duration':180,'simulations':100},'target':{'hitPoint':1e9},'characters':[]}
    for i in range(4):
        config['characters'].append({'name':'角色'+str(i+1),'enabled':True,'firstStrike':True,'job':'寒霜法师','skillGroup':'','stats':{},'equipment':{},'selectedRing':ring,'selectedContract':contract,'contract':'饮命者-力' if i==0 else '不激活','negativeEffect':'群体献祭' if i==0 else '无','skillMultiplier':6.9,'specialSources':{'trophies':{'magic':20},'day10':{'magic':1000,'strength':100,'constitution':100,'speed':1000,'armor':100,'resistance':200},'holy':{},'imprint':{}}})
    store=app.state.configuration_store
    original=store.save({'name':'特殊原件','configuration':config,'libraryId':'default_special'})['item']
    library=store.save_library({'name':'常规备份','configurationType':'regular'})['library']
    request=SimpleNamespace(app=app,query_params={})
    result=copy_regular(original['id'],{'name':'常规副本','libraryId':library['id']},request)
    converted=result['item']['configuration'];expected=prepare_configuration(copy.deepcopy(config),[])
    assert converted['configurationType']=='regular' and result['item']['libraryId']==library['id']
    assert result['activeId']==original['id'] and len(result['configurations'])==2
    assert store.read()['configurations'][0]['configuration']==config
    for old,new in zip(expected['characters'],converted['characters']):
        assert old['stats']==new['stats'] and new['selectedRing']==old['selectedRing'] and new['ringPanelIncluded'] is True and new['selectedContract'] is None and 'specialSources' not in new
    state=initialize_battle(converted,{})
    assert state.contract.name=='饮命者-力'
    assert state.characters[0].base_stats['magic']==converted['characters'][0]['stats']['magic']
    assert state.characters[0].base_stats['strength']==converted['characters'][0]['stats']['strength']
    assert state.characters[0].base_stats['armor']==170
    for item_id,payload in [(original['id'],{'libraryId':'default_special'}),(result['item']['id'],{}),('missing',{})]:
        try:copy_regular(item_id,payload,request);raise AssertionError('invalid conversion accepted')
        except SkillError:pass
    # Dynamic ring mechanics must match before/after conversion, including death.
    from engine.runtime.simulation import SingleBattle
    from engine.runtime.batch import simulate_batch
    import numpy as np
    scenarios=[('fire','sacrifice'),('fire','fragile'),('fire','polluted'),('sky','missingParty'),('earth','fullHealth'),('water','twoEnemies')]
    skill={'job':'寒霜法师','name':'攻击','damageType':'magic','cooldown':0,'hitRate':100,'criticalRate':0,'coefficients':{'magic':1},'effect':None}
    groups={'g':{'job':'寒霜法师','entry':'n','subgroups':[{'id':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]}}
    for kind,restriction in scenarios:
        draft=copy.deepcopy(config);draft['battle']={'duration':20,'simulations':16};draft['seed']=123
        draft['characters'][0]['selectedRing']={**next(r for r in rings() if r['kind']==kind),'restriction':restriction,'mainValue':321,'secondaryValue':123,'gainValue':12.3}
        for c in draft['characters']:c['skillGroup']='g'
        saved=store.save({'name':kind+restriction,'configuration':draft,'libraryId':'default_special','activate':False})['item']
        regular=copy_regular(saved['id'],{'name':kind+restriction+'常规'},request)['item']['configuration']
        special=prepare_configuration(draft,[])
        refs=[]
        for data in (special,regular):
            battle=SingleBattle(data,{}, {'s':skill},groups,seed=5,record_timeline=False);out=battle.run()
            refs.append((out,battle))
        assert refs[0][0]['total_damage']==refs[1][0]['total_damage']
        for a,b in zip(refs[0][1].state.characters,refs[1][1].state.characters):
            assert a.stats==b.stats and a.alive==b.alive and a.current_hp==b.current_hp,(kind,restriction)
        py=simulate_batch(regular,{}, {'s':skill},groups,engine='python',parallel=False)
        compiled=simulate_batch(regular,{}, {'s':skill},groups,engine='numba',workers=2)
        assert np.allclose(py['sorted_damage'],compiled['sorted_damage'],rtol=1e-10)
        assert py['all_alive_battles']==compiled['all_alive_battles']
        assert [c['survived_battles'] for c in py['characters']]==[c['survived_battles'] for c in compiled['characters']]
    print('PASS: sacrifice, fragility, pollution, missing-party, full-health and enemy-count ring effects retained; Python/njit damage and survival agree')
    print('PASS: special-to-regular copy freezes all panel fields without duplicate bonuses, keeps contract state, supports destination libraries, and preserves original/active configuration')
