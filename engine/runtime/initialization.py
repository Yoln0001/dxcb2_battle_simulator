"""Apply equipment start effects sequentially to the shared four-character state."""
from copy import deepcopy
import math
from .state import BattleState, CharacterState, BuffInstance, ContractState

START_SLOTS = ('weapon', 'armor', 'accessory1', 'accessory2')
START_ATTRIBUTES = ('strength', 'magic', 'technique', 'speed')


class BattleConfigurationError(ValueError):
    pass


def nonnegative(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise BattleConfigurationError(label + '必须为有限非负数')
    return float(value)


def initialize_battle(config, equipment_library, ally_targets=None):
    """Library is keyed by equipment ID. ally_targets maps (source_index, slot) to target index.

    Start coefficients read the wearer's current stats immediately before this effect.
    A team effect computes its value once, then gives that same amount to active allies.
    Disabled characters neither emit nor receive effects. Indices are 1-based.
    """
    if not isinstance(config, dict) or not isinstance(config.get('characters'), list) or len(config['characters']) != 4:
        raise BattleConfigurationError('队伍必须包含4个角色')
    characters = []
    for index, character in enumerate(config['characters'], 1):
        if not isinstance(character, dict) or type(character.get('enabled')) is not bool or not isinstance(character.get('stats'), dict) or not isinstance(character.get('equipment'), dict):
            raise BattleConfigurationError('角色配置格式无效')
        base = {key: nonnegative(value, key) for key, value in character['stats'].items()}
        if config.get('configurationType')=='special':
            for key,value in character.get('specialSources',{}).get('ringPanelBonuses',{}).items():
                base[key]=max(0,base.get(key,0)-nonnegative(value,'域之环面板增益'))
        if config.get('configurationType')!='special' and character.get('ringPanelIncluded'):
            for key,value in character.get('ringPanelBonuses',{}).items():
                base[key]=max(0,base.get(key,0)-nonnegative(value,'域之环面板增益'))
        worn=character.get('selectedContract')
        if worn and config.get('configurationType')!='special':
            from backend.contracts.store import validate_item
            worn=validate_item(worn);attr=worn['category'];base[attr]=base.get(attr,0)*(1+worn['baseBonus']/100)
        ring=character.get('selectedRing')
        if ring:
            from backend.rings.store import validate_item as validate_ring,base_values
            ring=validate_ring(ring)
            if config.get('configurationType')!='special' and not character.get('ringPanelIncluded'):
                multipliers=(character.get('specialSources',{}) if config.get('configurationType')=='special' else character).get('ringBattleMultipliers',{})
                for key,value in base_values(ring).items():base[key]=base.get(key,0)+value*nonnegative(multipliers.get(key,1),'域之环属性倍率')
        for attr in (*START_ATTRIBUTES,'armor','resistance'):
            base.setdefault(attr, 0.0)
        characters.append(CharacterState(index, character.get('name', f'角色{index}'), character.get('job', ''), character['enabled'], deepcopy(base), deepcopy(base), deepcopy(character['equipment']), first_strike=character.get('firstStrike',False) is True))
        characters[-1].domain_ring=ring
    state = BattleState(characters, deepcopy(config.get('target', {})))
    for key in ('allyLifestealReduction','allyHealingReduction','allyRegenerationReduction'):
        value=nonnegative(state.target.get(key,0),'己方回复降低比例')
        if value>100:raise BattleConfigurationError('己方回复降低比例不能超过100%')
        state.target[key]=value
    if 'hitPoint' in state.target:
        state.target_current_hp = nonnegative(state.target['hitPoint'], '目标生命值')
    from .rings import refresh_rings
    refresh_rings(state)
    # Resolve and check the full loadout before applying any effects.
    resolved = []
    for source in characters:
        if not source.enabled:
            continue
        for slot in START_SLOTS:
            equipment_id = source.equipment.get(slot, '')
            if not equipment_id:
                continue
            equipment = equipment_library.get(equipment_id)
            if not equipment:
                raise BattleConfigurationError(f'角色{source.index}的{slot}装备不存在，请重新选择')
            category = 'accessory' if slot.startswith('accessory') else slot
            if equipment['category'] != category:
                raise BattleConfigurationError('装备类型与槽位不匹配')
            if slot == 'weapon' and equipment.get('weaponJob'):
                from backend.equipment.jobs import JOB_FAMILIES
                if JOB_FAMILIES.get(source.job) != equipment['weaponJob']:
                    raise BattleConfigurationError('武器与角色职业不匹配')
            for key,enabled in equipment.get('negativeImmunities',{}).items():
                if enabled is True:source.negative_immunities[key]=True
            resolved.append((source, slot, equipment))
    for source, slot, original in resolved:
        bundle=original.get('battleStartEffects')
        effects=([{**original,'effectName':row['name'],'startingBuff':row['buff']} for row in bundle['entries'] if row['side']=='ally' and row.get('enabled',True)] if bundle.get('enabled') else []) if bundle is not None else [original]
        for equipment in effects:
            effect = equipment['startingBuff']
            if not effect.get('enabled', False) or (effect.get('kind','amplify')!='regeneration' and effect['target'] == 'none'):
                continue
            source_stats = deepcopy(source.stats)
            amount = sum(source_stats[attr] * nonnegative(effect['coefficients'][attr], '开战系数') for attr in START_ATTRIBUTES)
            nonnegative(amount, '开战增幅结果')
            recipient = effect['recipient']
            if recipient == 'self':
                recipients = [source]
            elif recipient == 'allAllies':
                recipients = [character for character in characters if character.enabled]
            elif recipient == 'singleAlly':
                target_index = (ally_targets or {}).get((source.index, slot))
                if type(target_index) is not int or not 1 <= target_index <= 4 or not characters[target_index - 1].enabled:
                    raise BattleConfigurationError('单个队友增幅需要明确指定参战目标')
                recipients = [characters[target_index - 1]]
            else:
                raise BattleConfigurationError('开战增幅对象无效')
            if effect.get('kind')=='regeneration':
                regeneration=effect.get('regeneration',{})
                amount=nonnegative(regeneration.get('baseValue',0),'回春基础数值')+sum(source_stats.get(attr,0)*nonnegative(regeneration.get('coefficients',{}).get(attr,0),'回春系数') for attr in (*START_ATTRIBUTES,'constitution'))
                # 肇始之心★ uses the base opening regeneration amount; recovery
                # penalties are still applied at each tick for all equipment.
                if regeneration.get('receivesHealingBonuses', not ('肇始之心★' in original['name'] or equipment.get('effectName') == '肇始之源')):
                    amount *= (1+nonnegative(source_stats.get('healingBonus',0),'回复效果')/100)*(1+nonnegative(source_stats.get('finalHealingBonus',0),'辉印回复')/100)
                nonnegative(amount,'回春数值')
                name=equipment.get('effectName') or equipment['name']
                for target in recipients:
                    replaced=any(buff['name']==name for buff in target.regeneration_buffs)
                    target.regeneration_buffs=[buff for buff in target.regeneration_buffs if buff['name']!=name]
                    target.regeneration_buffs.append({'name':name,'source_character':source.index,'target_character':target.index,'source_equipment_id':equipment['id'],'source_stats':source_stats,'amount':amount,'next_tick_at':1.0,'applied_at':0.0})
                    state.events.append({'time':0.0,'type':'starting_regeneration','source_character':source.index,'character':source.index,'target_character':target.index,'equipment_name':equipment['name'],'source_slot':slot,'name':name,'amount':amount,'replaced':replaced})
                continue
            target_attr = effect['target']
            if target_attr not in (*START_ATTRIBUTES,'armor','resistance'):
                raise BattleConfigurationError('开战增幅目标属性无效')
            for target in recipients:
                before = target.stats[target_attr]
                after = nonnegative(before + amount, '增幅后属性')
                buff = BuffInstance(f'start_{len(state.events)+1}', equipment.get('effectName') or equipment['name'], source.index, equipment['id'], equipment['name'], slot, target.index, target_attr, amount, deepcopy(source_stats))
                target.buffs.append(buff)
                target.stats[target_attr] = after
                state.events.append({'time': 0.0, 'type': 'starting_buff', 'name': buff.name, 'buff_id': buff.id, 'source_character': source.index, 'source_slot': slot, 'equipment_name': equipment['name'], 'target_character': target.index, 'attribute': target_attr, 'amount': amount, 'before': before, 'after': after})
    # Opening vulnerabilities replace by type in character/slot order, not add.
    opening_debuffs = {}
    opening_dots = {}
    recovery_debuffs = []
    recovery_multiplier = 1.0
    for source in characters:
        if not source.enabled:
            continue
        for slot in (*START_SLOTS, 'stone'):
            item_id = source.equipment.get(slot)
            if not item_id:
                continue
            item = equipment_library.get(item_id)
            if not item:
                raise BattleConfigurationError('装备不存在，请重新选择')
            container=item.get('startingDebuffs')
            rows=container.get('entries',[container]) if container is not None else [None]
            if container is not None and not container.get('enabled'):continue
            for opening in rows:
                for key, name in [('physicalVulnerability', '物理易伤'), ('magicVulnerability', '魔法易伤')]:
                    if opening is not None:
                        amount = nonnegative(opening.get(key, 0), name) if container.get('enabled') else 0
                    else:
                        stat = item.get('baseAttributes', {}).get(key, {})
                        amount = nonnegative(stat.get('value') if stat.get('value') is not None else (stat.get('min') or 0), name)
                    if amount == 0:
                        continue
                    immunity_key = 'immunePhysicalVulnerability' if key == 'physicalVulnerability' else 'immuneMagicVulnerability'
                    if state.target.get('immuneNegativeEffects') or state.target.get(immunity_key):
                        state.events.append({'time':0.0, 'type':'debuff_immune', 'character':source.index, 'name':name, 'debuff_name':name})
                        continue
                    replaced = key in opening_debuffs
                    opening_debuffs[key] = {'name':name, 'type':key, 'character':source.index, 'stacks':1,
                        'amount':amount, 'effect_name':(opening or {}).get('name',''), 'source_name':item['name'], 'source_slot':slot, 'expires_at':None}
                    state.target[key] = 1 + amount / 100
                    state.events.append({'time':0.0, 'type':'starting_vulnerability', 'character':source.index,
                        'name':name, 'effect_name':(opening or {}).get('name',''), 'equipment_name':item['name'], 'amount':amount, 'replaced':replaced})
                opening=opening or {}
                deprivation=nonnegative(opening.get('lifeDeprivation',0),'生命剥夺百分比')
                if deprivation>100:raise BattleConfigurationError('生命剥夺百分比必须处于0到100%')
                if deprivation:
                    if state.target_current_hp is None:raise BattleConfigurationError('生命剥夺需要设置敌方生命值')
                    before=state.target_current_hp;damage=before*deprivation/100
                    state.target_current_hp=max(0.0,before-damage)
                    state.events.append({'time':0.0,'type':'starting_life_deprivation','character':source.index,'name':opening.get('name') or '生命剥夺','equipment_name':item['name'],'percentage':deprivation,'damage':damage,'before':before,'after':state.target_current_hp})
                reduction = nonnegative(opening.get('healingReduction',0),'回复/吸血效果降低')
                if reduction>100:raise BattleConfigurationError('回复/吸血效果降低必须处于0到100%')
                if reduction:
                    name=opening.get('name') or item['name']+' 回复/吸血降低'
                    if state.target.get('immuneNegativeEffects'):
                        state.events.append({'time':0.0,'type':'debuff_immune','character':source.index,'name':name,'debuff_name':name})
                    else:
                        recovery_multiplier *= 1-reduction/100
                        recovery_debuffs.append({'name':name,'type':'healingReduction','character':source.index,'stacks':1,'amount':reduction,'source_name':item['name'],'expires_at':None})
                        state.events.append({'time':0.0,'type':'starting_healing_reduction','character':source.index,'name':name,'amount':reduction,'remaining_percent':recovery_multiplier*100,'combined_reduction':(1-recovery_multiplier)*100})
                if opening.get('dotEnabled'):
                    name = opening.get('name') or item['name']+' DOT'
                    if state.target.get('immuneNegativeEffects'):
                        state.events.append({'time':0.0,'type':'debuff_immune','character':source.index,'name':name,'debuff_name':name})
                        continue
                    from .damage import calculate_burn_damage
                    details = calculate_burn_damage(source.stats, {'kind':'debuff','type':'burn','baseValue':nonnegative(opening.get('dotDamage',0),'DOT基础伤害'),'coefficients':{}}, state.target)
                    replaced = name in opening_dots
                    opening_dots[name] = {'name':name,'type':'openingDot','character':source.index,'stacks':1,
                        'damage':details['final_damage'],'source_name':item['name'],'active_buff_refs':[{'name':b.name,'source_character':b.source_character,'target_character':source.index} for b in source.buffs],'expires_at':None,'next_tick_at':1.0}
                    state.events.append({'time':0.0,'type':'starting_dot','character':source.index,'name':name,'damage':details['final_damage'],'replaced':replaced})
    state.target['equipmentRecoveryDebuffs'] = recovery_debuffs
    state.target['recoveryMultiplier'] = recovery_multiplier
    state.target['combinedHealingReduction'] = (1-recovery_multiplier)*100
    state.target['equipmentDotDebuffs'] = list(opening_dots.values())
    state.target['equipmentVulnerabilityDebuffs'] = list(opening_debuffs.values())
    # All equipment effects finish before contract debuffs are attached.
    from .contracts import set_health, attach_group_sacrifice
    active_contracts = [(i, c) for i, c in enumerate(config['characters'], 1) if c.get('contract', '不激活') != '不激活']
    if len(active_contracts) > 1:
        raise BattleConfigurationError('契约只能由一个角色开启')
    for character in characters:
        maximum = nonnegative(character.stats.get('constitution', 0)*10, '最大生命值')
        if maximum > 0:
            set_health(character, maximum)
        else:
            character.maximum_hp = 0.0
            character.current_hp = 0.0
        character.stats['hitPoint'] = character.current_hp
    if active_contracts:
        source_index, row=active_contracts[0];owner=characters[source_index-1]
        name=row.get('contract')
        if owner.enabled:
            valid=['旧日支配者-魔','狂怒兽神-力','饮命者-力','旧日支配者-力','炎钢羽神-技','饮魂者-技','至高妖精-魔','饮命者-魔','黑雾潜者-速','饮命者-速','旧日支配者-速']
            if name not in valid:raise BattleConfigurationError('契约种类尚未定义')
            interval=7 if name.endswith('-速') else 14 if name.endswith(('-魔','-技')) else 28
            legacy=name=='旧日支配者-魔' and not row.get('selectedContract')
            state.contract=ContractState(name,source_index,nonnegative(row.get('skillMultiplier',1),'契约技能倍率'),interval=interval,clock_start_at=.1,next_tick_at=float(interval)+.1)
            negative=row.get('negativeEffect','无')
            if not legacy:
                from backend.contracts.store import RULES
                archetype={'饮命者-魔':'饮命者（魔力）','旧日支配者-魔':'旧日支配者（魔力）','饮命者-速':'饮命者（速度）','旧日支配者-速':'旧日支配者（速度）'}.get(name,name[:-2])
                allowed=RULES[archetype][1]
                if negative not in allowed:raise BattleConfigurationError('契约负面效果不匹配')
            if negative=='群体献祭':
                if any(c.enabled and c.maximum_hp<=0 for c in characters):raise BattleConfigurationError('群体献祭需要每个参战角色填写大于0的体质')
                attach_group_sacrifice(state,source_index)
            recipients=[c for c in characters if c.enabled] if negative.startswith('群体') else [owner]
            for target in recipients:
                if negative in ('脆化','群体脆化'):
                    for attr in ('physicalTakenMultiplier','magicTakenMultiplier','dotTakenMultiplier'):target.stats[attr]=1.3 if negative=='脆化' else 1.2
                if negative in ('污秽','群体污秽'):target.stats['contractRecoveryMultiplier']=.7 if negative=='污秽' else .8
                if negative in ('盲目','群体盲目'):
                    penalty=5 if negative=='盲目' else 3;before=target.stats.get('hitRate',0)
                    target.stats['hitRate']=max(0,before-penalty);target.stats['contractHitPenalty']=max(0,penalty-before)
                if negative in ('痴愚','群体痴愚'):target.stats['contractCooldown']=.3 if negative=='痴愚' else .1
                if negative not in ('无','群体献祭'):state.events.append({'time':0.,'type':'contract_negative','character':source_index,'target_character':target.index,'name':negative})
    from .rings import refresh_rings
    for character in characters:
        ring=character.domain_ring
        if not character.enabled or not ring:continue
        if ring['restriction']=='fragile':
            for attr in ('physicalTakenMultiplier','magicTakenMultiplier'):character.stats[attr]=character.stats.get(attr,1)*1.3
        if ring['restriction']=='polluted':character.stats['ringRecoveryMultiplier']=.7
    refresh_rings(state)
    # First actions are scheduled after every opening equipment effect.
    from .cooldowns import action_cooldown
    for character in characters:
        if character.enabled:
            character.next_action_at = 0.1 if character.first_strike else action_cooldown(character, 0)['total']
    return state
