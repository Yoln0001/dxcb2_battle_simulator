const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert");
const source = fs.readFileSync("frontend/js/app.js", "utf8");
const code = source.slice(
  source.indexOf("const slotCategory ="),
  source.indexOf("function updateEquipmentOptions"),
);
const selected = {
  id: "wiki-fixed",
  wikiId: "wiki-fixed",
  libraryRecordId: "new-copy",
  identityAliases: ["old-copy", "new-copy", "wiki-fixed"],
  name: "黑星★",
  category: "weapon",
  weaponJob: "法师",
  baseAttributes: { magic: { ownedValue: 200 } },
};
const select = {
  name: "weapon",
  value: "",
  children: [],
  replaceChildren() {
    this.children = [];
  },
  append(row) {
    this.children.push(row);
  },
};
const context = {
  window: { SkillModel: { findProfession: () => ({ name: "法师" }) } },
  teamEquipmentLibrary: [selected],
  slots: [["weapon", "武器"]],
  document: { createElement: () => ({}) },
};
vm.createContext(context);
vm.runInContext(code, context);
const card = { querySelector: () => ({ value: "血法师" }) };
context.fillEquipmentOptions(select, card, "old-copy");
assert.equal(select.value, "wiki-fixed");
assert.equal(select.children.find((o) => o.value === "wiki-fixed").textContent, "黑星★");
context.teamEquipmentLibrary = [
  { ...selected, libraryRecordId: "another-copy", baseAttributes: { magic: { ownedValue: 300 } } },
];
context.fillEquipmentOptions(select, card);
assert.equal(select.value, "wiki-fixed");
assert.equal(select.children.length, 2);
assert(!select.children.some((o) => o.disabled));
console.log(
  "PASS: refresh resolves old detached-library record to encyclopedia identity; subsequent library switch keeps wearing ID and readable name",
);
