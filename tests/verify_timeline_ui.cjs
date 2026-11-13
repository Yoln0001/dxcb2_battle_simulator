const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert"),
  path = require("path");
const root = path.resolve(__dirname, ".."),
  nodes = [];
class Node {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.handlers = {};
    this.attributes = {};
    this.style = {};
    this.dataset = {};
    this.classes = new Set();
    this.classList = { toggle: (k, v) => (v ? this.classes.add(k) : this.classes.delete(k)) };
    nodes.push(this);
  }
  append(...nodes) {
    this.children.push(...nodes);
  }
  replaceChildren(...nodes) {
    this.children = nodes;
  }
  setAttribute(k, v) {
    this.attributes[k] = v;
  }
  addEventListener(k, fn) {
    this.handlers[k] = fn;
  }
  querySelectorAll(selector) {
    return this.children
      .flatMap((n) => [n, ...n.querySelectorAll("*")])
      .filter(
        (n) => selector === "*" || (n.className || "").split(" ").includes(selector.slice(1)),
      );
  }
  before(node) {
    body.children.splice(body.children.indexOf(this), 0, node);
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
  }
}
const bossButton = new Node("button"),
  button = new Node("button"),
  body = new Node("body");
let request;
const character = {
  index: 1,
  job: "寒霜法师",
  enabled: true,
  current_hp: 100,
  maximum_hp: 100,
  stats: { magic: 100, hitRate: 50 },
  buffs: [],
  debuffs: [],
};
const snap = (magic) => ({
  target_current_hp: 1000,
  characters: Array.from({ length: 4 }, (_, i) => ({
    ...character,
    index: i + 1,
    stats: { ...character.stats, magic },
    buffs:
      i === 0
        ? [
            {
              name: "测试增幅",
              source_character: 1,
              applied_at: 0,
              expires_at: 15,
              stacks: 1,
              attribute: "magic",
              amount: 10,
            },
          ]
        : [],
  })),
  target_debuffs: [],
});
const data = {
  seed: 1,
  total_damage: 100,
  duration: 20,
  end_reason: "duration",
  warnings: [],
  timeline: [
    { time: 0, events: [{ type: "battle_started" }], snapshot: snap(100) },
    {
      time: 1.5,
      events: [
        { type: "skill_released", character: 1, job: "寒霜法师", skill_name: "冰锥术" },
        {
          type: "equipment_triggered",
          character: 1,
          equipment_name: "世界树之杖",
          name: "霜寒增幅",
        },
        {
          type: "skill_damage",
          character: 1,
          skill_name: "冰锥术",
          damage: 100,
          damage_type: "magic",
        },
      ],
      snapshot: snap(110),
    },
    {
      time: 20,
      events: [
        { type: "dot_damage", character: 2, name: "DOT", damage: 50 },
        { type: "skill_released", character: 3, job: "法师", skill_name: "技能3" },
        { type: "equipment_triggered", character: 4, equipment_name: "装备4", name: "效果4" },
        { type: "boss_party_wipe" },
      ],
      snapshot: snap(120),
    },
  ],
};
const context = {
  document: {
    createElement: (t) => new Node(t),
    body,
    querySelector: (selector) =>
      selector === "#simulate-single"
        ? button
        : selector === "#simulate-single-boss"
          ? bossButton
          : null,
  },
  window: {
    getTeamConfiguration: () => ({
      target: { name: "测试Boss", hitPoint: 1000, armor: 20 },
      battle: { duration: 20 },
    }),
    showToast: () => {},
  },
  fetch: async (url, args) => {
    request = { url, args };
    return { ok: true, json: async () => data };
  },
  console,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(root + "/frontend/js/battle/timeline.js", "utf8"), context);
const text = (n) => [n.textContent || "", ...n.children.map(text)].join(" ");
(async () => {
  await button.handlers.click();
  assert.equal(request.url, "/api/battle/simulate-single");
  assert.equal(button.disabled, false);
  assert(nodes.find((n) => n.tag === "dialog").open);
  const list = nodes.find((n) => n.className === "simulation-timeline"),
    detail = nodes.find((n) => n.className === "simulation-detail");
  const dots = () => list.querySelectorAll(".simulation-event-dot"),
    findControl = (label) => nodes.find((n) => n.attributes["aria-label"] === label);
  const skillInputs = () => {
    const filter = findControl("筛选释放的技能");
    return (filter.children[1]?.children || [])
      .filter((n) => n.tag === "label")
      .map((n) => n.children[0]);
  };
  const skillNames = () => [
    "全部技能",
    ...skillInputs()
      .slice(1)
      .map((n) => n.value),
  ];
  const selectSkills = (...names) => {
    const checks = skillInputs();
    for (const input of checks.slice(1))
      input.checked = !names.length || names.includes(input.value);
    if (checks.length > 1) checks[1].handlers.change();
  };

  assert(skillInputs().every((input) => !input.checked));
  assert(dots().every((n) => !n.classes.has("skill-highlighted")));
  assert.equal(findControl("筛选释放的技能").children[0].textContent, "未选择技能");
  assert.equal(dots().length, 6);
  assert(
    dots().some((n) => n.className.includes("actor-1") && n.className.includes("action-event")),
  );
  assert(
    dots().some((n) => n.className.includes("actor-2") && !n.className.includes("action-event")),
  );
  assert(dots().some((n) => n.className.includes("actor-3")));
  assert(dots().some((n) => n.className.includes("actor-4")));
  assert(
    dots().some((n) => n.className.includes("actor-boss") && n.className.includes("action-event")),
  );
  const menu = nodes.findLast((n) => n.className === "simulation-role-menu");
  assert(menu.children.every((label) => label.children[0].checked));
  const pick = (...values) => {
    const checks = menu.children.map((label) => label.children[0]);
    for (const input of checks)
      if (input.value !== "all") input.checked = values.includes(input.value);
    checks[1].handlers.change();
  };
  pick("1", "boss");
  assert.equal(dots().length, 2);
  assert(
    dots().every((n) => n.className.includes("actor-1") || n.className.includes("actor-boss")),
  );
  const allCheck = menu.children[0].children[0];
  assert(allCheck.indeterminate);
  allCheck.checked = false;
  allCheck.handlers.change();
  assert.equal(dots().length, 0);
  assert(text(list).includes("没有相关战斗记录"));
  allCheck.checked = true;
  allCheck.handlers.change();
  assert.equal(dots().length, 6);
  pick("1", "boss");
  const eventsControl = findControl("筛选事件类型"),
    skillsControl = findControl("筛选释放的技能");
  eventsControl.value = "actions";
  eventsControl.handlers.change();
  assert.deepEqual(skillNames(), ["全部技能", "冰锥术", "定时全队全灭"]);
  assert.equal(dots().length, 2);
  selectSkills("冰锥术");
  assert.equal(dots().length, 2);
  assert.equal(dots().filter((n) => n.classes.has("skill-highlighted")).length, 1);
  assert(
    dots()
      .find((n) => n.classes.has("skill-highlighted"))
      .title.includes("冰锥术"),
  );
  allCheck.checked = true;
  allCheck.handlers.change();
  assert(skillInputs().every((input) => !input.checked));
  assert(dots().every((n) => !n.classes.has("skill-highlighted")));
  assert(skillNames().includes("技能3"));
  eventsControl.value = "all";
  eventsControl.handlers.change();
  const fullCount = dots().length;
  assert(skillInputs().length > 1);
  selectSkills("冰锥术", "定时全队全灭");
  assert.equal(dots().length, fullCount);
  assert.deepEqual(
    dots()
      .filter((n) => n.classes.has("skill-highlighted"))
      .map((n) => n.dataset.time),
    ["1.5", "20"],
  );
  assert(dots().some((n) => !n.classes.has("skill-highlighted")));
  eventsControl.value = "actions";
  eventsControl.handlers.change();
  assert.equal(dots().length, 3);
  assert.equal(dots().filter((n) => n.classes.has("skill-highlighted")).length, 2);
  eventsControl.value = "all";
  eventsControl.handlers.change();
  assert.equal(dots().length, fullCount);
  assert.equal(dots().filter((n) => n.classes.has("skill-highlighted")).length, 2);
  skillInputs()[0].checked = false;
  skillInputs()[0].handlers.change();
  assert.equal(dots().length, fullCount);
  assert(dots().every((n) => !n.classes.has("skill-highlighted")));
  selectSkills();
  const skill = dots().find((n) => n.title.includes("释放「冰锥术」"));
  skill.handlers.click();
  assert(text(detail).includes("110"));
  assert(text(detail).includes("世界树之杖"));
  assert(text(detail).includes("魔法伤害"));
  assert(text(detail).includes("13.5秒"));
  assert.equal(detail.querySelectorAll(".simulation-character").length, 1);
  assert(skill.classes.has("selected"));
  assert.equal(skill.attributes["aria-pressed"], "true");
  const bossDot = dots().find((n) => n.title.includes("全队死亡"));
  bossDot.handlers.click();
  assert(text(detail).includes("测试Boss"));
  assert.equal(detail.querySelectorAll(".simulation-character").length, 5);
  const selectRoles = (...values) => {
    const menu = nodes.findLast((n) => n.className === "simulation-role-menu");
    const checks = menu.children.map((label) => label.children[0]);
    for (const input of checks)
      if (input.value !== "all") input.checked = !values.length || values.includes(input.value);
    checks.find((input) => input.value !== "all").handlers.change();
  };
  const type = findControl("筛选事件类型");
  selectRoles("1");
  assert.equal(dots().length, 1);
  assert(dots().every((n) => n.className.includes("actor-1")));
  type.value = "actions";
  type.handlers.change();
  assert.equal(dots().length, 1);
  const skillFilter = findControl("筛选释放的技能"),
    skillWrap = nodes.find(
      (n) => n.className === "simulation-role-control" && n.children.includes(skillFilter),
    );
  assert.equal(skillWrap.hidden, false);
  assert.deepEqual(skillNames(), ["全部技能", "冰锥术"]);
  data.timeline.push({
    time: 3,
    events: [
      { type: "skill_released", character: 1, job: "寒霜法师", skill_name: "治疗术" },
      { type: "healing", character: 1, target_character: 2, skill_name: "治疗术", amount: 10 },
    ],
    snapshot: snap(115),
  });
  selectRoles("1");
  assert.deepEqual(skillNames(), ["全部技能", "冰锥术", "治疗术"]);
  selectSkills("治疗术");
  assert.equal(dots().length, 2);
  assert.equal(dots().filter((n) => n.classes.has("skill-highlighted")).length, 1);
  dots()
    .find((n) => n.title.includes("治疗术"))
    .handlers.click();
  assert(text(detail).includes("回复角色2"));
  selectSkills();
  assert.equal(dots().length, 2);
  selectRoles("2");
  assert(skillInputs().every((input) => !input.checked));
  assert(text(list).includes("没有相关战斗记录"));
  type.value = "all";
  type.handlers.change();
  assert.equal(skillWrap.hidden, false);
  data.timeline.pop();
  type.value = "actions";
  type.handlers.change();
  selectRoles("boss");
  assert.equal(dots().length, 1);
  assert(dots()[0].title.includes("全队死亡"));
  assert.equal(skillWrap.hidden, false);
  assert.deepEqual(skillNames(), ["全部技能", "定时全队全灭"]);
  data.timeline.push(
    {
      time: 4,
      events: [
        { type: "boss_skill_released", skill_name: "生命萃取" },
        {
          type: "boss_skill_damage",
          skill_name: "生命萃取",
          target_character: 1,
          damage: 120,
          damage_type: "magic",
        },
      ],
      snapshot: snap(110),
    },
    {
      time: 5,
      events: [{ type: "boss_skill_released", skill_name: "普通攻击" }],
      snapshot: snap(110),
    },
  );
  selectRoles("boss");
  assert.deepEqual(skillNames(), ["全部技能", "定时全队全灭", "生命萃取", "普通攻击"]);
  selectSkills("生命萃取");
  assert.equal(dots().length, 3);
  assert.equal(dots().filter((n) => n.classes.has("skill-highlighted")).length, 1);
  assert(
    dots()
      .find((n) => n.classes.has("skill-highlighted"))
      .title.includes("生命萃取"),
  );
  selectSkills("定时全队全灭");
  assert.equal(dots().length, 3);
  assert.equal(dots().filter((n) => n.classes.has("skill-highlighted")).length, 1);
  assert(
    dots()
      .find((n) => n.classes.has("skill-highlighted"))
      .title.includes("全队死亡"),
  );
  selectSkills("生命萃取", "普通攻击");
  assert.equal(dots().length, 3);
  assert.equal(dots().filter((n) => n.classes.has("skill-highlighted")).length, 2);
  assert(
    dots()
      .filter((n) => n.classes.has("skill-highlighted"))
      .every((n) => !n.title.includes("全队死亡")),
  );
  assert(skillInputs()[0].indeterminate);
  skillInputs()[0].checked = false;
  skillInputs()[0].handlers.change();
  assert.equal(dots().length, 3);
  assert(dots().every((n) => !n.classes.has("skill-highlighted")));
  skillInputs()[0].checked = true;
  skillInputs()[0].handlers.change();
  assert.equal(dots().length, 3);
  assert(skillInputs().every((input) => input.checked));
  data.timeline.pop();
  data.timeline.pop();
  selectRoles("2");
  assert(text(list).includes("没有相关战斗记录"));
  type.value = "all";
  type.handlers.change();
  assert.equal(dots().length, 1);
  dots()[0].handlers.click();
  assert.equal(detail.querySelectorAll(".simulation-character").length, 1);
  assert(text(detail).includes("角色2 ·"));
  selectRoles();
  const interval = findControl("时间轴刻度间隔（秒）"),
    spacing = findControl("时间轴刻度间距（像素）");
  assert.equal(interval.value, 10);
  assert.equal(spacing.value, 100);
  assert(list.querySelectorAll(".simulation-axis-row").some((n) => n.dataset.time === "10"));
  interval.value = 5;
  interval.handlers.change();
  assert(list.querySelectorAll(".simulation-axis-row").some((n) => n.dataset.time === "5"));
  const old = list.children[0].style.height;
  spacing.value = 200;
  spacing.handlers.change();
  assert(parseFloat(list.children[0].style.height) > parseFloat(old));
  data.timeline.push({
    time: 2,
    events: [
      {
        type: "buff_applied",
        source_character: 2,
        target_character: 1,
        name: "队友增幅",
        stacks: 1,
        attribute: "magic",
        amount: 10,
      },
    ],
    snapshot: snap(115),
  });
  await button.handlers.click();
  dots()
    .find((n) => n.title.includes("队友增幅"))
    .handlers.click();
  assert.equal(detail.querySelectorAll(".simulation-character").length, 2);
  data.timeline[0].events.unshift(
    {
      type: "starting_buff",
      source_character: 1,
      target_character: 1,
      equipment_name: "装备A",
      attribute: "magic",
      amount: 10,
    },
    {
      type: "starting_buff",
      source_character: 1,
      target_character: 2,
      equipment_name: "装备B",
      attribute: "magic",
      amount: 20,
    },
    {
      type: "starting_vulnerability",
      character: 1,
      equipment_name: "装备C",
      name: "魔法易伤",
      amount: 12,
    },
    { type: "starting_dot", character: 2, name: "开战DOT", damage: 50 },
  );
  data.timeline[1].events.push({
    type: "target_debuff_applied",
    character: 1,
    name: "灼烧",
    stacks: 1,
  });
  await button.handlers.click();
  const opening = dots().filter((n) => n.dataset.time === "0");
  assert.equal(opening.length, 3);
  opening.find((n) => n.title.includes("角色1")).handlers.click();
  assert(text(detail).includes("装备A"));
  assert(text(detail).includes("装备B"));
  assert(text(detail).includes("装备C"));
  assert.equal(detail.querySelectorAll(".simulation-character").length, 2);
  type.value = "actions";
  type.handlers.change();
  const merged = dots().find((n) => n.title.includes("冰锥术"));
  merged.handlers.click();
  assert(text(detail).includes("灼烧"));
  assert(text(detail).includes("世界树之杖"));
  assert(text(detail).includes("魔法伤害"));
  assert.equal(dots().filter((n) => n.dataset.time === "1.5").length, 1);
  selectRoles();
  type.value = "all";
  type.handlers.change();
  const mode = findControl("时间轴分布方式");
  assert.equal(mode.value, "events");
  mode.value = "time";
  mode.handlers.change();
  const positions = () =>
    Object.fromEntries(
      list
        .querySelectorAll(".simulation-axis-row")
        .map((row) => [row.dataset.time, parseFloat(row.style.top)]),
    );
  let pos = positions();
  assert.equal(pos["0"], 0);
  assert.equal(pos["1.5"], 60);
  assert.equal(pos["2"], 80);
  assert.equal(pos["5"], 200);
  assert.equal(pos["20"], 800);
  assert(pos["2"] - pos["1.5"] < pos["20"] - pos["2"]);
  assert.equal(dots().filter((n) => n.dataset.time === "1.5").length, 1);
  spacing.value = 100;
  spacing.handlers.change();
  pos = positions();
  assert.equal(pos["1.5"], 30);
  assert.equal(pos["20"], 400);
  dots()
    .find((n) => n.title.includes("冰锥术"))
    .handlers.click();
  assert(text(detail).includes("灼烧"));
  mode.value = "events";
  mode.handlers.change();
  assert.equal(list.children[0].dataset.distribution, "events");

  // Track repeated casts from one source, replacements, exact pre-action refs and snapshotted DOT.
  const tracked = (id, start, end, source = 2) => ({
    id,
    name: "凝神静气",
    source_character: source,
    applied_at: start,
    expires_at: end,
    stacks: 1,
    attribute: "technique",
    amount: 10,
  });
  const frame = (time, buffs, events) => {
    const snapshot = snap(100);
    snapshot.characters[0].buffs = buffs;
    return { time, snapshot, events };
  };
  const refs = (source) => [{ name: "凝神静气", source_character: source, target_character: 1 }];
  const action = (source) => ({
    type: "skill_released",
    character: 1,
    skill_name: "测试行动",
    active_buff_refs: source ? refs(source) : [],
  });
  data.duration = 30;
  data.timeline = [
    frame(0, [], [{ type: "battle_started" }]),
    frame(
      2,
      [tracked("a", 2, 8)],
      [
        {
          type: "buff_applied",
          buff_id: "a",
          name: "凝神静气",
          source_character: 2,
          target_character: 1,
          expires_at: 8,
        },
      ],
    ),
    frame(3, [tracked("a", 2, 8)], [action(2)]),
    frame(
      6,
      [tracked("other", 6, 9, 3)],
      [
        {
          type: "buff_replaced",
          buff_id: "a",
          name: "凝神静气",
          source_character: 2,
          target_character: 1,
        },
        action(3),
      ],
    ),
    frame(10, [tracked("b", 10, 20)], [action(0)]),
    frame(11, [tracked("b", 10, 20)], [action(2)]),
    frame(
      21,
      [],
      [{ type: "dot_damage", character: 1, name: "灼烧", damage: 10, active_buff_refs: refs(2) }],
    ),
    frame(25, [], [action(0)]),
  ];
  type.value = "all";
  selectRoles();
  mode.value = "time";
  await button.handlers.click();
  dots()
    .find((n) => n.dataset.time === "3")
    .handlers.click();
  detail.querySelectorAll(".simulation-buff-button")[0].handlers.click();
  const bands = () => list.querySelectorAll(".simulation-buff-coverage");
  assert.equal(bands().length, 2);
  assert(bands()[0].title.includes("2.0～6.0"));
  assert(bands()[1].title.includes("10.0～20.0"));
  assert.equal(parseFloat(bands()[0].style.top), 50);
  assert.equal(parseFloat(bands()[0].style.height), 80);
  assert.deepEqual(
    dots()
      .filter((n) => n.classes.has("buff-affected"))
      .map((n) => n.dataset.time),
    ["3", "11", "21"],
  );
  assert.equal(
    detail.querySelectorAll(".simulation-buff-button")[0].attributes["aria-pressed"],
    "true",
  );
  type.value = "actions";
  type.handlers.change();
  assert.equal(bands().length, 2);
  assert.deepEqual(
    dots()
      .filter((n) => n.classes.has("buff-affected"))
      .map((n) => n.dataset.time),
    ["3", "11"],
  );
  mode.value = "events";
  mode.handlers.change();
  assert.equal(bands().length, 2);
  assert(bands().every((n) => parseFloat(n.style.height) > 0));
  nodes.find((n) => n.textContent === "取消 buff 追踪").handlers.click();
  assert.equal(bands().length, 0);
  assert(dots().every((n) => !n.classes.has("buff-affected")));
  await bossButton.handlers.click();
  assert.equal(request.url, "/api/battle/simulate-single-with-boss");
  assert.equal(skillWrap.hidden, false);
  assert(skillInputs().every((input) => !input.checked));
  assert(dots().every((n) => !n.classes.has("skill-highlighted")));
  console.log(
    "PASS: independent Boss endpoint; vertical ticks, adjustable spacing, colored action/other dots, chronological events, actor/Boss and action filters, selected related-character/Boss snapshots",
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
