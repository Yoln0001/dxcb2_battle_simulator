const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert");
class N {
  constructor(tag, text) {
    this.tag = tag;
    this.textContent = text;
    this.children = [];
    this.value = "";
    this.handlers = {};
  }
  append(...n) {
    this.children.push(...n);
  }
  setAttribute(k, v) {
    this[k] = v;
  }
  addEventListener(k, fn) {
    this.handlers[k] = fn;
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
  }
  remove() {}
  reportValidity() {
    return true;
  }
}
const source = { id: "special", name: "攻略队伍", configuration: { configurationType: "special" } },
  copy = {
    id: "regular",
    name: "攻略常规",
    libraryId: "custom_regular",
    configuration: { configurationType: "regular" },
  };
let handler, submitted, notified;
const context = {
  el: (tag, text) => new N(tag, text),
  items: [source],
  selected: source.id,
  libraries: [
    { id: "default_regular", name: "默认常规", configurationType: "regular" },
    { id: "custom_regular", name: "自定义常规", configurationType: "regular" },
    { id: "special_lib", name: "特殊库", configurationType: "special" },
  ],
  dialog: new N("dialog"),
  category: new N("select"),
  libraryId: "special_lib",
  pending: null,
  button: (label, fn) => {
    handler = fn;
    return new N("button", label);
  },
  request: async (path, method, body) => {
    submitted = { path, method, body };
    return { item: copy, configurations: [source, copy] };
  },
  absorb: (data) => {
    context.items = data.configurations;
  },
  render() {},
  toast: (message) => (notified = message),
};
vm.createContext(context);
const code = fs.readFileSync("frontend/js/configurations/library.js", "utf8");
vm.runInContext(
  code.slice(code.indexOf(" const copyRegular = button("), code.indexOf(' button("删除配置",')),
  context,
);
(async () => {
  await handler();
  const popup = context.dialog.children[0],
    form = popup.children[0],
    destination = form.children[2],
    name = form.children[3];
  assert.deepEqual(
    destination.children.map((n) => n.value),
    ["default_regular", "custom_regular"],
  );
  destination.value = "custom_regular";
  name.value = "攻略常规";
  await form.onsubmit({ preventDefault() {} });
  assert.equal(submitted.path, "/special/copy-regular");
  assert.equal(submitted.body.libraryId, "custom_regular");
  assert.equal(context.category.value, "regular");
  assert.equal(context.selected, "regular");
  assert.equal(source.configuration.configurationType, "special");
  assert(notified.includes("点击加载配置"));
  assert.equal(popup.open, false);
  console.log(
    "PASS: conversion dialog chooses regular destination/name, selects independent result and does not load or overwrite current team",
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
