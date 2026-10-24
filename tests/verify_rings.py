import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.rings.store import presets,validate_item,gain_value
from backend.configurations.special import calculate
from engine.runtime.initialization import initialize_battle
from engine.runtime.rings import refresh_rings,process_ring_ticks
from engine.runtime.health import reduce_ally_recovery
from engine.runtime.simulation import SingleBattle
from engine.runtime.batch import simulate_batch
ring=presets()[0];ring.update(mainValue=100,secondaryValue=50,gainValue=17.5,gain='magicDamage')
assert gain_value(validate_item(ring))==17.5
config={'battle':{'duration':2,'simulations':2},'target':{'hitPoint':1e9},'characters':[{'enabled':i==0,'job':'寒霜法师','stats':{'magic':100,'strength':1,'technique':100,'speed':10000,'constitution':100,'hitRate':100},'equipment':{},'skillGroup':'g','contract':'不激活','selectedRing':ring if i==0 else None} for i in range(4)]}
s=initialize_battle(config,{});c=s.characters[0];assert c.stats['physicalDamage']==17.5 and c.domain_ring['gain']=='physicalMagicDamage'
assert validate_item({**ring,'gain':'physicalDamage'})['gain']=='physicalMagicDamage'
assert c.stats['technique']==200 and c.stats['speed']==10050 and c.stats['magicDamage']==17.5
refresh_rings(s);assert c.stats['magicDamage']==17.5 and c.stats['physicalDamage']==17.5
ring['restriction']='twoEnemies';s=initialize_battle(config,{});assert s.characters[0].stats['magicDamage']==0
s.target['enemyCount']=2;refresh_rings(s);assert s.characters[0].stats['magicDamage']==17.5
ring['restriction']='missingParty';s=initialize_battle(config,{});assert s.characters[0].stats['magicDamage']==52.5
water=next(i for i in presets() if i['kind']=='water');water.update(mainValue=100,secondaryValue=50,gainValue=10)
stats,_=calculate({'day10':{'technique':100},'selectedRing':water},{},[]);assert stats['technique']==270 and stats['constitution']==50
fire=next(i for i in presets() if i['kind']=='fire');fire.update(mainValue=0,secondaryValue=0,gainValue=10,restriction='polluted');config['characters'][0]['selectedRing']=fire
s=initialize_battle(config,{});assert reduce_ally_recovery(s,100,recipient=s.characters[0])==70
fire['restriction']='fragile';s=initialize_battle(config,{});assert s.characters[0].stats['physicalTakenMultiplier']==1.3 and s.characters[0].stats['magicTakenMultiplier']==1.3 and s.characters[0].stats.get('dotTakenMultiplier',1)==1
fire['restriction']='sacrifice';s=initialize_battle(config,{});s.time=1;process_ring_ticks(s);assert s.characters[0].current_hp==925
s.time=14;process_ring_ticks(s);assert s.characters[0].current_hp==0
skill={'job':'寒霜法师','name':'测试','damageType':'magic','cooldown':0,'hitRate':100,'criticalRate':0,'coefficients':{'magic':1},'effect':None}
groups={'g':{'job':'寒霜法师','entry':'n','subgroups':[{'id':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]}}
battle=SingleBattle(config,{}, {'s':skill},groups,seed=5);result=battle.run();assert any(e['type']=='sacrifice_tick' and e['time']==1 for f in result['timeline'] for e in f['events'])
assert simulate_batch(config,{}, {'s':skill},groups,parallel=False)['engine']=='numba_njit'
print('PASS: manual values, base addition, special panel, conditions, missing-party stacks, recovery penalties, lethal second ticks and compiled batch execution')
