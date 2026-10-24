from copy import deepcopy
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.initialization import initialize_battle, BattleConfigurationError
from engine.runtime.amplification import attack_snapshot


def equip(item_id, slot, ratio, recipient='self', attribute='magic'):
    return {'id':item_id,'name':item_id,'category':slot,'weaponJob':'','effectName':item_id,'startingBuff':{'enabled':True,'recipient':recipient,'coefficients':{'strength':0,'magic':ratio,'technique':0,'speed':0},'target':attribute}}


def team():
    return {'target':{'hitPoint':1000000},'characters':[{'name':f'角色{i+1}','enabled':True,'job':'寒霜法师','stats':{'strength':100,'magic':10000,'technique':200,'speed':300,'constitution':1000},'equipment':{}} for i in range(4)]}

config=team();config['characters'][0]['equipment']={'weapon':'a','accessory2':'b'};library={'a':equip('a','weapon',.5),'b':equip('b','accessory',.4)}
original=deepcopy(config);saved_library=deepcopy(library);state=initialize_battle(config,library);c=state.characters[0]
assert c.stats['magic']==21000 and [b.amount for b in c.buffs]==[5000,6000]
assert [b.source_stats['magic'] for b in c.buffs]==[10000,15000]
assert config==original and library==saved_library
assert all(char.stats['magic']==10000 for char in state.characters[1:])
attack=attack_snapshot(c,[{'kind':'amplify','conversions':[{'enabled':True,'target':'magic','coefficients':{'magic':1}}]}]);assert attack['magic']==42000 and c.stats['magic']==21000
assert initialize_battle(config,library).to_dict()==state.to_dict()
# Global source and slot order, including team buffs feeding later sources.
config=team();library={}
for i,char in enumerate(config['characters']):
    for slot,category in [('weapon','weapon'),('armor','armor'),('accessory1','accessory'),('accessory2','accessory')]:
        key=f'{i}_{slot}';char['equipment'][slot]=key;library[key]=equip(key,category,.01)
state=initialize_battle(config,library);assert [(e['source_character'],e['source_slot']) for e in state.events]==[(i,slot) for i in range(1,5) for slot in ('weapon','armor','accessory1','accessory2')]
config=team();config['characters'][0]['equipment']={'weapon':'team'};config['characters'][1]['equipment']={'weapon':'self'};library={'team':equip('team','weapon',.5,'allAllies'),'self':equip('self','weapon',.4)}
state=initialize_battle(config,library);assert state.characters[1].stats['magic']==21000;assert [b.amount for b in state.characters[1].buffs]==[5000,6000];assert state.characters[0].stats['magic']==15000
config['characters'][3]['enabled']=False;assert initialize_battle(config,library).characters[3].buffs==[]
library['team']['startingBuff']['enabled']=False;assert initialize_battle(config,library).characters[0].stats['magic']==10000
library['team']['startingBuff']['enabled']=True;library['team']['startingBuff']['recipient']='singleAlly'
try:initialize_battle(config,library)
except BattleConfigurationError:pass
else:raise AssertionError('single ally needs explicit target')
assert initialize_battle(config,library,{(1,'weapon'):2}).characters[1].stats['magic']==21000
snapshot=attack_snapshot(state.characters[0],[{'kind':'amplify','conversions':[{'enabled':True,'target':'magic','coefficients':{'lostHitPoint':.5}}]}],{'maximum':10000,'current':6000});assert snapshot['magic']==17000
print('PASS: sequential compound buffs, independent amounts, source snapshots, four-character/slot order, team recipients, disabled states, replay, config immutability and temporary attack amplification')
