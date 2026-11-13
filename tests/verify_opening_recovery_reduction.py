from pathlib import Path
import sys,copy,runpy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.initialization import initialize_battle
from engine.runtime.health import apply_enemy_recovery
from backend.equipment.validation import validate_equipment
ns=runpy.run_path(str(Path(__file__).with_name('verify_opening_dot.py')))
config=copy.deepcopy(ns['cfg']);gear=copy.deepcopy(ns['gear'])
gear['a'].pop('battleStartEffects',None)
gear['a']['startingDebuffs']['entries']=[{'name':'削弱','healingReduction':20},{'name':'削弱','healingReduction':30}]
gear['a']=validate_equipment(gear['a'])
state=initialize_battle(config,gear)
assert abs(state.target['recoveryMultiplier']-.56)<1e-12
assert abs(state.target['combinedHealingReduction']-44)<1e-12
assert len(state.target['equipmentRecoveryDebuffs'])==2
for kind in ('healing','lifesteal'):
    state.target_current_hp=1000
    assert abs(apply_enemy_recovery(state,1000,kind=kind)-560)<1e-9
    assert abs(state.target_current_hp-1560)<1e-9
# Multiple characters and equipment slots stack in the same way.
config['characters'][1]['enabled']=True;config['characters'][1]['equipment']={'armor':'a'}
assert abs(initialize_battle(config,gear).target['recoveryMultiplier']-.56**2)<1e-12
gear['a']['startingDebuffs']['entries'].append({'name':'完全抑制','healingReduction':100})
state=initialize_battle(config,gear);state.target_current_hp=1000
assert apply_enemy_recovery(state,1000)==0
config['target']['immuneNegativeEffects']=True
assert initialize_battle(config,gear).target['recoveryMultiplier']==1
for invalid in (-1,101,float('nan')):
    broken=copy.deepcopy(gear['a']);broken.pop('battleStartEffects',None);broken['startingDebuffs']['entries']=[{'healingReduction':invalid}]
    try:validate_equipment(broken)
    except ValueError:pass
    else:raise AssertionError(invalid)
print('PASS: multiplicative recovery/lifesteal reduction, same-name stacking, multiple wearers, immunity, 100% suppression and range validation')
