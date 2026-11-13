const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert");
const source = fs.readFileSync("frontend/js/app.js", "utf8");
const code = source.slice(
  source.indexOf("let configurationLoading = false;"),
  source.indexOf("function getValid()"),
);
let release,
  fail = false,
  rendered = [],
  restored;
const nodes = { "#characters": { children: [] }, "#duration": {}, "#simulations": {} };
const context = {
  configurationType: "regular",
  modeDrafts: {},
  collect: () => ({}),
  normalize: structuredClone,
  $: (id) => nodes[id],
  document: { querySelectorAll: () => [] },
  toast: (m) => {
    context.message = m;
  },
  renderTarget: (t) => rendered.push(["target", t]),
  render: (c) => rendered.push(["characters", c]),
  syncConfigurationMode() {},
  refreshDefaultStyles() {},
  window: {
    PlayerLibraries: {
      restore: async (choices) => {
        restored = structuredClone(choices);
        await new Promise((r) => (release = r));
        if (fail) throw Error("库加载失败");
      },
    },
  },
};
vm.createContext(context);
vm.runInContext(code, context);
(async () => {
  const kinds = [
    "equipment",
    "stones",
    "people",
    "trophies",
    "bosses",
    "contracts",
    "rings",
    "holies",
    "imprints",
  ];
  for (const prefix of ["A", "B"]) {
    const librarySelections = Object.fromEntries(kinds.map((k) => [k, prefix + "-" + k]));
    const config = {
      configurationType: "special",
      librarySelections,
      target: { name: prefix },
      battle: { duration: 100, simulations: 10 },
      characters: [{ name: prefix }],
    };
    const loading = context.apply(config);
    assert.deepEqual(restored, librarySelections);
    assert.equal(rendered.length, 0);
    assert.equal(context.getForSave(), null);
    assert(context.message.includes("正在加载"));
    release();
    await loading;
    assert.equal(rendered[0][1].name, prefix);
    assert.equal(rendered[1][1][0].name, prefix);
    assert.equal(context.configurationType, "special");
    rendered = [];
  }
  fail = true;
  const loading = context.apply({
    configurationType: "special",
    librarySelections: { people: "missing" },
    battle: {},
    characters: [],
  });
  release();
  await assert.rejects(loading, /库加载失败/);
  assert.equal(rendered.length, 0);
  assert.notEqual(context.getForSave(), null);
  console.log(
    "PASS: loading configurations A/B restores all nine library choices before rendering; saving blocked during load; failed restore does not render mixed data",
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
