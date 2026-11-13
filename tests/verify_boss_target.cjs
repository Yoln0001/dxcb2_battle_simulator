const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert");
const source = fs.readFileSync("frontend/js/app.js", "utf8");
const start = source.indexOf("function normalizeTarget("),
  end = source.indexOf("let timer;", start);
const context = {
  targetNumbers: [
    ["hitPoint", "血量", 175000000],
    ["speed", "速度", 43750],
    ["armor", "护甲", 0],
    ["allyLifestealReduction", "吸血降低 %", 0],
    ["allyHealingReduction", "回复降低 %", 0],
    ["allyRegenerationReduction", "回春降低 %", 0],
  ],
  targetImmunities: [],
  validateNumber(v) {
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0) throw Error("invalid");
    return v;
  },
  blankTarget() {
    return {};
  },
  structuredClone,
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
const boss = { id: "boss", name: "龙", attributes: { magic: 900 } };
const result = context.normalizeTarget({
  race: "龙",
  hitPoint: 100000,
  speed: 123,
  speedAuto: false,
  name: "龙",
  skillGroup: { name: "专属组", skills: [] },
  attributes: { magic: 900, armor: 200 },
  selectedBoss: boss,
  allyLifestealReduction: 20,
  allyHealingReduction: 30,
  allyRegenerationReduction: 40,
});
assert.equal(result.allyLifestealReduction, 20);
assert.equal(result.allyHealingReduction, 30);
assert.equal(result.allyRegenerationReduction, 40);
assert.equal(result.skillGroup.name, "专属组");
assert.equal(result.speed, 123);
assert.equal(result.attributes.magic, 900);
assert.equal(result.selectedBoss.id, "boss");
assert.throws(() => context.normalizeTarget({ race: "龙", attributes: { magic: -1 } }));
console.log(
  "PASS: frontend target normalization preserves Boss group, panel, explicit speed and saved snapshot",
);
