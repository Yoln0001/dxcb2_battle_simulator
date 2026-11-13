const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert"),
  crypto = require("crypto"),
  path = require("path");
const nodes = [];
class Node {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this._value = "";
    this.dataset = {};
    nodes.push(this);
  }
  get value() {
    return this._value || (this.tag === "select" ? this.children[0]?.value || "" : "");
  }
  set value(v) {
    this._value = String(v);
  }
  get options() {
    return this.children;
  }
  append(...items) {
    this.children.push(...items);
    for (const i of items) i.parentNode = this;
  }
  prepend(...items) {
    this.children.unshift(...items);
  }
  replaceChildren(...items) {
    this.children = items;
    this._value = "";
  }
  setAttribute(k, v) {
    this[k] = v;
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
  }
  reportValidity() {
    return true;
  }
}
const open = new Node("button"),
  cards = [],
  storage = {};
const context = {
  document: {
    body: new Node("body"),
    createElement: (t) => new Node(t),
    querySelector: () => open,
    querySelectorAll: () => cards,
  },
  location: { protocol: "file:" },
  window: { showToast() {}, PlayerLibraries: { current: {}, mount() {} } },
  localStorage: { getItem: (k) => storage[k] || null, setItem: (k, v) => (storage[k] = v) },
  crypto,
  structuredClone,
  confirm: () => true,
  Event: class {},
  console,
};
vm.createContext(context);
vm.runInContext(
  fs.readFileSync(path.join(__dirname, "../frontend/js/rings/library.js"), "utf8"),
  context,
);
(async () => {
  await new Promise((r) => setImmediate(r));
  open.onclick();
  const dialog = nodes.find((n) => n.tag === "dialog");
  assert(dialog.open);
  const fields = Object.fromEntries(nodes.filter((n) => n.name).map((n) => [n.name, n]));
  assert.equal(fields.gainValue.value, "0");
  assert(!fields.pair);
  assert.equal(fields.mainAttribute.options.length, 5);
  assert.equal(fields.secondaryAttribute.options.length, 5);
  fields.mainAttribute.value = "constitution";
  fields.secondaryAttribute.value = "speed";
  fields.kind.value = "water";
  fields.kind.onchange();
  assert.equal(fields.mainAttribute.value, "constitution");
  assert.equal(fields.secondaryAttribute.value, "speed");
  fields.restriction.value = "none";
  fields.gain.value = "healingBonus";
  fields.gainValue.value = "13.7";
  nodes.find((n) => n.textContent === "另存为副本").onclick();
  fields.name.value = "手填水环";
  await nodes.find((n) => n.tag === "form").onsubmit({ preventDefault() {} });
  const data = JSON.parse(storage["dungeon2-ring-library-v1"]);
  assert.equal(data.length, 13);
  assert.equal(data.at(-1).mainAttribute, "constitution");
  assert.equal(data.at(-1).secondaryAttribute, "speed");
  assert.equal(data.at(-1).gainValue, 13.7);
  assert(!("breakthroughs" in data.at(-1)));
  const host = new Node("div"),
    card = {
      querySelector: () => host,
      dispatchEvent() {},
      specialSources: {},
      refreshSpecial() {
        this.refreshed = true;
      },
    };
  cards.push(card);
  context.window.RingLibrary.attach(card, {});
  const wear = host.children[0].children[1];
  wear.value = data.at(-1).id;
  wear.onchange();
  assert.equal(card.selectedRing.gainValue, 13.7);
  assert.equal(card.specialSources.selectedRing.gain, "healingBonus");
  assert(card.refreshed);
  fields.gainValue.value = "22";
  fields.mainValue.value = "810";
  fields.name.value = "更新水环";
  await nodes.find((n) => n.tag === "form").onsubmit({ preventDefault() {} });
  assert.equal(card.selectedRing.gainValue, 22);
  assert.equal(card.selectedRing.name, "更新水环");
  assert.equal(card.specialSources.selectedRing.mainValue, 810);
  nodes.find((n) => n.textContent === "删除域之环").onclick();
  await new Promise((r) => setImmediate(r));
  assert.equal(card.selectedRing, null);
  assert.equal(card.specialSources.selectedRing, null);
  console.log(
    "PASS: ring editor initializes, saves manual percentage without breakthrough data and supplies wearer configuration",
  );
})();
