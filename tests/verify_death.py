from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.initialization import initialize_battle, BattleConfigurationError
from engine.runtime.contracts import process_sacrifice_ticks,calculate_contract_damage,set_health
from engine.runtime.health import mark_deaths
from engine.runtime.cooldowns import check_action_ready
from engine.runtime.simulation import simulate_single
config={'battle':{'duration':25},'target':{'speed':100,'hitPoint':1000000,'magicVulnerability':1},'characters':[{'job':'寒霜法师','enabled':True,'stats':{'constitution':100,'magic':100,'strength':0,'speed':99,'hitRate':100},'equipment':{},'skillGroup':'g'} for _ in range(4)]}
config['characters'][0].update(contract='旧日支配者-魔',negativeEffect='群体献祭',skillMultiplier=1)
s=initialize_battle(config,{})
s.characters[1].current_hp=0;mark_deaths(s)
assert not s.characters[1].alive and calculate_contract_damage(s)['total_magic']==300
assert not check_action_ready(s.characters[1],10)['ready']
try:set_health(s.characters[1],1000)
except BattleConfigurationError:pass
else:raise AssertionError('dead character revived')
s.characters[0].current_hp=50
process_sacrifice_ticks(s,1)
assert not s.characters[0].alive and not s.contract.active
assert s.characters[2].current_hp==950
process_sacrifice_ticks(s,2)
assert s.characters[2].current_hp==900 and s.characters[3].current_hp==900
assert s.characters[0].current_hp==0 and s.characters[1].current_hp==0
assert len([e for e in s.events if e['type']=='character_died'])==2
skill={'id':'s','name':'攻击','job':'寒霜法师','damageType':'magic','cooldown':0,'hitRate':0,'coefficients':{'magic':1},'effect':None}
group={'job':'寒霜法师','entry':'n','subgroups':[{'id':'sub','nextGroup':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]}
r=simulate_single(config,{}, {'s':skill},{'g':group},seed=1)
assert r['end_reason']=='party_defeated' and r['duration']==20
frame=next(f for f in r['timeline'] if f['time']==20)
assert sum(e['type']=='character_died' for e in frame['events'])==4
assert not any(e['type']=='skill_released' for e in frame['events'])
assert len([e for f in r['timeline'] for e in f['events'] if e['type']=='contract_damage'])==1
assert all(not c['alive'] for c in r['final_state']['characters'])
print('PASS: irreversible death, excluded team stats, owner contract disabled, allies sacrifice persists, all-dead termination')
