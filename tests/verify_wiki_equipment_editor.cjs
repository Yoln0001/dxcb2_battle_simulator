const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert"),
  crypto = require("crypto");
const root = process.argv[2] || require("path").resolve(__dirname, "..");
const model = require(root + "/frontend/js/equipment/model.js");
const nodes = [],
  named = new Map();
class Node {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.handlers = {};
    this.dataset = {};
    this.classList = { add() {}, remove() {}, toggle() {} };
    this.checked = false;
    this.defaultValue = "";
    this.value = "";
    this.textContent = "";
    nodes.push(this);
  }
  set name(n) {
    this._name = n;
    named.set(n, this);
  }
  get name() {
    return this._name;
  }
  get firstChild() {
    return this.children[0];
  }
  after() {}
  get lastChild() {
    return this.children.at(-1);
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this.children = children;
  }
  setAttribute(k, v) {
    this[k] = v;
  }
  addEventListener(kind, fn) {
    (this.handlers[kind] ??= []).push(fn);
  }
  querySelectorAll(selector) {
    const all = this.children.flatMap((c) => [c, ...c.querySelectorAll("*")]);
    return selector === "[data-matrix]" ? all.filter((c) => c.dataset.matrix) : all;
  }
  get elements() {
    return { namedItem: (n) => named.get(n) };
  }
  reportValidity() {
    return true;
  }
  reset() {
    for (const x of named.values()) {
      x.checked = false;
      x.value = x.tag === "select" ? x.children[0]?.value || "" : x.defaultValue;
    }
  }
  close() {}
  showModal() {}
  click() {
    for (const fn of this.handlers.click || []) fn();
  }
}
const toast = new Node("div"),
  open = new Node("button"),
  data = {};
const context = {
  document: {
    createElement: (tag) => new Node(tag),
    body: new Node("body"),
    querySelector: (s) => (s === "#toast" ? toast : open),
  },
  window: {
    showToast() {},
    EquipmentModel: model,
    SkillModel: require(root + "/frontend/js/skills/model.js"),
  },
  location: { protocol: "file:" },
  localStorage: { getItem: (k) => data[k] ?? null, setItem: (k, v) => (data[k] = v) },
  setTimeout: () => 0,
  clearTimeout() {},
  confirm: () => true,
  crypto,
  console,
  structuredClone,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(root + "/frontend/js/equipment/editor.js", "utf8"), context);
vm.runInContext(fs.readFileSync(root + "/frontend/js/equipment/wiki-details.js", "utf8"), context);
context.window.createEquipmentLibraryEditor({
  wiki: true,
  title: "百科装备库",
  dialogId: "wiki-equipment-editor-dialog",
  api: "/api/wiki-equipment",
  storageKey: "dungeon2-wiki-equipment-library-v1",
});
(async () => {
  const form = nodes.find((n) => n.id === "wiki-equipment-form"),
    create = nodes.filter((n) => n.textContent === "＋ 创建装备").at(-1);
  for (const kind of ["none", "amplify", "magicTrueDamage", "immediateAction", "debuff", "buff"]) {
    create.click();
    named.get("startEnabled").checked = true;
    named.get("triggerEnabled").checked = true;
    named.get("name").value = "测试 " + kind;
    named.get("effectKind").value = kind;
    named.get("effectName").value = "开战 " + kind;
    named.get("triggerEffectName").value = "触发 " + kind;
    named.get("attackType").value = "magic";
    if (["amplify", "buff"].includes(kind)) {
      named.get(kind + "-enabled-strength").checked = true;
      named.get(kind + "-strength-magic").value = "170";
    }
    if (kind === "amplify") named.get("amplify-strength-lostHitPoint").value = "45";
    const main = nodes.filter((n) => n["aria-label"] === "装备主属性").at(-1);
    main.value = "magic";
    for (const fn of main.handlers.change || []) fn();
    assert(
      nodes.some(
        (n) => n.className === "equipment-main-attribute-badge" && n.textContent === "主属性",
      ),
    );
    for (const fn of form.handlers.change || []) fn();
    await form.handlers.submit[0]({ preventDefault() {} });
    const saved = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment;
    const item = saved.find((x) => x.name === "测试 " + kind);
    assert.ok(item, kind);
    assert.equal(item.mainAttribute, "magic");
    assert.equal(nodes.filter((n) => n["aria-label"] === "装备主属性").at(-1).value, "magic");
    assert.equal(item.effect?.kind || "none", kind);
    if (kind === "amplify") {
      assert.equal(item.effect.conversions[0].coefficients.lostHitPoint, 0.45);
      assert.equal(named.get("amplify-strength-lostHitPoint").value, 45);
    }
    assert.equal(item.effectName, "开战 " + kind);
    assert.equal(item.triggerEffectName, "触发 " + kind);
    assert.equal(item.attackType, "magic");
    assert.equal(item.startingBuff.enabled, true);
    assert.equal(item.triggerEnabled, true);
    assert.equal(named.get("effectName").value, item.effectName);
    assert.equal(named.get("triggerEffectName").value, item.triggerEffectName);
    if (["amplify", "buff"].includes(kind))
      assert.equal(item.effect.conversions[0].coefficients.magic, 1.7);
  }
  assert.equal(JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.length, 6);
  const duplicate = nodes.filter((n) => n.textContent === "另存为副本").at(-1);
  duplicate.click();
  await form.handlers.submit[0]({ preventDefault() {} });
  assert.equal(JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.length, 7);
  named.get("startEnabled").checked = false;
  named.get("triggerEnabled").checked = false;
  for (const fn of form.handlers.change || []) fn();
  assert.equal(named.get("start-magic").disabled, true);
  assert.equal(named.get("triggerRate").disabled, true);
  await form.handlers.submit[0]({ preventDefault() {} });
  const closed = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find((x) =>
    x.name.endsWith("（副本）"),
  );
  assert.equal(closed.startingBuff.enabled, false);
  assert.equal(closed.triggerEnabled, false);
  assert.equal(closed.effect.kind, "buff");
  assert.equal(named.get("startEnabled").checked, false);
  assert.equal(named.get("triggerEnabled").checked, false);
  create.click();
  named.get("name").value = "双触发装备";
  named.get("triggerEnabled").checked = true;
  named.get("triggerEffectName").value = "物理特效";
  named.get("attackType").value = "physical";
  named.get("effectKind").value = "immediateAction";
  named.get("triggerRate").value = "30";
  nodes
    .filter((n) => n.textContent === "＋ 添加特效")
    .at(-1)
    .click();
  named.get("triggerEffectName").value = "魔法特效";
  named.get("attackType").value = "magic";
  named.get("effectKind").value = "magicTrueDamage";
  named.get("triggerRate").value = "60";
  named.get("true-magic").value = "200";
  nodes
    .filter((n) => n.tag === "button" && n.textContent === "特效 1 · 物理特效")
    .at(-1)
    .click();
  assert.equal(named.get("triggerEffectName").value, "物理特效");
  assert.equal(named.get("triggerRate").value, 30);
  await form.handlers.submit[0]({ preventDefault() {} });
  const multi = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "双触发装备",
  );
  assert.equal(multi.triggerEffects.length, 2);
  assert.equal(multi.triggerEffects[0].triggerType, "physical");
  assert.equal(multi.triggerEffects[1].triggerType, "magic");
  assert.equal(multi.triggerEffects[1].effect.coefficients.magic, 2);
  nodes
    .filter((n) => n.tag === "button" && n.textContent === "特效 2 · 魔法特效")
    .at(-1)
    .click();
  assert.equal(named.get("triggerRate").value, 60);
  nodes
    .filter((n) => n.textContent === "删除当前特效")
    .at(-1)
    .click();
  await form.handlers.submit[0]({ preventDefault() {} });
  assert.equal(
    JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
      (x) => x.name === "双触发装备",
    ).triggerEffects.length,
    1,
  );
  const label = (value) => nodes.filter((n) => n["aria-label"] === value).at(-1);
  label("命中率固定值").value = "-4";
  assert.equal(label("命中率最小"), undefined);
  label("魔力最小").value = "300";
  label("魔力最大").value = "700";
  label("启用晶络").checked = true;
  label("启用晶络").handlers.change[0]();
  label("晶络魔力").value = "12.5";
  label("晶络力量").value = "3";
  await form.handlers.submit[0]({ preventDefault() {} });
  const edited = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "双触发装备",
  );
  assert.equal(edited.crystal.enabled, true);
  assert.equal(edited.crystal.attributes.magic, 12.5);
  assert.equal(label("晶络魔力").value, 12.5);
  assert.equal(edited.baseAttributes.magic.min, 300);
  assert.equal(edited.baseAttributes.magic.max, 700);
  assert.equal(edited.baseAttributes.hitRate.value, -4);
  assert.equal(
    nodes.find((n) => n.textContent === "补充属性与特效"),
    undefined,
  );
  label("启用晶络").checked = false;
  label("启用晶络").handlers.change[0]();
  await form.handlers.submit[0]({ preventDefault() {} });
  assert.equal(label("晶络魔力").disabled, true);
  assert.equal(
    JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
      (x) => x.name === "双触发装备",
    ).crystal.attributes.magic,
    12.5,
  );
  named.get("triggerEnabled").checked = true;
  named.get("effectKind").value = "healing";
  named.get("healRecipient").value = "allAllies";
  named.get("heal-magic").value = "200";
  for (const fn of form.handlers.change || []) fn();
  await form.handlers.submit[0]({ preventDefault() {} });
  const healed = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "双触发装备",
  );
  assert.equal(healed.effect.kind, "healing");
  assert.equal(healed.effect.coefficients.magic, 2);
  assert.equal(healed.effect.recipient, "allAllies");
  assert.equal(named.get("effectKind").value, "healing");
  named.get("effectKind").value = "buff";
  named.get("buffType").value = "constitution";
  named.get("buff-enabled-constitution").checked = true;
  named.get("buff-constitution-magic").value = "10";
  for (const fn of form.handlers.change || []) fn();
  await form.handlers.submit[0]({ preventDefault() {} });
  const augmented = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "双触发装备",
  );
  assert.equal(augmented.effect.conversions.length, 7);
  assert.equal(
    augmented.effect.conversions.find((r) => r.target === "constitution").coefficients.magic,
    0.1,
  );
  nodes
    .filter((n) => n.textContent === "删除当前特效")
    .at(-1)
    .click();
  assert.equal(named.get("triggerEnabled").checked, false);
  await form.handlers.submit[0]({ preventDefault() {} });
  assert.equal(
    JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
      (x) => x.name === "双触发装备",
    ).triggerEffects.length,
    0,
  );
  named.get("triggerEnabled").checked = true;
  for (const fn of form.handlers.change || []) fn();
  named.get("effectKind").value = "buff";
  for (const fn of form.handlers.change || []) fn();
  const buffPanel = nodes
    .filter((n) => n.tag === "fieldset" && n.children[0]?.textContent === "对友方释放 buff")
    .at(-1);
  assert.equal(buffPanel.hidden, false);
  assert.equal(buffPanel.disabled, false);
  named.get("effectKind").value = "healing";
  for (const fn of form.handlers.change || []) fn();
  named.get("heal-magic").value = "200";
  await form.handlers.submit[0]({ preventDefault() {} });
  const repaired = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "双触发装备",
  );
  assert.equal(repaired.triggerEffects.length, 1);
  assert.equal(repaired.triggerEffects[0].effect.kind, "healing");
  create.click();
  named.get("name").value = "独立debuff";
  named.get("startEnabled").checked = true;
  named.get("startSide").value = "enemy";
  for (const fn of form.handlers.change || []) fn();
  named.get("startEnemyName").value = "腐蚀";
  named.get("startDebuffType").value = "dot";
  named.get("startDotDamage").value = "125";
  for (const fn of form.handlers.change || []) fn();
  assert.equal(named.get("start-physicalVulnerability").disabled, true);
  assert.equal(named.get("startDotDamage").disabled, false);
  nodes
    .filter((n) => n.textContent === "＋ 添加开战效果")
    .at(-1)
    .click();
  named.get("startSide").value = "enemy";
  for (const fn of form.handlers.change || []) fn();
  named.get("startEnemyName").value = "罚罪";
  named.get("startDebuffType").value = "healingReduction";
  named.get("start-healingReduction").value = "20";
  for (const fn of form.handlers.change || []) fn();
  assert.equal(named.get("startDotDamage").disabled, true);
  await form.handlers.submit[0]({ preventDefault() {} });
  const rows = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "独立debuff",
  ).startingDebuffs.entries;
  assert.equal(rows.length, 2);
  assert.equal(rows[0].type, "dot");
  assert.equal(rows[0].dotDamage, 125);
  assert.equal(rows[0].physicalVulnerability, 0);
  assert.equal(rows[1].type, "healingReduction");
  assert.equal(rows[1].healingReduction, 20);
  assert.equal(rows[1].dotEnabled, false);
  nodes
    .filter((n) => n.tag === "button" && n.textContent.startsWith("开战效果 2"))
    .at(-1)
    .click();
  assert.equal(named.get("startDebuffType").value, "healingReduction");
  assert.equal(named.get("start-healingReduction").value, 20);
  nodes
    .filter((n) => n.textContent === "删除当前开战效果")
    .at(-1)
    .click();
  await form.handlers.submit[0]({ preventDefault() {} });
  assert.equal(
    JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
      (x) => x.name === "独立debuff",
    ).startingDebuffs.entries.length,
    1,
  );
  create.click();
  named.get("name").value = "免疫测试";
  const burn = nodes.filter((n) => n["aria-label"] === "装备免疫灼烧").at(-1),
    fear = nodes.filter((n) => n["aria-label"] === "装备免疫技巧衰减").at(-1);
  burn.checked = true;
  fear.checked = true;
  for (const label of ["装备免疫物理易伤", "装备免疫魔法易伤"]) {
    const input = nodes.filter((n) => n["aria-label"] === label).at(-1);
    assert(input);
    input.checked = true;
  }
  await form.handlers.submit[0]({ preventDefault() {} });
  const immuneItem = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "免疫测试",
  );
  assert.equal(immuneItem.negativeImmunities.immuneBurn, true);
  assert.equal(immuneItem.negativeImmunities.immunePhysicalVulnerability, true);
  assert.equal(immuneItem.negativeImmunities.immuneMagicVulnerability, true);
  assert.equal(immuneItem.negativeImmunities.immuneTechniqueDecay, true);
  assert.equal(burn.checked, true);
  assert.equal(fear.checked, true);
  create.click();
  assert.equal(burn.checked, false);
  assert.equal(fear.checked, false);
  create.click();
  named.get("name").value = "开战回春";
  named.get("startEnabled").checked = true;
  named.get("startSide").value = "ally";
  assert.equal(named.has("startAllyEnabled"), false);
  assert.equal(named.has("startEnemyEnabled"), false);
  named.get("startKind").value = "regeneration";
  for (const fn of form.handlers.change || []) fn();
  assert.equal(named.get("startTarget").disabled, true);
  assert.equal(named.get("startRegenBase").disabled, false);
  named.get("startRegenBase").value = "25";
  named.get("startRegen-constitution").value = "100";
  named.get("startRegenBonuses").value = "false";
  await form.handlers.submit[0]({ preventDefault() {} });
  const regenItem = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "开战回春",
  );
  assert.equal(regenItem.startingBuff.kind, "regeneration");
  assert.equal(regenItem.startingBuff.regeneration.baseValue, 25);
  assert.equal(regenItem.startingBuff.regeneration.receivesHealingBonuses, false);
  assert.equal(named.get("startRegenBonuses").value, "false");
  assert.equal(regenItem.startingBuff.regeneration.coefficients.constitution, 1);
  assert.equal(named.get("startKind").value, "regeneration");
  named.get("startKind").value = "amplify";
  for (const fn of form.handlers.change || []) fn();
  assert.equal(named.get("startRegenBase").disabled, true);
  assert.equal(named.get("startTarget").disabled, false);
  create.click();
  named.get("name").value = "混合开战效果";
  named.get("startEnabled").checked = true;
  named.get("effectName").value = "增幅A";
  named.get("start-magic").value = "50";
  named.get("startTarget").value = "magic";
  nodes
    .filter((n) => n.textContent === "＋ 添加开战效果")
    .at(-1)
    .click();
  named.get("effectName").value = "回春B";
  named.get("startKind").value = "regeneration";
  named.get("startRegenBase").value = "25";
  named.get("startRegen-constitution").value = "100";
  for (const fn of form.handlers.change || []) fn();
  nodes
    .filter((n) => n.textContent === "＋ 添加开战效果")
    .at(-1)
    .click();
  named.get("startSide").value = "enemy";
  for (const fn of form.handlers.change || []) fn();
  named.get("startEnemyName").value = "易伤C";
  named.get("startDebuffType").value = "magicVulnerability";
  named.get("start-magicVulnerability").value = "12";
  for (const fn of form.handlers.change || []) fn();
  await form.handlers.submit[0]({ preventDefault() {} });
  const mixed = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "混合开战效果",
  );
  assert.equal(mixed.battleStartEffects.entries.length, 3);
  assert.equal(mixed.battleStartEffects.entries[1].buff.kind, "regeneration");
  assert.equal(mixed.battleStartEffects.entries[2].side, "enemy");
  assert.equal(mixed.startingDebuffs.entries[0].magicVulnerability, 12);
  nodes
    .filter((n) => n.tag === "button" && n.textContent.startsWith("开战效果 2"))
    .at(-1)
    .click();
  assert.equal(named.get("startKind").value, "regeneration");
  assert.equal(named.get("startRegenBase").value, 25);
  nodes
    .filter((n) => n.tag === "button" && n.textContent.startsWith("开战效果 1"))
    .at(-1)
    .click();
  assert.equal(named.get("start-magic").value, 50);
  assert.equal(named.get("startTarget").value, "magic");
  named.get("startEnabled").checked = false;
  await form.handlers.submit[0]({ preventDefault() {} });
  const off = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "混合开战效果",
  );
  assert.equal(off.battleStartEffects.enabled, false);
  assert.equal(off.battleStartEffects.entries.length, 3);
  create.click();
  named.get("name").value = "生命剥夺装备";
  named.get("startEnabled").checked = true;
  named.get("startSide").value = "enemy";
  for (const fn of form.handlers.change || []) fn();
  named.get("startDebuffType").value = "lifeDeprivation";
  for (const fn of form.handlers.change || []) fn();
  assert.equal(named.get("start-lifeDeprivation").disabled, false);
  assert.equal(named.get("startDotDamage").disabled, true);
  named.get("start-lifeDeprivation").value = "10";
  await form.handlers.submit[0]({ preventDefault() {} });
  const life = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "生命剥夺装备",
  );
  assert.equal(life.startingDebuffs.entries[0].type, "lifeDeprivation");
  assert.equal(life.startingDebuffs.entries[0].lifeDeprivation, 10);
  assert.equal(named.get("start-lifeDeprivation").value, 10);
  for (const trigger of ["receivedPhysical", "receivedMagic"]) {
    create.click();
    named.get("name").value = "受击装备" + trigger;
    named.get("triggerEnabled").checked = true;
    named.get("attackType").value = trigger;
    named.get("effectKind").value = "immediateAction";
    named.get("triggerRate").value = "100";
    for (const fn of form.handlers.change || []) fn();
    await form.handlers.submit[0]({ preventDefault() {} });
    const saved = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
      (x) => x.name === "受击装备" + trigger,
    );
    assert.equal(saved.triggerEffects[0].triggerType, trigger);
    assert.equal(named.get("attackType").value, trigger);
  }
  create.click();
  named.get("name").value = "护甲抗性转化";
  named.get("triggerEnabled").checked = true;
  named.get("effectKind").value = "amplify";
  for (const target of ["magic", "armor", "resistance"])
    named.get("amplify-enabled-" + target).checked = true;
  named.get("amplify-magic-armor").value = "200";
  named.get("amplify-magic-resistance").value = "300";
  named.get("amplify-armor-magic").value = "50";
  named.get("amplify-resistance-strength").value = "40";
  for (const fn of form.handlers.change || []) fn();
  await form.handlers.submit[0]({ preventDefault() {} });
  const defense = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "护甲抗性转化",
  );
  assert.equal(defense.effect.conversions.length, 6);
  assert.equal(defense.effect.conversions.find((r) => r.target === "magic").coefficients.armor, 2);
  assert.equal(
    defense.effect.conversions.find((r) => r.target === "armor").coefficients.magic,
    0.5,
  );
  assert.equal(named.get("amplify-magic-resistance").value, 300);
  assert.equal(named.get("amplify-resistance-strength").value, 40);
  create.click();
  named.get("name").value = "百分比装备";
  let liveRefreshes = 0;
  context.window.refreshPlayerEquipment = () => {
    liveRefreshes++;
  };
  const field = (label) => nodes.filter((n) => n["aria-label"] === label).at(-1),
    edit = (label, value) => {
      const input = field(label);
      input.value = String(value);
      for (const fn of input.handlers.input || []) fn();
    };
  edit("武威最小", 532);
  edit("武威最大", 862);
  edit("武威我的数值", 697);
  assert.equal(Number(field("武威百分比").value), 50);
  edit("武威百分比", 25);
  assert.equal(Number(field("武威我的数值").value), 614.5);
  edit("武威百分比", 0);
  assert.equal(Number(field("武威我的数值").value), 532);
  edit("武威百分比", 100);
  assert.equal(Number(field("武威我的数值").value), 862);
  edit("武威百分比", "");
  assert.equal(field("武威我的数值").value, "");
  edit("武威我的数值", 697);
  edit("武威最大", 1192);
  assert.equal(Number(field("武威百分比").value), 25);
  assert.equal(Number(field("武威我的数值").value), 697);
  edit("武威最大", 532);
  assert.equal(field("武威百分比").disabled, true);
  assert.equal(field("武威百分比").value, "");
  edit("武威最大", "");
  assert.equal(field("武威百分比").disabled, true);
  edit("武威最大", 862);
  edit("武威百分比", 50);
  assert.equal(field("武威百分比").disabled, false);
  await form.handlers.submit[0]({ preventDefault() {} });
  const progressItem = JSON.parse(data["dungeon2-wiki-equipment-library-v1"]).equipment.find(
    (x) => x.name === "百分比装备",
  );
  assert(progressItem);
  assert.equal(progressItem.baseAttributes.weaponPower.ownedValue, 697);
  assert(!("ownedPercentage" in progressItem.baseAttributes.weaponPower));
  assert.equal(Number(field("武威百分比").value), 50);
  assert(
    liveRefreshes > 0,
    "saving wiki equipment must refresh the main selected equipment library",
  );
  console.log(
    "PASS: editor initialization, switching all effect panels, collecting fields, matrix values, local persistence, edit reload, independent duplicate",
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
