const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert"),
  path = require("path");
class Node {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.handlers = {};
    this.attributes = {};
    this.value = "";
  }
  append(...v) {
    this.children.push(...v);
  }
  replaceChildren(...v) {
    this.children = v;
  }
  setAttribute(k, v) {
    this.attributes[k] = v;
  }
  addEventListener(k, v) {
    this.handlers[k] = v;
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
  }
}
const body = new Node("body"),
  entry = new Node("button"),
  calls = [],
  timers = new Map();
let token = 0,
  revision = 0,
  time = 0,
  pending = null,
  mode = "manual",
  decisions = [];
function data() {
  return {
    id: "session",
    revision,
    time,
    step: 0.1,
    duration: 1,
    horizon: time,
    seed: 12,
    boss_attacks: true,
    total_damage: time * 100,
    finished: false,
    warnings: [],
    pending_character: pending,
    target_maximum_hp: 1000,
    decisions,
    snapshot: {
      target_current_hp: 1000 - time * 100,
      target_debuffs: [],
      characters: [
        {
          index: 1,
          enabled: true,
          alive: true,
          job: "寒霜法师",
          current_hp: 100,
          maximum_hp: 100,
          stats: { magic: 10 },
          buffs: [],
          regeneration_buffs: [],
          debuffs: [],
        },
      ],
    },
    characters: [
      {
        index: 1,
        mode,
        automatic_available: true,
        statuses: [],
        next_action_at: 0.1,
        skills: [
          { id: "s", name: "冰锥术", damage_type: "magic", cooldown: 0 },
          {
            id: "heal",
            name: "单体治疗",
            damage_type: "none",
            healing_recipient: "self",
            cooldown: 0,
          },
          {
            id: "group",
            name: "凝神静气",
            damage_type: "none",
            healing_recipient: "allAllies",
            cooldown: 3,
          },
        ],
      },
    ],
    events: pending ? [] : [{ type: "skill_released", character: 1, skill_name: "冰锥术" }],
  };
}
const context = {
  document: {
    body,
    createElement: (t) => new Node(t),
    querySelector: (q) => (q === "#open-tas" ? entry : null),
  },
  window: {
    getTeamConfiguration: () => ({ target: { hitPoint: 1000 } }),
    showToast: (message) => {
      throw Error(message);
    },
  },
  setTimeout: (fn) => {
    timers.set(++token, fn);
    return token;
  },
  clearTimeout: (id) => timers.delete(id),
  fetch: async (url, args) => {
    calls.push({ url, args });
    if (args.method === "DELETE") return { ok: true, json: async () => ({ closed: true }) };
    if (url === "/api/battle/tas") return { ok: true, json: async () => data() };
    const op = JSON.parse(args.body);
    assert.equal(op.revision, revision);
    revision++;
    if (op.kind === "step") {
      time = Number((time + 0.1).toFixed(1));
      pending = mode === "manual" ? 1 : null;
    }
    if (op.kind === "cast") {
      assert(["s", "heal", "group"].includes(op.skill_id));
      decisions.push({ time, character: 1, skill_id: "s" });
      pending = null;
    }
    if (op.kind === "mode") {
      mode = op.mode;
      if (mode === "auto") pending = null;
    }
    if (op.kind === "seek") {
      time = op.tick / 10;
      pending = null;
    }
    return { ok: true, json: async () => data() };
  },
  console,
};
vm.createContext(context);
vm.runInContext(
  fs.readFileSync(path.resolve(__dirname, "../frontend/js/battle/tas.js"), "utf8"),
  context,
);
const all = (n) => [n, ...n.children.flatMap(all)],
  find = (text) => all(body).find((n) => n.textContent === text),
  aria = (label) => all(body).find((n) => n.attributes["aria-label"] === label),
  flush = () => new Promise((resolve) => setImmediate(resolve));
(async () => {
  await entry.handlers.click();
  assert(all(body).find((n) => n.tag === "dialog").open);
  assert.equal(calls[0].url, "/api/battle/tas");
  find("▶ 播放").handlers.click();
  assert.equal(timers.size, 1);
  const fn = [...timers.values()][0];
  timers.clear();
  await fn();
  await flush();
  assert(find("▶ 播放").disabled);
  assert(!find("释放所选技能").disabled);
  assert.equal(timers.size, 0);
  const skill = aria("角色1释放技能"),
    target = aria("单体回复对象");
  assert(target.hidden);
  skill.value = "group";
  skill.handlers.change();
  assert(target.hidden && target.disabled);
  assert(find("群体回复：全体存活队友"));
  skill.value = "heal";
  skill.handlers.change();
  assert(!target.hidden && !target.disabled);
  target.value = "1";
  find("释放所选技能").handlers.click();
  await flush();
  assert.equal(JSON.parse(calls.at(-1).args.body).target_character, 1);
  assert(!find("▶ 播放").disabled);
  find("前进 0.1 秒").handlers.click();
  await flush();
  const groupSelect = aria("角色1释放技能");
  groupSelect.value = "group";
  groupSelect.handlers.change();
  aria("单体回复对象").value = "1";
  find("释放所选技能").handlers.click();
  await flush();
  assert.equal(JSON.parse(calls.at(-1).args.body).skill_id, "group");
  assert(!("target_character" in JSON.parse(calls.at(-1).args.body)));
  aria("角色1控制模式").value = "auto";
  aria("角色1控制模式").handlers.change();
  await flush();
  assert.equal(mode, "auto");
  find("前进 0.1 秒").handlers.click();
  await flush();
  assert.equal(time, 0.3);
  const range = aria("回溯已探索的战斗时间轴");
  range.value = "0";
  range.handlers.input();
  range.handlers.change();
  await flush();
  assert.equal(time, 0);
  aria("关闭 TAS 战斗").handlers.click();
  await flush();
  assert.equal(calls.at(-1).args.method, "DELETE");
  assert(!all(body).find((n) => n.tag === "dialog").open);
  console.log(
    "PASS: TAS UI entry, playback, cooldown pause, cast/target, automatic mode, stepping, scrub rewind and close",
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
