"use strict";
const storageKey = "dungeon2-team-v1";
const fields = [
  ["weaponPower", "武威", 0],
  ["strength", "力量", 0],
  ["magic", "魔力", 0],
  ["technique", "技巧", 0],
  ["speed", "速度", 0],
  ["constitution", "体质", 0],
  ["criticalRate", "暴击率 %", 0],
  ["hitRate", "命中 %", 0],
  ["ignoreArmor", "无视护甲", 0],
  ["ignoreResistance", "无视抗性", 0],
  ["abnormalBonus", "异常附加率 %", 0],
  ["physicalDamage", "物理伤害 %", 0],
  ["finalPhysicalDamage", "辉印物伤 %", 0],
  ["magicDamage", "魔法伤害 %", 0],
  ["finalMagicDamage", "辉印魔伤 %", 0],
  ["dotDamage", "持续伤害 %", 0],
  ["finalDotDamage", "辉印持伤 %", 0],
  ["healingBonus", "回复效果 %", 0],
  ["finalHealingBonus", "辉印回复 %", 0],
  ["unload", "卸负", 0],
  ["criticalMultiplier", "暴伤系数增加 %", 0],
  ["physicalSingleLifesteal", "物理单体吸血 %", 0],
  ["magicSingleLifesteal", "魔法单体吸血 %", 0],
  ["physicalAreaLifesteal", "物理群体吸血 %", 0],
  ["magicAreaLifesteal", "魔法群体吸血 %", 0],
];
let configurationType = "regular";
const modeDrafts = {};
const slots = [
  ["weapon", "武器"],
  ["armor", "防具"],
  ["accessory1", "饰品1"],
  ["accessory2", "饰品2"],
  ["stone", "魔石特效"],
];
const textFields = [
  "name",
  "job",
  "skillGroup",
  "contract",
  "negativeEffect",
  ...slots.map((x) => x[0]),
];
const $ = (s) => document.querySelector(s);
const targetNumbers = [
  ["hitPoint", "血量", 175000000],
  ["armor", "护甲", 0],
  ["resistance", "抗性", 0],
  ["speed", "速度", 43750],
  ["dodgeRate", "闪避 %", 0],
  ["physicalReduction", "物理减伤 %", 0],
  ["magicReduction", "魔法减伤 %", 0],
  ["dotReduction", "持续减伤 %", 0],
  ["allyLifestealReduction", "吸血降低 %", 0],
  ["allyHealingReduction", "回复降低 %", 0],
  ["allyRegenerationReduction", "回春降低 %", 0],
];
const targetImmunities = [
  ["immuneBleeding", "流血"],
  ["immunePlague", "瘟疫"],
  ["immuneBurn", "灼烧"],
  ["immuneSpeedReduction", "减速"],
  ["immuneStun", "眩晕"],
  ["immuneWeakness", "虚弱"],
  ["immuneFear", "恐惧"],
  ["immuneLifeLoss", "生命流失"],
  ["immunePhysicalVulnerability", "物理易伤"],
  ["immuneMagicVulnerability", "魔法易伤"],
  ["immuneNegativeEffects", "全部负面"],
];
let targetSpeedAuto = true,
  targetBossInfo = {};
function blankTarget() {
  return {
    race: "傀儡",
    speedAuto: true,
    ...Object.fromEntries(targetNumbers.map(([k, , v]) => [k, v])),
    ...Object.fromEntries(targetImmunities.map(([k]) => [k, false])),
  };
}
function renderTarget(target) {
  targetBossInfo = {
    partyWipe: structuredClone(
      target.partyWipe || target.selectedBoss?.partyWipe || { enabled: false, time: 120 },
    ),
    name: target.name || "",
    skillGroup: structuredClone(target.skillGroup || { name: "", skills: [] }),
    attributes: structuredClone(target.attributes || {}),
    selectedBoss: target.selectedBoss ? structuredClone(target.selectedBoss) : null,
  };
  window.BossLibrary?.syncTarget(targetBossInfo);
  const grid = $("#target-fields");
  grid.replaceChildren();
  targetSpeedAuto = target.speedAuto ?? target.speed === target.hitPoint / 4000;
  const race = document.createElement("label");
  race.className = "field";
  const label = document.createElement("span");
  label.textContent = "种族";
  const select = document.createElement("select");
  select.name = "target-race";
  select.setAttribute("aria-label", "目标种族");
  const races = ["未指定", "灵体", "人形", "野兽", "龙", "傀儡", "其他"];
  if (!races.includes(target.race)) races.push(target.race);
  races.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
  select.value = target.race;
  race.append(label, select);
  grid.append(race);
  for (const [k, title, defaultValue] of targetNumbers) {
    if (k === "allyLifestealReduction") {
      const heading = document.createElement("h4");
      heading.textContent = "对己方附加 debuff";
      heading.style.gridColumn = "1 / -1";
      grid.append(heading);
    }
    const field = makeField("target-" + k, title, target[k] ?? defaultValue);
    field.querySelector("input").setAttribute("aria-label", "目标" + title);
    if (
      [
        "dodgeRate",
        "abnormalResistance",
        "physicalReduction",
        "magicReduction",
        "dotReduction",
        "allyLifestealReduction",
        "allyHealingReduction",
        "allyRegenerationReduction",
      ].includes(k)
    )
      field.querySelector("input").max = "100";
    grid.append(field);
  }
  const hp = grid.querySelector('[name="target-hitPoint"]'),
    speed = grid.querySelector('[name="target-speed"]');
  speed.title = "默认速度＝目标血量÷4000，可手动修改";
  hp.addEventListener("input", () => {
    if (targetSpeedAuto) speed.value = Number(hp.value) / 4000;
    dirty();
  });
  speed.addEventListener("input", () => {
    targetSpeedAuto = speed.value === "" || Number(speed.value) === Number(hp.value) / 4000;
    if (speed.value === "") speed.value = Number(hp.value) / 4000;
    dirty();
  });
  const dropdown = document.createElement("details");
  dropdown.className = "target-immunity-dropdown";
  const summary = document.createElement("summary");
  const caption = document.createElement("span");
  caption.textContent = "免疫负面";
  const selected = document.createElement("span");
  summary.append(caption, selected);
  dropdown.append(summary);
  const options = document.createElement("div");
  options.className = "target-immunity-options";
  dropdown.append(options);
  const immunityInput = (k) => options.querySelector('[name="target-' + k + '"]');
  const individualKeys = targetImmunities
    .map(([k]) => k)
    .filter((k) => k !== "immuneNegativeEffects");
  const update = () => {
    const names = targetImmunities
      .filter(([k]) => immunityInput(k).checked)
      .map(([, title]) => title);
    selected.textContent = immunityInput("immuneNegativeEffects").checked
      ? "全部负面"
      : names.length
        ? names.join("、")
        : "请选择（可多选）";
  };
  const syncImmunities = (changed) => {
    if (changed === "immuneNegativeEffects") {
      const checked = immunityInput(changed).checked;
      individualKeys.forEach((k) => {
        immunityInput(k).checked = checked;
      });
    } else
      immunityInput("immuneNegativeEffects").checked = individualKeys.every(
        (k) => immunityInput(k).checked,
      );
    update();
  };
  for (const [k, title] of targetImmunities) {
    const row = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "target-" + k;
    input.checked = target[k];
    const text = document.createElement("span");
    text.textContent = title;
    row.append(input, text);
    options.append(row);
    input.addEventListener("change", () => syncImmunities(k));
  }
  if (target.immuneNegativeEffects)
    individualKeys.forEach((k) => {
      immunityInput(k).checked = true;
    });
  syncImmunities();
  grid.append(dropdown);
  dropdown.addEventListener("keydown", (event) => {
    if (event.key === "Escape") dropdown.open = false;
  });
}
function collectTarget() {
  const grid = $("#target-fields");
  const value = (k) => grid.querySelector('[name="target-' + k + '"]').value;
  return {
    ...structuredClone(targetBossInfo),
    race: value("race"),
    speedAuto: targetSpeedAuto,
    ...Object.fromEntries(targetNumbers.map(([k]) => [k, Number(value(k))])),
    ...Object.fromEntries(
      targetImmunities.map(([k]) => [k, grid.querySelector('[name="target-' + k + '"]').checked]),
    ),
  };
}
function normalizeTarget(data) {
  if (data === undefined) return blankTarget(); // 兼容旧版不包含目标的存档。
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("目标属性格式无效");
  const target = {};
  for (const k of ["race"]) {
    if (typeof data[k] !== "string" || data[k].length > 120)
      throw new Error("目标种族或技能格式无效");
    target[k] = data[k];
  }
  for (const [k, title, defaultValue] of targetNumbers)
    target[k] = validateNumber(
      data[k] === undefined ? defaultValue : data[k],
      "目标" + title,
      0,
      [
        "dodgeRate",
        "abnormalResistance",
        "physicalReduction",
        "magicReduction",
        "dotReduction",
        "allyLifestealReduction",
        "allyHealingReduction",
        "allyRegenerationReduction",
      ].includes(k)
        ? 100
        : Number.MAX_VALUE,
    );
  target.speedAuto =
    data.speedAuto ?? (data.speed === undefined || data.speed === target.hitPoint / 4000);
  if (typeof target.speedAuto !== "boolean") throw Error("目标速度默认设置无效");
  if (target.speedAuto) target.speed = target.hitPoint / 4000;
  for (const [k, title] of targetImmunities) {
    const value = data[k] === undefined ? false : data[k];
    if (typeof value !== "boolean") throw new Error(title + "格式无效");
    target[k] = value;
  }
  for (const key of ["name"]) {
    if (data[key] !== undefined) {
      if (typeof data[key] !== "string" || data[key].length > 120) throw Error("Boss信息格式无效");
      target[key] = data[key];
    }
  }
  if (data.skillGroup !== undefined) {
    if (
      typeof data.skillGroup !== "string" &&
      (!data.skillGroup ||
        typeof data.skillGroup !== "object" ||
        Array.isArray(data.skillGroup) ||
        !Array.isArray(data.skillGroup.skills))
    )
      throw Error("Boss技能组格式无效");
    target.skillGroup = structuredClone(data.skillGroup);
  }
  if (data.attributes !== undefined) {
    if (!data.attributes || typeof data.attributes !== "object" || Array.isArray(data.attributes))
      throw Error("Boss基础属性格式无效");
    target.attributes = Object.fromEntries(
      Object.entries(data.attributes).map(([k, v]) => [k, validateNumber(v, "Boss属性")]),
    );
  }
  if (data.partyWipe !== undefined) {
    if (!data.partyWipe || typeof data.partyWipe.enabled !== "boolean")
      throw Error("定时击杀设置无效");
    const strategy = data.partyWipe.strategy || "all";
    if (!["random", "lowestHp", "highestHp", "all"].includes(strategy))
      throw Error("定时击杀策略无效");
    target.partyWipe = {
      enabled: data.partyWipe.enabled,
      time: validateNumber(data.partyWipe.time, "击杀间隔", 0.1, 3600),
      strategy,
    };
  }
  if (data.selectedBoss) target.selectedBoss = structuredClone(data.selectedBoss);
  return target;
}
let timer;
function toast(message) {
  window.showToast(message);
}
function makeField(key, label, value, type = "number", list = "") {
  const element = document.createElement("label");
  element.className = "field";
  const isPercent = type === "number" && label.trim().endsWith("%");
  const title = document.createElement("span");
  title.textContent = isPercent ? label.replace(/\s*%$/, "") : label;
  const input = document.createElement("input");
  input.name = key;
  input.type = type;
  input.value = value;
  input.setAttribute("aria-label", label);
  if (type === "number") {
    input.min = "0";
    input.step = "any";
    input.required = true;
  } else {
    input.placeholder = "输入或选择";
    input.maxLength = 120;
    if (list) input.setAttribute("list", list);
  }
  element.append(title, input);
  if (isPercent) {
    const unit = document.createElement("span");
    unit.className = "field-unit";
    unit.textContent = "%";
    unit.setAttribute("aria-hidden", "true");
    element.append(unit);
  }
  return element;
}
function section(label, hint = "") {
  const e = document.createElement("div");
  e.className = "section-label";
  const s = document.createElement("span");
  s.textContent = label;
  const h = document.createElement("small");
  h.textContent = hint;
  e.append(s, h);
  return e;
}
function blank(i) {
  return {
    name: `角色 ${i + 1}`,
    enabled: true,
    job: "",
    skillGroup: "",
    firstStrike: false,
    lifetime: 200,
    stats: Object.fromEntries(fields.map(([k, , v]) => [k, v])),
    equipment: Object.fromEntries(slots.map(([k]) => [k, ""])),
    selectedRing: null,
    selectedContract: null,
    contract: "不激活",
    negativeEffect: "无",
    skillMultiplier: 1,
  };
}
let teamEquipmentLibrary = [],
  teamSkillGroups = [],
  teamSkillGroupsReady = false;
function fillGroupOptions(select, card, value = select.value) {
  const job = card.querySelector('[name="job"]').value,
    groups = teamSkillGroups.filter((g) => g.job === job);
  if (!teamSkillGroupsReady && value) select.dataset.pendingGroup = value;
  if (teamSkillGroupsReady && select.dataset.pendingGroup) {
    value = select.dataset.pendingGroup;
    delete select.dataset.pendingGroup;
  }
  select.replaceChildren();
  const add = (value, text) => {
    const o = document.createElement("option");
    o.value = value;
    o.textContent = text;
    select.append(o);
  };
  add(
    "",
    !job
      ? "请先选择转职"
      : !teamSkillGroupsReady
        ? "正在加载技能组"
        : groups.length
          ? "请选择技能组"
          : "该职业暂无技能组",
  );
  groups.forEach((g) =>
    add(g.id, g.name + (g.scope?.kind === "boss" ? " · " + g.scope.bossName + "专用" : "")),
  );
  const match = groups.find((g) => g.id === value) || groups.find((g) => g.name === value);
  select.value = match ? match.id : "";
  select.disabled = !job || !teamSkillGroupsReady || !groups.length;
}
window.onSkillGroupLibraryChange = (groups) => {
  teamSkillGroups = groups;
  teamSkillGroupsReady = true;
  document
    .querySelectorAll(".character")
    .forEach((card) => fillGroupOptions(card.querySelector('[name="skillGroup"]'), card));
};

const slotCategory = (key) => (key.startsWith("accessory") ? "accessory" : key);
function fillEquipmentOptions(select, card, value = select.value) {
  const category = slotCategory(select.name),
    job = card.querySelector('[name="job"]').value,
    family =
      window.SkillModel.findProfession(job)?.name ||
      card.querySelector('[name="profession"]')?.value;
  const entries = teamEquipmentLibrary.filter(
    (item) =>
      item.category === category &&
      (category !== "weapon" || !item.weaponJob || item.weaponJob === family),
  );
  select.replaceChildren();
  const add = (value, label, disabled = false) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    option.disabled = disabled;
    select.append(option);
  };
  add("", "请选择" + (slots.find(([k]) => k === select.name)?.[1] || "装备"));
  for (const item of entries) add(item.id, item.name);
  if (value && !entries.some((item) => item.id === value)) {
    const match =
      entries.find((item) => item.wikiId === value || item.identityAliases?.includes(value)) ||
      entries.find((item) => item.name === value);
    if (match) value = match.id;
    else {
      const original = teamEquipmentLibrary.find((item) => item.id === value);
      if (category === "weapon" && family && original?.weaponJob && original.weaponJob !== family)
        value = "";
      else add(value, (original?.name || value) + "（不可用，请重新选择）", true);
    }
  }
  select.value = value || "";
}
function updateEquipmentOptions(card) {
  const group = card.querySelector('[name="skillGroup"]');
  if (group) fillGroupOptions(group, card);
  for (const select of card.querySelectorAll(".equipment select"))
    fillEquipmentOptions(select, card);
  card.refreshSpecial?.();
}
window.onEquipmentLibraryChange = (items) => {
  const previous = teamEquipmentLibrary;
  document.querySelectorAll(".character").forEach((card) => {
    for (const select of card.querySelectorAll(".equipment select")) {
      const original = previous.find((item) => item.id === select.value);
      const match =
        items.find((item) => item.id === select.value) ||
        items.find((item) => original?.wikiId && item.wikiId === original.wikiId) ||
        items.find(
          (item) =>
            !original?.wikiId &&
            !item.wikiId &&
            original &&
            item.name === original.name &&
            item.category === original.category &&
            item.weaponJob === original.weaponJob,
        );
      if (
        match &&
        original &&
        JSON.stringify(match.baseAttributes) !== JSON.stringify(original.baseAttributes) &&
        card.specialSources?.saturation
      )
        delete card.specialSources.saturation[select.name];
      if (match && match.id !== select.value) {
        const option = document.createElement("option");
        option.value = match.id;
        option.textContent = match.name;
        select.append(option);
        select.value = match.id;
      }
    }
  });
  teamEquipmentLibrary = items;
  document.querySelectorAll(".character").forEach((card) => {
    updateEquipmentOptions(card);
    card.refreshSpecial?.();
  });
};
window.getRingPanelContext = () => ({
  partySize: [...document.querySelectorAll(".character [name=enabled]")].filter((n) => n.checked)
    .length,
  enemyCount: collectTarget().enemyCount || 1,
});
function arrangeCharacterChoices(card) {
  const body = card.querySelector(".card-body"),
    identity = card.querySelector(".identity");
  const person = card.querySelector(".special-person-picker"),
    equipment = card.querySelector(".equipment"),
    contract = card.querySelector(".contract");
  const skill = card.querySelector('[name="skillGroup"]').closest(".field");
  const ring =
    contract.querySelector('[aria-label="选择域之环"]')?.closest(".field") ||
    [...contract.children].find(
      (row) =>
        row.querySelector("select") &&
        !row.querySelector("[name]") &&
        !row.querySelector('[aria-label="选择契约"]'),
    );
  const details = document.createElement("div");
  details.className = "character-details";
  details.id = "character-details-" + card.dataset.index;
  details.hidden = true;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "character-details-toggle";
  button.textContent = "展示详情";
  button.setAttribute("aria-expanded", "false");
  button.setAttribute("aria-controls", details.id);
  button.addEventListener("click", () => {
    details.hidden = !details.hidden;
    button.textContent = details.hidden ? "展示详情" : "收起详情";
    button.setAttribute("aria-expanded", String(!details.hidden));
  });
  const negative = contract.querySelector('[name="negativeEffect"]').closest(".field"),
    multiplier = contract.querySelector('[name="skillMultiplier"]').closest(".field");
  const state = document.createElement("div");
  state.className = "character-calculation-state";
  state.hidden = true;
  state.append(identity, negative, multiplier, card.querySelector(".special-sources"));
  const panel = card.querySelector(".stats");
  for (const key of [
    "strength",
    "constitution",
    "magic",
    "armor",
    "technique",
    "resistance",
    "speed",
    "weaponPower",
  ].reverse()) {
    const row = panel.querySelector('[name="' + key + '"]')?.closest(".field");
    if (row) panel.prepend(row);
  }
  details.append(section("面板属性", "自动计算 · 开战前数值"), panel);
  function choice(title, node, key) {
    const box = document.createElement("section");
    box.className = "character-choice-block";
    box.dataset.choice = key;
    box.append(section(title), node);
    return box;
  }
  const nodes = [];
  if (person) {
    const help = person.querySelector("p");
    if (help) help.hidden = true;
    nodes.push(person);
  }
  nodes.push(
    choice("技能组", skill, "skills"),
    choice("装备", equipment, "equipment"),
    choice("契约", contract, "contract"),
    choice("魔石", card.choiceHosts.stone, "stone"),
  );
  if (ring) nodes.push(choice("域之环", ring, "ring"));
  nodes.push(choice("战利品", card.choiceHosts.trophies, "trophies"));
  const panelError = card.querySelector(".character-panel-error");
  if (panelError) nodes.push(panelError);
  nodes.push(state, button, details);
  body.replaceChildren(...nodes);
  card.classList.add("character-from-library");
}
function render(characters) {
  $("#characters").replaceChildren();
  characters.forEach((c, i) => {
    const card = document.createElement("article");
    card.className = "character";
    card.dataset.index = i;
    card.ringPanelIncluded = c.ringPanelIncluded === true;
    card.ringPanelBonuses = structuredClone(c.ringPanelBonuses || {});
    card.ringBattleMultipliers = structuredClone(c.ringBattleMultipliers || {});
    const head = document.createElement("div");
    head.className = "card-head";
    head.innerHTML = `<div class="card-title"><span class="number">0${i + 1}</span><strong>角色 ${i + 1}</strong></div><label class="switch-label">参战<input type="checkbox" name="enabled" class="switch" aria-label="角色${i + 1}参战"></label>`;
    head.draggable = true;
    head.title = "拖动卡片顶部调整站位";
    head.querySelector("input").checked = c.enabled;
    head.querySelector("input").addEventListener("change", (event) => {
      if (
        event.target.checked &&
        document.querySelectorAll(".character [name=enabled]:checked").length > 4
      ) {
        event.target.checked = false;
        toast("最多4名角色参战，请先取消其他角色参战");
      }
      updateCount();
    });
    if (characters.length > 4) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "移除";
      remove.addEventListener("click", () => {
        if (!confirm("移除此角色配置？")) return;
        const data = collect();
        data.characters.splice(Number(card.dataset.index), 1);
        render(data.characters);
        dirty();
      });
      head.append(remove);
    }
    const body = document.createElement("div");
    body.className = "card-body";
    const identity = document.createElement("div");
    identity.className = "identity";
    function jobSelect(name, label) {
      const row = document.createElement("label");
      row.className = "field";
      const caption = document.createElement("span");
      caption.textContent = label;
      const select = document.createElement("select");
      select.name = name;
      select.setAttribute("aria-label", label);
      row.append(caption, select);
      identity.append(row);
      return select;
    }
    function option(select, value, label) {
      const item = document.createElement("option");
      item.value = value;
      item.textContent = label;
      select.append(item);
    }
    const family = jobSelect("profession", "职业"),
      job = jobSelect("job", "转职");
    option(family, "", "请选择职业");
    window.SkillModel.professions.forEach((p) => option(family, p.name, p.name));
    const current = window.SkillModel.findProfession(c.job);
    family.value = current?.name || "";
    function updateJobs(value = "") {
      job.replaceChildren();
      option(job, "", "请选择转职");
      const p = window.SkillModel.professions.find((p) => p.name === family.value);
      if (p) p.jobs.forEach((name) => option(job, name, name));
      job.disabled = !p;
      job.value = p?.jobs.includes(value) ? value : "";
    }
    updateJobs(c.job);
    family.addEventListener("change", () => {
      updateJobs();
      updateEquipmentOptions(card);
      dirty();
    });
    job.addEventListener("change", () => {
      updateEquipmentOptions(card);
      dirty();
    });
    const group = jobSelect("skillGroup", "技能组");
    card.append(body);
    body.append(identity);
    fillGroupOptions(group, card, c.skillGroup);
    group.addEventListener("change", () => {
      delete group.dataset.pendingGroup;
      dirty();
    });
    const first = document.createElement("label");
    first.className = "switch-label";
    first.style.padding = "5px 0";
    first.innerHTML = '先发制人 <input type="checkbox" name="firstStrike" class="switch">';
    first.querySelector("input").checked = configurationType === "special" ? false : c.firstStrike;
    if (configurationType === "special") first.hidden = true;
    identity.append(first);
    const stats = document.createElement("div");
    stats.className = "stats";
    (configurationType === "special"
      ? fields
      : [...fields, ...(window.SpecialConfiguration?.extras || [])]
    ).forEach(([k, l, v = 0]) => {
      const field = makeField(k, l, c.stats[k] ?? v);
      if (k === "physicalDamage") field.style.gridColumn = "1";
      stats.append(field);
    });
    card.append(body);
    body.append(identity);
    const equipment = document.createElement("div");
    equipment.className = "equipment";
    slots.forEach(([k, l]) => {
      const row = document.createElement("label");
      row.className = "field";
      const caption = document.createElement("span");
      caption.textContent = l;
      const select = document.createElement("select");
      select.name = k;
      select.setAttribute("aria-label", l);
      row.append(caption, select);
      equipment.append(row);
      fillEquipmentOptions(select, card, c.equipment[k]);
    });
    const contract = document.createElement("div");
    contract.className = "contract";
    function contractSelect(key, label, choices, value) {
      const row = document.createElement("label");
      row.className = "field";
      const caption = document.createElement("span");
      caption.textContent = label;
      const select = document.createElement("select");
      select.name = key;
      select.setAttribute("aria-label", label);
      for (const choice of choices) {
        const option = document.createElement("option");
        option.value = choice;
        option.textContent = choice;
        select.append(option);
      }
      select.value = choices.includes(value) ? value : choices[0];
      row.append(caption, select);
      return row;
    }
    contract.append(
      contractSelect(
        "contract",
        "状态",
        [
          "不激活",
          "旧日支配者-魔",
          "狂怒兽神-力",
          "饮命者-力",
          "旧日支配者-力",
          "炎钢羽神-技",
          "饮魂者-技",
          "至高妖精-魔",
          "饮命者-魔",
          "黑雾潜者-速",
          "饮命者-速",
          "旧日支配者-速",
        ],
        c.contract,
      ),
      contractSelect(
        "negativeEffect",
        "负面效果",
        ["无", "群体献祭", "脆化", "污秽", "盲目", "痴愚", "群体盲目", "群体痴愚"],
        c.negativeEffect,
      ),
      makeField("skillMultiplier", "技能倍率", c.skillMultiplier),
    );
    body.append(
      identity,
      section("面板属性", "开战前数值"),
      stats,
      section("装备配置", "从装备库选择"),
      equipment,
      section("界域契约"),
      contract,
    );
    card.append(head, body);
    $("#characters").append(card);
    if (configurationType === "special")
      window.SpecialConfiguration.attach({
        card,
        sources: c.specialSources,
        fields,
        slots,
        getLibrary: () => teamEquipmentLibrary,
        onChange: dirty,
      });
    window.ContractLibrary?.attach(card, c);
    window.RingLibrary?.attach(card, c);
    if (configurationType === "special") arrangeCharacterChoices(card);
  });
  updateCardPositions();
  updateCount();
  if (configurationType === "special")
    document.querySelectorAll(".character").forEach((card) => card.refreshSpecial?.());
}
function updateCardPositions() {
  const cards = [...$("#characters").querySelectorAll(".character")];
  cards.forEach((card, index) => {
    card.dataset.index = index;
    card.querySelector(".card-title .number").textContent = String(index + 1).padStart(2, "0");
    card.querySelector(".card-title strong").textContent = "角色 " + (index + 1);
    card
      .querySelector('[name="enabled"]')
      .setAttribute("aria-label", "角色" + (index + 1) + "参战");
    for (const button of card.querySelectorAll(".character-move")) {
      const direction = Number(button.dataset.direction);
      button.disabled = direction < 0 ? index === 0 : index === cards.length - 1;
      button.title = direction < 0 ? "向前移动一个站位" : "向后移动一个站位";
      button.setAttribute(
        "aria-label",
        "角色" + (index + 1) + (direction < 0 ? "向前移动" : "向后移动"),
      );
    }
  });
}
function moveCharacterCard(card, direction) {
  const cards = [...$("#characters").querySelectorAll(".character")];
  const index = cards.indexOf(card),
    target = cards[index + direction];
  if (index < 0 || !target || ![-1, 1].includes(direction)) return;
  const finishAnimation = globalThis.CharacterCardMotion?.capture(cards);
  // Move the existing card to preserve every input, pending selection and listener.
  if (direction < 0) target.before(card);
  else target.after(card);
  updateCardPositions();
  dirty();
  finishAnimation?.();
}
function updateCount() {
  let active = 0;
  document.querySelectorAll(".character").forEach((c) => {
    const enabled = c.querySelector("[name=enabled]").checked;
    c.classList.toggle("disabled", !enabled);
    if (enabled) active++;
  });
  $("#active-count").textContent = active;
}
function collect() {
  return {
    schemaVersion: 1,
    configurationType,
    librarySelections: structuredClone(window.PlayerLibraries?.current || {}),
    target: collectTarget(),
    battle: {
      duration: Number($("#duration").value),
      simulations: Number($("#simulations").value),
    },
    characters: [...document.querySelectorAll(".character")].map((card, i) => {
      const val = (k) => card.querySelector(`[name="${k}"]`).value;
      return {
        name: `角色 ${i + 1}`,
        enabled: card.querySelector("[name=enabled]").checked,
        job: val("job"),
        skillGroup: val("skillGroup"),
        firstStrike:
          configurationType === "special"
            ? (card.specialSources?.selectedTrophies || []).some((t) => t.firstStrike === true)
            : card.querySelector("[name=firstStrike]").checked,
        lifetime: Number($("#duration").value),
        ...(configurationType === "special"
          ? { specialSources: structuredClone(card.specialSources) }
          : {}),
        stats: Object.fromEntries(
          [...fields, ...(window.SpecialConfiguration?.extras || [])].map(([k]) => [
            k,
            configurationType === "special"
              ? Number(
                  card.querySelector('.stats [name="' + k + '"]').dataset.calculatedValue ?? val(k),
                )
              : Number(val(k)),
          ]),
        ),
        equipment: Object.fromEntries(
          slots.map(([k]) => [k, card.querySelector('.equipment select[name="' + k + '"]').value]),
        ),
        selectedRing: structuredClone(card.selectedRing || null),
        ringPanelIncluded: card.ringPanelIncluded === true,
        ringPanelBonuses: structuredClone(card.ringPanelBonuses || {}),
        ringBattleMultipliers: structuredClone(card.ringBattleMultipliers || {}),
        selectedContract: structuredClone(card.selectedContract || null),
        contract: val("contract"),
        negativeEffect: val("negativeEffect"),
        skillMultiplier: Number(val("skillMultiplier")),
      };
    }),
  };
}
function validateNumber(n, name, min = 0, max = Number.MAX_VALUE) {
  if (typeof n !== "number" || !Number.isFinite(n) || n < min || n > max)
    throw new Error(`${name}数值无效`);
  return n;
}
function normalize(data) {
  if (
    !data ||
    data.schemaVersion !== 1 ||
    !Array.isArray(data.characters) ||
    data.characters.length < 1 ||
    data.characters.length > 100
  )
    throw new Error("配置需要包含版本号和1至100个角色");
  validateNumber(data.battle?.duration, "战斗时长", 0.1);
  validateNumber(data.battle?.simulations, "模拟次数", 1, 1000000);
  if (!Number.isInteger(data.battle.simulations)) throw new Error("模拟次数必须是整数");
  const characters = data.characters.map((c, i) => {
    if (!c || typeof c !== "object") throw new Error("角色格式无效");
    const out = blank(i);
    if (typeof c.enabled !== "boolean" || typeof c.firstStrike !== "boolean")
      throw new Error("参战或先发制人格式无效");
    out.enabled = c.enabled;
    out.firstStrike = c.firstStrike;
    for (const k of textFields) {
      const v = slots.some(([s]) => s === k) ? c.equipment?.[k] : c[k];
      if (typeof v !== "string" || v.length > 120) throw new Error("角色名称、技能或装备格式无效");
      if (k in out.equipment) out.equipment[k] = v;
      else out[k] = v;
    }
    out.selectedRing = structuredClone(c.selectedRing || null);
    out.ringPanelIncluded = c.ringPanelIncluded === true;
    out.ringPanelBonuses = structuredClone(c.ringPanelBonuses || {});
    out.ringBattleMultipliers = structuredClone(c.ringBattleMultipliers || {});
    out.selectedContract = structuredClone(c.selectedContract || null);
    out.lifetime = validateNumber(c.lifetime, "存活时长");
    out.skillMultiplier = validateNumber(c.skillMultiplier, "技能倍率");
    if (data.configurationType === "special")
      out.specialSources = structuredClone(c.specialSources || window.SpecialConfiguration.blank());
    for (const [k, l, defaultValue] of [...fields, ...(window.SpecialConfiguration?.extras || [])])
      out.stats[k] = validateNumber(c.stats?.[k] === undefined ? defaultValue : c.stats[k], l);
    return out;
  });
  if (characters.filter((c) => c.enabled).length > 4) throw Error("最多4名角色参战");
  if (characters.filter((c) => c.enabled && c.contract !== "不激活").length > 1)
    throw Error("契约只能由一个角色开启");
  return {
    schemaVersion: 1,
    configurationType: data.configurationType || "regular",
    ...(data.librarySelections
      ? { librarySelections: structuredClone(data.librarySelections) }
      : {}),
    target: normalizeTarget(data.target),
    battle: { ...data.battle },
    characters,
  };
}
let configurationLoading = false;
async function apply(data, { changedLibrariesOnly = false } = {}) {
  if (configurationLoading) throw Error("正在加载配置，请稍候");
  if ($("#characters").children.length) modeDrafts[configurationType] = collect();
  const clean = normalize(data);
  configurationLoading = true;
  try {
    if (window.PlayerLibraries) {
      if (window.PlayerLibraries.whenMounted) await window.PlayerLibraries.whenMounted("equipment");
      await window.PlayerLibraries.restore(clean.librarySelections || {}, {
        changedOnly: changedLibrariesOnly,
      });
    }
    configurationType = clean.configurationType;
    window.ConfigurationLibrary?.selectType?.(configurationType);
    renderTarget(clean.target);
    if (configurationType === "special") window.BossLibrary?.refreshTarget?.();
    $("#duration").value = clean.battle.duration;
    $("#simulations").value = clean.battle.simulations;
    render(clean.characters);
    if (configurationType === "special")
      document
        .querySelectorAll(".character .stats input")
        .forEach((input) => (input.readOnly = true));
    syncConfigurationMode();
    refreshDefaultStyles();
  } finally {
    configurationLoading = false;
  }
}
function getForSave() {
  if (configurationLoading) {
    toast("正在加载配置，请稍候再保存");
    return null;
  }
  try {
    return normalize(collect());
  } catch (e) {
    toast(e.message);
    return null;
  }
}
function getValid() {
  if (configurationLoading) {
    toast("正在加载配置，请稍候再模拟");
    return null;
  }
  if (configurationType === "special") window.BossLibrary?.refreshTarget?.();
  if (!teamSkillGroupsReady) {
    toast("技能组库尚未加载完成，请稍后保存；若持续提示，请检查服务连接");
    return null;
  }
  if ([...$("#target-fields").querySelectorAll("input")].some((input) => !input.checkValidity())) {
    $("#target-panel").open = true;
    const enemy = $("#enemy-information");
    if (enemy) enemy.open = true;
  }
  if ([...document.querySelectorAll(".character input")].some((input) => !input.checkValidity())) {
    const ally = $("#ally-information");
    if (ally) ally.open = true;
  }
  if (!$("#team-form").reportValidity()) return null;
  try {
    for (const card of document.querySelectorAll(".character")) {
      card.refreshSpecial?.();
      if (card.querySelector("[name=enabled]").checked && card.specialError)
        throw Error(card.specialError);
    }
    const data = normalize(collect());
    if (configurationType === "special" && !data.target.selectedBoss)
      throw Error("请从Boss库选择敌方Boss");
    for (const c of data.characters) {
      if (c.skillGroup && !teamSkillGroups.some((g) => g.id === c.skillGroup && g.job === c.job))
        throw Error("技能组必须从当前转职的已有技能组中选择");
      const group = teamSkillGroups.find((g) => g.id === c.skillGroup),
        scope = group?.scope;
      if (
        c.enabled &&
        scope?.kind === "boss" &&
        (data.target.selectedBoss?.id !== scope.bossId ||
          (data.librarySelections?.bosses || "") !== scope.libraryId)
      )
        throw Error(
          "技能组“" + group.name + "”仅适用于" + scope.libraryName + " · " + scope.bossName,
        );
    }
    return data;
  } catch (e) {
    toast(e.message);
    return null;
  }
}
function refreshDefaultStyles() {
  const defaults = {
    duration: 200,
    simulations: 100,
    contract: "不激活",
    negativeEffect: "无",
    skillMultiplier: 1,
    profession: "",
    job: "",
    skillGroup: "",
    ...Object.fromEntries(fields.map(([k, , v]) => [k, v])),
    ...Object.fromEntries(slots.map(([k]) => [k, ""])),
  };
  const targetDefaults = blankTarget();
  targetDefaults.speed =
    Number($("#target-fields").querySelector('[name="target-hitPoint"]').value) / 4000;
  for (const control of $("#team-form").querySelectorAll('input:not([type="checkbox"]),select')) {
    const key = control.id || control.name;
    const expected = key.startsWith("target-") ? targetDefaults[key.slice(7)] : defaults[key];
    control.classList.toggle(
      "default-value",
      expected !== undefined && control.value === String(expected),
    );
  }
  const immunity = $(".target-immunity-dropdown summary");
  if (immunity)
    immunity.classList.toggle(
      "default-value",
      !targetImmunities.some(
        ([k]) => $("#target-fields").querySelector('[name="target-' + k + '"]').checked,
      ),
    );
}
function dirty() {
  refreshDefaultStyles();
  updateCount();
  $("#save-state").textContent = "有未保存的修改";
}
$("#team-form").addEventListener("input", dirty);
$("#team-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const data = getForSave();
  if (data) window.ConfigurationLibrary?.save(data);
});
$("#export").addEventListener("click", () => {
  const data = getValid();
  if (!data) return;
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "地下城堡2-队伍配置.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast("队伍配置已导出");
});
$("#import").addEventListener("click", () => $("#file-input").click());
$("#file-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    if (file.size > 1024 * 1024) throw new Error("配置文件不能超过1MB");
    const data = JSON.parse(await file.text());
    await apply(data);
    dirty();
    toast("配置已导入，点击保存可保留");
  } catch (err) {
    toast(`导入失败：${err.message}`);
  } finally {
    e.target.value = "";
  }
});
$("#preview").addEventListener("click", () => {
  const data = getValid();
  if (!data) return;
  $("#json-preview").textContent = JSON.stringify(data, null, 2);
  $("#data-dialog").showModal();
});
$("#close-dialog").addEventListener("click", () => $("#data-dialog").close());
renderTarget(blankTarget());
render([0, 1, 2, 3].map(blank));
$("#add-character").addEventListener("click", () => {
  const data = collect();
  if (data.characters.length >= 100) {
    toast("最多保存100名角色");
    return;
  }
  data.characters.push({ ...blank(data.characters.length), enabled: false });
  render(data.characters);
  dirty();
});

$("#team-form").addEventListener("change", (event) => {
  if (event.target.name === "enabled" && configurationType === "special")
    document.querySelectorAll(".character").forEach((card) => card.refreshSpecial?.());
  dirty();
});
new MutationObserver(refreshDefaultStyles).observe($("#team-form"), {
  childList: true,
  subtree: true,
});
refreshDefaultStyles();

window.getTeamConfiguration = () => {
  const data = getValid();
  if (!data) return null;
  if (data.characters.length !== 4) {
    data.characters = data.characters.filter((c) => c.enabled);
    while (data.characters.length < 4)
      data.characters.push({ ...blank(data.characters.length), enabled: false });
  }
  return data;
};
window.getTeamConfigurationForSave = getForSave;

window.applyTeamConfiguration = apply;
window.newTeamConfiguration = (type = "regular") => ({
  schemaVersion: 1,
  configurationType: type,
  target: blankTarget(),
  battle: { duration: 200, simulations: 100 },
  characters: [0, 1, 2, 3].map(blank),
});

window.normalizeTeamConfiguration = normalize;

window.BossPanelFields = [
  ...fields,
  ["hitPoint", "血量", 0],
  ["armor", "护甲", 0],
  ["resistance", "抗性", 0],
  ["dodgeRate", "闪避率 %", 0],
];
window.applyBossTarget = (item) => {
  const attrs = item.attributes || {};
  renderTarget({
    ...blankTarget(),
    race: item.race || "傀儡",
    ...item.targetRules,
    ...Object.fromEntries(
      ["hitPoint", "armor", "resistance", "speed", "dodgeRate"].map((k) => [k, attrs[k] || 0]),
    ),
    speedAuto: false,
    partyWipe: structuredClone(item.partyWipe || { enabled: false, time: 120 }),
    name: item.name,
    skillGroup: structuredClone(item.skillGroup || { name: "", skills: [] }),
    attributes: structuredClone(attrs),
    selectedBoss: structuredClone(item),
  });
  syncConfigurationMode();
  dirty();
};

window.clearBossTarget = () => {
  renderTarget({
    ...collectTarget(),
    name: "",
    skillGroup: "",
    selectedBoss: null,
    partyWipe: { enabled: false, time: 120 },
  });
  syncConfigurationMode();
  dirty();
};

function syncConfigurationMode() {
  const special = configurationType === "special";
  document.body.dataset.configurationType = configurationType;
  for (const [type, id] of [
    ["regular", "#mode-regular"],
    ["special", "#mode-special"],
  ]) {
    const button = $(id);
    if (button) {
      button.classList.toggle("selected", configurationType === type);
      button.setAttribute("aria-pressed", String(configurationType === type));
    }
  }
  const help = $("#configuration-mode-help");
  if (help)
    help.textContent = special
      ? "选择Boss和出战人物，依次搭配装备、契约、魔石、域之环、战利品和技能组；点击展示详情查看角色面板。"
      : "手动填写敌方目标和己方角色的面板属性。";
  const picker = $("#boss-target-picker");
  if (picker) picker.hidden = !special;
  for (const input of $("#target-fields").querySelectorAll("input,select")) {
    if (input.tagName === "INPUT" && input.type === "number") input.readOnly = special;
    else input.disabled = special;
  }
  window.BossLibrary?.setMode(special);
}
window.getConfigurationType = () => configurationType;
window.switchConfigurationMode = async (type) => {
  if (!["regular", "special"].includes(type) || type === configurationType) return;
  modeDrafts[configurationType] = collect();
  const next = modeDrafts[type] || window.newTeamConfiguration(type);
  try {
    // 两种模式的草稿来自同一会话：库没换就不必重新向后端请求。
    await apply(structuredClone(next), { changedLibrariesOnly: true });
    dirty();
  } catch (error) {
    toast("配置加载失败：" + error.message);
  }
};
$("#mode-regular")?.addEventListener("click", () => window.switchConfigurationMode("regular"));
$("#mode-special")?.addEventListener("click", () => window.switchConfigurationMode("special"));
syncConfigurationMode();
