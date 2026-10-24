"""Temporary amplification of one action; never mutate persistent character stats."""
from copy import deepcopy
from .initialization import nonnegative, BattleConfigurationError


def attack_snapshot(character, triggered_effects, health=None):
    """Effects passed here have already triggered; probability checks belong to the scheduler.

    All enabled rows in one effect read one snapshot, avoiding dependence on row order.
    Multiple effects apply sequentially. health optionally contains maximum/current HP.
    """
    if health is None and character.maximum_hp is not None and character.current_hp is not None:
        health = {'maximum': character.maximum_hp, 'current': character.current_hp}
    stats = deepcopy(character.stats)
    for effect in triggered_effects:
        if effect.get('kind') != 'amplify':
            raise BattleConfigurationError('攻击属性快照只处理增幅特效')
        source = deepcopy(stats)
        changes = {}
        for row in effect['conversions']:
            if not row['enabled']:
                continue
            amount = 0.0
            for attr, coefficient in row['coefficients'].items():
                coefficient = nonnegative(coefficient, '攻击增幅系数')
                if not coefficient:
                    continue
                if attr == 'lostHitPoint':
                    if health is None:
                        raise BattleConfigurationError('已损失血量增幅需要最大及当前血量')
                    maximum = nonnegative(health['maximum'], '最大血量')
                    current = nonnegative(health['current'], '当前血量')
                    if current > maximum:
                        raise BattleConfigurationError('当前血量不能超过最大血量')
                    value = maximum - current
                else:
                    if attr not in source:
                        raise BattleConfigurationError('缺少攻击增幅所需属性：' + attr)
                    value = source[attr]
                amount += value * coefficient
            changes[row['target']] = nonnegative(amount, '攻击增幅结果')
        for attr, amount in changes.items():
            stats[attr] = nonnegative(stats.get(attr, 0) + amount, '攻击属性')
    return stats
