const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert"),
  path = require("path");
const source = fs.readFileSync(path.resolve(__dirname, "../frontend/js/app.js"), "utf8");
const context = vm.createContext({ structuredClone, window: {} });
vm.runInContext(
  source.slice(source.indexOf("const fields ="), source.indexOf("const $ =")),
  context,
);
vm.runInContext(
  `function blank(i){return {name:'角色 '+i,enabled:true,job:'',skillGroup:'',firstStrike:false,lifetime:200,stats:Object.fromEntries(fields.map(([k,,v])=>[k,v])),equipment:Object.fromEntries(slots.map(([k])=>[k,''])),contract:'不激活',negativeEffect:'无',skillMultiplier:1};} function normalizeTarget(t){return t;}`,
  context,
);
vm.runInContext(
  source.slice(source.indexOf("function validateNumber("), source.indexOf("async function apply(")),
  context,
);
const data = vm.runInContext(
  `({schemaVersion:1,battle:{duration:200,simulations:100},target:{race:'傀儡'},characters:[0,1,2,3].map(blank)})`,
  context,
);
for (const c of data.characters) {
  c.job = "寒霜法师";
  c.skillGroup = "saved-group";
  c.stats.magic = 12578;
  c.equipment.weapon = "saved-weapon";
  delete c.stats.healingBonus;
  delete c.stats.finalHealingBonus;
}
const original = JSON.stringify(data);
context.data = data;
const migrated = vm.runInContext("normalize(data)", context);
for (const c of migrated.characters) {
  assert.equal(c.job, "寒霜法师");
  assert.equal(c.skillGroup, "saved-group");
  assert.equal(c.equipment.weapon, "saved-weapon");
  assert.equal(c.stats.magic, 12578);
  assert.equal(c.stats.healingBonus, 0);
  assert.equal(c.stats.finalHealingBonus, 0);
  for (const key of [
    "physicalSingleLifesteal",
    "magicSingleLifesteal",
    "physicalAreaLifesteal",
    "magicAreaLifesteal",
  ])
    assert.equal(c.stats[key], 0);
}
assert.equal(JSON.stringify(data), original);
data.characters[0].stats.healingBonus = 26;
data.characters[0].stats.finalHealingBonus = 8;
assert.equal(vm.runInContext("normalize(data).characters[0].stats.healingBonus", context), 26);
data.characters[0].stats.healingBonus = "bad";
assert.throws(() => vm.runInContext("normalize(data)", context));
console.log(
  "PASS: old saved configuration restores jobs, groups, equipment and stats; new fields default to zero; input untouched",
);

context.data = migrated;
for (const c of migrated.characters) {
  c.stats.physicalSingleLifesteal = 12.5;
  c.stats.magicAreaLifesteal = 8;
}
const saved = vm.runInContext("normalize(data)", context);
assert.equal(saved.characters[0].stats.physicalSingleLifesteal, 12.5);
assert.equal(saved.characters[0].stats.magicAreaLifesteal, 8);
