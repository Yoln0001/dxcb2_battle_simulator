"""Periodic max-health loss from group sacrifice, separate from additive stat buffs."""
from copy import deepcopy
from .state import clone_for_resolution
from .state import PeriodicDebuff
from .initialization import nonnegative, BattleConfigurationError


def attach_group_sacrifice(state, source_index):
    """Attach once to active participants after all start equipment buffs finish.

    t=0 only applies the debuff. First loss is at t=1, never on application.
    This helper receives an explicit source; contract activation is handled by caller.
    """
    if state.time != 0:
        raise BattleConfigurationError('群体献祭应在开战装备增幅结束后附加')
    for character in state.characters:
        if not character.enabled or any(d.name == '群体献祭' for d in character.debuffs):
            continue
        debuff = PeriodicDebuff(f'sacrifice_{character.index}', '群体献祭', source_index)
        character.debuffs.append(debuff)
        state.events.append({'time':0.0,'type':'debuff_applied','name':debuff.name,'source_character':source_index,'target_character':character.index,'interval':1.0,'maximum_hp_ratio':.05,'next_tick_at':1.0})


def set_health(character, maximum, current=None):
    if not character.alive:
        raise BattleConfigurationError('死亡角色无法复活或重新设置生命值')
    maximum = nonnegative(maximum, '最大生命值')
    current = maximum if current is None else nonnegative(current, '当前生命值')
    if maximum <= 0 or current > maximum:
        raise BattleConfigurationError('生命值设置无效')
    character.maximum_hp = maximum
    character.current_hp = current


def process_sacrifice_ticks(state, now):
    """Only processes sacrifice events. The scheduler must interleave other events.

    Loss uses maximum HP at the tick, never 5% of remaining HP. Inputs contain
    explicit maximum/current HP; this module does not guess constitution scaling.
    """
    now = nonnegative(now, '战斗时间')
    if now < state.time:
        raise BattleConfigurationError('战斗时间不能倒退')
    draft = clone_for_resolution(state)
    while True:
        due = [(d.next_tick_at,c.index,d.id) for c in draft.characters if c.enabled and c.alive for d in c.debuffs if d.name=='群体献祭' and d.next_tick_at <= now]
        if not due:
            break
        tick_at, index, debuff_id = min(due)
        c = draft.characters[index-1]
        d = next(d for d in c.debuffs if d.id == debuff_id)
        if c.maximum_hp is None or c.current_hp is None:
            raise BattleConfigurationError('群体献祭结算需要明确的最大及当前生命值')
        maximum = nonnegative(c.maximum_hp,'最大生命值')
        before = nonnegative(c.current_hp,'当前生命值')
        nominal = nonnegative(maximum*d.maximum_hp_ratio,'献祭扣血')
        c.current_hp = max(0.0,before-nominal)
        draft.events.append({'time':tick_at,'type':'sacrifice_tick','name':d.name,'target_character':index,'maximum_hp':maximum,'amount':before-c.current_hp,'nominal_amount':nominal,'before':before,'after':c.current_hp})
        from .health import mark_deaths
        mark_deaths(draft,tick_at)
        d.next_tick_at = tick_at+d.interval
    for original,updated in zip(state.characters,draft.characters):
        original.alive=updated.alive
        original.current_hp=updated.current_hp
        original.stats['hitPoint']=updated.current_hp
        original.debuffs=updated.debuffs
    state.contract=draft.contract
    state.time=now
    state.events=draft.events


def calculate_contract_damage(state):
    """Five factors: team current magic, owner's magic bonus/imprint, target factors.

    No armor/resistance, crit, race bonus or temporary attack-only amplification.
    """
    contract = state.contract
    if contract is not None and contract.active and (contract.name.endswith(('-力','-速')) or contract.name in ('至高妖精-魔','饮命者-魔')):
        return strength_contract_damage(state)
    if contract is None or not contract.active or contract.name != '旧日支配者-魔':
        raise BattleConfigurationError('当前没有旧日支配者-魔契约')
    owner = state.characters[contract.owner_index-1]
    if not owner.alive:
        raise BattleConfigurationError('契约佩戴者死亡，契约已失效')
    magic = [{'character':c.index,'magic':nonnegative(c.stats.get('magic',0),'当前魔力')} for c in state.characters if c.enabled and c.alive]
    total_magic = nonnegative(sum(row['magic'] for row in magic),'己方魔力总和')
    multiplier = nonnegative(contract.skill_multiplier,'契约技能倍率')
    magic_bonus = 1+nonnegative(owner.stats.get('magicDamage',0),'契约佩戴者魔法伤害百分数')/100
    imprint = 1+nonnegative(owner.stats.get('finalMagicDamage',0),'契约佩戴者辉印魔伤百分数')/100
    vulnerability = nonnegative(state.target.get('magicVulnerability',1),'目标魔法易伤')
    reduction = nonnegative(state.target.get('magicReduction',0),'目标魔法减伤百分数')
    if reduction > 100:
        raise BattleConfigurationError('目标魔法减伤不能超过100%')
    factors = {'skill_damage':total_magic*multiplier,'magic_damage_bonus':magic_bonus,'imprint':imprint,'target_vulnerability':vulnerability,'magic_reduction':1-reduction/100}
    damage = nonnegative(factors['skill_damage']*magic_bonus*imprint*vulnerability*factors['magic_reduction'],'契约伤害')
    from .damage import minimum_damage
    damage = minimum_damage(damage, reduction)
    return {'owner_character':owner.index,'team_magic':magic,'total_magic':total_magic,'skill_multiplier':multiplier,'factors':factors,'damage':damage}


def resolve_contract_tick(state, *, expire_due=True):
    """Called by scheduler at precisely next_tick_at, after due buff expirations.

    Each call handles only one event so other skills/buffs can interleave between
    contract ticks. Clock begins at 0.1s: triggers are 14.1s, 28.1s, 42.1s, ... .
    """
    if state.contract is None:
        raise BattleConfigurationError('没有已激活契约')
    if state.time != state.contract.next_tick_at:
        raise BattleConfigurationError('请在契约下次触发时间结算，避免遗漏中间战斗事件')
    draft = clone_for_resolution(state)
    from .buffs import expire_buffs
    if expire_due:
        expire_buffs(draft,draft.time)
    details = calculate_contract_damage(draft)
    before = draft.target_current_hp
    if before is not None:
        draft.target_current_hp = max(0.0,before-details['damage'])
    draft.contract.ticks += 1
    draft.contract.total_damage = nonnegative(draft.contract.total_damage+details['damage'],'累计契约伤害')
    from decimal import Decimal
    draft.contract.next_tick_at = float(Decimal(str(draft.contract.next_tick_at))+Decimal(str(draft.contract.interval)))
    draft.events.append({'time':draft.time,'type':'contract_damage','name':draft.contract.name,**details,
        'target_hp_before':before,'target_hp_after':draft.target_current_hp,
        'actual_hp_loss':before-draft.target_current_hp if before is not None else None,
        'next_tick_at':draft.contract.next_tick_at})
    for original,updated in zip(state.characters,draft.characters):
        original.stats=updated.stats
        original.buffs=updated.buffs
    state.contract=draft.contract
    state.target_current_hp=draft.target_current_hp
    state.events=draft.events
    return details


def resolve_contract_action_tie(state, action, *, roll=None, rng=None):
    """Temporary empirical model for a contract-owner action at the same timestamp.

    action is a callback resolving that one owner's action on this state, including
    persistent magic changes. The scheduler calls this only for an actual tie.
    50% action first, 50% contract first. No randomization across different times.
    This does not randomize all buff expiration/action ordering.
    """
    if state.contract is None or state.time != state.contract.next_tick_at:
        raise BattleConfigurationError('仅在契约与佩戴者行动同一时刻调用边界结算')
    if not callable(action):
        raise BattleConfigurationError('需要契约佩戴者行动回调')
    if roll is None:
        import random
        roll = (rng or random).random()
    roll = nonnegative(roll, '同刻事件随机值')
    if roll >= 1:
        raise BattleConfigurationError('同刻事件随机值必须处于[0,1)')
    order = ['owner_action','contract'] if roll < .5 else ['contract','owner_action']
    state.events.append({'time':state.time,'type':'contract_action_tie','owner_character':state.contract.owner_index,'order':order,'roll':roll,'action_first_probability':.5})
    if roll < .5:
        action(state)
        details = resolve_contract_tick(state)
    else:
        details = resolve_contract_tick(state)
        action(state)
    return details


def strength_contract_damage(state):
    import math
    contract=state.contract;owner=state.characters[contract.owner_index-1]
    if not owner.alive:raise BattleConfigurationError('契约佩戴者死亡，契约已失效')
    name=contract.name[:-2]
    attribute='magic' if contract.name.endswith('-魔') else 'speed' if contract.name.endswith('-速') else 'strength'
    damage_type='magic' if attribute=='magic' else 'physical'
    strength=sum(c.stats.get(attribute,0) for c in state.characters if c.enabled and c.alive) if name=='旧日支配者' else owner.stats.get(attribute,0)
    extra=4 if name in ('狂怒兽神','至高妖精','黑雾潜者') and contract.ticks==0 else 1
    if name=='饮命者':
        maximum=state.target.get('hitPoint',0)
        if maximum<=0 or state.target_current_hp is None:raise BattleConfigurationError('饮命者需要敌方最大和当前生命值')
        extra=1+.3*min(4,math.floor(max(0,1-state.target_current_hp/maximum)*4+1e-9))
    reduction=state.target.get(damage_type+'Reduction',0)
    from .damage import minimum_damage
    value=minimum_damage(strength*contract.skill_multiplier*extra*(1+owner.stats.get(damage_type+'Damage',0)/100)*(1+owner.stats.get('finalMagicDamage' if damage_type=='magic' else 'finalPhysicalDamage',0)/100)*state.target.get(damage_type+'Vulnerability',1)*(1-reduction/100),reduction)
    return {'owner_character':owner.index,'total_strength':strength,'skill_multiplier':contract.skill_multiplier,'factors':{'strength':strength,'extra_multiplier':extra},'targeting':'all' if name=='旧日支配者' else 'single','damage':value}
