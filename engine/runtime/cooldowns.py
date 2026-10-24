"""Action cooldown rules: fixed 1.5s + skill cooldown + floored strength/speed ratio."""
import math
from functools import lru_cache
from decimal import Decimal, ROUND_FLOOR, localcontext
from .initialization import nonnegative, BattleConfigurationError

FIXED_COOLDOWN = 1.5


def strength_speed_ratio(strength, unload, speed):
    strength = nonnegative(strength, '力量')
    unload = nonnegative(unload, '卸负')
    speed = nonnegative(speed, '速度')
    # Decimal input avoids flooring an exact 0.3 to 0.2 due to binary roundoff.
    with localcontext() as context:
        context.prec = 50
        numerator = max(Decimal(str(strength))-Decimal(str(unload)), Decimal(1))
        denominator = Decimal(str(speed))+Decimal(1)
        tenths = (numerator/denominator*10).to_integral_value(rounding=ROUND_FLOOR)
        return min(3.0, nonnegative(float(tenths/10), '力速比'))


def action_cooldown(character, skill_cooldown):
    if isinstance(skill_cooldown, bool) or not isinstance(skill_cooldown, (int, float)) or not math.isfinite(skill_cooldown):
        raise BattleConfigurationError('技能冷却必须为有限数值')
    stats = character.stats
    ratio = strength_speed_ratio(stats.get('strength', 0), stats.get('unload', 0), stats.get('speed', 0))
    total = max(0.5, float(Decimal('1.5')+Decimal(str(skill_cooldown))+Decimal(str(stats.get('contractCooldown',0)))+Decimal(str(ratio))))
    return {'fixed': FIXED_COOLDOWN, 'skill': skill_cooldown, 'strength_speed_ratio': ratio, 'total': total}


def schedule_after_action(state, character_index, skill_cooldown, *, released_at=None, check_ready=True):
    """Record release time and skill cooldown; next_action_at is a current estimate."""
    if type(character_index) is not int or not 1 <= character_index <= len(state.characters):
        raise BattleConfigurationError('行动角色无效')
    character = state.characters[character_index-1]
    if not character.enabled or not character.alive:
        raise BattleConfigurationError('未参战角色不能行动')
    now = state.time if released_at is None else nonnegative(released_at, '释放时间')
    if now != state.time:
        raise BattleConfigurationError('请先推进战斗状态到技能释放时间')
    if check_ready and not check_action_ready(character, now)["ready"]:
        raise BattleConfigurationError('角色行动冷却尚未结束')
    details = action_cooldown(character, skill_cooldown)
    next_action = nonnegative(float(Decimal(str(now))+Decimal(str(details['total']))), '下次行动时间')
    character.last_action_at = now
    character.last_skill_cooldown = skill_cooldown
    character.next_action_at = next_action
    state.events.append({'time': now, 'type': 'action_scheduled', 'character': character_index,
                         'next_action_at': next_action, 'cooldown': details})
    return details


def check_action_ready(character, now):
    """Recalculate on every 0.1s check using current persistent attributes.

    Before the first action, the clock starts at 0 and skill cooldown is zero.
    next_action_at is an estimate, never a locked deadline.
    """
    now = nonnegative(now, '战斗时间')
    start = 0.0 if character.last_action_at is None else character.last_action_at
    if now < start:
        raise BattleConfigurationError('检查时间不能早于上次技能释放时间')
    skill = 0.0 if character.last_action_at is None else character.last_skill_cooldown
    details = action_cooldown(character, skill)
    if character.last_action_at is None and character.first_strike:
        details = {**details, 'total':0.1}
    deadline = float(Decimal(str(start))+Decimal(str(details['total'])))
    character.next_action_at = deadline
    elapsed = float(Decimal(str(now))-Decimal(str(start)))
    return {'ready': character.enabled and character.alive and Decimal(str(now)) >= Decimal(str(deadline)),
            'elapsed': elapsed, 'next_action_at': deadline, 'cooldown': details}


@lru_cache(maxsize=16384)
def _cached_deadline(start, skill, strength, unload, speed):
    ratio = strength_speed_ratio(strength, unload, speed)
    total = max(Decimal('0.5'), Decimal('1.5')+Decimal(str(skill))+Decimal(str(ratio)))
    return float(Decimal(str(start))+total)


def current_action_deadline(character):
    """Cache only by all determining values, so any attribute change invalidates it."""
    if character.last_action_at is None and character.first_strike:
        character.next_action_at = 0.1
        return 0.1
    start = 0.0 if character.last_action_at is None else character.last_action_at
    skill = 0.0 if character.last_action_at is None else character.last_skill_cooldown
    stats = character.stats
    deadline = _cached_deadline(start,skill,stats.get('strength',0),stats.get('unload',0),stats.get('speed',0))
    character.next_action_at = deadline
    return deadline


def action_ready_now(character, now):
    return character.enabled and character.alive and now >= current_action_deadline(character)
