from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.initialization import initialize_battle, BattleConfigurationError
from engine.runtime.cooldowns import check_action_ready, schedule_after_action
config={'characters':[{'enabled':True,'stats':{'strength':200,'speed':99,'unload':0},'equipment':{}} for _ in range(4)]}
s=initialize_battle(config,{})
c=s.characters[0]
assert not check_action_ready(c,3.4)['ready']
s.time=3.5
schedule_after_action(s,1,2)
assert c.next_action_at==9
assert not check_action_ready(c,8.5)['ready']
c.stats['strength']=0
assert check_action_ready(c,8.5)['ready']
assert c.next_action_at==7
s.time=8.5
schedule_after_action(s,1,2)
c.stats['strength']=200
assert not check_action_ready(c,12)['ready']
assert check_action_ready(c,14)['ready']
c.stats['strength']=0
s.time=14
schedule_after_action(s,1,-10)
assert not check_action_ready(c,14.4)['ready']
assert check_action_ready(c,14.5)['ready']
print('PASS: current ratio advances/delays readiness, release clock resets, 0.5s floor')
