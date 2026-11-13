"""Named persistent buffs: remove old deltas before recalculating replacement stacks."""

from copy import deepcopy
from .state import clone_for_resolution
from decimal import Decimal
from .state import BuffInstance
from .initialization import nonnegative, BattleConfigurationError


def _time(state, now):
    now = nonnegative(now, "战斗时间")
    if now < state.time:
        raise BattleConfigurationError("战斗时间不能倒退")
    return now


def _remove(state, character, buff, reason, now):
    before = character.stats[buff.attribute]
    after = before - buff.amount
    if after < -1e-7:
        raise BattleConfigurationError("buff增量与当前属性不一致")
    character.stats[buff.attribute] = max(0.0, after)
    character.buffs.remove(buff)
    state.events.append(
        {
            "time": now,
            "type": reason,
            "buff_id": buff.id,
            "name": buff.name,
            "target_character": character.index,
            "source_character": buff.source_character,
            "attribute": buff.attribute,
            "amount": -buff.amount,
            "before": before,
            "after": character.stats[buff.attribute],
        }
    )


def _expire(state, now):
    expired = sorted(
        [
            (buff.expires_at, char.index, buff.id)
            for char in state.characters
            for buff in char.buffs
            if buff.expires_at is not None and buff.expires_at <= now
        ]
    )
    for expiry, index, buff_id in expired:
        character = state.characters[index - 1]
        buff = next(buff for buff in character.buffs if buff.id == buff_id)
        _remove(state, character, buff, "buff_expired", expiry)
    state.time = now


def _commit(original, draft):
    for old, new in zip(original.characters, draft.characters):
        old.stats = new.stats
        old.buffs = new.buffs
    original.time = draft.time
    original.events = draft.events


def expire_buffs(state, now):
    """Expires at equality too: a buff ending at t=15 is gone before actions at t=15."""
    now = _time(state, now)
    draft = clone_for_resolution(state)
    _expire(draft, now)
    _commit(state, draft)


def apply_named_buff(
    state,
    *,
    name,
    source_index,
    target_indices,
    conversions,
    now,
    duration=None,
    max_stacks=1,
    source_equipment_id="",
    source_equipment_name="",
    source_slot="",
    base_values=None,
    expire_due=True,
    return_snapshot=True,
):
    """One name replaces all previous instances on each recipient, including other casters.

    conversions maps destination attribute to source-attribute coefficient map.
    Old recorded deltas are removed before reading the caster's current attributes.
    Each recipient's new layer count is min(old layers + 1, max_stacks).
    All replacement removals happen before one shared caster snapshot is taken.
    Multiple rows share that snapshot; a layer cap still refreshes value and duration.
    Changes are atomic: invalid formulas leave the original state untouched.
    """
    now = _time(state, now)
    if not isinstance(name, str) or not name.strip():
        raise BattleConfigurationError("持续buff需要名称")
    name = name.strip()
    if type(source_index) is not int or not 1 <= source_index <= len(state.characters):
        raise BattleConfigurationError("buff来源角色无效")
    if (
        not state.characters[source_index - 1].enabled
        or not state.characters[source_index - 1].alive
    ):
        raise BattleConfigurationError("buff来源角色未参战")
    if (
        not isinstance(target_indices, list)
        or not target_indices
        or any(type(i) is not int or not 1 <= i <= len(state.characters) for i in target_indices)
        or len(set(target_indices)) != len(target_indices)
    ):
        raise BattleConfigurationError("buff目标角色无效或重复")
    if any(
        not state.characters[i - 1].enabled or not state.characters[i - 1].alive
        for i in target_indices
    ):
        raise BattleConfigurationError("buff目标角色未参战")
    if type(max_stacks) is not int or not 1 <= max_stacks <= 999:
        raise BattleConfigurationError("buff层数上限无效")
    if duration is not None:
        duration = nonnegative(duration, "buff持续时间")
        if duration == 0:
            raise BattleConfigurationError("持续buff时长必须大于0；永久buff使用None")
    if not isinstance(conversions, dict) or not conversions:
        raise BattleConfigurationError("buff属性公式不能为空")
    draft = clone_for_resolution(state)
    if expire_due:
        _expire(draft, now)
    layers = {}
    for index in target_indices:
        target = draft.characters[index - 1]
        old = [buff for buff in target.buffs if buff.name == name]
        layers[index] = min(max((buff.stacks for buff in old), default=0) + 1, max_stacks)
        for buff in old:
            _remove(draft, target, buff, "buff_replaced", now)
    source_stats = draft.characters[source_index - 1].stats.copy()
    amounts = {}
    for attribute, coefficients in conversions.items():
        if not isinstance(attribute, str) or not isinstance(coefficients, dict):
            raise BattleConfigurationError("buff属性公式无效")
        amount = nonnegative((base_values or {}).get(attribute, 0), "buff基础值")
        for key, coefficient in coefficients.items():
            coefficient = nonnegative(coefficient, "buff增幅系数")
            if not coefficient:
                continue
            if key not in source_stats:
                raise BattleConfigurationError("缺少buff计算所需属性：" + key)
            amount += source_stats[key] * coefficient
        amounts[attribute] = nonnegative(amount, "单层buff增量")
    created = []
    for index in target_indices:
        target = draft.characters[index - 1]
        for attribute, per_layer in amounts.items():
            amount = nonnegative(per_layer * layers[index], "buff总增量")
            before = target.stats.get(attribute, 0)
            after = nonnegative(before + amount, "增幅后属性")
            buff = BuffInstance(
                id=f"buff_{draft.discarded_event_count + len(draft.events) + 1}",
                name=name,
                source_character=source_index,
                source_equipment_id=source_equipment_id,
                source_equipment_name=source_equipment_name,
                source_slot=source_slot,
                target_character=index,
                attribute=attribute,
                amount=amount,
                source_stats=source_stats.copy(),
                applied_at=now,
                duration=duration,
                stacks=layers[index],
                max_stacks=max_stacks,
                expires_at=float(Decimal(str(now)) + Decimal(str(duration)))
                if duration is not None
                else None,
            )
            target.stats[attribute] = after
            target.buffs.append(buff)
            created.append(buff)
            draft.events.append(
                {
                    "time": now,
                    "type": "buff_applied",
                    "buff_id": buff.id,
                    "name": name,
                    "source_character": source_index,
                    "target_character": index,
                    "attribute": attribute,
                    "stacks": layers[index],
                    "amount": amount,
                    "before": before,
                    "after": after,
                    "expires_at": buff.expires_at,
                }
            )
    _commit(state, draft)
    return deepcopy(created) if return_snapshot else None
