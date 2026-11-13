const fs = require("fs"),
  vm = require("vm"),
  path = require("path"),
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
  setAttribute() {}
  addEventListener(type, fn) {
    this.handlers[type] = fn;
  }
}
(async () => {
  const requests = [],
    switches = [];
  const libraries = { equipment: [{ id: "gear-a", name: "装备库A" }], stones: [] };
  const context = {
    document: {
      body: new Node("body"),
      createElement: (tag) => new Node(tag),
      querySelector: () => ({ textContent: "" }),
    },
    window: { showToast() {} },
    fetch: async (url, options) => {
      requests.push([url, options.method]);
      const kind = url.split("/").pop();
      return {
        ok: true,
        json: async () => ({ libraries: libraries[kind].map((x) => ({ ...x })) }),
      };
    },
  };
  vm.createContext(context);
  vm.runInContext(
    fs.readFileSync(path.resolve(__dirname, "../frontend/js/ui/library-sets.js"), "utf8"),
    context,
  );
  const libs = context.window.PlayerLibraries;
  for (const kind of ["equipment", "stones"])
    libs.mount(new Node("div"), kind, "默认库", async () => switches.push(kind));
  await new Promise((resolve) => setTimeout(resolve, 0));
  const reset = () => {
    requests.length = 0;
    switches.length = 0;
  };

  // 加载已保存的配置：全部类别重新读取并校验。
  reset();
  await libs.restore({ equipment: "gear-a" });
  assert.equal(requests.length, 2);
  assert.deepEqual([...switches].sort(), ["equipment", "stones"]);
  assert.equal(libs.current.equipment, "gear-a");

  // 切换配置模式且所选库不变：不发任何请求，也不重新加载库内容。
  reset();
  await libs.restore({ equipment: "gear-a" }, { changedOnly: true });
  assert.equal(requests.length, 0);
  assert.equal(switches.length, 0);
  assert.equal(libs.pending, false);

  // 切换配置模式且只有装备库不同：只重新加载装备库。
  reset();
  await libs.restore({}, { changedOnly: true });
  assert.deepEqual(requests, [["/api/library-sets/equipment", "GET"]]);
  assert.deepEqual(switches, ["equipment"]);
  assert.equal(libs.current.equipment, "");

  const app = fs.readFileSync(path.resolve(__dirname, "../frontend/js/app.js"), "utf8");
  assert(app.includes("await apply(structuredClone(next), { changedLibrariesOnly: true });"));
  console.log(
    "PASS: configuration mode switch reloads only libraries whose selection changed; saved configurations still reload all",
  );
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
