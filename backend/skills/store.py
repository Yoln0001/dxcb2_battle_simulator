"""技能校验及JSON文件存储，不依赖第三方库。"""

import functools
import json
import math
import os
import pickle
import threading
import uuid
from collections import OrderedDict
from pathlib import Path

ATTRS = ["strength", "magic", "technique", "speed", "constitution", "hitPoint"]
TARGETS = ATTRS[:4]


class SkillError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def text(value, label, required=True):
    if not isinstance(value, str) or len(value) > 120 or required and not value.strip():
        raise SkillError(f"{label}无效（最多120字）")
    return value.strip()


def number(value, label, maximum=None):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        or maximum is not None
        and value > maximum
    ):
        raise SkillError(f"{label}数值无效")
    return value


def cooldown_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SkillError("冷却必须为有限数值")
    return value


def choice(value, values, label):
    if not isinstance(value, str) or value not in values:
        raise SkillError(f"{label}选项无效")
    return value


def coefficients(value, keys):
    if not isinstance(value, dict):
        raise SkillError("属性倍率格式无效")
    return {key: number(value.get(key), key) for key in keys}


def validate_skill(data, generate_id=False):
    if (
        not isinstance(data, dict)
        or type(data.get("schemaVersion")) is not int
        or data["schemaVersion"] != 1
    ):
        raise SkillError("技能数据版本无效")
    skill_id = data.get("id")
    if generate_id and (skill_id is None or skill_id == ""):
        skill_id = "skill_" + str(uuid.uuid4())
    race = {"race": "none", "multiplier": 0} if data.get("job") == "Boss" else data.get("raceBonus")
    if not isinstance(race, dict):
        raise SkillError("种族特攻格式无效")
    result = {
        "schemaVersion": 1,
        "id": text(skill_id, "技能ID"),
        "name": text(data.get("name"), "技能名称"),
        "job": text(data.get("job"), "职业"),
        "damageType": choice(data.get("damageType"), ["physical", "magic", "none"], "触发类型"),
        "ignoreTaunt": data.get("ignoreTaunt", False),
        "targeting": choice(data.get("targeting", "single"), ["single", "all"], "伤害范围"),
        "healingRecipient": choice(
            data.get("healingRecipient", "self"), ["self", "allAllies"], "回复对象"
        ),
        "cooldown": cooldown_number(data.get("cooldown")),
        "lifesteal": number(data.get("lifesteal", 0), "吸血百分比", 100),
        "hitRate": number(data.get("hitRate"), "命中率", 100),
        "criticalRate": number(data.get("criticalRate"), "暴击率", 100),
        "coefficients": coefficients(data.get("coefficients"), ATTRS + ["weaponPower"]),
        "raceBonus": {
            "race": choice(
                race.get("race"),
                ["none", "spirit", "human", "beast", "dragon", "construct", "other"],
                "种族特攻",
            ),
            "multiplier": number(race.get("multiplier"), "特攻增幅倍率"),
        },
        "effect": None,
    }
    if type(result["ignoreTaunt"]) is not bool:
        raise SkillError("无视嘲讽必须为布尔值")
    if "effect" not in data:
        raise SkillError("缺少effect字段；无特效应填写null")
    effect = data["effect"]
    if effect is not None:
        if not isinstance(effect, dict):
            raise SkillError("触发特效格式无效")
        kind = effect.get("kind")
        common = {
            "kind": kind,
            "baseValue": number(effect.get("baseValue"), "基础值"),
            "duration": number(effect.get("duration"), "持续时间"),
        }
        if kind == "debuff":
            result["effect"] = {
                **common,
                "type": choice(
                    effect.get("type"),
                    ["bleeding", "plague", "burn", "slow", "stun", "weakness", "fear", "lifeLoss"]
                    + (
                        [
                            "strengthDecay",
                            "magicDecay",
                            "techniqueDecay",
                            "speedDecay",
                            "armorDecay",
                            "resistanceDecay",
                        ]
                        if result["job"] == "Boss"
                        else []
                    ),
                    "debuff类型",
                ),
                "applicationRate": number(effect.get("applicationRate"), "异常附加率"),
                "coefficients": coefficients(effect.get("coefficients"), TARGETS),
            }
            if result["job"] == "Boss":
                layers = effect.get("maxStacks", 1)
                if type(layers) is not int or not 1 <= layers <= 999:
                    raise SkillError("debuff最大叠加层数必须为1到999的整数")
                result["effect"]["maxStacks"] = layers
        elif kind == "buff":
            rows = effect.get("conversions")
            if effect.get("type") == "regeneration":
                rows = [{"target": target, "enabled": False} for target in TARGETS]
            if not isinstance(rows, list) or len(rows) != 4:
                raise SkillError("buff转化矩阵需要4行")
            conversions = []
            for target in TARGETS:
                matches = [
                    row for row in rows if isinstance(row, dict) and row.get("target") == target
                ]
                if len(matches) != 1 or type(matches[0].get("enabled")) is not bool:
                    raise SkillError("buff转化目标或开关格式无效")
                row = matches[0]
                conversions.append(
                    {
                        "target": target,
                        "enabled": row["enabled"],
                        "coefficients": coefficients(row.get("coefficients"), ATTRS)
                        if row["enabled"]
                        else dict.fromkeys(ATTRS, 0),
                    }
                )
            result["effect"] = {
                **common,
                "type": choice(
                    effect.get("type"),
                    [
                        "strength",
                        "magic",
                        "technique",
                        "speed",
                        "armor",
                        "resistance",
                        "regeneration",
                    ],
                    "buff类型",
                ),
                "triggerRate": number(effect.get("triggerRate"), "触发率", 100),
                "recipient": choice(
                    effect.get("recipient"),
                    ["self", "allAllies", "singleAlly", "healingTargets"],
                    "buff对象",
                ),
                "skillType": choice(effect.get("skillType"), ["damage", "support"], "技能类型"),
                "conversions": conversions,
            }
            if result["job"] == "Boss":
                layers = effect.get("maxStacks", 1)
                if type(layers) is not int or not 1 <= layers <= 999:
                    raise SkillError("buff最大叠加层数必须为1到999的整数")
                result["effect"]["maxStacks"] = layers
            if effect.get("type") == "regeneration":
                result["effect"]["coefficients"] = coefficients(
                    effect.get("coefficients"), ATTRS[:5]
                )
        else:
            raise SkillError("触发特效类型无效")
    return result


def validate_library(data):
    if (
        not isinstance(data, dict)
        or data.get("schemaVersion") != 1
        or not isinstance(data.get("skills"), list)
        or len(data["skills"]) > 5000
    ):
        raise SkillError("技能库格式无效或超过5000条")
    skills = [validate_skill(skill) for skill in data["skills"]]
    if len({s["id"] for s in skills}) != len(skills):
        raise SkillError("技能库存在重复ID")
    return {"schemaVersion": 1, "skills": skills}


# 已校验库的内存缓存：文件的修改时间和大小都没变时，跳过重新解析和逐条校验。
# 缓存保存序列化后的结果，每次读取都还原出独立副本，调用方可以放心修改返回值。
_READ_CACHE = OrderedDict()
_READ_CACHE_LOCK = threading.Lock()
_READ_CACHE_LIMIT = 32


def _file_stamp(path):
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def forget_cached_read(path):
    with _READ_CACHE_LOCK:
        _READ_CACHE.pop(str(path), None)


def cached_read(method):
    """只用于结果完全由self.path文件内容决定的read方法。"""

    @functools.wraps(method)
    def read(self):
        with self.lock:
            key = str(self.path)
            stamp = _file_stamp(self.path)
            if stamp is None:
                return method(self)
            with _READ_CACHE_LOCK:
                entry = _READ_CACHE.get(key)
                if entry is not None and entry[0] is type(self) and entry[1] == stamp:
                    _READ_CACHE.move_to_end(key)
                    return pickle.loads(entry[2])
            result = method(self)
            # 读取期间文件被改动时不缓存，避免把旧内容记在新时间戳下。
            if _file_stamp(self.path) == stamp:
                blob = pickle.dumps(result, pickle.HIGHEST_PROTOCOL)
                with _READ_CACHE_LOCK:
                    _READ_CACHE[key] = (type(self), stamp, blob)
                    _READ_CACHE.move_to_end(key)
                    while len(_READ_CACHE) > _READ_CACHE_LIMIT:
                        _READ_CACHE.popitem(last=False)
            return result

    return read


class SkillStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.RLock()

    @cached_read
    def read(self):
        with self.lock:
            if not self.path.exists():
                return {"schemaVersion": 1, "skills": []}
            try:
                return validate_library(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, OSError) as error:
                raise SkillError(
                    "技能文件无法读取，请修复或从备份恢复；原文件未覆盖", 500
                ) from error

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(self.path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temp.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)
            forget_cached_read(self.path)

    def save(self, value, update_id=None):
        skill = validate_skill(value, generate_id=update_id is None)
        if update_id is not None and skill["id"] != update_id:
            raise SkillError("路径ID与技能ID不一致")
        with self.lock:
            data = self.read()
            index = next((i for i, s in enumerate(data["skills"]) if s["id"] == skill["id"]), None)
            if update_id is None and index is not None:
                raise SkillError("技能ID已存在，请使用更新接口", 409)
            if update_id is not None and index is None:
                raise SkillError("技能不存在", 404)
            if index is None:
                if len(data["skills"]) >= 5000:
                    raise SkillError("技能库最多5000条")
                data["skills"].append(skill)
            else:
                data["skills"][index] = skill
            self._write(data)
            return {**data, "skill": skill}

    def import_library(self, value):
        incoming = validate_library(value)
        with self.lock:
            data = self.read()
            existing = {s["id"]: s for s in data["skills"]}
            for skill in incoming["skills"]:
                if skill["id"] in existing and existing[skill["id"]] != skill:
                    raise SkillError("同一ID的技能内容不同，未导入：" + skill["name"], 409)
                existing[skill["id"]] = skill
            result = validate_library({"schemaVersion": 1, "skills": list(existing.values())})
            self._write(result)
            return result
