import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.rings.store import presets
from backend.configurations.special import calculate,prepare_configuration
from engine.runtime.initialization import initialize_battle
from engine.runtime.rings import refresh_rings
for gain,keys in [('physicalMagicDamage',['physicalDamage','magicDamage']),('hitRate',['hitRate']),('dotDamage',['dotDamage'])]:
 ring=next(r for r in presets() if r['kind']=='sky');ring.update(gain=gain,gainValue=13,mainValue=0,secondaryValue=0)
 sources={'day10':{'constitution':100},'selectedRing':ring}
 values,_=calculate(sources,{},[]);assert all(values[k]==0 for k in keys)
 ring['restriction']='twoEnemies';assert calculate(sources,{},[])[0][keys[0]]==0
 assert calculate(sources,{},[],context={'enemyCount':2})[0][keys[0]]==0
 ring['restriction']='missingParty';assert calculate(sources,{},[],context={'partySize':2})[0][keys[0]]==0
 ring['restriction']='none'
 config={'configurationType':'special','battle':{'duration':1},'target':{'hitPoint':10000},'characters':[{'enabled':True,'equipment':{},'job':'','contract':'不激活','selectedRing':ring if i==0 else None,'specialSources':{'day10':{'constitution':100}}} for i in range(4)]}
 prepared=prepare_configuration(config,[]);assert all(prepared['characters'][0]['stats'][k]==0 for k in keys)
 state=initialize_battle(prepared,{});assert all(state.characters[0].stats[k]==13 for k in keys)
 refresh_rings(state);assert all(state.characters[0].stats[k]==13 for k in keys)
 assert prepare_configuration(prepared,[])['characters'][0]['stats']==prepared['characters'][0]['stats']
for gain,key in [('abnormalBonus','abnormalBonus'),('healingBonus','healingBonus'),('dodgeRate','dodgeRate')]:
 ring=next(r for r in presets() if r['kind']=='water');ring.update(gain=gain,gainValue=7)
 assert calculate({'selectedRing':ring},{},[])[0][key]==0
ring=next(r for r in presets() if r['kind']=='earth');ring.update(gain='doubleBlock',gainValue=100,restriction='fullHealth')
values,_=calculate({'selectedRing':ring},{},[]);assert values['physicalBlock']==0 and values['magicBlock']==0
print('PASS: ring panel gains and conditions; frontend/backend save-preview design counts gain only once in live battle')
