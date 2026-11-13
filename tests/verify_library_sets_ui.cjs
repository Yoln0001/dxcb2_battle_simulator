const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert");
class Node {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.handlers = {};
    this.value = "";
  }
  append(...nodes) {
    this.children.push(...nodes);
  }
  replaceChildren(...nodes) {
    this.children = nodes;
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
    this.handlers.close?.();
  }
  remove() {}
  focus() {}
  select() {}
  setAttribute() {}
  addEventListener(type, fn) {
    this.handlers[type] = fn;
  }
}
(async () => {
  let rows = [{ id: "player", name: "玩家库" }],
    answer = "新名字",
    approved = false,
    switches = 0;
  const requests = [];
  const context = {
    document: {
      body: new Node("body"),
      createElement: (tag) => new Node(tag),
      querySelector: () => ({ textContent: "" }),
    },
    window: { showToast() {} },
    prompt: () => answer,
    confirm: () => approved,
    fetch: async (url, options) => {
      requests.push([url, options.method]);
      if (options.method === "PUT") rows[0].name = JSON.parse(options.body).name;
      if (options.method === "DELETE") rows = [];
      return { ok: true, json: async () => ({ libraries: rows.map((x) => ({ ...x })) }) };
    },
  };
  vm.createContext(context);
  vm.runInContext(
    fs.readFileSync(
      require("path").resolve(__dirname, "../frontend/js/ui/library-sets.js"),
      "utf8",
    ),
    context,
  );
  const host = new Node("div"),
    api = context.window.PlayerLibraries;
  api.current.stones = "player";
  const bar = api.mount(host, "stones", "默认魔石库", async () => {
    switches++;
  });
  await new Promise(setImmediate);
  const [select, create, copy, rename, remove] = bar.children;
  assert.equal(select.tag, "select");
  assert.equal(rename.disabled, false);
  await rename.handlers.click();
  const dialog = context.document.body.children.at(-1),
    form = dialog.children[0],
    input = form.children[2].children[0];
  input.value = answer;
  await form.handlers.submit({ preventDefault() {} });
  assert.equal(select.children[1].textContent, "新名字");
  assert.equal(api.current.stones, "player");
  await remove.handlers.click();
  assert.equal(rows.length, 1);
  assert(!requests.some((r) => r[1] === "DELETE"));
  approved = true;
  await remove.handlers.click();
  assert.equal(api.current.stones, "");
  assert.equal(select.value, "");
  assert.equal(switches, 1);
  assert(!rename.disabled && remove.disabled);
  api.current.stones = "deleted";
  const before = switches;
  await assert.rejects(api.restore({ stones: "deleted" }), /不存在/);
  assert.equal(api.current.stones, "deleted");
  assert.equal(switches, before);
  assert.equal(api.pending, false);
  console.log(
    "PASS: leftmost picker, rename, delete confirmation, fallback and missing saved-library recovery",
  );
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
