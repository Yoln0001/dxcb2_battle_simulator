const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert"),
  path = require("path");
const strings = [],
  downloads = [],
  urls = [];
let revoked = false,
  fail = false;
const ctx = {
  scale() {},
  fillRect() {},
  strokeRect() {},
  fillText(value) {
    strings.push(value);
  },
};
const canvas = {
  getContext: () => ctx,
  toBlob(fn, type) {
    assert.equal(type, "image/png");
    fn(fail ? null : { type });
  },
};
const context = {
  document: {
    fonts: { ready: Promise.resolve() },
    body: { append() {} },
    createElement(tag) {
      if (tag === "canvas") return canvas;
      return {
        click() {
          downloads.push(this.download);
        },
        remove() {},
      };
    },
  },
  window: {},
  URL: {
    createObjectURL(blob) {
      urls.push(blob);
      return "blob:test";
    },
    revokeObjectURL(url) {
      assert.equal(url, "blob:test");
      revoked = true;
    },
  },
  setTimeout: (fn) => fn(),
  console,
};
vm.createContext(context);
vm.runInContext(
  fs.readFileSync(path.resolve(__dirname, "../frontend/js/battle/result-export.js"), "utf8"),
  context,
);
const data = {
  seed: 123,
  boss_attacks: true,
  total_battles: 1000,
  passed_battles: 123,
  pass_rate: 12.3,
  all_alive_rate: 45.6,
  all_alive_battles: 456,
  expected_damage: 10000000,
  characters: [1, 2, 3, 4].map((index) => ({
    index,
    survival_rate: 70,
    survived_battles: 700,
    job: "灵魂贤者",
    enabled: index !== 4,
    expected_damage: index * 1000000 + 0.67,
  })),
};
const config = {
  target: { selectedBoss: { name: "圣者的幻影" } },
  characters: [1, 2, 3, 4].map((i) => ({
    stats: {
      strength: 204.7,
      constitution: 3962.2,
      magic: 10753.4,
      armor: 518.75,
      technique: 6933.8,
      resistance: 582.125,
      speed: 1318.6,
      weaponPower: 1793.25,
      hitRate: 54.3456,
      physicalDamage: 27.0,
      magicDamage: 21.2,
      criticalMultiplier: 17.4,
    },
  })),
};
(async () => {
  await context.window.BatchResultExport.download(data, config);
  assert.equal(canvas.width, 3200);
  assert.equal(canvas.height, 1580);
  for (const label of [
    "力量",
    "体质",
    "魔力",
    "护甲",
    "技巧",
    "抗性",
    "速度",
    "武威",
    "命中率",
    "物理伤害",
    "魔法伤害",
    "暴击伤害系数",
  ])
    assert.equal(strings.filter((x) => x === label).length, 4, label);
  for (const value of [
    "54.3456%",
    "17.4%",
    "21.2%",
    "27%",
    "205",
    "3962",
    "10753",
    "6934",
    "1319",
    "519",
    "582",
    "1793",
    "1000001",
    "全员存活比例：45.6%",
    "通过率：12.3%",
    "战斗场次：1,000",
    "未参战",
  ])
    assert(strings.includes(value), value);
  assert(!strings.includes("1,000,001"));
  assert(strings.includes("10753"));
  assert(!strings.includes("10,753"));
  assert.equal(downloads[0], "战斗结果-1000场-123.png");
  assert(revoked);
  strings.length = 0;
  context.window.BatchResultExport.draw({ ...data, boss_attacks: false }, config);
  assert(strings.includes("全员存活比例：45.6%"));
  assert(strings.includes("存活率：70%"));
  assert(!strings.some((x) => x.includes("未统计")));
  fail = true;
  await assert.rejects(context.window.BatchResultExport.download(data, config), /生成 PNG 失败/);
  console.log(
    "PASS: four panels, exact requested attributes and statistics, PNG dimensions/download, ordinary simulation and export failure",
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
