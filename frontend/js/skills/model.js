(function (root, factory) {
  const model = factory();
  if (typeof module === "object" && module.exports) module.exports = model;
  else root.SkillModel = model;
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";
  const professions = [
    { name: "圣职", jobs: ["教宗", "圣光贤者", "神官骑士", "圣殿骑士"] },
    { name: "战士", jobs: ["圣龙将军", "黑骑士", "剑豪", "剑宗", "剑魔"] },
    {
      name: "法师",
      jobs: [
        "传奇法师",
        "岩浆法师",
        "寒霜法师",
        "血法师",
        "幻境先知",
        "虚空法师",
        "大巫医",
        "灵魂贤者",
      ],
    },
    { name: "潜行者", jobs: ["夜莺", "夜魇", "诡术大师", "幻术刺客"] },
    { name: "火枪手", jobs: ["圣枪侠", "烈枪侠", "传奇猎人", "巨龙猎人"] },
    { name: "野蛮人", jobs: ["狂战神", "蛮荒之王", "毁灭者", "火刑官"] },
  ];
  function findProfession(job) {
    return professions.find((p) => p.jobs.includes(job));
  }
  const attributes = ["strength", "magic", "technique", "speed", "constitution", "hitPoint"];
  const conversionTargets = ["strength", "magic", "technique", "speed"];
  const zeros = () => Object.fromEntries(attributes.map((k) => [k, 0]));
  function blank() {
    return {
      schemaVersion: 1,
      id: "",
      name: "",
      job: "",
      damageType: "physical",
      healingRecipient: "self",
      targeting: "single",
      ignoreTaunt: false,
      lifesteal: 0,
      cooldown: 0,
      hitRate: 0,
      criticalRate: 0,
      coefficients: { ...zeros(), weaponPower: 1 },
      raceBonus: { race: "none", multiplier: 0 },
      effect: null,
    };
  }
  function number(value, label, max = Number.MAX_VALUE) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > max)
      throw new Error(label + "必须是有效的非负数" + (max === 100 ? "（0～100）" : ""));
    return value;
  }
  function text(value, label, required = false) {
    if (typeof value !== "string" || value.length > 120 || (required && !value.trim()))
      throw new Error("请填写有效的" + label + "（最多120字）");
    return value.trim();
  }
  function cooldown(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) throw new Error("冷却必须为有限数值");
    return value;
  }
  function choice(value, choices, label) {
    if (!choices.includes(value)) throw new Error(label + "选项无效");
    return value;
  }
  function coefficients(value, keys = attributes) {
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw new Error("属性倍率格式无效");
    return Object.fromEntries(keys.map((k) => [k, number(value[k], k + "倍率")]));
  }
  function validate(value, requireId = true) {
    if (!value || value.schemaVersion !== 1) throw new Error("技能数据版本无效");
    const result = {
      schemaVersion: 1,
      id: text(value.id, "技能ID", requireId),
      name: text(value.name, "技能名称", true),
      job: text(value.job, "职业", true),
      damageType: choice(value.damageType, ["physical", "magic", "none"], "触发类型"),
      targeting: choice(value.targeting ?? "single", ["single", "all"], "伤害范围"),
      ignoreTaunt: value.ignoreTaunt ?? false,
      healingRecipient: choice(value.healingRecipient ?? "self", ["self", "allAllies"], "回复对象"),
      cooldown: cooldown(value.cooldown),
      lifesteal: number(value.lifesteal ?? 0, "吸血百分比", 100),
      hitRate: number(value.hitRate, "命中率", 100),
      criticalRate: number(value.criticalRate, "暴击率", 100),
      coefficients: coefficients(value.coefficients, [...attributes, "weaponPower"]),
      raceBonus: {
        race: choice(
          value.raceBonus?.race,
          ["none", "spirit", "human", "beast", "dragon", "construct", "other"],
          "种族特攻",
        ),
        multiplier: number(value.raceBonus?.multiplier, "特攻增幅倍率"),
      },
      effect: null,
    };
    if (typeof result.ignoreTaunt !== "boolean") throw new Error("无视嘲讽必须为是或否");
    if (value.effect !== null) {
      let e = value.effect;
      if (!e || typeof e !== "object") throw new Error("触发特效格式无效");
      if (e.kind === "debuff") {
        result.effect = {
          kind: "debuff",
          type: choice(
            e.type,
            ["bleeding", "plague", "burn", "slow", "stun", "weakness", "fear", "lifeLoss"],
            "debuff类型",
          ),
          applicationRate: number(e.applicationRate, "异常附加率"),
          baseValue: number(e.baseValue, "debuff基础值"),
          duration: number(e.duration, "debuff持续时间"),
          coefficients: coefficients(e.coefficients, ["strength", "magic", "technique", "speed"]),
        };
      } else if (e.kind === "buff") {
        if (e.type === "regeneration")
          e = {
            ...e,
            conversions: conversionTargets.map((target) => ({
              target,
              enabled: false,
              coefficients: zeros(),
            })),
          };
        if (!Array.isArray(e.conversions) || e.conversions.length !== 4)
          throw new Error("buff转化矩阵需要4行");
        const conversions = conversionTargets.map((target) => {
          const rows = e.conversions.filter((row) => row && row.target === target);
          if (rows.length !== 1) throw new Error("buff转化目标重复或缺失");
          const row = rows[0];
          if (typeof row.enabled !== "boolean") throw new Error("转化开关格式无效");
          return {
            target,
            enabled: row.enabled,
            coefficients: row.enabled ? coefficients(row.coefficients) : zeros(),
          };
        });
        result.effect = {
          kind: "buff",
          type: choice(
            e.type,
            ["strength", "magic", "technique", "speed", "armor", "resistance", "regeneration"],
            "buff类型",
          ),
          triggerRate: number(e.triggerRate, "触发率", 100),
          baseValue: number(e.baseValue, "buff基础值"),
          duration: number(e.duration, "buff持续时间"),
          recipient: choice(
            e.recipient,
            ["self", "allAllies", "singleAlly", "healingTargets"],
            "buff对象",
          ),
          skillType: choice(e.skillType, ["damage", "support"], "技能类型"),
          conversions,
        };
        if (e.type === "regeneration")
          result.effect.coefficients = coefficients(e.coefficients, attributes.slice(0, 5));
      } else throw new Error("触发特效类型无效");
    }
    return result;
  }
  function library(value) {
    if (
      !value ||
      value.schemaVersion !== 1 ||
      !Array.isArray(value.skills) ||
      value.skills.length > 5000
    )
      throw new Error("请选择本界面导出的技能库文件（最多5000条）");
    const skills = value.skills.map((s) => validate(s));
    if (new Set(skills.map((s) => s.id)).size !== skills.length)
      throw new Error("技能库存在重复ID");
    return { schemaVersion: 1, skills };
  }
  function merge(current, incoming) {
    const result = new Map(current.map((s) => [s.id, s]));
    for (const s of incoming) {
      const old = result.get(s.id);
      if (old && JSON.stringify(old) !== JSON.stringify(s))
        throw new Error("同一ID的技能内容不同，导入未执行：" + s.name);
      result.set(s.id, s);
    }
    return library({ schemaVersion: 1, skills: [...result.values()] }).skills;
  }
  return {
    professions,
    findProfession,
    attributes,
    conversionTargets,
    zeros,
    blank,
    validate,
    library,
    merge,
  };
});
