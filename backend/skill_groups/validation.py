import uuid
from ..skills.store import SkillError, text, number
from ..equipment.jobs import JOB_FAMILIES


def migrate(data):
    if data.get("schemaVersion") != 1:
        return data
    loops = data.get("loops")
    if not isinstance(loops, list) or len(loops) != 2 or not loops[0].get("skills"):
        raise SkillError("旧技能组循环配置无效")
    subgroups = []
    for i, loop in enumerate(loops):
        if not loop.get("skills"):
            continue
        nodes = []
        for j, skill_id in enumerate(loop["skills"]):
            target = (
                f"legacy_{i}_{j + 1}"
                if j + 1 < len(loop["skills"])
                else f"legacy_{1 if loop.get('next') == 'loop2' else 0}_0"
            )
            nodes.append({"id": f"legacy_{i}_{j}", "skillId": skill_id, "next": target})
        subgroups.append({"id": f"legacy_group_{i}", "skills": nodes})
    return dict(data, schemaVersion=2, subgroups=subgroups, entry="legacy_0_0")


TARGET_SELECTIONS = (
    "lowestHp",
    "highestHp",
    "lowestArmor",
    "highestArmor",
    "lowestResistance",
    "highestResistance",
    "random",
)


def target_selection(value):
    if value not in TARGET_SELECTIONS:
        raise SkillError("释放对象选项无效")
    return value


def validate_status_condition(case):
    result = {"kind": "memberStatus", "threshold": 20, "includeSelf": case.get("includeSelf", True)}
    if type(result["includeSelf"]) is not bool:
        raise SkillError("检查对象设置无效")
    for key in ("requiredDebuff", "absentBuff"):
        effect = case.get(key)
        if effect is None:
            result[key] = None
            continue
        if not isinstance(effect, dict):
            raise SkillError("状态条件格式无效")
        result[key] = {
            k: text(effect.get(k), "状态条件" + k) for k in ("type", "skillId", "skillName")
        }
        if key == "requiredDebuff" and result[key]["type"] not in (
            "burn",
            "bleeding",
            "plague",
            "slow",
            "stun",
            "weakness",
            "fear",
            "lifeLoss",
            "strengthDecay",
            "magicDecay",
            "techniqueDecay",
            "speedDecay",
            "armorDecay",
            "resistanceDecay",
        ):
            raise SkillError("负面条件类型无效")
        if key == "absentBuff" and result[key]["type"] not in (
            "strength",
            "magic",
            "technique",
            "speed",
            "armor",
            "resistance",
            "regeneration",
        ):
            raise SkillError("增益条件类型无效")
    if not result.get("requiredDebuff") and not result.get("absentBuff"):
        raise SkillError("请选择至少一个状态条件")
    for key, label in [("recognitionDelay", "状态识别延迟"), ("operationDelay", "操作耗时")]:
        value = number(case.get(key, 0), label, 3600)
        if abs(value * 10 - round(value * 10)) > 1e-8:
            raise SkillError(label + "请按0.1秒填写")
        result[key] = round(value * 10) / 10
    if result["recognitionDelay"] and not result.get("requiredDebuff"):
        raise SkillError("状态识别延迟需要选择指定负面")
    if result["operationDelay"] and case.get("targetSelection") != "matchedMember":
        raise SkillError("操作耗时需要对条件命中的成员释放单体回复技能")
    return result


def wait_seconds(value):
    value = number(value, "等待时间", 3600)
    if value < 0.1:
        raise SkillError("等待时间至少0.1秒")
    return value


def validate_group(data, generate_id=False):
    if not isinstance(data, dict):
        raise SkillError("技能组格式无效")
    data = migrate(data)
    if data.get("schemaVersion") != 2:
        raise SkillError("技能组版本无效")
    item_id = data.get("id") or ("group_" + str(uuid.uuid4()) if generate_id else "")
    job = text(data.get("job"), "职业")
    if job not in JOB_FAMILIES or JOB_FAMILIES[job] == job:
        raise SkillError("请选择细分职业")
    scope = data.get("scope") or {"kind": "general"}
    if not isinstance(scope, dict) or scope.get("kind") not in ("general", "boss"):
        raise SkillError("技能适用范围无效")
    groups = data.get("subgroups")
    if not isinstance(groups, list) or not groups:
        raise SkillError("至少需要一个子技能组")
    result = []
    group_ids, node_ids = set(), set()
    for group in groups:
        if (
            not isinstance(group, dict)
            or not isinstance(group.get("skills"), list)
            or not group["skills"]
        ):
            raise SkillError("每个子技能组至少需要一个技能")
        group_id = text(group.get("id"), "子技能组ID")
        if group_id in group_ids:
            raise SkillError("子技能组ID重复")
        group_ids.add(group_id)
        nodes = []
        for node in group["skills"]:
            if not isinstance(node, dict):
                raise SkillError("技能节点格式无效")
            node_id = text(node.get("id"), "技能节点ID")
            if node_id in node_ids:
                raise SkillError("技能节点ID重复")
            node_ids.add(node_id)
            condition = node.get("jumpCondition")
            if condition is not None:
                if (
                    not isinstance(condition, dict)
                    or type(condition.get("effectIndex")) is not int
                    or condition["effectIndex"] < 0
                ):
                    raise SkillError("装备特效跳转条件无效")
                equipment_name = text(condition.get("equipmentName", ""), "条件装备名称", False)
                equipment_id = text(condition.get("equipmentId", ""), "条件装备ID", False)
                if not equipment_name and not equipment_id:
                    raise SkillError("请选择条件装备")
                condition = {
                    "effectIndex": condition["effectIndex"],
                    "effectName": text(condition.get("effectName", ""), "条件特效名称", False),
                }
                if equipment_name:
                    condition["equipmentName"] = equipment_name
                if equipment_id:
                    condition["equipmentId"] = equipment_id
            release = node.get("releaseCondition")
            if release is not None:
                if not isinstance(release, dict) or release.get("kind") not in (
                    "always",
                    "allyHealthBelow",
                    "noAllyHealthBelow",
                    "never",
                ):
                    raise SkillError("技能释放条件无效")
                threshold = release.get("threshold", 20)
                if type(threshold) not in (int, float) or not 0 <= threshold <= 100:
                    raise SkillError("血量阈值必须处于0到100%")
                release = {"kind": release["kind"], "threshold": threshold}
            decision = node.get("decision")
            if decision is not None:
                if (
                    not group.get("conditionsEnabled")
                    or len(group["skills"]) != 1
                    or not isinstance(decision, dict)
                    or not isinstance(decision.get("cases"), list)
                    or not decision["cases"]
                ):
                    raise SkillError("条件子技能组只有一个技能位置，至少需要一个if条件和else技能")
                cases = []
                for case in decision["cases"]:
                    if not isinstance(case, dict) or case.get("kind") not in (
                        "allyHealthBelow",
                        "noAllyHealthBelow",
                        "memberStatus",
                    ):
                        raise SkillError("条件分支无效")
                    threshold = case.get("threshold", 20)
                    if type(threshold) not in (int, float) or not 0 <= threshold <= 100:
                        raise SkillError("血量阈值必须处于0到100%")
                    selection = case.get("targetSelection", "lowestHp")
                    if selection == "matchedMember" and case["kind"] != "memberStatus":
                        raise SkillError("条件命中的成员仅可用于状态条件")
                    cases.append(
                        {
                            **(
                                validate_status_condition(case)
                                if case["kind"] == "memberStatus"
                                else {"kind": case["kind"], "threshold": threshold}
                            ),
                            "skillId": text(case.get("skillId"), "分支技能"),
                            "targetSelection": selection
                            if selection == "matchedMember"
                            else target_selection(selection),
                            **(
                                {"waitDuration": wait_seconds(case.get("waitDuration", 1))}
                                if case.get("skillId") == "__wait__"
                                else {}
                            ),
                        }
                    )
                decision = {
                    "cases": cases,
                    "elseTargetSelection": target_selection(
                        decision.get("elseTargetSelection", "lowestHp")
                    ),
                    "elseSkillId": text(decision.get("elseSkillId"), "else技能"),
                    **(
                        {"elseWaitDuration": wait_seconds(decision.get("elseWaitDuration", 1))}
                        if decision.get("elseSkillId") == "__wait__"
                        else {}
                    ),
                }
            nodes.append(
                {
                    "targetSelection": target_selection(node.get("targetSelection", "lowestHp")),
                    "id": node_id,
                    "skillId": text(node.get("skillId"), "技能ID"),
                    "next": text(node.get("next", ""), "跳转目标", False),
                    "jumpCondition": condition,
                    "releaseCondition": release,
                    **(
                        {"waitDuration": wait_seconds(node.get("waitDuration", 1))}
                        if node.get("skillId") == "__wait__"
                        else {}
                    ),
                    **({"decision": decision} if decision is not None else {}),
                }
            )
        if type(group.get("conditionsEnabled", False)) is not bool:
            raise SkillError("条件分支开关无效")
        branch = group.get("healthBranch")
        if branch is not None:
            if not isinstance(branch, dict) or branch.get("kind") != "allyHealthBelow":
                raise SkillError("子技能组条件分支无效")
            threshold = branch.get("threshold", 20)
            if type(threshold) not in (int, float) or not 0 <= threshold <= 100:
                raise SkillError("血量阈值必须处于0到100%")
            branch = {
                "kind": "allyHealthBelow",
                "threshold": threshold,
                "whenTrue": text(branch.get("whenTrue"), "满足条件技能"),
                "whenFalse": text(branch.get("whenFalse"), "不满足条件技能"),
            }
        result.append(
            {
                "id": group_id,
                "skills": nodes,
                "nextGroup": text(group.get("nextGroup", ""), "子技能组跳转目标", False),
                "healthBranch": branch,
                "conditionsEnabled": group.get("conditionsEnabled", False),
            }
        )
    for group in result:
        if group["nextGroup"] and group["nextGroup"] not in group_ids:
            raise SkillError("请选择有效子技能组")
        for node in group["skills"]:
            if node["next"] and node["next"] not in node_ids:
                raise SkillError("跳转目标不存在，请重新选择")
    for group in result:
        branch = group.get("healthBranch")
        if branch and (branch["whenTrue"] not in node_ids or branch["whenFalse"] not in node_ids):
            raise SkillError("条件分支目标技能不存在")
    if scope["kind"] != "boss" and any(
        case.get("requiredDebuff")
        for sub in result
        for node in sub["skills"]
        for case in node.get("decision", {}).get("cases", [])
    ):
        raise SkillError("负面来源条件需要选择特定场景和Boss")
    entry = text(data.get("entry", result[0]["skills"][0]["id"]), "入口技能")
    if entry not in node_ids:
        raise SkillError("入口技能不存在")

    def legacy_sequence(key):
        value = data.get(key, [])
        if not isinstance(value, list):
            raise SkillError("旧技能顺序格式无效")
        return [text(v, "技能ID") for v in value]

    scope = (
        {"kind": "general"}
        if scope["kind"] == "general"
        else {
            "kind": "boss",
            **{
                k: text(scope.get(k, ""), "适用场景" + k, k not in ("libraryId",))
                for k in ("bossId", "bossName", "libraryId", "libraryName")
            },
        }
    )
    return {
        "scope": scope,
        "schemaVersion": 2,
        "id": text(item_id, "技能组ID"),
        "name": text(data.get("name"), "技能组名称"),
        "job": job,
        "entry": entry,
        "subgroups": result,
        "selfBuff": legacy_sequence("selfBuff"),
        "opening": legacy_sequence("opening"),
    }


def validate_library(data):
    if (
        not isinstance(data, dict)
        or data.get("schemaVersion") not in (1, 2)
        or not isinstance(data.get("groups"), list)
        or len(data["groups"]) > 5000
    ):
        raise SkillError("技能组库格式无效")
    items = [validate_group(item) for item in data["groups"]]
    if len({item["id"] for item in items}) != len(items):
        raise SkillError("技能组ID重复")
    return {"schemaVersion": 2, "groups": items}
