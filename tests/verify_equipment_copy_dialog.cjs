const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert");
class Element {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.listeners = {};
    this.value = "";
    this.textContent = "";
  }
  append(...items) {
    this.children.push(...items);
  }
  replaceChildren(...items) {
    this.children = items;
  }
  insertBefore(item, before) {
    this.children.splice(this.children.indexOf(before), 0, item);
  }
  setAttribute() {}
  addEventListener(name, fn) {
    this.listeners[name] = fn;
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
    this.listeners.close?.();
  }
  remove() {}
  focus() {}
  select() {}
}
const body = new Element("body"),
  context = { window: {}, document: { body, createElement: (tag) => new Element(tag) } };
vm.runInNewContext(fs.readFileSync("frontend/js/ui/library-sets.js", "utf8"), context);
(async () => {
  let saved;
  context.window.PlayerLibraries.nameDialog(
    "复制当前库",
    "",
    "说明",
    async (name, values) => {
      saved = { name, values };
    },
    true,
  );
  const dialog = body.children[0],
    form = dialog.children[0],
    name = form.children[2].children[0],
    fields = form.children[3],
    error = form.children[4];
  assert.equal(fields.children.length, 3);
  assert.equal(fields.children[0].children[0].min, "0");
  assert.equal(fields.children[0].children[0].max, "100");
  name.value = "副本";
  fields.children[0].children[0].value = "101";
  await form.listeners.submit({ preventDefault() {} });
  assert(!saved);
  assert(error.textContent.includes("0～100"));
  fields.children[0].children[0].value = "90";
  fields.children[1].children[0].value = "50";
  fields.children[2].children[0].value = "25";
  await form.listeners.submit({ preventDefault() {} });
  assert.equal(saved.name, "副本");
  assert.equal(saved.values.main, 90);
  assert.equal(saved.values.other, 50);
  assert.equal(saved.values.defense, 25);
  assert.equal(dialog.open, false);
  context.window.PlayerLibraries.nameDialog("新建库", "", "说明", async (name, values) => {
    saved = { name, values };
  });
  const normal = body.children[1].children[0];
  assert.equal(normal.children.length, 5);
  normal.children[2].children[0].value = "普通库";
  await normal.listeners.submit({ preventDefault() {} });
  assert.equal(saved.name, "普通库");
  context.window.showToast = () => {};
  context.document.querySelector = () => null;
  let switched = 0,
    submitted;
  context.fetch = async (url, opts) => ({
    ok: true,
    json: async () => {
      if (opts.method === "PUT") {
        submitted = JSON.parse(opts.body);
        return { libraries: [{ id: "existing", name: submitted.name }] };
      }
      return url.endsWith("/existing")
        ? { attributePercentages: { main: 80, other: 50, defense: 25 } }
        : { libraries: [{ id: "existing", name: "旧库" }] };
    },
  });
  const api = context.window.PlayerLibraries;
  api.current.equipment = "existing";
  const bar = api.mount(new Element("div"), "equipment", "默认库", async () => {
    switched++;
  });
  await new Promise(setImmediate);
  assert.equal(bar.children[3].textContent, "修改当前库属性");
  await bar.children[3].listeners.click();
  const editing = body.children.at(-1).children[0],
    editingFields = editing.children[3];
  assert.equal(editingFields.children[0].children[0].value, "80");
  assert.equal(editing.children.at(-1).children[1].textContent, "保存修改");
  editingFields.children[0].children[0].value = "90";
  await editing.listeners.submit({ preventDefault() {} });
  assert.equal(submitted.name, "旧库");
  assert.equal(submitted.attributePercentages.main, 90);
  assert.equal(submitted.attributePercentages.defense, 25);
  assert.equal(switched, 1);
  assert.equal(api.current.equipment, "existing");
  console.log(
    "PASS: edit current equipment library prefills three percentages and saves unchanged name with changed rolls, then refreshes selected library",
  );
  console.log(
    "PASS: equipment copy dialog validates and submits main/other percentages; ordinary name dialog remains compatible",
  );
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
