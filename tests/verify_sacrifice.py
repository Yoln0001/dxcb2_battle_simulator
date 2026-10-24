from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.initialization import initialize_battle
from engine.runtime.contracts import attach_group_sacrifice,set_health,process_sacrifice_ticks
config={'characters':[{'enabled':i!=3,'stats':{'magic':10000},'equipment':{}} for i in range(4)]}
state=initialize_battle(config,{})
for character in state.characters:set_health(character,10000)
attach_group_sacrifice(state,1);attach_group_sacrifice(state,2)
assert len(state.characters[0].debuffs)==1 and not state.characters[3].debuffs
assert state.characters[0].current_hp==10000
process_sacrifice_ticks(state,.999);assert state.characters[0].current_hp==10000
process_sacrifice_ticks(state,1);assert state.characters[0].current_hp==9500
process_sacrifice_ticks(state,2);assert state.characters[0].current_hp==9000
process_sacrifice_ticks(state,5);assert state.characters[0].current_hp==7500
assert [e['time'] for e in state.events if e['type']=='sacrifice_tick' and e['target_character']==1]==[1,2,3,4,5]
assert state.characters[3].current_hp==10000
print('PASS: delayed first tick, 5% maximum HP each second, independent character health and one negative buff per recipient')

config={'characters':[{'enabled':True,'job':'岩浆法师','stats':{'magic':10000,'constitution':1000},'equipment':{},'contract':'旧日支配者-魔' if i==0 else '不激活','negativeEffect':'群体献祭'} for i in range(4)]}
config['characters'][0]['equipment']={'weapon':'start'}
library={'start':{'id':'start','name':'开战杖','category':'weapon','weaponJob':'法师','effectName':'开战魔力','startingBuff':{'enabled':True,'recipient':'self','coefficients':{'strength':0,'magic':.5,'technique':0,'speed':0},'target':'magic'}}}
state=initialize_battle(config,library);assert all(c.maximum_hp==10000 and len(c.debuffs)==1 for c in state.characters);assert state.events[0]['type']=='starting_buff';assert all(e['type']=='debuff_applied' for e in state.events[1:]);assert state.characters[0].stats['magic']==15000
process_sacrifice_ticks(state,1);assert state.characters[0].current_hp==9500 and state.characters[0].stats['hitPoint']==9500
config['characters'][1]['contract']='旧日支配者-魔'
from engine.runtime.initialization import BattleConfigurationError
try:initialize_battle(config,library)
except BattleConfigurationError:pass
else:raise AssertionError('only one contract allowed')
print('PASS: constitution x10 health, contract single owner, all equipment buffs precede sacrifice application')
