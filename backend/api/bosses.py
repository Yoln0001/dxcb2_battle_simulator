"""Boss records with panel attributes, target rules and a saved skill group."""

from .library_routes import library_router
from ..library_store import LibraryStore
from ..skill_groups.validation import target_selection, wait_seconds
from ..skills.store import SkillError, text, number, validate_skill
import uuid, json
from copy import deepcopy

ATTRIBUTES = (
    "weaponPower",
    "strength",
    "magic",
    "technique",
    "speed",
    "constitution",
    "hitPoint",
    "armor",
    "resistance",
    "criticalRate",
    "hitRate",
    "ignoreArmor",
    "ignoreResistance",
    "abnormalBonus",
    "physicalDamage",
    "finalPhysicalDamage",
    "magicDamage",
    "finalMagicDamage",
    "dotDamage",
    "finalDotDamage",
    "healingBonus",
    "finalHealingBonus",
    "unload",
    "criticalMultiplier",
    "physicalSingleLifesteal",
    "magicSingleLifesteal",
    "physicalAreaLifesteal",
    "magicAreaLifesteal",
    "dodgeRate",
)
TARGET_DEFAULTS = {
    "physicalReduction": 0,
    "magicReduction": 0,
    "dotReduction": 0,
    "allyLifestealReduction": 0,
    "allyHealingReduction": 0,
    "allyRegenerationReduction": 0,
}
IMMUNITIES = (
    "immuneBleeding",
    "immunePlague",
    "immuneBurn",
    "immuneSpeedReduction",
    "immuneStun",
    "immuneWeakness",
    "immuneFear",
    "immuneLifeLoss",
    "immunePhysicalVulnerability",
    "immuneMagicVulnerability",
    "immuneNegativeEffects",
)


def validate_boss_group(value):
    # Old player-group references remain readable but are never shared with Boss skills.
    if isinstance(value, str):
        value = {}
    if value is None:
        value = {}
    if not isinstance(value, dict) or not isinstance(value.get("skills", []), list):
        raise SkillError("Boss专属技能组格式无效")
    rows = value.get("skills", [])
    if len(rows) > 100:
        raise SkillError("Boss技能组最多100个技能")
    skills = []
    for row in rows:
        if not isinstance(row, dict):
            raise SkillError("Boss技能格式无效")
        kind = row.get("damageType", "physical")
        target = row.get("targeting", "single")
        if kind not in ("physical", "magic", "none") or target not in ("single", "all"):
            raise SkillError("Boss技能类型无效")
        coefs = row.get("coefficients", {})
        if not isinstance(coefs, dict) or any(k not in ATTRIBUTES for k in coefs):
            raise SkillError("Boss技能倍率无效")
        definition = validate_skill(
            {
                "schemaVersion": 1,
                "id": "boss-effect",
                "name": row.get("name"),
                "job": "Boss",
                "damageType": kind,
                "targeting": target,
                "ignoreTaunt": row.get("ignoreTaunt", False),
                "healingRecipient": row.get("healingRecipient", "self"),
                "cooldown": 0,
                "hitRate": 0,
                "criticalRate": 0,
                "coefficients": dict.fromkeys(
                    (
                        "strength",
                        "magic",
                        "technique",
                        "speed",
                        "constitution",
                        "hitPoint",
                        "weaponPower",
                    ),
                    0,
                ),
                "raceBonus": {"race": "none", "multiplier": 0},
                "effect": row.get("effect"),
            }
        )
        skills.append(
            {
                "id": text(row.get("id", f"boss_skill_{len(skills)}"), "Boss技能ID"),
                "name": text(row.get("name"), "Boss技能名称"),
                "damageType": kind,
                "targeting": target,
                "cooldown": number(row.get("cooldown", 0), "技能冷却"),
                "baseValue": number(row.get("baseValue", 0), "技能基础值"),
                "hitRate": number(row.get("hitRate", 100), "技能命中率"),
                "criticalRate": number(row.get("criticalRate", 0), "技能暴击率", 100),
                "coefficients": {k: number(v, "技能倍率") for k, v in coefs.items()},
                "targetSelection": target_selection(row.get("targetSelection", "lowestHp")),
                "ignoreTaunt": definition["ignoreTaunt"],
                "healingRecipient": definition["healingRecipient"],
                "raceBonus": definition["raceBonus"],
                "effect": definition["effect"],
            }
        )
    skill_ids = {s["id"] for s in skills}
    if len(skill_ids) != len(skills):
        raise SkillError("Boss技能ID重复")
    groups = value.get("subgroups")
    if groups is None:
        groups = (
            [
                {
                    "id": "boss_legacy_group",
                    "nextGroup": "boss_legacy_group",
                    "skills": [
                        {
                            "id": f"boss_legacy_node_{i}",
                            "skillId": s["id"],
                            "targetSelection": s["targetSelection"],
                        }
                        for i, s in enumerate(skills)
                    ],
                }
            ]
            if skills
            else []
        )
    if not isinstance(groups, list) or len(groups) > 100:
        raise SkillError("Boss子技能组格式无效（最多100组）")
    groups = deepcopy(groups)
    # Migrate the former multiple-position random group to one shared position.
    aliases = {}
    for group in groups:
        if (
            isinstance(group, dict)
            and group.get("type") == "random"
            and isinstance(group.get("skills"), list)
            and group["skills"]
        ):
            rows = group["skills"]
            if any(not isinstance(n, dict) for n in rows):
                raise SkillError("Boss技能节点格式无效")
            if len(rows) > 1 or "skillIds" not in rows[0]:
                first = rows[0]
                candidates = list(
                    dict.fromkeys(
                        n.get("skillId")
                        for n in rows
                        if isinstance(n, dict) and n.get("skillId") in skill_ids
                    )
                )
                aliases.update(
                    {n.get("id"): first.get("id") for n in rows[1:] if isinstance(n, dict)}
                )
                group["skills"] = [
                    {
                        **first,
                        "skillIds": candidates,
                        "skillJumps": {
                            n["skillId"]: n.get("next", "")
                            for n in rows
                            if n.get("skillId") in candidates
                        },
                        "skillTargets": {
                            n["skillId"]: n.get("targetSelection", "lowestHp")
                            for n in rows
                            if n.get("skillId") in candidates
                        },
                    }
                ]
    for group in groups:
        if isinstance(group, dict):
            for node in group.get("skills", []):
                if isinstance(node, dict):
                    if node.get("next") in aliases:
                        node["next"] = aliases[node["next"]]
                    if isinstance(node.get("skillJumps"), dict):
                        node["skillJumps"] = {
                            k: aliases.get(v, v) if isinstance(v, str) else v
                            for k, v in node["skillJumps"].items()
                        }
    result = []
    group_ids = set()
    node_ids = set()
    for group in groups:
        if (
            not isinstance(group, dict)
            or not isinstance(group.get("skills"), list)
            or not group["skills"]
        ):
            raise SkillError("每个Boss子技能组至少需要一个技能位置")
        group_id = text(group.get("id"), "Boss子技能组ID")
        if group_id in group_ids:
            raise SkillError("Boss子技能组ID重复")
        group_ids.add(group_id)
        nodes = []
        mode = group.get("type", "sequential")
        if mode not in ("sequential", "conditional", "random"):
            raise SkillError("Boss子技能组类型无效")
        if mode == "conditional" and len(group["skills"]) < 2:
            raise SkillError("条件子技能组至少需要if和else两个分支")
        for node in group["skills"]:
            if not isinstance(node, dict):
                raise SkillError("Boss技能节点格式无效")
            node_id = text(node.get("id"), "Boss技能节点ID")
            skill_id = text(node.get("skillId"), "Boss技能") if mode != "random" else ""
            if node_id in node_ids:
                raise SkillError("Boss技能节点ID重复")
            if len(node_ids) >= 1000:
                raise SkillError("Boss技能组最多1000个技能位置")
            node_ids.add(node_id)
            if mode != "random" and skill_id not in skill_ids and skill_id != "__wait__":
                raise SkillError("请从当前Boss技能库选择技能")
            if node.get("jumpCondition"):
                raise SkillError("Boss跳转不使用装备特效条件")
            candidates = None
            jumps = None
            targets = None
            if mode == "random":
                candidates = node.get("skillIds")
                if (
                    not isinstance(candidates, list)
                    or not candidates
                    or len(candidates) > 100
                    or any(not isinstance(k, str) or k not in skill_ids for k in candidates)
                    or len(set(candidates)) != len(candidates)
                ):
                    raise SkillError("随机技能请至少选择一个当前Boss技能库中的技能，不可重复")
                raw_jumps = node.get("skillJumps", {k: node.get("next", "") for k in candidates})
                if not isinstance(raw_jumps, dict) or any(k not in candidates for k in raw_jumps):
                    raise SkillError("随机候选技能跳转设置无效")
                jumps = {
                    k: text(raw_jumps.get(k, ""), "随机候选技能跳转目标", False) for k in candidates
                }
                raw_targets = node.get(
                    "skillTargets", {k: node.get("targetSelection", "lowestHp") for k in candidates}
                )
                if not isinstance(raw_targets, dict) or any(
                    k not in candidates for k in raw_targets
                ):
                    raise SkillError("随机候选技能释放对象设置无效")
                targets = {k: target_selection(raw_targets.get(k, "lowestHp")) for k in candidates}
            condition = None
            if mode == "conditional":
                last = len(nodes) == len(group["skills"]) - 1
                condition = node.get(
                    "releaseCondition",
                    {"kind": "always" if last else "bossHealthBelow", "threshold": 50},
                )
                if not isinstance(condition, dict):
                    raise SkillError("Boss条件分支格式无效")
                kind = condition.get("kind")
                if last:
                    if kind != "always":
                        raise SkillError("条件子技能组最后一个分支必须为else")
                    condition = {"kind": "always"}
                else:
                    if kind not in (
                        "bossHealthBelow",
                        "bossHealthAbove",
                        "enemyHealthBelow",
                        "noEnemyHealthBelow",
                        "timeAtLeast",
                    ):
                        raise SkillError("Boss if条件无效")
                    condition = {
                        "kind": kind,
                        "threshold": number(
                            condition.get("threshold", 50),
                            "Boss条件阈值",
                            3600 if kind == "timeAtLeast" else 100,
                        ),
                    }
            nodes.append(
                {
                    "id": node_id,
                    **(
                        {"skillIds": candidates, "skillJumps": jumps, "skillTargets": targets}
                        if mode == "random"
                        else {"skillId": skill_id}
                    ),
                    "next": text(node.get("next", ""), "Boss跳转目标", False)
                    if mode != "random"
                    else "",
                    "targetSelection": target_selection(node.get("targetSelection", "lowestHp")),
                    **({"releaseCondition": condition} if condition is not None else {}),
                    **(
                        {"waitDuration": wait_seconds(node.get("waitDuration", 1))}
                        if skill_id == "__wait__"
                        else {}
                    ),
                }
            )
        result.append(
            {
                "type": mode,
                "id": group_id,
                "nextGroup": text(group.get("nextGroup", ""), "Boss组末跳转", False),
                "skills": nodes,
            }
        )
    for group in result:
        if group["nextGroup"] and group["nextGroup"] not in group_ids:
            raise SkillError("Boss组末跳转目标不存在")
        for node in group["skills"]:
            if node["next"] and node["next"] not in node_ids:
                raise SkillError("Boss技能跳转目标不存在")
            if any(
                target and target not in node_ids for target in node.get("skillJumps", {}).values()
            ):
                raise SkillError("随机候选技能跳转目标不存在")
    entry = text(
        value.get("entry", result[0]["skills"][0]["id"] if result else ""), "Boss入口技能", False
    )
    entry = aliases.get(entry, entry)
    if (result and entry not in node_ids) or (not result and entry):
        raise SkillError("Boss入口技能不存在")
    return {
        "name": text(value.get("name", ""), "Boss技能组名称", False),
        "skills": skills,
        "entry": entry,
        "subgroups": result,
    }


def validate_party_wipe(value):
    if value is None:
        value = {"enabled": False, "time": 120}
    if not isinstance(value, dict) or type(value.get("enabled", False)) is not bool:
        raise SkillError("定时击杀设置无效")
    seconds = number(value.get("time", 120), "击杀间隔", 3600)
    if seconds < 0.1:
        raise SkillError("击杀间隔至少0.1秒")
    strategy = value.get("strategy", "all")
    if strategy not in ("random", "lowestHp", "highestHp", "all"):
        raise SkillError("定时击杀策略无效")
    return {"enabled": value.get("enabled", False), "time": seconds, "strategy": strategy}


def validate_item(payload, item_id=None):
    if not isinstance(payload, dict):
        raise SkillError("Boss格式无效")
    attrs = payload.get("attributes", {})
    rules = payload.get("targetRules", {})
    if not isinstance(attrs, dict) or any(k not in ATTRIBUTES for k in attrs):
        raise SkillError("Boss属性无效")
    if not isinstance(rules, dict) or any(
        k
        not in (
            *TARGET_DEFAULTS,
            *IMMUNITIES,
            "physicalVulnerability",
            "magicVulnerability",
            "dotVulnerability",
        )
        for k in rules
    ):
        raise SkillError("Boss目标设置无效")
    values = {k: number(attrs.get(k, 0), "Boss属性") for k in ATTRIBUTES}
    values["hitPoint"] = number(values["constitution"] * 10, "Boss血量")
    if values["dodgeRate"] > 100:
        raise SkillError("闪避率不能超过100%")
    target = {
        k: number(rules.get(k, v), "目标设置", 100 if k.endswith("Reduction") else None)
        for k, v in TARGET_DEFAULTS.items()
    }
    for k in IMMUNITIES:
        if type(rules.get(k, False)) is not bool:
            raise SkillError("免疫设置无效")
        target[k] = rules.get(k, False)
    group = validate_boss_group(payload.get("skillGroup"))
    has_skills = True
    return {
        "id": item_id or str(uuid.uuid4()),
        "name": text(payload.get("name"), "Boss名称"),
        "race": text(payload.get("race", "傀儡"), "种族"),
        "hasSkills": has_skills,
        "partyWipe": validate_party_wipe(payload.get("partyWipe")),
        "skillGroup": group,
        "attributes": values,
        "targetRules": target,
    }


class BossStore(LibraryStore):
    key = "bosses"
    label = "Boss"
    validate = staticmethod(validate_item)


router = library_router("bosses", "Boss库")
