"""Damage factors using the attack-time attribute snapshot.

Physical damage uses armor; magical damage uses resistance.
Hit/miss and proc rolls belong to the action scheduler.
"""
import random
from .initialization import nonnegative, BattleConfigurationError

RACES = {'灵体':'spirit', '人形':'human', '野兽':'beast', '龙':'dragon', '傀儡':'construct', '黑暗':'other', '其他':'other', '未指定':'none', '无特攻':'none'}


def calculate_damage_terms(attack_stats, skill, target, *, critical_roll=None, rng=None):
    damage_type = skill.get('damageType')
    if damage_type not in ('physical', 'magic'):
        raise BattleConfigurationError('回复技能需单独结算，不能使用伤害公式')
    if not isinstance(attack_stats, dict) or not isinstance(skill.get('coefficients'), dict) or not isinstance(target, dict):
        raise BattleConfigurationError('伤害计算配置无效')
    base_damage = 0.0
    contributions = {}
    for attribute, coefficient in skill['coefficients'].items():
        coefficient = nonnegative(coefficient, '技能系数')
        if coefficient == 0:
            continue
        if attribute not in attack_stats:
            raise BattleConfigurationError('缺少技能伤害所需属性：' + attribute)
        amount = nonnegative(attack_stats[attribute], attribute) * coefficient
        contributions[attribute] = nonnegative(amount, '技能伤害分项')
        base_damage += amount
    base_damage = nonnegative(base_damage, '技能基础伤害')
    damage_key = 'physicalDamage' if damage_type == 'physical' else 'magicDamage'
    imprint_key = 'finalPhysicalDamage' if damage_type == 'physical' else 'finalMagicDamage'
    vulnerability_key = 'physicalVulnerability' if damage_type == 'physical' else 'magicVulnerability'
    damage_factor = 1 + nonnegative(attack_stats.get(damage_key, 0), '面板伤害百分数')/100
    technique_rate = nonnegative(attack_stats.get('technique', 0), '攻击瞬间技巧')/20
    skill_rate = nonnegative(skill.get('criticalRate', 0), '技能暴击率')
    panel_rate = nonnegative(attack_stats.get('criticalRate', 0), '面板暴击率')
    raw_rate = nonnegative(skill_rate + panel_rate + technique_rate, '总暴击率')
    probability = min(raw_rate/100, 1.0)
    if critical_roll is None:
        critical_roll = (rng or random).random()
    critical_roll = nonnegative(critical_roll, '暴击随机值')
    if critical_roll >= 1:
        raise BattleConfigurationError('暴击随机值必须处于[0,1)')
    critical = critical_roll < probability
    critical_factor = 1.5 + nonnegative(attack_stats.get('criticalMultiplier', 0), '暴伤系数增加百分数')/100 if critical else 1.0
    bonus = skill.get('raceBonus', {'race':'none', 'multiplier':0})
    if not isinstance(bonus, dict):
        raise BattleConfigurationError('技能种族特攻配置无效')
    bonus_race = RACES.get(bonus.get('race'), bonus.get('race'))
    target_race = RACES.get(target.get('race'), target.get('race'))
    race_matched = bonus_race not in (None, '', 'none') and bonus_race == target_race
    race_factor = 1 + nonnegative(bonus.get('multiplier', 0), '种族特攻增幅倍率') if race_matched else 1.0
    imprint_factor = 1 + nonnegative(attack_stats.get(imprint_key, 0), '辉印伤害百分数')/100
    vulnerability_factor = nonnegative(target.get(vulnerability_key,1), '目标易伤系数')
    damage = nonnegative(base_damage * damage_factor * critical_factor * race_factor * imprint_factor * vulnerability_factor, '减伤前伤害')
    return {'damage_type': damage_type, 'base_contributions': contributions, 'critical': critical,
            'critical_rate': {'skill_percent': skill_rate, 'panel_percent': panel_rate,
                              'technique_percent': technique_rate, 'raw_percent': raw_rate,
                              'probability': probability, 'roll': critical_roll},
            'race_matched': race_matched,
            'factors': {'skill_damage': base_damage, 'damage_bonus': damage_factor,
                        'critical': critical_factor, 'race_bonus': race_factor,
                        'imprint': imprint_factor, 'target_vulnerability': vulnerability_factor},
            'pre_mitigation_damage': damage,
            'pending_factors': ['armor_mitigation' if damage_type == 'physical' else 'resistance_mitigation', 'physical_magic_reduction']}


def calculate_damage(attack_stats, skill, target, *, critical_roll=None, rng=None):
    """Defense factor = 50/(max(defense - ignored defense, 0) + 50)."""
    result = calculate_damage_terms(attack_stats, skill, target, critical_roll=critical_roll, rng=rng)
    physical = result['damage_type'] == 'physical'
    defense_key = 'armor' if physical else 'resistance'
    ignore_key = 'ignoreArmor' if physical else 'ignoreResistance'
    factor_key = 'armor_mitigation' if physical else 'resistance_mitigation'
    defense = nonnegative(target.get(defense_key, 0), '目标护甲' if physical else '目标抗性')
    ignored = nonnegative(attack_stats.get(ignore_key, 0), '无视护甲' if physical else '无视抗性')
    effective = max(defense - ignored, 0.0)
    defense_factor = 50/(effective+50)
    reduction_key = 'physicalReduction' if result['damage_type'] == 'physical' else 'magicReduction'
    reduction_percent = nonnegative(target.get(reduction_key, 0), '目标伤害减免百分数')
    if reduction_percent > 100:
        raise BattleConfigurationError('目标物理或魔法减伤必须处于0到100%')
    reduction_factor = 1 - reduction_percent/100
    result['factors'][factor_key] = defense_factor
    result['factors']['type_reduction'] = reduction_factor
    result['effective_armor' if physical else 'effective_resistance'] = effective
    result['raw_damage'] = nonnegative(result['pre_mitigation_damage']*defense_factor*reduction_factor, '最终伤害')
    result['final_damage'] = minimum_damage(result['raw_damage'], reduction_percent)
    result['pending_factors'] = []
    return result


def minimum_damage(raw_damage, reduction_percent):
    """Successful damage always has a floor of 1, including 100% reduction."""
    raw_damage = nonnegative(raw_damage, '伤害')
    reduction_percent = nonnegative(reduction_percent, '减伤百分数')
    if reduction_percent > 100:
        raise BattleConfigurationError('减伤必须处于0到100%')
    return max(1.0, raw_damage)


def calculate_burn_damage(source_stats, effect, target):
    """One burn or life-loss tick. Caller supplies the chosen attribute snapshot.

    Snapshot timing, tick interval and stacking are handled by the scheduler.
    """
    if not isinstance(effect, dict) or effect.get('kind') != 'debuff' or effect.get('type') not in ('burn', 'lifeLoss'):
        raise BattleConfigurationError('需要灼烧技能特效配置')
    coefficients = effect.get('coefficients')
    if not isinstance(coefficients, dict):
        raise BattleConfigurationError('灼烧属性倍率配置无效')
    contributions = {}
    for attribute, coefficient in coefficients.items():
        coefficient = nonnegative(coefficient, '灼烧技能系数')
        if coefficient:
            if attribute not in source_stats:
                raise BattleConfigurationError('缺少灼烧所需属性：'+attribute)
            contributions[attribute] = nonnegative(source_stats[attribute], attribute)*coefficient
    base = nonnegative(effect.get('baseValue', 0), '灼烧基础值')+sum(contributions.values())
    reduction = nonnegative(target.get('dotReduction', 0), '目标持续减伤百分数')
    if reduction > 100:
        raise BattleConfigurationError('目标持续减伤必须处于0到100%')
    factors = {
        'skill_damage': base,
        'damage_bonus': 1+nonnegative(source_stats.get('dotDamage', 0), '持续伤害百分数')/100,
        'imprint': 1+nonnegative(source_stats.get('finalDotDamage', 0), '辉印持伤百分数')/100,
        'target_vulnerability': nonnegative(target.get('dotVulnerability', 1), '持续易伤系数'),
        'type_reduction': 1-reduction/100,
    }
    raw = 1.0
    for value in factors.values():
        raw *= value
    raw = nonnegative(raw, '灼烧伤害')
    return {'damage_type': 'dot', 'base_contributions': contributions, 'factors': factors,
            'raw_damage': raw, 'final_damage': minimum_damage(raw, reduction)}


def calculate_equipment_damage(attack_stats, effect, target, damage_type):
    """Equipment true damage keeps type bonus, imprint, vulnerability, reduction."""
    if damage_type not in ('physical','magic'):
        raise BattleConfigurationError('真伤特效需要指定物理或魔法触发类型')
    physical = damage_type == 'physical'
    base = sum(nonnegative(attack_stats.get(k,0), k)*nonnegative(v,'装备伤害系数')
               for k,v in effect['coefficients'].items())
    reduction = nonnegative(target.get('physicalReduction' if physical else 'magicReduction',0),'目标减伤')
    if reduction > 100:
        raise BattleConfigurationError('目标减伤必须处于0到100%')
    factors = {
        'skill_damage':base,
        'damage_bonus':1+nonnegative(attack_stats.get('physicalDamage' if physical else 'magicDamage',0),'面板伤害百分数')/100,
        'imprint':1+nonnegative(attack_stats.get('finalPhysicalDamage' if physical else 'finalMagicDamage',0),'辉印百分数')/100,
        'target_vulnerability':nonnegative(target.get('physicalVulnerability' if physical else 'magicVulnerability',1),'目标易伤'),
        'type_reduction':1-reduction/100,
    }
    raw=1.0
    for factor in factors.values():raw*=factor
    return {'factors':factors,'raw_damage':raw,'final_damage':minimum_damage(raw,reduction)}


def calculate_hit_chance(attack_stats, skill, target):
    speed = nonnegative(target.get('speed',43750), '目标速度')
    if speed == 0:
        raise BattleConfigurationError('攻击命中计算要求目标速度大于0')
    technique_percent = nonnegative(attack_stats.get('technique',0),'攻击瞬间技巧')/speed*30
    raw_percent = (nonnegative(skill.get('hitRate',0),'技能命中率')
                   +nonnegative(attack_stats.get('hitRate',0),'面板命中率')-nonnegative(attack_stats.get('contractHitPenalty',0),'契约命中降低')
                   -nonnegative(target.get('dodgeRate',0),'目标闪避率')+technique_percent)
    return {'raw_percent':raw_percent,'technique_percent':technique_percent,
            'probability':min(1.0,max(0.0,raw_percent/100))}
