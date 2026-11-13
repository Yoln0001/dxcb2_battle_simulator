"""Single-battle timeline: integer 0.1s clock and seeded same-tick ordering."""

from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal, ROUND_CEILING
import random
import re
from .initialization import initialize_battle, BattleConfigurationError, nonnegative
from .cooldowns import (
    check_action_ready,
    schedule_after_action,
    action_ready_now,
    current_action_deadline,
)
from .buffs import apply_named_buff, _remove
from .amplification import attack_snapshot
from .contracts import process_sacrifice_ticks, resolve_contract_tick
from .rings import refresh_rings, process_ring_ticks
from .damage import (
    calculate_damage,
    calculate_burn_damage,
    calculate_equipment_damage,
    calculate_hit_chance,
)
from .health import mark_deaths, reduce_ally_recovery
from .targeting import select_target
from .boss_rules import party_wipe_time, periodic_kill_strategy
from .debuffs import check_skill_debuff_application

IMMUNITIES = {
    "burn": "immuneBurn",
    "bleeding": "immuneBleeding",
    "plague": "immunePlague",
    "slow": "immuneSpeedReduction",
    "stun": "immuneStun",
    "weakness": "immuneWeakness",
    "fear": "immuneFear",
    "lifeLoss": "immuneLifeLoss",
}
DEBUFF_NAMES = {
    "burn": "灼烧",
    "bleeding": "流血",
    "plague": "瘟疫",
    "slow": "减速",
    "stun": "眩晕",
    "weakness": "虚弱",
    "fear": "恐惧",
    "lifeLoss": "生命流失",
}


def add_time(a, b):
    return float(Decimal(str(a)) + Decimal(str(b)))


def expand_decisions(group):
    """Compile one logical decision slot into priority candidates, keeping graph targets stable."""
    group = deepcopy(group)
    for sub in group["subgroups"]:
        if not sub.get("conditionsEnabled") or not sub["skills"][0].get("decision"):
            continue
        anchor = sub["skills"][0]
        decision = anchor["decision"]
        destination = next(
            (g["skills"][0]["id"] for g in group["subgroups"] if g["id"] == sub.get("nextGroup")),
            "",
        )
        candidates = decision["cases"] + [
            {
                "kind": "always",
                "threshold": 20,
                "skillId": decision["elseSkillId"],
                "waitDuration": decision.get("elseWaitDuration", 1),
                "targetSelection": decision.get("elseTargetSelection", "lowestHp"),
            }
        ]
        sub["skills"] = []
        for i, case in enumerate(candidates):
            node = deepcopy(anchor)
            node.pop("decision", None)
            node.update(
                id=anchor["id"] if i == 0 else anchor["id"] + "__case_" + str(i),
                skillId=case["skillId"],
                releaseCondition={
                    k: v
                    for k, v in case.items()
                    if k
                    in (
                        "kind",
                        "threshold",
                        "includeSelf",
                        "requiredDebuff",
                        "absentBuff",
                        "recognitionDelay",
                        "operationDelay",
                    )
                },
                _decisionFallback=destination,
            )
            node["waitDuration"] = case.get("waitDuration", 1)
            node["targetSelection"] = case.get("targetSelection", "lowestHp")
            node["next"] = anchor.get("next") or destination
            sub["skills"].append(node)
    return group


def resolve_equipment_conditions(group, equipped, equipment):
    """Use equipment names across player libraries; resolve legacy ID-only conditions."""
    group = deepcopy(group)
    for sub in group["subgroups"]:
        for node in sub["skills"]:
            condition = node.get("jumpCondition")
            if condition and not condition.get("equipmentName"):
                original = equipment.get(condition.get("equipmentId"))
                if original:
                    condition["equipmentName"] = original["name"]
    return group


class SkillSequence:
    def __init__(self, group, skills, job):
        if group.get("job") != job:
            raise BattleConfigurationError("技能组与角色转职不一致")
        group = expand_decisions(group)
        self.group = group
        self.nodes, self.following, self.fallback, self.conditions = {}, {}, {}, {}
        self.branches = {}
        self.release_rules = {}
        subgroups = {g["id"]: g for g in group["subgroups"]}
        for g in subgroups.values():
            for pos, node in enumerate(g["skills"]):
                skill = (
                    {
                        "name": "等待",
                        "job": job,
                        "damageType": "wait",
                        "waitDuration": node.get("waitDuration", 1),
                    }
                    if node["skillId"] == "__wait__"
                    else skills.get(node["skillId"])
                )
                if skill and skill.get("damageType") == "wait":
                    duration = nonnegative(skill["waitDuration"], "等待时间")
                    if not 0.1 <= duration <= 3600:
                        raise BattleConfigurationError("等待时间应为0.1到3600秒")
                if not skill or skill["job"] != job:
                    raise BattleConfigurationError("技能组中的技能不存在或与转职不一致")
                skill = deepcopy(skill)
                skill["matchedMember"] = node.get("targetSelection") == "matchedMember"
                skill["operationDelay"] = (node.get("releaseCondition") or {}).get(
                    "operationDelay", 0
                )
                skill["targetSelection"] = (
                    node.get("targetSelection", "lowestHp")
                    if skill.get("damageType") in ("physical", "magic")
                    and skill.get("targeting", "single") == "single"
                    else "default"
                )
                self.nodes[node["id"]] = skill
                self.branches[node["id"]] = g.get("healthBranch")
                if g.get("conditionsEnabled"):
                    self.release_rules[node["id"]] = g["skills"]
                following = g["skills"][pos + 1]["id"] if pos + 1 < len(g["skills"]) else ""
                if pos + 1 == len(g["skills"]) and g.get("nextGroup"):
                    destination = subgroups.get(g["nextGroup"])
                    if not destination or not destination["skills"]:
                        raise BattleConfigurationError("子技能组跳转目标无效")
                    following = destination["skills"][0]["id"]
                following = node.get("_decisionFallback", following)
                self.fallback[node["id"]] = following
                self.conditions[node["id"]] = node.get("jumpCondition")
                self.following[node["id"]] = node.get("next") or following
        self.current = group["entry"]
        if self.current not in self.nodes or any(
            n and n not in self.nodes for n in self.following.values()
        ):
            raise BattleConfigurationError("技能组入口或跳转目标无效")

    def choose_for_action(self, characters, actor, battle=None):
        self.matched_member = None
        self.matched_members = []
        candidates = self.release_rules.get(self.current)
        if candidates is not None:
            for node in candidates:
                condition = node.get("releaseCondition") or {"kind": "always", "threshold": 20}
                kind = condition["kind"]
                if kind == "memberStatus":
                    matches = (
                        battle.matching_members(condition, actor) if battle is not None else []
                    )
                    if matches:
                        self.matched_members = matches
                        self.matched_member = min(matches, key=lambda c: c.current_hp)
                        self.current = node["id"]
                        return True
                    continue
                low = any(
                    c.index != actor
                    and c.enabled
                    and c.alive
                    and c.maximum_hp > 0
                    and c.current_hp / c.maximum_hp * 100 < condition.get("threshold", 20)
                    for c in characters
                )
                if (
                    kind == "always"
                    or kind == "allyHealthBelow"
                    and low
                    or kind == "noAllyHealthBelow"
                    and not low
                ):
                    self.current = node["id"]
                    return True
            return False
        branch = self.branches.get(self.current)
        if not branch:
            return True
        matched = any(
            c.index != actor
            and c.enabled
            and c.alive
            and c.maximum_hp > 0
            and c.current_hp / c.maximum_hp * 100 < branch["threshold"]
            for c in characters
        )
        target = branch["whenTrue"] if matched else branch["whenFalse"]
        if target not in self.nodes:
            raise BattleConfigurationError("条件分支目标技能不存在")
        self.current = target
        return True

    def advance(self, procs=()):
        condition = self.conditions[self.current]
        matched = not condition or any(
            (
                item.get("name") == condition["equipmentName"]
                if condition.get("equipmentName")
                else item["id"] == condition["equipmentId"]
            )
            and item.get("triggerEffects", []).index(row) == condition["effectIndex"]
            and row.get("name", "") == condition.get("effectName", "")
            for item, _, row in procs
        )
        self.current = self.following[self.current] if matched else self.fallback[self.current]


class SingleBattle:
    def __init__(
        self, config, equipment, skills, groups, *, seed=None, rules=None, record_timeline=True
    ):
        self.boss_attacks = False
        self.record_timeline = record_timeline
        self.duration = nonnegative(config.get("battle", {}).get("duration", 200), "战斗时长")
        if self.duration > 3600 or self.duration < 0.1:
            raise BattleConfigurationError("单次模拟时长应为0.1到3600秒")
        if seed is not None and (type(seed) is not int or not 0 <= seed <= 2**53 - 1):
            raise BattleConfigurationError("随机种子应为0到2^53-1的整数")
        self.seed = seed if seed is not None else random.SystemRandom().randrange(2**53)
        self.rng = random.Random(self.seed)
        self.state = initialize_battle(config, equipment)
        self.equipment = equipment
        self.rules = {
            "burn_ticks": True,
            "true_damage": True,
            "immediate_action": True,
            "healing": True,
            **(rules or {}),
        }
        self.warnings = set()
        if any(c.domain_ring and c.domain_ring["kind"] == "earth" for c in self.state.characters):
            self.warnings.add(
                "地之环格挡属性已计算；本次模拟不包含敌方攻击，格挡不生效（为所选Boss设置技能组后才会模拟Boss攻击）。"
            )
        if any(
            c.domain_ring and c.domain_ring["restriction"] == "fragile"
            for c in self.state.characters
        ):
            self.warnings.add(
                "炎之环受伤增幅已记录；本次模拟不包含敌方攻击，受伤增幅不生效（为所选Boss设置技能组后才会模拟Boss攻击）。"
            )
        self.sequences = {}
        for c, row in zip(self.state.characters, config["characters"]):
            if not c.enabled:
                continue
            group = groups.get(row.get("skillGroup"))
            if not group:
                raise BattleConfigurationError(f"角色{c.index}请选择当前转职的技能组")
            scope = group.get("scope") or {"kind": "general"}
            if scope.get("kind") == "boss":
                selected = config.get("target", {}).get("selectedBoss") or {}
                if selected.get("id") != scope.get("bossId") or config.get(
                    "librarySelections", {}
                ).get("bosses", "") != scope.get("libraryId", ""):
                    raise BattleConfigurationError(
                        "技能组“"
                        + group["name"]
                        + "”仅适用于"
                        + scope.get("libraryName", "")
                        + " · "
                        + scope.get("bossName", "")
                    )
            for sub in group["subgroups"]:
                for node in sub["skills"]:
                    for case in node.get("decision", {}).get("cases", []):
                        negative = case.get("requiredDebuff")
                        positive = case.get("absentBuff")
                        if negative:
                            boss_skills = (
                                (config.get("target", {}).get("selectedBoss") or {})
                                .get("skillGroup", {})
                                .get("skills", [])
                            )
                            if not any(
                                s.get("id") == negative["skillId"]
                                and (s.get("effect") or {}).get("kind") == "debuff"
                                and s["effect"].get("type") == negative["type"]
                                for s in boss_skills
                            ):
                                raise BattleConfigurationError(
                                    "指定Boss负面来源已变更，请重新选择状态条件"
                                )
                        if positive:
                            definition = skills.get(positive["skillId"], {})
                            if (
                                definition.get("name") != positive["skillName"]
                                or (definition.get("effect") or {}).get("type") != positive["type"]
                            ):
                                raise BattleConfigurationError(
                                    "指定增益技能已变更，请重新选择状态条件"
                                )
                        if case.get("targetSelection") == "matchedMember":
                            definition = skills.get(case["skillId"], {})
                            if (
                                definition.get("damageType") != "none"
                                or definition.get("healingRecipient") == "allAllies"
                            ):
                                raise BattleConfigurationError("条件命中的成员仅可用于单体回复技能")
            self.sequences[c.index] = SkillSequence(
                resolve_equipment_conditions(group, c.equipment, equipment), skills, c.job
            )
            for slot in ("weapon", "armor", "accessory1", "accessory2", "stone"):
                item_id = c.equipment.get(slot)
                if item_id and item_id not in equipment:
                    raise BattleConfigurationError("装备不存在，请重新选择")
        if not self.sequences:
            raise BattleConfigurationError("至少需要一个参战角色")
        self.boss_debuffs = {}
        self.target_base_attributes = deepcopy(self.state.target.get("attributes", {}))
        for attribute in ("strength", "technique"):
            self.target_base_attributes.setdefault(attribute, self.state.target.get(attribute, 0))
        self.frames = []
        self.total_damage = sum(
            e["damage"] for e in self.state.events if e["type"] == "starting_life_deprivation"
        )
        self.immediate = {}
        self.waiting = {}
        self.operating = {}
        self.party_wipe_at = party_wipe_time(config["target"])
        self.kill_interval = self.party_wipe_at
        self.kill_strategy = periodic_kill_strategy(config["target"])
        self.survival_at_all_kill = None
        self.end_reason = "duration"
        self.character_damage = [
            sum(
                e["damage"]
                for e in self.state.events
                if e["type"] == "starting_life_deprivation" and e["character"] == i
            )
            for i in range(1, 5)
        ]
        self.effect_counts = [{} for _ in range(4)]

    def refresh_target_attributes(self):
        attributes = deepcopy(self.target_base_attributes)
        for buff in self.boss_debuffs.values():
            attribute = buff.get("attribute")
            if attribute:
                attributes[attribute] = max(1, attributes.get(attribute, 0) - buff["amount"])
        self.state.target["attributes"] = attributes
        for attribute in ("strength", "technique"):
            self.state.target[attribute] = attributes.get(attribute, 0)

    def buff_refs(self, character):
        return [
            {
                "name": b.name,
                "source_character": b.source_character,
                "target_character": character.index,
            }
            for b in character.buffs
        ]

    def emit(self, event_type, **values):
        self.state.events.append({"time": self.state.time, "type": event_type, **values})

    def snapshot(self):
        return {
            "characters": [asdict(c) for c in self.state.characters],
            "target_current_hp": self.state.target_current_hp,
            "target_attributes": deepcopy(
                self.state.target.get("attributes", self.target_base_attributes)
            ),
            "target_recovery_multiplier": self.state.target.get("recoveryMultiplier", 1),
            "target_healing_reduction": self.state.target.get("combinedHealingReduction", 0),
            "target_debuffs": deepcopy(
                self.state.target.get("equipmentVulnerabilityDebuffs", [])
                + self.state.target.get("equipmentDotDebuffs", [])
                + self.state.target.get("equipmentRecoveryDebuffs", [])
                + list(self.boss_debuffs.values())
            ),
        }

    def record(self, offset):
        events = self.state.events[offset:]
        for event in events:
            if event["type"] in (
                "skill_damage",
                "equipment_damage",
                "dot_damage",
                "contract_damage",
            ):
                index = event.get("character", event.get("owner_character"))
                self.character_damage[index - 1] += event["damage"]
            elif event["type"] == "equipment_triggered":
                key = (
                    event["source_slot"],
                    event["equipment_id"],
                    event["name"],
                    event["trigger_type"],
                    event["kind"],
                )
                counts = self.effect_counts[event["character"] - 1]
                counts[key] = counts.get(key, 0) + 1
        if events and self.record_timeline:
            self.frames.append(
                {"time": self.state.time, "events": deepcopy(events), "snapshot": self.snapshot()}
            )
        if not self.record_timeline:
            self.state.discarded_event_count += len(self.state.events)
            self.state.events.clear()

    def deal_damage(self, amount):
        self.total_damage += amount
        if self.state.target_current_hp is not None:
            self.state.target_current_hp = max(0.0, self.state.target_current_hp - amount)

    def recipients(self, source, recipient):
        if recipient == "self":
            return [source.index]
        if recipient == "allAllies":
            return [c.index for c in self.state.characters if c.enabled and c.alive]
        if recipient == "singleAlly":
            allies = [
                c
                for c in self.state.characters
                if c.enabled and c.alive and c.index != source.index
            ]
            return [min(allies, key=lambda c: c.current_hp).index] if allies else []
        raise BattleConfigurationError("buff对象无效")

    def apply_buff(
        self, c, name, effect, item=None, slot="", selected_target=None, healing_targets=None
    ):
        targets = (
            healing_targets or []
            if effect.get("recipient") == "healingTargets"
            else self.recipients(c, effect.get("recipient", "self"))
        )
        if effect.get("type") == "regeneration":
            source_stats = deepcopy(c.stats)
            amount = (
                (
                    effect.get("baseValue", 0)
                    + sum(
                        source_stats.get(k, 0) * v
                        for k, v in effect.get("coefficients", {}).items()
                    )
                )
                * (1 + source_stats.get("healingBonus", 0) / 100)
                * (1 + source_stats.get("finalHealingBonus", 0) / 100)
            )
            for index in targets:
                target = self.state.characters[index - 1]
                target.regeneration_buffs = [
                    b for b in target.regeneration_buffs if b["name"] != name
                ]
                target.regeneration_buffs.append(
                    {
                        "name": name,
                        "source_character": c.index,
                        "target_character": index,
                        "source_stats": source_stats,
                        "amount": amount,
                        "next_tick_at": add_time(self.state.time, 1),
                        "applied_at": self.state.time,
                        "expires_at": add_time(self.state.time, effect["duration"])
                        if effect.get("duration")
                        else None,
                    }
                )
                self.emit(
                    "regeneration_applied",
                    character=c.index,
                    target_character=index,
                    name=name,
                    amount=amount,
                    duration=effect.get("duration", 0),
                )
            return
        rows = {
            r["target"]: r["coefficients"] for r in effect.get("conversions", []) if r["enabled"]
        }
        if not rows:
            raise BattleConfigurationError("buff没有启用任何属性增幅，请检查：" + name)
        base = {effect["type"]: effect.get("baseValue", 0)}
        apply_named_buff(
            self.state,
            name=name,
            source_index=c.index,
            target_indices=targets,
            conversions=rows,
            now=self.state.time,
            duration=effect.get("duration") or None,
            max_stacks=effect.get("maxStacks", 1),
            base_values=base,
            source_equipment_id=item["id"] if item else "",
            source_equipment_name=item["name"] if item else "",
            source_slot=slot,
            expire_due=False,
            return_snapshot=self.record_timeline,
        )

    def apply_debuff(self, c, name, effect, stats, *, equipment=False, active_buff_refs=None):
        kind = effect["type"]
        source_name = name
        name = DEBUFF_NAMES[kind]
        if self.state.target.get("immuneNegativeEffects") or self.state.target.get(
            IMMUNITIES[kind]
        ):
            self.emit("debuff_immune", name=name, debuff_name=DEBUFF_NAMES[kind], character=c.index)
            return
        if not equipment:
            details = check_skill_debuff_application(
                stats, effect, self.state.target, hit=True, rng=self.rng
            )
            if not details["applied"]:
                self.emit("debuff_failed", name=name, character=c.index, **details)
                return
        old = self.boss_debuffs.get(name)
        stacks = 1  # Target debuffs replace the old effect; never accumulate layers.
        value = {
            "name": name,
            "type": kind,
            "character": c.index,
            "stacks": stacks,
            "effect": deepcopy(effect),
            "source_stats": deepcopy(stats),
            "source_name": source_name,
            "active_buff_refs": self.buff_refs(c) if active_buff_refs is None else active_buff_refs,
            "expires_at": add_time(self.state.time, effect["duration"]),
            "next_tick_at": add_time(self.state.time, 1),
            "applied_at": self.state.time,
        }
        if kind in ("weakness", "fear"):
            value["attribute"] = "strength" if kind == "weakness" else "technique"
            value["amount"] = effect.get("baseValue", 0) + sum(
                stats.get(k, 0) * v for k, v in effect.get("coefficients", {}).items()
            )
        self.boss_debuffs[name] = value
        if kind in ("weakness", "fear"):
            self.refresh_target_attributes()
        self.emit(
            "target_debuff_applied",
            name=name,
            debuff_name=DEBUFF_NAMES[kind],
            character=c.index,
            stacks=stacks,
            expires_at=value["expires_at"],
            attribute=value.get("attribute"),
            amount=value.get("amount"),
        )
        if kind in ("burn", "lifeLoss") and not self.rules.get("burn_ticks"):
            self.warnings.add(
                "灼烧暂只记录附加和到期；周期、属性取值及覆盖规则待确认，未计入总伤害。"
            )
        elif kind in ("bleeding", "plague"):
            self.warnings.add("流血和瘟疫伤害规则尚未指定，暂只记录附加和到期。")

    def procs(self, c, skill):
        result = []
        for slot in ("weapon", "armor", "accessory1", "accessory2", "stone"):
            item = self.equipment.get(c.equipment.get(slot))
            if not item or not item.get("triggerEnabled"):
                continue
            for row in item.get("triggerEffects", []):
                if (
                    row.get("effect")
                    and row["triggerType"] == skill["damageType"]
                    and self.rng.random() < row["probability"] / 100
                ):
                    # Only the first successful effect may trigger this action.
                    return [(item, slot, row)]
        return result

    def matching_members(self, condition, actor):
        matches = []
        negative = condition.get("requiredDebuff")
        positive = condition.get("absentBuff")
        for member in self.state.characters:
            if (
                not member.enabled
                or not member.alive
                or (not condition.get("includeSelf", True) and member.index == actor)
            ):
                continue
            if negative:
                if not hasattr(self, "boss_runtime"):
                    continue
                from .compiled.boss import KINDS

                k = KINDS.index(negative["type"])
                status = self.boss_runtime[4][member.index - 1, k]
                idx = next(
                    (
                        i
                        for i, s in enumerate(self.boss_group["skills"])
                        if s["id"] == negative["skillId"]
                    ),
                    -1,
                )
                if not status[0] or status[5] != idx:
                    continue
                if self.state.time + 1e-9 < add_time(
                    float(status[6]), condition.get("recognitionDelay", 0)
                ):
                    continue
            if positive:
                buff_name = re.sub(
                    r"\s*lv\.?\s*\d+\s*$", "", positive["skillName"], flags=re.IGNORECASE
                ).strip()
                if positive["type"] == "regeneration":
                    present = any(b["name"] == buff_name for b in member.regeneration_buffs)
                else:
                    present = any(
                        b.name == buff_name and b.attribute == positive["type"]
                        for b in member.buffs
                    )
                if present:
                    continue
            matches.append(member)
        return matches

    def healing_target(self, source):
        return min(
            (ally for ally in self.state.characters if ally.enabled and ally.alive),
            key=lambda ally: ally.current_hp,
        )

    def action(self, index):
        c = self.state.characters[index - 1]
        sequence = self.sequences[index]
        if not c.alive or not sequence.current:
            return
        finished_wait = False
        operation = self.operating.get(index)
        if operation:
            if self.state.time < operation[0]:
                return
            self.operating.pop(index)
            target = self.state.characters[operation[1] - 1]
            if not target.enabled or not target.alive:
                self.emit("operation_cancelled", character=index, target_character=target.index)
                return
            sequence.matched_member = target
            self.emit("operation_finished", character=index, target_character=target.index)
        if index in self.waiting:
            if self.state.time < self.waiting[index]:
                return
            self.waiting.pop(index)
            self.emit("wait_finished", character=index)
            sequence.advance()
            if not sequence.current:
                return
            finished_wait = True
        ready = action_ready_now(c, self.state.time)
        forced = self.immediate.get(index)
        if (
            not operation
            and not finished_wait
            and not (self.state.time >= forced if forced is not None else ready)
        ):
            return
        if not operation and not sequence.choose_for_action(self.state.characters, index, self):
            return
        skill = sequence.nodes[sequence.current]
        if not operation and skill.get("operationDelay", 0) > 0:
            end = add_time(self.state.time, skill["operationDelay"])
            self.operating[index] = (end, sequence.matched_member.index)
            self.immediate.pop(index, None)
            c.next_action_at = end
            self.emit(
                "operation_started",
                character=index,
                target_character=sequence.matched_member.index,
                skill_name=skill["name"],
                duration=skill["operationDelay"],
                ends_at=end,
            )
            return
        if skill.get("damageType") == "wait":
            # Wait begins only after ordinary CD readiness; it never rolls equipment procs.
            if not finished_wait and not ready:
                return
            self.immediate.pop(index, None)
            end = add_time(self.state.time, skill["waitDuration"])
            self.waiting[index] = end
            c.next_action_at = end
            self.emit(
                "skill_released",
                character=index,
                character_name=c.name,
                job=c.job,
                skill_name="等待",
            )
            self.emit("wait_started", character=index, duration=skill["waitDuration"], ends_at=end)
            return
        selection = skill.get("targetSelection", "default")
        chosen = (
            (
                sequence.matched_member
                if skill.get("matchedMember") and sequence.matched_member is not None
                else self.healing_target(c)
            )
            if skill["damageType"] == "none"
            else c
        )
        healing_targets = []
        selected_target = None
        self.emit(
            "skill_released",
            character=index,
            character_name=c.name,
            job=c.job,
            skill_name=skill["name"],
        )
        procs = self.procs(c, skill)
        for item, slot, row in procs:
            self.emit(
                "equipment_triggered",
                character=index,
                equipment_name=item["name"],
                name=row["name"] or item["name"],
                kind=row["effect"]["kind"],
                equipment_id=item["id"],
                source_slot=slot,
                trigger_type=row["triggerType"],
            )
        attack_refs = self.buff_refs(c) if self.record_timeline else []
        stats = attack_snapshot(
            c, [row["effect"] for _, _, row in procs if row["effect"]["kind"] == "amplify"]
        )
        hit = True
        if skill["damageType"] in ("physical", "magic"):
            hit_details = calculate_hit_chance(stats, skill, self.state.target)
            probability = hit_details["probability"]
            roll = self.rng.random()
            hit = roll < probability
            if hit:
                details = calculate_damage(stats, skill, self.state.target, rng=self.rng)
                self.deal_damage(details["final_damage"])
                self.emit(
                    "skill_damage",
                    character=index,
                    skill_name=skill["name"],
                    damage=details["final_damage"],
                    damage_type=skill["damageType"],
                    critical=details["critical"],
                    attack_stats=stats,
                    factors=details["factors"],
                )
                # Lifesteal uses only this landed skill's resolved damage, before equipment effects.
                scope = "Area" if skill.get("targeting", "single") == "all" else "Single"
                rate = stats.get(skill["damageType"] + scope + "Lifesteal", 0) + skill.get(
                    "lifesteal", 0
                )
                if rate > 0:
                    amount = reduce_ally_recovery(
                        self.state,
                        details["final_damage"] * rate / 100,
                        kind="lifesteal",
                        recipient=c,
                    )
                    before = c.current_hp
                    c.current_hp = min(c.maximum_hp, c.current_hp + amount)
                    c.stats["hitPoint"] = c.current_hp
                    self.emit(
                        "lifesteal",
                        character=index,
                        target_character=index,
                        skill_name=skill["name"],
                        amount=amount,
                        effective_amount=c.current_hp - before,
                        damage_type=skill["damageType"],
                        targeting=skill.get("targeting", "single"),
                    )
            else:
                self.emit(
                    "skill_missed",
                    character=index,
                    skill_name=skill["name"],
                    hit_probability=probability,
                    roll=roll,
                )
        else:
            if self.rules.get("healing"):
                base = sum(stats.get(k, 0) * v for k, v in skill["coefficients"].items())
                healing_factor = 1 + stats.get("healingBonus", 0) / 100
                imprint_factor = 1 + stats.get("finalHealingBonus", 0) / 100
                amount = base * healing_factor * imprint_factor
                recipients = (
                    self.state.characters
                    if skill.get("healingRecipient", "self") == "allAllies"
                    else [chosen or c]
                )
                for recipient in recipients:
                    if not recipient.enabled or not recipient.alive:
                        continue
                    healing_targets.append(recipient.index)
                    before = recipient.current_hp
                    recipient.current_hp = min(
                        recipient.maximum_hp,
                        recipient.current_hp
                        + reduce_ally_recovery(self.state, amount, recipient=recipient),
                    )
                    recipient.stats["hitPoint"] = recipient.current_hp
                    self.emit(
                        "healing",
                        character=index,
                        target_character=recipient.index,
                        skill_name=skill["name"],
                        amount=reduce_ally_recovery(self.state, amount, recipient=recipient),
                        effective_amount=recipient.current_hp - before,
                    )
            else:
                self.warnings.add("回复技能的回血公式待确认，当前执行其buff和装备触发，暂不回血。")
        # Persistent equipment buffs start after this skill's damage/healing.
        for item, slot, row in procs:
            if row["effect"]["kind"] == "buff":
                self.apply_buff(c, row["name"] or item["name"], row["effect"], item, slot)
        effect = skill.get("effect")
        if (
            effect
            and effect["kind"] == "buff"
            and self.rng.random() < effect.get("triggerRate", 100) / 100
        ):
            buff_name = re.sub(
                r"\s*lv\.?\s*\d+\s*$", "", skill["name"], flags=re.IGNORECASE
            ).strip()
            self.apply_buff(
                c,
                buff_name,
                effect,
                selected_target=selected_target,
                healing_targets=healing_targets,
            )
        elif effect and effect["kind"] == "debuff" and hit:
            self.apply_debuff(
                c,
                skill["name"] + "·" + DEBUFF_NAMES[effect["type"]],
                effect,
                stats,
                active_buff_refs=attack_refs,
            )
        for item, slot, row in procs:
            effect = row["effect"]
            if effect["kind"] in ("trueDamage", "physicalTrueDamage", "magicTrueDamage"):
                if self.rules.get("true_damage"):
                    damage_type = {
                        "physicalTrueDamage": "physical",
                        "magicTrueDamage": "magic",
                    }.get(effect["kind"], row["triggerType"])
                    details = calculate_equipment_damage(
                        stats, effect, self.state.target, damage_type
                    )
                    damage = details["final_damage"]
                    self.deal_damage(damage)
                    self.emit(
                        "equipment_damage",
                        character=index,
                        equipment_name=item["name"],
                        name=row["name"],
                        damage=damage,
                        damage_type=damage_type,
                        factors=details["factors"],
                    )
                else:
                    self.warnings.add("装备真伤的结算规则待确认，当前只记录触发，未计入总伤害。")
            elif effect["kind"] == "healing":
                amount = (
                    sum(stats.get(k, 0) * v for k, v in effect["coefficients"].items())
                    * (1 + stats.get("healingBonus", 0) / 100)
                    * (1 + stats.get("finalHealingBonus", 0) / 100)
                )
                for recipient_index in self.recipients(c, effect.get("recipient", "self")):
                    recipient = self.state.characters[recipient_index - 1]
                    if not recipient.alive:
                        continue
                    before = recipient.current_hp
                    recipient.current_hp = min(
                        recipient.maximum_hp,
                        before + reduce_ally_recovery(self.state, amount, recipient=recipient),
                    )
                    recipient.stats["hitPoint"] = recipient.current_hp
                    self.emit(
                        "healing",
                        character=index,
                        target_character=recipient.index,
                        skill_name=row["name"] or item["name"],
                        amount=reduce_ally_recovery(self.state, amount, recipient=recipient),
                        effective_amount=recipient.current_hp - before,
                    )
            elif effect["kind"] == "debuff" and hit:
                self.apply_debuff(
                    c,
                    row["name"] or item["name"],
                    effect,
                    stats,
                    equipment=True,
                    active_buff_refs=attack_refs,
                )
        # Forced 0.5s actions may bypass the ordinary readiness check only here.
        if forced is not None:
            c.last_action_at = self.state.time
            c.last_skill_cooldown = skill["cooldown"]
            self.immediate.pop(index, None)
        else:
            schedule_after_action(self.state, index, skill["cooldown"], check_ready=False)
        sequence.advance(procs)
        if any(row["effect"]["kind"] == "immediateAction" for _, _, row in procs):
            if self.rules.get("immediate_action"):
                self.immediate[index] = add_time(self.state.time, 0.5)
            else:
                self.warnings.add("立即行动特效规则待确认，当前只记录触发。")

    def next_event_step(self, step, last_step):
        """Jump only across empty 0.1s ticks; no random draws occur on those ticks.

        Attribute changes happen at events. Recompute all deadlines after each
        event group, retaining dynamic cooldowns and the original 0.1s grid.
        """
        times = [
            c.ring_next_tick
            for c in self.state.characters
            if c.enabled
            and c.alive
            and c.domain_ring
            and c.domain_ring["restriction"] == "sacrifice"
        ]
        times += [b["next_tick_at"] for b in self.state.target.get("equipmentDotDebuffs", [])]
        if self.party_wipe_at is not None:
            times.append(self.party_wipe_at)
        for c in self.state.characters:
            times.extend(b.expires_at for b in c.buffs if b.expires_at is not None)
            if c.enabled and c.alive:
                times.extend(d.next_tick_at for d in c.debuffs if d.name == "群体献祭")
                sequence = self.sequences.get(c.index)
                if sequence and sequence.current:
                    if c.index in self.operating:
                        times.append(self.operating[c.index][0])
                    elif c.index in self.waiting:
                        times.append(self.waiting[c.index])
                    else:
                        times.append(self.immediate.get(c.index, current_action_deadline(c)))
        for b in self.boss_debuffs.values():
            times.append(b["expires_at"])
            if (
                b["type"] in ("burn", "lifeLoss")
                and self.rules.get("burn_ticks")
                and b["next_tick_at"] <= b["expires_at"]
            ):
                times.append(b["next_tick_at"])
        if self.state.contract and self.state.contract.active:
            times.append(self.state.contract.next_tick_at)
        next_step = min(
            (int((Decimal(str(t)) * 10).to_integral_value(rounding=ROUND_CEILING)) for t in times),
            default=last_step,
        )
        return max(step + 1, min(next_step, last_step))

    def has_manual_action(self, index):
        return False

    def before_action(self, index):
        # Interactive engines may suspend here, preserving same-tick event ordering.
        return ()

    def run(self, cancel_event=None):
        iterator = self.iter_run(cancel_event)
        while True:
            try:
                next(iterator)
            except StopIteration as result:
                return result.value

    def iter_run(self, cancel_event=None):
        self.emit("battle_started")
        mark_deaths(self.state)
        self.record(0)
        yield {"kind": "tick"}
        last_step = int(Decimal(str(self.duration)) * 10)
        if self.state.target_current_hp is not None and self.state.target_current_hp <= 0:
            self.end_reason = "target_defeated"
            last_step = 0
        step = 1
        while step <= last_step:
            if cancel_event is not None:
                from .cancellation import check_cancelled

                check_cancelled(cancel_event)
            self.state.time = step / 10
            offset = len(self.state.events)
            refresh_rings(self.state)
            # DOT ticks have absolute priority, including the party wipe deadline.
            for buff in self.state.target.get("equipmentDotDebuffs", []):
                if buff["next_tick_at"] <= self.state.time:
                    self.deal_damage(buff["damage"])
                    self.emit(
                        "dot_damage",
                        character=buff["character"],
                        name=buff["name"],
                        damage=buff["damage"],
                        damage_type="dot",
                        active_buff_refs=buff.get("active_buff_refs", []),
                    )
                    buff["next_tick_at"] = add_time(buff["next_tick_at"], 1)
            for name, buff in list(self.boss_debuffs.items()):
                if (
                    buff["type"] in ("burn", "lifeLoss")
                    and self.rules.get("burn_ticks")
                    and buff["next_tick_at"] <= self.state.time
                    and buff["next_tick_at"] <= buff["expires_at"]
                ):
                    details = calculate_burn_damage(
                        buff["source_stats"], buff["effect"], self.state.target
                    )
                    damage = details["final_damage"] * buff["stacks"]
                    self.deal_damage(damage)
                    self.emit(
                        "dot_damage",
                        character=buff["character"],
                        name=name,
                        damage=damage,
                        damage_type="dot",
                        active_buff_refs=buff.get("active_buff_refs", []),
                    )
                    buff["next_tick_at"] = add_time(buff["next_tick_at"], 1)
                    if buff["expires_at"] <= self.state.time:
                        del self.boss_debuffs[name]
                        self.emit("target_debuff_expired", name=name, character=buff["character"])
            if self.state.target_current_hp is not None and self.state.target_current_hp <= 0:
                self.end_reason = "target_defeated"
                self.record(offset)
                break
            if self.boss_attacks:
                self.boss_periodic()
            if self.party_wipe_at is not None and self.state.time >= self.party_wipe_at:
                if self.kill_strategy == "all" and self.survival_at_all_kill is None:
                    self.survival_at_all_kill = [
                        c.enabled and c.alive for c in self.state.characters
                    ]
                candidates = [c for c in self.state.characters if c.enabled and c.alive]
                if self.kill_strategy == "random" and candidates:
                    candidates = [
                        candidates[
                            min(len(candidates) - 1, int(self.rng.random() * len(candidates)))
                        ]
                    ]
                elif self.kill_strategy == "lowestHp" and candidates:
                    candidates = [min(candidates, key=lambda c: c.current_hp)]
                elif self.kill_strategy == "highestHp" and candidates:
                    candidates = [max(candidates, key=lambda c: c.current_hp)]
                self.emit(
                    "boss_periodic_kill",
                    skill_name="定时击杀",
                    scheduled_at=self.party_wipe_at,
                    strategy=self.kill_strategy,
                    target_characters=[c.index for c in candidates],
                )
                for c in candidates:
                    c.current_hp = 0.0
                    c.stats["hitPoint"] = 0.0
                mark_deaths(self.state)
                self.party_wipe_at = add_time(self.party_wipe_at, self.kill_interval)
                if not any(c.enabled and c.alive for c in self.state.characters):
                    self.end_reason = "party_defeated"
                    self.record(offset)
                    break
            process_ring_ticks(self.state)
            if any(
                d.next_tick_at <= self.state.time
                for c in self.state.characters
                if c.enabled and c.alive
                for d in c.debuffs
                if d.name == "群体献祭"
            ):
                process_sacrifice_ticks(self.state, self.state.time)
            mark_deaths(self.state)
            for c in self.state.characters:
                if not c.enabled or not c.alive:
                    c.regeneration_buffs = []
                    continue
                c.regeneration_buffs = [
                    buff
                    for buff in c.regeneration_buffs
                    if buff.get("expires_at") is None or buff["next_tick_at"] <= buff["expires_at"]
                ]
                for buff in c.regeneration_buffs:
                    if buff["next_tick_at"] <= self.state.time:
                        amount = reduce_ally_recovery(
                            self.state, buff["amount"], kind="regeneration", recipient=c
                        )
                        before = c.current_hp
                        c.current_hp = min(c.maximum_hp, before + amount)
                        c.stats["hitPoint"] = c.current_hp
                        buff["next_tick_at"] = add_time(buff["next_tick_at"], 1)
                        self.emit(
                            "regeneration",
                            character=buff["source_character"],
                            target_character=c.index,
                            name=buff["name"],
                            amount=amount,
                            effective_amount=c.current_hp - before,
                        )
            pending = []
            for c in self.state.characters:
                expired = {}
                for buff in c.buffs:
                    if buff.expires_at is not None and buff.expires_at <= self.state.time:
                        key = (buff.name, buff.source_character, buff.applied_at, buff.expires_at)
                        expired.setdefault(key, []).append(buff.id)
                for identifiers in expired.values():
                    pending.append(("expire", c.index, identifiers))
            for name, buff in self.boss_debuffs.items():
                if buff["expires_at"] <= self.state.time:
                    if not (
                        buff["type"] in ("burn", "lifeLoss")
                        and self.rules.get("burn_ticks")
                        and buff["next_tick_at"] <= buff["expires_at"]
                    ):
                        pending.append(("target_expire", name, buff["applied_at"]))
                if (
                    buff["type"] in ("burn", "lifeLoss")
                    and self.rules.get("burn_ticks")
                    and buff["next_tick_at"] <= self.state.time
                    and buff["next_tick_at"] <= buff["expires_at"]
                ):
                    pass  # Already resolved before wipe and actions.
            for index, sequence in self.sequences.items():
                if sequence.current or self.has_manual_action(index):
                    pending.append(("action", index, None))
            if (
                self.state.contract
                and self.state.contract.active
                and self.state.contract.next_tick_at <= self.state.time
            ):
                pending.append(("contract", None, None))
            # All character actions form one indivisible block, in party order.
            # Other events can occur before or after the block, never inside it.
            actions = sorted(
                (event for event in pending if event[0] == "action"), key=lambda event: event[1]
            )
            pending = [event for event in pending if event[0] != "action"]
            if actions:
                pending.append(("action_block", None, None))
            if self.boss_attacks and self.boss_ready():
                pending.append(("boss_action", None, None))
            self.rng.shuffle(pending)
            for kind, index, identifier in pending:
                refresh_rings(self.state)
                if kind == "boss_action":
                    self.boss_action()
                elif kind == "expire":
                    c = self.state.characters[index - 1]
                    for buff_id in identifier:
                        buff = next((b for b in c.buffs if b.id == buff_id), None)
                        if buff:
                            _remove(self.state, c, buff, "buff_expired", self.state.time)
                elif kind == "action_block":
                    for _, actor, _ in actions:
                        action_offset = len(self.state.events)
                        refs = (
                            self.buff_refs(self.state.characters[actor - 1])
                            if self.record_timeline
                            else []
                        )
                        refresh_rings(self.state)
                        yield from self.before_action(actor)
                        self.action(actor)
                        action_events = self.state.events[action_offset:]
                        if any(e["type"] == "skill_released" for e in action_events):
                            action_id = f"{step}:{actor}:{action_offset}"
                            for e in action_events:
                                e["action_id"] = action_id
                                e["action_character"] = actor
                                if self.record_timeline:
                                    e["active_buff_refs"] = refs
                elif kind == "contract":
                    if not self.state.contract or not self.state.contract.active:
                        continue
                    # Existing helper expects the exact deadline; all supported ticks are on grid.
                    contract = self.state.contract
                    if contract.name.endswith("-技"):
                        owner = self.state.characters[contract.owner_index - 1]
                        extra = 4 if contract.name == "炎钢羽神-技" and contract.ticks == 0 else 1
                        if contract.name == "饮魂者-技":
                            maximum = self.state.target.get("hitPoint", 0)
                            if maximum <= 0:
                                raise BattleConfigurationError("饮魂者需要敌方最大生命值")
                            import math

                            extra = 1 + 0.3 * min(
                                4,
                                math.floor(
                                    max(0, 1 - self.state.target_current_hp / maximum) * 4 + 1e-9
                                ),
                            )
                        effect = {
                            "kind": "debuff",
                            "type": "burn",
                            "baseValue": 0,
                            "duration": 1,
                            "coefficients": {"technique": contract.skill_multiplier * extra},
                        }
                        self.apply_debuff(owner, contract.name, effect, owner.stats, equipment=True)
                        self.emit(
                            "contract_dot_applied",
                            character=owner.index,
                            name=contract.name,
                            next_tick_at=add_time(self.state.time, 1),
                        )
                        contract.ticks += 1
                        contract.next_tick_at = add_time(contract.next_tick_at, contract.interval)
                    else:
                        details = resolve_contract_tick(self.state, expire_due=False)
                        self.total_damage += details["damage"]
                elif kind == "target_expire":
                    buff = self.boss_debuffs.get(index)
                    if (
                        buff
                        and buff["applied_at"] == identifier
                        and buff["expires_at"] <= self.state.time
                    ):
                        del self.boss_debuffs[index]
                        self.refresh_target_attributes()
                        self.emit("target_debuff_expired", name=index, character=buff["character"])
                elif kind == "burn":
                    buff = self.boss_debuffs.get(index)
                    if (
                        buff
                        and buff["applied_at"] == identifier
                        and buff["next_tick_at"] <= self.state.time
                    ):
                        details = calculate_burn_damage(
                            buff["source_stats"], buff["effect"], self.state.target
                        )
                        damage = details["final_damage"] * buff["stacks"]
                        self.deal_damage(damage)
                        self.emit(
                            "dot_damage",
                            character=buff["character"],
                            name=index,
                            damage=damage,
                            damage_type="dot",
                            active_buff_refs=buff.get("active_buff_refs", []),
                        )
                        buff["next_tick_at"] = add_time(buff["next_tick_at"], 1)
                        if buff["expires_at"] <= self.state.time:
                            del self.boss_debuffs[index]
                            self.emit(
                                "target_debuff_expired", name=index, character=buff["character"]
                            )
            self.record(offset)
            if not any(c.enabled and c.alive for c in self.state.characters):
                self.end_reason = "party_defeated"
                break
            if self.state.target_current_hp is not None and self.state.target_current_hp <= 0:
                self.end_reason = "target_defeated"
                break
            yield {"kind": "tick"}
            step = step + 1 if self.record_timeline else self.next_event_step(step, last_step)
        return {
            "seed": self.seed,
            "step": 0.1,
            "duration": self.state.time,
            "end_reason": self.end_reason,
            "total_damage": self.total_damage,
            "warnings": sorted(self.warnings),
            "timeline": self.frames,
            "final_state": self.snapshot() if self.record_timeline else None,
            "character_damage": self.character_damage,
            "effect_counts": [
                [
                    {
                        "slot": key[0],
                        "equipment_id": key[1],
                        "name": key[2],
                        "trigger_type": key[3],
                        "kind": key[4],
                        "count": count,
                    }
                    for key, count in counts.items()
                ]
                for counts in self.effect_counts
            ],
        }


def simulate_single(config, equipment, skills, groups, *, seed=None, rules=None):
    return SingleBattle(config, equipment, skills, groups, seed=seed, rules=rules).run()
