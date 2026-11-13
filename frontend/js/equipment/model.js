(function (root, factory) {
  if (typeof module === "object" && module.exports)
    module.exports = factory(require("../skills/model.js"));
  else root.EquipmentModel = factory(root.SkillModel);
})(typeof window !== "undefined" ? window : globalThis, function (skills) {
  "use strict";
  const attrs = skills.attributes,
    targets = skills.conversionTargets,
    zeros = skills.zeros;
  function weaponJob(value) {
    value = text(value, "武器职业");
    if (!value) return "";
    const aliases = { 枪手: "火枪手", 狂战: "野蛮人" };
    value = aliases[value] || value;
    const family = skills.professions.find((p) => p.name === value) || skills.findProfession(value);
    if (!family) throw Error("武器职业必须从六大类职业中选择");
    return family.name;
  }
  const immunityLabels = {
    immuneBleeding: "流血",
    immunePlague: "瘟疫",
    immuneBurn: "灼烧",
    immuneStun: "眩晕",
    immunePhysicalVulnerability: "物理易伤",
    immuneMagicVulnerability: "魔法易伤",
    immuneStrengthDecay: "力量衰减",
    immuneMagicDecay: "魔力衰减",
    immuneTechniqueDecay: "技巧衰减",
    immuneSpeedDecay: "速度衰减",
    immuneArmorDecay: "护甲衰减",
    immuneResistanceDecay: "抗性衰减",
  };
  const buffTargets = [...targets, "constitution", "armor", "resistance"];
  const amplificationAttrs = [...attrs, "lostHitPoint", "armor", "resistance"];
  const amplificationTargets = [...targets, "armor", "resistance"];
  const emptyRows = () =>
    targets.map((target) => ({ target, enabled: false, coefficients: zeros() }));
  function blank() {
    return {
      schemaVersion: 1,
      id: "",
      name: "",
      mainAttribute: "",
      category: "weapon",
      weaponJob: "",
      attackType: "physical",
      effectName: "",
      triggerEffectName: "",
      triggerEnabled: false,
      startingBuff: {
        enabled: false,
        recipient: "self",
        coefficients: Object.fromEntries(targets.map((k) => [k, 0])),
        target: "none",
      },
      triggerRate: 0,
      effect: null,
    };
  }
  function text(value, label, required = false) {
    if (typeof value !== "string" || value.length > 120 || (required && !value.trim()))
      throw Error("请填写有效的" + label + "（最多120字）");
    return value.trim();
  }
  function num(value, label, max = Number.MAX_VALUE) {
    if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > max)
      throw Error(label + "数值无效");
    return value;
  }
  function choice(value, values, label) {
    if (!values.includes(value)) throw Error(label + "选项无效");
    return value;
  }
  function coefficients(value, keys) {
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw Error("属性系数格式无效");
    return Object.fromEntries(keys.map((k) => [k, num(value[k], k)]));
  }
  function rows(value, keys = attrs, destinations = targets) {
    if (!Array.isArray(value) || ![4, destinations.length].includes(value.length))
      throw Error("转化矩阵需要4行");
    return destinations.map((target) => {
      const matches = value.filter((r) => r && r.target === target);
      if (!matches.length && !targets.includes(target))
        return {
          target,
          enabled: false,
          coefficients: Object.fromEntries(keys.map((k) => [k, 0])),
        };
      if (matches.length !== 1 || typeof matches[0].enabled !== "boolean")
        throw Error("转化目标或开关无效");
      const row = matches[0];
      return {
        target,
        enabled: row.enabled,
        coefficients: row.enabled
          ? coefficients(
              {
                ...row.coefficients,
                lostHitPoint: row.coefficients?.lostHitPoint ?? 0,
                armor: row.coefficients?.armor ?? 0,
                resistance: row.coefficients?.resistance ?? 0,
              },
              keys,
            )
          : Object.fromEntries(keys.map((k) => [k, 0])),
      };
    });
  }
  function flag(value, label) {
    if (typeof value !== "boolean") throw Error(label + "开关无效");
    return value;
  }
  function layers(value) {
    if (!Number.isInteger(value) || value < 1 || value > 999) throw Error("层数必须为1～999的整数");
    return value;
  }
  function validateSingle(data, requireId = true) {
    if (!data || data.schemaVersion !== 1) throw Error("装备版本无效");
    const category = choice(data.category, ["weapon", "armor", "accessory", "stone"], "类型");
    const start = data.startingBuff;
    if (!start) throw Error("缺少开战增幅");
    const result = {
      schemaVersion: 1,
      id: text(data.id, "装备ID", requireId),
      name: text(data.name, "装备名称", true),
      category,
      weaponJob: category === "weapon" ? weaponJob(data.weaponJob) : "",
      attackType: choice(
        data.attackType,
        ["physical", "magic", "none", "receivedPhysical", "receivedMagic"],
        "触发类型",
      ),
      effectName: text(data.effectName, "战斗开始特效名称"),
      triggerEffectName: text(data.triggerEffectName ?? "", "特效名称"),
      triggerEnabled: flag(
        data.triggerEnabled === undefined ? data.effect !== null : data.triggerEnabled,
        "触发特效",
      ),
      startingBuff: {
        enabled: flag(
          start.enabled === undefined
            ? Boolean(data.effectName) || targets.some((k) => start.coefficients?.[k] > 0)
            : start.enabled,
          "战斗开始增幅",
        ),
        recipient: choice(start.recipient, ["self", "allAllies", "singleAlly"], "开始buff对象"),
        coefficients: coefficients(start.coefficients, targets),
        target: choice(start.target, ["none", ...targets, "armor", "resistance"], "开战转化目标"),
      },
      triggerRate: num(data.triggerRate, "触发概率", 100),
      effect: null,
    };
    result.startingBuff.kind = choice(
      start.kind ?? "amplify",
      ["amplify", "regeneration"],
      "开始buff特效类型",
    );
    const regen = start.regeneration ?? {};
    if (!regen || typeof regen !== "object" || Array.isArray(regen))
      throw Error("开战回春格式无效");
    if (
      regen.coefficients !== undefined &&
      (!regen.coefficients ||
        typeof regen.coefficients !== "object" ||
        Array.isArray(regen.coefficients))
    )
      throw Error("回春系数格式无效");
    const regenKeys = ["strength", "magic", "technique", "speed", "constitution"];
    result.startingBuff.regeneration = {
      receivesHealingBonuses: flag(
        regen.receivesHealingBonuses ??
          !(result.name.includes("肇始之心★") || result.effectName === "肇始之源"),
        "回春回复加成",
      ),
      baseValue: num(regen.baseValue ?? 0, "回春基础数值"),
      coefficients: coefficients(
        { ...Object.fromEntries(regenKeys.map((k) => [k, 0])), ...regen.coefficients },
        regenKeys,
      ),
    };
    if (data.effect !== null) {
      const e = data.effect;
      if (!e || typeof e !== "object") throw Error("特效无效");
      if (e.kind === "amplify")
        result.effect = {
          kind: e.kind,
          conversions: rows(e.conversions, amplificationAttrs, amplificationTargets),
        };
      else if (["trueDamage", "physicalTrueDamage", "magicTrueDamage"].includes(e.kind))
        result.effect = {
          kind:
            e.kind === "trueDamage"
              ? ["magic", "receivedMagic"].includes(data.attackType)
                ? "magicTrueDamage"
                : "physicalTrueDamage"
              : e.kind,
          coefficients: coefficients(e.coefficients, [...targets, "weaponPower"]),
        };
      else if (e.kind === "immediateAction") result.effect = { kind: e.kind };
      else if (e.kind === "debuff")
        result.effect = {
          kind: e.kind,
          type: choice(
            e.type,
            ["bleeding", "plague", "burn", "slow", "stun", "weakness", "fear", "lifeLoss"],
            "debuff类型",
          ),
          baseValue: num(e.baseValue, "基础值"),
          duration: num(e.duration, "持续时间"),
          maxStacks: layers(e.maxStacks),
          coefficients: coefficients(e.coefficients, targets),
        };
      else if (e.kind === "healing")
        result.effect = {
          kind: e.kind,
          recipient: choice(e.recipient, ["self", "allAllies", "singleAlly"], "回复对象"),
          coefficients: coefficients(e.coefficients, [...attrs, "weaponPower"]),
        };
      else if (e.kind === "buff" && e.type === "regeneration")
        result.effect = {
          kind: "buff",
          type: "regeneration",
          recipient: choice(e.recipient ?? "self", ["self", "allAllies"], "回春对象"),
          baseValue: num(e.baseValue ?? 0, "回春基础值"),
          duration: num(e.duration ?? 0, "持续时间"),
          coefficients: {},
          conversions: [],
          maxStacks: 1,
        };
      else if (e.kind === "buff")
        result.effect = {
          kind: e.kind,
          type: choice(e.type, buffTargets, "buff类型"),
          recipient: choice(e.recipient, ["self", "allAllies", "singleAlly"], "对象"),
          duration: num(e.duration, "持续时间"),
          maxStacks: layers(e.maxStacks),
          conversions: rows(e.conversions, attrs, buffTargets),
        };
      else throw Error("装备特效类型无效");
    }
    return result;
  }
  function validate(data, requireId = true) {
    const source = data?.triggerEffects;
    if (source !== undefined && (!Array.isArray(source) || source.length > 50))
      throw Error("触发特效列表无效（最多50条）");
    const entries =
      source === undefined
        ? [
            {
              name: data.triggerEffectName ?? "",
              triggerType: data.attackType,
              probability: data.triggerRate,
              effect: data.effect,
            },
          ]
        : source;
    const triggers = entries.map((t) => {
      if (!t || typeof t !== "object") throw Error("触发特效格式无效");
      const item = validateSingle(
        {
          ...data,
          attackType: t.triggerType,
          triggerEffectName: t.name,
          triggerRate: t.probability,
          effect: t.effect,
        },
        requireId,
      );
      return {
        name: item.triggerEffectName,
        triggerType: item.attackType,
        probability: item.triggerRate,
        effect: item.effect,
      };
    });
    const first = triggers[0];
    const result = validateSingle(
      {
        ...data,
        ...(first
          ? {
              attackType: first.triggerType,
              triggerEffectName: first.name,
              triggerRate: first.probability,
              effect: first.effect,
            }
          : { attackType: "physical", triggerEffectName: "", triggerRate: 0, effect: null }),
      },
      requireId,
    );
    const vulnerabilityKeys = ["physicalVulnerability", "magicVulnerability"];
    const legacy = Object.fromEntries(
      vulnerabilityKeys.map((k) => [
        k,
        data.baseAttributes?.[k]?.value ?? data.baseAttributes?.[k]?.min ?? 0,
      ]),
    );
    const opening = data.startingDebuffs ?? {
      enabled: Object.values(legacy).some((v) => v > 0),
      ...legacy,
    };
    const debuffEntries = opening.entries ?? [opening];
    if (!Array.isArray(debuffEntries) || debuffEntries.length > 50)
      throw Error("开战敌方debuff最多50条");
    const openingRows = debuffEntries.flatMap((row) => {
      if (!row || typeof row !== "object" || Array.isArray(row))
        throw Error("开战敌方debuff格式无效");
      const name = text(row.name ?? "", "开战敌方debuff名称");
      const values = {
        physicalVulnerability: num(row.physicalVulnerability ?? 0, "物理易伤百分比"),
        magicVulnerability: num(row.magicVulnerability ?? 0, "魔法易伤百分比"),
        dot: num(row.dotDamage ?? 0, "DOT每秒基础伤害"),
        healingReduction: num(row.healingReduction ?? 0, "回复/吸血效果降低", 100),
        lifeDeprivation: num(row.lifeDeprivation ?? 0, "敌方当前生命值百分比", 100),
      };
      const dotOn = flag(row.dotEnabled ?? false, "开战DOT");
      let kinds =
        row.type !== undefined
          ? [choice(row.type, Object.keys(values), "开战debuff类型")]
          : Object.keys(values).filter((k) => (k === "dot" ? dotOn : values[k] > 0));
      if (!kinds.length) kinds = ["physicalVulnerability"];
      return kinds.map((type) => ({
        name,
        type,
        dotEnabled: type === "dot",
        dotDamage: type === "dot" ? values.dot : 0,
        ...Object.fromEntries(
          [
            "physicalVulnerability",
            "magicVulnerability",
            "healingReduction",
            "lifeDeprivation",
          ].map((k) => [k, type === k ? values[k] : 0]),
        ),
      }));
    });
    if (openingRows.length > 50) throw Error("拆分后开战敌方debuff超过50条");
    result.startingDebuffs = {
      enabled: flag(opening.enabled ?? false, "开战敌方debuff"),
      entries: openingRows,
      ...(openingRows[0] ?? {}),
    };
    const immunity = data.negativeImmunities ?? {};
    if (
      !immunity ||
      typeof immunity !== "object" ||
      Array.isArray(immunity) ||
      Object.keys(immunity).some(
        (k) =>
          !(k in immunityLabels) &&
          ![
            "immuneSpeedReduction",
            "immuneWeakness",
            "immuneFear",
            "immuneLifeLoss",
            "immuneLifestealReduction",
            "immuneHealingReduction",
            "immuneRegenerationReduction",
            "immuneNegativeEffects",
          ].includes(k),
      )
    )
      throw Error("装备负面免疫格式无效");
    result.negativeImmunities = Object.fromEntries(
      Object.keys(immunityLabels).map((k) => [k, flag(immunity[k] ?? false, "负面免疫")]),
    );
    const bundle = data.battleStartEffects;
    if (bundle !== undefined) {
      if (
        !bundle ||
        typeof bundle !== "object" ||
        Array.isArray(bundle) ||
        !Array.isArray(bundle.entries) ||
        bundle.entries.length > 100
      )
        throw Error("战斗开始效果最多100条");
      const enabled = flag(bundle.enabled ?? false, "战斗开始效果");
      const entries = bundle.entries.map((row) => {
        if (!row || typeof row !== "object" || Array.isArray(row))
          throw Error("战斗开始效果格式无效");
        const side = choice(row.side, ["ally", "enemy"], "施加阵营"),
          name = text(row.name ?? "", "战斗开始特效名称"),
          on = flag(row.enabled ?? true, "开战效果条目");
        if (side === "ally") {
          const buff = validateSingle(
            { ...data, effectName: name, startingBuff: row.buff, effect: null },
            requireId,
          ).startingBuff;
          return { side, name, enabled: on, buff };
        }
        if (!row.debuff || typeof row.debuff !== "object" || Array.isArray(row.debuff))
          throw Error("开战敌方debuff格式无效");
        const old = { ...data };
        delete old.battleStartEffects;
        const normalized = validate(
          { ...old, startingDebuffs: { enabled: true, entries: [{ ...row.debuff, name }] } },
          requireId,
        ).startingDebuffs.entries;
        if (normalized.length !== 1) throw Error("每条敌方开战效果只能选择一种debuff");
        return { side, name, enabled: on, debuff: normalized[0] };
      });
      if (entries.filter((row) => row.side === "enemy").length > 50)
        throw Error("开战敌方debuff最多50条");
      result.battleStartEffects = { enabled, entries };
    } else {
      const allyConfigured =
        result.startingBuff.enabled ||
        result.effectName ||
        result.startingBuff.kind === "regeneration" ||
        result.startingBuff.target !== "none" ||
        Object.values(result.startingBuff.coefficients).some((v) => v > 0);
      const enemyConfigured = result.startingDebuffs.entries.filter(
        (row) =>
          result.startingDebuffs.enabled ||
          row.name ||
          row.dotEnabled ||
          row.physicalVulnerability ||
          row.magicVulnerability ||
          row.healingReduction ||
          row.lifeDeprivation,
      );
      result.battleStartEffects = {
        enabled: result.startingBuff.enabled || result.startingDebuffs.enabled,
        entries: [
          ...(allyConfigured
            ? [
                {
                  side: "ally",
                  name: result.effectName,
                  enabled: result.startingBuff.enabled,
                  buff: structuredClone(result.startingBuff),
                },
              ]
            : []),
          ...enemyConfigured.map((debuff) => ({
            side: "enemy",
            name: debuff.name,
            enabled: result.startingDebuffs.enabled,
            debuff: structuredClone(debuff),
          })),
        ],
      };
    }
    const bundleResult = result.battleStartEffects,
      ally = bundleResult.entries.find((row) => row.side === "ally" && row.enabled);
    if (ally) {
      result.effectName = ally.name;
      result.startingBuff = { ...structuredClone(ally.buff), enabled: bundleResult.enabled };
    } else result.startingBuff.enabled = false;
    const enemy = bundleResult.entries
      .filter((row) => row.side === "enemy" && row.enabled)
      .map((row) => ({ ...structuredClone(row.debuff), name: row.name }));
    result.startingDebuffs = {
      enabled: bundleResult.enabled && enemy.length > 0,
      entries: enemy,
      ...(enemy[0] ?? {}),
    };
    if (data.wikiId) result.wikiId = text(data.wikiId, "百科装备身份");
    result.mainAttribute = choice(
      data.mainAttribute ?? "",
      ["", "strength", "magic", "technique", "speed", "constitution"],
      "主属性",
    );
    result.triggerEffects = triggers;
    for (const key of [
      "crystal",
      "baseAttributes",
      "extraAttributes",
      "startingEffects",
      "effectDefinitions",
      "passiveEffects",
      "reviewIssues",
      "classificationStatus",
      "source",
      "reviewNotes",
    ])
      if (data[key] !== undefined) result[key] = structuredClone(data[key]);
    if (result.baseAttributes) for (const k of vulnerabilityKeys) delete result.baseAttributes[k];
    return result;
  }
  function library(data) {
    if (
      !data ||
      data.schemaVersion !== 1 ||
      !Array.isArray(data.equipment) ||
      data.equipment.length > 5000
    )
      throw Error("装备库格式无效或超过5000条");
    const items = data.equipment.map((x) => validate(x));
    if (new Set(items.map((x) => x.id)).size !== items.length) throw Error("装备ID重复");
    return { schemaVersion: 1, equipment: items };
  }
  function merge(current, incoming) {
    const map = new Map(current.map((x) => [x.id, x]));
    for (const x of incoming) {
      if (map.has(x.id) && JSON.stringify(map.get(x.id)) !== JSON.stringify(x))
        throw Error("同一ID内容不同，未导入：" + x.name);
      map.set(x.id, x);
    }
    return library({ schemaVersion: 1, equipment: [...map.values()] }).equipment;
  }
  return {
    blank,
    validate,
    library,
    merge,
    immunityLabels,
    attrs,
    amplificationAttrs,
    amplificationTargets,
    targets,
    buffTargets,
    zeros,
    emptyRows,
  };
});
