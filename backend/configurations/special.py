"""Special configuration panel calculation from persisted attribute sources."""

from copy import deepcopy
import math
from ..skills.store import SkillError

FIVE = ("strength", "magic", "technique", "speed", "constitution")
RANGED = FIVE + ("weaponPower", "armor", "resistance")
KEYS = (
    ("weaponPower",)
    + FIVE
    + (
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
        "armor",
        "resistance",
        "dodgeRate",
        "dodge",
        "load",
        "physicalBlock",
        "magicBlock",
    )
)


def number(n=0, maximum=None):
    if (
        type(n) not in (int, float)
        or not math.isfinite(n)
        or n < 0
        or maximum is not None
        and n > maximum
    ):
        raise SkillError("属性来源数值无效")
    return n


HOLY = {
    "战士": {"constitution": 1360, "strength": 880, "technique": 880, "speed": 680},
    "法师": {"constitution": 680, "magic": 1560, "technique": 1560},
    "潜行者": {"constitution": 680, "strength": 400, "technique": 1560, "speed": 1160},
    "火枪手": {"constitution": 680, "strength": 880, "technique": 1560, "speed": 680},
    "圣职": {"constitution": 1160, "magic": 1560, "technique": 1080},
    "野蛮人": {"constitution": 680, "strength": 1560, "technique": 400, "speed": 1160},
}
IMPRINT_KEYS = (
    "finalPhysicalDamage",
    "finalMagicDamage",
    "finalDotDamage",
    "finalHealingBonus",
    "hitRate",
    "criticalRate",
    "abnormalBonus",
)
IMPRINT = {
    "战士": (3, 0, 6, 5, 3, 5, 20),
    "法师": (0, 5, 2, 15, 5, 5, 20),
    "潜行者": (4, 0, 6, 5, 3, 5, 25),
    "火枪手": (4, 0, 3, 5, 3, 5, 20),
    "圣职": (1, 4, 2, 20, 3, 0, 20),
    "野蛮人": (7, 0, 2, 5, 5, 5, 20),
}


def imprint_for(profession, job):
    v = dict(zip(IMPRINT_KEYS, IMPRINT.get(profession, (0,) * 7)))
    if job == "剑魔":
        v["finalPhysicalDamage"] += 3
    if job in ("寒霜法师", "霜寒法师", "血法师"):
        v["finalMagicDamage"] += 3
    if job == "幻术刺客":
        v["finalPhysicalDamage"] += 5
    if job in ("夜魇", "夜魔"):
        v["finalPhysicalDamage"] += 3
    if job == "毁灭者":
        v["hitRate"] += 3
    return v


def calculate(sources, equipment, library, job="", context=None):
    if not isinstance(sources, dict):
        raise SkillError("特殊配置属性来源无效")
    s = deepcopy(sources)
    for key in ("day10", "stone", "contract", "holy", "imprint", "ring", "trophies", "saturation"):
        s.setdefault(key, {})
        if not isinstance(s[key], dict):
            raise SkillError("属性来源格式无效")
        if key != "saturation":
            for attr, n in s[key].items():
                if attr not in (
                    KEYS
                    if key == "trophies"
                    else FIVE + ("physicalDamage", "magicDamage", "dotDamage")
                    if key == "ring"
                    else FIVE + ("hitRate",)
                    if key == "stone"
                    else IMPRINT_KEYS
                    if key == "imprint"
                    else FIVE + ("armor", "resistance")
                    if key == "day10"
                    else FIVE
                ):
                    raise SkillError("未知属性来源：" + attr)
                number(n)
    selected = s.get("selectedTrophies", [])
    if not isinstance(selected, list) or len(selected) > 100:
        raise SkillError("所选战利品格式无效（最多100件）")
    trophy_values = dict(s["trophies"])
    for item in selected:
        if not isinstance(item, dict) or not isinstance(item.get("attributes"), dict):
            raise SkillError("所选战利品属性无效")
        for key, n in item["attributes"].items():
            if key not in KEYS + ("adventureGoldBonus", "adventureSoulBonus"):
                raise SkillError("未知战利品属性：" + key)
            trophy_values[key] = trophy_values.get(key, 0) + number(n)
    from ..equipment.jobs import normalize_weapon_job

    try:
        profession = normalize_weapon_job(job) if job else ""
    except SkillError:
        profession = ""
    if (
        profession in HOLY
        and not s.get("holyCustom")
        and (s.get("holyProfession") or not any(s["holy"].values()))
    ):
        s["holy"] = {k: HOLY[profession].get(k, 0) for k in FIVE}
        s["holyProfession"] = profession
    if profession in IMPRINT and not s.get("imprintCustom"):
        s["imprint"] = imprint_for(profession, job)
    for group, selection in (("holy", "selectedHoly"), ("imprint", "selectedImprint")):
        if s.get(selection):
            if group == "holy":
                from ..api.holies import validate_item as validate_source
            else:
                from ..api.imprints import validate_item as validate_source
            selected_source = validate_source(s[selection], s[selection].get("id"))
            s[selection] = selected_source
            s[group] = deepcopy(selected_source["attributes"])
            s[group + "Custom"] = True
    if s.get("selectedExtraImprint"):
        from ..api.imprints import validate_item

        extra = validate_item(s["selectedExtraImprint"], s["selectedExtraImprint"].get("id"))
        base = s.get("selectedImprint")
        if extra.get("scope") != "extra" or (base and base["kind"] != extra["kind"]):
            raise SkillError("基础辉印与额外辉印的职业不一致")
        if not base:
            s["imprint"] = imprint_for(extra["kind"], extra["kind"])
        s["imprint"] = {k: s["imprint"].get(k, 0) + extra["attributes"][k] for k in IMPRINT_KEYS}
        s["selectedExtraImprint"] = extra
        s["imprintCustom"] = True
    gear = {}
    crystal = dict.fromkeys(FIVE, 0)
    for slot, id in equipment.items():
        if not id:
            continue
        item = next((i for i in library if i["id"] == id), None)
        if not item:
            raise SkillError("所选装备不存在，请重新选择")
        if (
            slot == "weapon"
            and profession
            and item.get("weaponJob")
            and item["weaponJob"] != profession
        ):
            raise SkillError(item.get("name", "所选武器") + "与当前职业不符，请重新选择武器")
        saturation = s["saturation"].get(slot, {})
        if not isinstance(saturation, dict):
            raise SkillError("装备饱和度格式无效")
        for key, a in item.get("baseAttributes", {}).items():
            if key in RANGED:
                low = a.get("min", 0)
                high = a.get("max", low)
                if low is None or high is None:
                    raise SkillError(
                        item["name"] + "的" + a["label"] + "缺少数值，请先补齐装备属性"
                    )
                entry = saturation.get(
                    key,
                    {"mode": "value", "value": a["ownedValue"]}
                    if a.get("ownedValue") is not None
                    else 100,
                )
                if item.get("wikiId") or s.get("gearPercentEnabled") is False:
                    if a.get("ownedValue") is not None:
                        entry = {"mode": "value", "value": a["ownedValue"]}
                    elif low == high:
                        entry = {"mode": "value", "value": low}
                    else:
                        raise SkillError(
                            item["name"]
                            + "的"
                            + a.get("label", key)
                            + "未填写我的数值，请到装备库补齐"
                        )
                if isinstance(entry, dict):
                    mode = entry.get("mode")
                    n = entry.get("value")
                    if mode == "value":
                        if (
                            type(n) not in (int, float)
                            or not math.isfinite(n)
                            or not low <= n <= high
                        ):
                            raise SkillError(
                                item["name"]
                                + "的"
                                + a.get("label", key)
                                + "必须在 "
                                + str(low)
                                + "～"
                                + str(high)
                                + " 范围内"
                            )
                        value = n
                    elif mode == "percent":
                        value = low + (high - low) * number(n, 100) / 100
                    else:
                        raise SkillError("装备属性输入方式无效")
                else:
                    value = low + (high - low) * number(entry, 100) / 100
            else:
                value = a.get("value") if a.get("value") is not None else a.get("min") or 0
            gear[key] = gear.get(key, 0) + value
            if key == "lifesteal":
                for target in (
                    "physicalSingleLifesteal",
                    "physicalAreaLifesteal",
                    "magicSingleLifesteal",
                    "magicAreaLifesteal",
                ):
                    gear[target] = gear.get(target, 0) + value
        if item.get("crystal", {}).get("enabled"):
            for key in FIVE:
                crystal[key] += item["crystal"]["attributes"].get(key, 0)
    from ..rings.store import validate_item as validate_ring, base_values

    ring_values = base_values(validate_ring(s["selectedRing"])) if s.get("selectedRing") else {}
    from ..contracts.store import validate_item as validate_contract

    contract = validate_contract(s["selectedContract"]) if s.get("selectedContract") else {}
    s["ringPanelBonuses"] = {}
    s["ringBattleMultipliers"] = {key: 1 + trophy_values.get(key, 0) / 100 for key in FIVE}
    stats = {}
    for key in KEYS:
        base = s["day10"].get(key, 0)
        value = (
            (
                base
                * 1.7
                * (
                    1
                    + (
                        (contract.get("baseBonus", 0) if contract.get("category") == key else 0)
                        + crystal[key]
                        + s["stone"].get(key, 0)
                    )
                    / 100
                )
                + s["holy"].get(key, 0)
                + ring_values.get(key, 0)
                + gear.get(key, 0)
            )
            * (1 + trophy_values.get(key, 0) / 100)
            if key in FIVE
            else base * (1.7 if key in ("armor", "resistance") else 1)
            + gear.get(key, 0)
            + trophy_values.get(key, 0)
            + s["imprint"].get(key, 0)
            + (s["stone"].get("hitRate", 0) if key == "hitRate" else 0)
        )
        stats[key] = round(max(0, value), 8)
    return stats, s


def prepare_configuration(config, library, allow_incomplete=False):
    if config.get("configurationType", "regular") != "special":
        return config
    result = deepcopy(config)
    context = {
        "partySize": sum(c.get("enabled", True) for c in result["characters"]),
        "enemyCount": result.get("target", {}).get("enemyCount", 1),
    }
    for c in result["characters"]:
        sources = c.setdefault("specialSources", {})
        from ..rings.store import validate_item as validate_ring
        from ..contracts.store import validate_item as validate_contract

        # The visible wearing controls are authoritative, including explicit removal.
        for key, validate in (
            ("selectedRing", validate_ring),
            ("selectedContract", validate_contract),
        ):
            chosen = validate(c[key]) if c.get(key) else None
            c[key] = chosen
            sources[key] = deepcopy(chosen)
        if not c["selectedContract"]:
            c["contract"] = "不激活"
            c["negativeEffect"] = "无"
            c["skillMultiplier"] = 1
        stone = c.get("specialSources", {}).get("selectedStone")
        if stone:
            from ..api.stones import validate_item as validate_stone

            stone = validate_stone(stone, stone.get("id"))
            c["specialSources"]["selectedStone"] = stone
            c["specialSources"]["stone"] = deepcopy(stone["attributes"])
        person = c.get("specialSources", {}).get("selectedPerson")
        if person:
            from ..api.people import validate_item

            person = validate_item(person, person.get("id"))
            c["specialSources"]["selectedPerson"] = person
            c["specialSources"]["day10"] = deepcopy(person["attributes"])
            from ..equipment.jobs import normalize_weapon_job

            if person["job"] not in HOLY:
                c["job"] = person["job"]
            elif normalize_weapon_job(c.get("job", "")) != person["job"]:
                raise SkillError("人物职业与角色职业不一致")
        c["firstStrike"] = any(
            t.get("firstStrike") is True
            for t in c.get("specialSources", {}).get("selectedTrophies", [])
            if isinstance(t, dict)
        )
        try:
            c["stats"], c["specialSources"] = calculate(
                c.get("specialSources", {}), c["equipment"], library, c.get("job", ""), context
            )
            c.pop("panelCalculationError", None)
        except SkillError as error:
            if not allow_incomplete:
                raise
            # Drafts preserve selections and sources, never an outdated calculated panel.
            c["stats"] = dict.fromkeys(KEYS, 0)
            c["panelCalculationError"] = str(error)
    return result
