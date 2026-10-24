from pathlib import Path
import sys, math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.damage import calculate_damage
from engine.runtime.initialization import BattleConfigurationError
stats={'strength':300,'magic':300,'technique':0,'ignoreArmor':50,'ignoreResistance':50}
target={'armor':150,'resistance':150,'physicalVulnerability':1,'magicVulnerability':1,'physicalReduction':25,'magicReduction':40}
for kind,attribute,defense,ignore,factor,expected in [
    ('physical','strength','armor','ignoreArmor','armor_mitigation',75),
    ('magic','magic','resistance','ignoreResistance','resistance_mitigation',60)]:
    skill={'damageType':kind,'coefficients':{attribute:1}}
    r=calculate_damage(stats,skill,target,critical_roll=.5)
    assert math.isclose(r['factors'][factor],1/3)
    assert math.isclose(r['final_damage'],expected)
    other_defense='resistance' if kind=='physical' else 'armor'
    other_ignore='ignoreResistance' if kind=='physical' else 'ignoreArmor'
    assert calculate_damage({**stats,other_ignore:99999},skill,{**target,other_defense:99999},critical_roll=.5)['final_damage']==r['final_damage']
    reduction='physicalReduction' if kind=='physical' else 'magicReduction'
    for value in [0,50]:
        r=calculate_damage(stats,skill,{**target,defense:value,reduction:0},critical_roll=.5)
        assert r['factors'][factor]==1 and r['final_damage']==300
    assert calculate_damage(stats,skill,{**target,reduction:100},critical_roll=.5)['final_damage']==1
    try:
        calculate_damage(stats,skill,{**target,reduction:101},critical_roll=.5)
        raise AssertionError('invalid reduction accepted')
    except BattleConfigurationError:
        pass
print('PASS: independent armor/resistance and ignore stats, 1/3 mitigation, defense clamp, minimum damage')
