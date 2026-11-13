"use strict";
(() => {
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const format = (n) => Number(n ?? 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  const labels = {
    armor: "护甲",
    resistance: "抗性",
    dodgeRate: "闪避率",
    dodge: "闪避",
    load: "负重",
    physicalBlock: "物理格挡",
    magicBlock: "魔法格挡",
    weaponPower: "武威",
    strength: "力量",
    magic: "魔力",
    technique: "技巧",
    speed: "速度",
    constitution: "体质",
    hitPoint: "当前生命值",
    criticalRate: "暴击率",
    hitRate: "命中率",
    ignoreArmor: "无视护甲",
    ignoreResistance: "无视抗性",
    abnormalBonus: "异常附加率",
    physicalDamage: "物理伤害",
    magicDamage: "魔法伤害",
    dotDamage: "持续伤害",
    finalPhysicalDamage: "辉印物伤",
    finalMagicDamage: "辉印魔伤",
    finalDotDamage: "辉印持伤",
    unload: "卸负",
    criticalMultiplier: "暴伤系数增加",
    healingBonus: "回复效果",
    finalHealingBonus: "辉印回复",
    physicalSingleLifesteal: "物理单体吸血",
    magicSingleLifesteal: "魔法单体吸血",
    physicalAreaLifesteal: "物理群体吸血",
    magicAreaLifesteal: "魔法群体吸血",
  };
  const percents = new Set([
    "criticalRate",
    "hitRate",
    "abnormalBonus",
    "physicalDamage",
    "magicDamage",
    "dotDamage",
    "finalPhysicalDamage",
    "finalMagicDamage",
    "finalDotDamage",
    "criticalMultiplier",
    "healingBonus",
    "finalHealingBonus",
    "physicalSingleLifesteal",
    "magicSingleLifesteal",
    "physicalAreaLifesteal",
    "magicAreaLifesteal",
  ]);
  const damageTypes = { physical: "物理", magic: "魔法", dot: "持续", true: "真实" };
  const dialog = el("dialog", undefined, "simulation-dialog");
  const header = el("div", undefined, "dialog-head");
  const close = el("button", "×");
  close.type = "button";
  close.setAttribute("aria-label", "关闭战斗时间表");
  close.addEventListener("click", () => dialog.close());
  header.append(el("h2", "单次战斗时间表"), close);
  const summary = el("p", undefined, "simulation-summary"),
    warnings = el("div", undefined, "simulation-warnings"),
    layout = el("div", undefined, "simulation-layout");
  const list = el("div", undefined, "simulation-timeline"),
    detail = el("section", undefined, "simulation-detail");
  list.setAttribute("aria-label", "战斗时间点");
  detail.setAttribute("aria-live", "polite");
  layout.append(list, detail);
  dialog.append(header, summary, warnings, layout);
  document.body.append(dialog);
  const filterBar = el("div", undefined, "simulation-filter");
  const roleFilter = el("details", undefined, "simulation-role-filter"),
    eventFilter = el("select"),
    skillFilter = el("details", undefined, "simulation-role-filter simulation-skill-filter"),
    distribution = el("select"),
    tickInterval = el("input"),
    tickSpacing = el("input");
  roleFilter.setAttribute("aria-label", "筛选战斗角色");
  eventFilter.setAttribute("aria-label", "筛选事件类型");
  skillFilter.setAttribute("aria-label", "筛选释放的技能");
  for (const [value, text] of [
    ["all", "所有事件"],
    ["actions", "行动事件"],
  ]) {
    const option = el("option", text);
    option.value = value;
    eventFilter.append(option);
  }
  eventFilter.value = "all";
  distribution.setAttribute("aria-label", "时间轴分布方式");
  for (const [value, text] of [
    ["events", "按事件均匀分布"],
    ["time", "按时间间距分布"],
  ]) {
    const option = el("option", text);
    option.value = value;
    distribution.append(option);
  }
  distribution.value = "events";
  function control(label, input) {
    const wrap = el("label");
    wrap.append(el("span", label), input);
    filterBar.append(wrap);
    return wrap;
  }
  tickInterval.type = tickSpacing.type = "number";
  tickInterval.min = 1;
  tickInterval.max = 3600;
  tickInterval.step = 1;
  tickInterval.value = 10;
  tickInterval.setAttribute("aria-label", "时间轴刻度间隔（秒）");
  tickSpacing.min = 30;
  tickSpacing.max = 600;
  tickSpacing.step = 10;
  tickSpacing.value = 100;
  tickSpacing.setAttribute("aria-label", "时间轴刻度间距（像素）");
  const roleControl = el("div", undefined, "simulation-role-control");
  roleControl.append(el("span", "角色 / Boss"), roleFilter);
  filterBar.append(roleControl);
  control("事件", eventFilter);
  const skillControl = el("div", undefined, "simulation-role-control");
  skillControl.append(el("span", "技能"), skillFilter);
  filterBar.append(skillControl);
  skillControl.hidden = true;
  skillControl.style.display = "none";
  control("分布方式", distribution);
  control("刻度间隔（秒）", tickInterval);
  control("刻度间距（像素）", tickSpacing);
  layout.before(filterBar);
  const legend = el("div", undefined, "simulation-axis-legend");
  for (const [key, text] of [
    ["1", "角色1"],
    ["2", "角色2"],
    ["3", "角色3"],
    ["4", "角色4"],
    ["boss", "Boss"],
  ]) {
    const item = el("span");
    item.append(el("i", undefined, "axis-dot actor-" + key), el("span", text));
    legend.append(item);
  }
  legend.append(el("span", "大点：行动 · 小点：其他事件 · 同时刻从左到右按结算顺序排列"));
  layout.before(legend);
  const buffTracker = el("div", undefined, "simulation-buff-tracker"),
    buffTrackerText = el("span"),
    clearBuff = el("button", "取消 buff 追踪");
  clearBuff.type = "button";
  buffTracker.append(buffTrackerText, clearBuff);
  buffTracker.hidden = true;
  layout.before(buffTracker);
  let result,
    selectedTime,
    selectedEvent,
    selectedBuff,
    buffCoverage = [],
    battleTarget = {};
  clearBuff.addEventListener("click", () => {
    selectedBuff = null;
    buffTracker.hidden = true;
    renderTimeline();
  });
  const actionTypes = new Set([
    "skill_released",
    "boss_periodic_kill",
    "boss_party_wipe",
    "boss_skill_released",
    "boss_action",
    "enemy_skill_released",
  ]);
  function isAction(event) {
    return actionTypes.has(event.type);
  }
  function isBoss(event) {
    return (
      event.actor === "boss" || event.type.startsWith("boss_") || event.type.startsWith("enemy_")
    );
  }
  function eventActor(event) {
    if (isBoss(event)) return "boss";
    return String(
      event.character ||
        event.source_character ||
        event.owner_character ||
        event.target_character ||
        "boss",
    );
  }
  function related(event, index) {
    if (event.groupEvents) return event.groupEvents.some((e) => related(e, index));
    if (index === "boss") return isBoss(event);
    return ["character", "target_character", "source_character", "owner_character"].some(
      (key) => Number(event[key]) === Number(index),
    );
  }
  let selectedRoles = new Set(),
    roleChecks = [],
    allRolesCheck;
  const roleSummary = el("summary", "全部角色 / Boss");
  function updateRoles() {
    selectedRoles = new Set(
      roleChecks.filter((input) => input.checked).map((input) => input.value),
    );
    const all = selectedRoles.size === roleChecks.length;
    allRolesCheck.checked = all;
    allRolesCheck.indeterminate = selectedRoles.size > 0 && !all;
    roleSummary.textContent = all
      ? "全部角色 / Boss"
      : selectedRoles.size
        ? roleChecks
            .filter((input) => input.checked)
            .map((input) => (input.value === "boss" ? "Boss" : "角色" + input.value))
            .join("、")
        : "未选择角色 / Boss";
    refreshSkillFilter();
    renderTimeline();
  }
  function actionSkillName(event) {
    if (!isAction(event)) return "";
    return (
      event.skill_name ||
      event.name ||
      (event.type === "boss_periodic_kill"
        ? "定时击杀"
        : event.type === "boss_party_wipe"
          ? "定时全队全灭"
          : "")
    );
  }
  let selectedSkills = new Set(),
    skillChecks = [],
    allSkillsCheck;
  const skillSummary = el("summary", "未选择技能");
  function updateSkills() {
    selectedSkills = new Set(
      skillChecks.filter((input) => input.checked).map((input) => input.value),
    );
    const all = skillChecks.length > 0 && selectedSkills.size === skillChecks.length;
    allSkillsCheck.checked = all;
    allSkillsCheck.indeterminate = selectedSkills.size > 0 && !all;
    skillSummary.textContent = all
      ? "全部技能"
      : selectedSkills.size
        ? "已选 " + selectedSkills.size + " 项技能"
        : "未选择技能";
    skillSummary.title = [...selectedSkills].join("、");
    renderTimeline();
  }
  function refreshSkillFilter() {
    const active = !!result;
    skillControl.hidden = !active;
    skillControl.style.display = active ? "flex" : "none";
    skillFilter.replaceChildren();
    skillChecks = [];
    selectedSkills = new Set();
    skillSummary.textContent = "未选择技能";
    skillSummary.title = "";
    skillFilter.open = false;
    if (!active || !result) return;
    const names = new Set();
    for (const frame of result.timeline)
      for (const event of groupEvents(frame))
        if (selectedRoles.has(eventActor(event)) && actionSkillName(event))
          names.add(actionSkillName(event));
    const menu = el("div", undefined, "simulation-role-menu simulation-skill-menu");
    function skillOption(value, text) {
      const label = el("label"),
        input = el("input");
      input.type = "checkbox";
      input.value = value;
      input.checked = false;
      input.setAttribute("aria-label", text);
      label.append(input, el("span", text));
      menu.append(label);
      return input;
    }
    allSkillsCheck = skillOption("", "全选");
    allSkillsCheck.disabled = !names.size;
    allSkillsCheck.addEventListener("change", () => {
      for (const input of skillChecks) input.checked = allSkillsCheck.checked;
      updateSkills();
    });
    for (const name of names) {
      const input = skillOption(name, name);
      skillChecks.push(input);
      input.addEventListener("change", updateSkills);
    }
    if (!names.size) menu.append(el("p", "没有已释放的技能。", "muted"));
    skillFilter.append(skillSummary, menu);
  }
  for (const input of [eventFilter]) input.addEventListener("change", () => renderTimeline());
  for (const input of [distribution]) input.addEventListener("change", () => renderTimeline());
  for (const input of [tickInterval, tickSpacing])
    input.addEventListener("change", () => {
      if (Number(input.value) >= Number(input.min) && Number(input.value) <= Number(input.max))
        renderTimeline();
    });
  const openingTypes = new Set([
    "ring_equipped",
    "contract_negative",
    "starting_life_deprivation",
    "starting_regeneration",
    "starting_buff",
    "starting_vulnerability",
    "starting_dot",
    "starting_healing_reduction",
    "debuff_immune",
  ]);
  const actionEffectTypes = new Set([
    "equipment_triggered",
    "skill_damage",
    "equipment_damage",
    "skill_missed",
    "lifesteal",
    "healing",
    "regeneration_applied",
    "buff_applied",
    "buff_replaced",
    "target_debuff_applied",
    "debuff_failed",
    "debuff_immune",
    "wait_started",
    "enemy_healing",
    "enemy_lifesteal",
  ]);
  function groupEvents(frame) {
    const groups = [],
      byKey = new Map();
    let currentAction = null;
    for (const [index, event] of frame.events.entries()) {
      const actor =
        event.action_character ||
        event.character ||
        event.source_character ||
        event.owner_character ||
        event.target_character;
      let key,
        primary = event;
      if (frame.time === 0 && openingTypes.has(event.type) && actor) {
        key = "opening:" + actor;
        primary = { type: "equipment_start", character: actor };
      } else if (event.action_id) {
        key = "action:" + event.action_id;
      } else if (isAction(event)) {
        key = "action:" + index;
        currentAction = { key, actor: eventActor(event) };
      } else if (
        currentAction &&
        actionEffectTypes.has(event.type) &&
        eventActor(event) === currentAction.actor
      ) {
        key = currentAction.key;
      }
      if (!key) {
        groups.push({ ...event, groupKey: "event:" + index, groupEvents: [event] });
        if (!actionEffectTypes.has(event.type)) currentAction = null;
        continue;
      }
      let group = byKey.get(key);
      if (!group) {
        group = { ...primary, groupKey: key, groupEvents: [] };
        byKey.set(key, group);
        groups.push(group);
      }
      group.groupEvents.push(event);
      if (event.type === "skill_released") {
        Object.assign(group, event);
        currentAction = { key, actor: eventActor(event) };
      }
    }
    return groups;
  }
  function collectBuffCoverage() {
    const instances = new Map();
    const removals = new Map();
    for (const frame of result.timeline) {
      for (const e of frame.events) {
        if (e.buff_id && ["buff_replaced", "buff_expired"].includes(e.type))
          removals.set(e.buff_id, Math.min(removals.get(e.buff_id) ?? Infinity, frame.time));
        if (e.type === "buff_applied" && e.buff_id && !instances.has(e.buff_id))
          instances.set(e.buff_id, { ...e, id: e.buff_id, applied_at: frame.time });
      }
      for (const c of frame.snapshot.characters)
        for (const b of c.buffs) {
          const key =
            b.id || [b.name, b.source_character, c.index, b.applied_at, b.attribute].join("|");
          if (!instances.has(key)) instances.set(key, { ...b, target_character: c.index });
        }
    }
    const intervals = [];
    for (const [id, b] of instances) {
      if (b.name !== selectedBuff.name || Number(b.source_character) !== selectedBuff.source)
        continue;
      let end = Math.min(
        b.expires_at ?? result.duration,
        removals.get(id) ?? result.duration,
        result.duration,
      );
      for (const f of result.timeline)
        if (
          f.time >= b.applied_at &&
          f.events.some((e) => e.type === "character_died" && e.character === b.target_character)
        )
          end = Math.min(end, f.time);
      if (end > b.applied_at)
        intervals.push({ start: b.applied_at || 0, end, target: b.target_character });
    }
    intervals.sort((a, b) => a.target - b.target || a.start - b.start);
    const merged = [];
    for (const range of intervals) {
      const last = merged[merged.length - 1];
      if (last && last.target === range.target && range.start <= last.end + 1e-9)
        last.end = Math.max(last.end, range.end);
      else merged.push({ ...range });
    }
    return merged;
  }
  function buffAffected(event, frame) {
    if (!selectedBuff) return false;
    const records = event.groupEvents || [event];
    const precise = records.filter((e) => Array.isArray(e.active_buff_refs));
    if (precise.length)
      return precise.some((e) =>
        e.active_buff_refs.some(
          (b) => b.name === selectedBuff.name && Number(b.source_character) === selectedBuff.source,
        ),
      );
    const actor = Number(eventActor(event));
    if (!(actor >= 1 && actor <= 4)) return false;
    return buffCoverage.some(
      (r) => r.target === actor && frame.time > r.start && frame.time < r.end,
    );
  }
  function drawBuffCoverage(axis, ordered) {
    if (!selectedBuff) return;
    const pos = (time) => {
      if (distribution.value === "time")
        return (time / (Number(tickInterval.value) || 10)) * (Number(tickSpacing.value) || 100);
      const exact = ordered.find((r) => r.time === time);
      if (exact) return exact.top;
      const after = ordered.find((r) => r.time > time),
        before = [...ordered].reverse().find((r) => r.time < time);
      if (!before) return ordered[0].top;
      if (!after) return ordered[ordered.length - 1].top;
      return (
        before.top + ((after.top - before.top) * (time - before.time)) / (after.time - before.time)
      );
    };
    for (const range of buffCoverage) {
      const band = el("div", undefined, "simulation-buff-coverage actor-" + selectedBuff.source);
      band.style.top = pos(range.start) + 10 + "px";
      band.style.height = Math.max(2, pos(range.end) - pos(range.start)) + "px";
      band.style.left = 74 + (range.target - 1) * 4 + "px";
      band.title =
        "角色" +
        selectedBuff.source +
        "的「" +
        selectedBuff.name +
        "」→角色" +
        range.target +
        "：" +
        range.start.toFixed(1) +
        "～" +
        range.end.toFixed(1) +
        "秒";
      band.setAttribute("aria-label", band.title);
      axis.append(band);
    }
    buffTracker.hidden = false;
    buffTrackerText.textContent =
      "追踪：角色" +
      selectedBuff.source +
      "施加的「" +
      selectedBuff.name +
      "」 · " +
      buffCoverage.length +
      "个覆盖区间 · 高亮受影响事件";
  }
  function skillHighlighted(event) {
    return selectedRoles.has(eventActor(event)) && selectedSkills.has(actionSkillName(event));
  }
  function renderTimeline() {
    if (!result) return;
    list.replaceChildren();
    const allRoles = selectedRoles.size === roleChecks.length;
    const frames = result.timeline
      .map((frame) => ({
        ...frame,
        events: groupEvents(frame).filter(
          (event) =>
            selectedRoles.size > 0 &&
            (eventFilter.value === "actions"
              ? selectedRoles.has(eventActor(event))
              : allRoles || [...selectedRoles].some((role) => related(event, role))) &&
            (eventFilter.value !== "actions" || isAction(event)) &&
            eventText(event),
        ),
      }))
      .filter((frame) => frame.events.length)
      .sort((a, b) => a.time - b.time);
    if (!frames.length) {
      list.append(el("p", "没有相关战斗记录。", "muted"));
      detail.replaceChildren();
      return;
    }
    const interval = Number(tickInterval.value) || 10,
      spacing = Number(tickSpacing.value) || 100;
    const byTime = new Map();
    for (const frame of frames) {
      const prior = byTime.get(frame.time);
      if (prior) {
        prior.frame.events.push(...frame.events);
        prior.frame.snapshot = frame.snapshot;
      } else byTime.set(frame.time, { time: frame.time, frame });
    }
    for (let n = 0; n <= Math.floor(result.duration / interval); n++) {
      const time = Number((n * interval).toFixed(6));
      const row = byTime.get(time) || { time };
      row.tick = true;
      byTime.set(time, row);
    }
    if (!byTime.has(result.duration))
      byTime.set(result.duration, { time: result.duration, tick: true });
    const axis = el("div", undefined, "simulation-axis");
    list.append(axis);
    axis.dataset.distribution = distribution.value;
    let bottom = 0,
      lastLabel = -Infinity,
      maxLanes = 10;
    const laneEnds = [];
    const ordered = [...byTime.values()].sort((a, b) => a.time - b.time);
    for (const entry of ordered) {
      const row = el(
        "div",
        undefined,
        "simulation-axis-row" + (entry.tick ? " axis-major-tick" : ""),
      );
      row.dataset.time = String(entry.time);
      const timeMode = distribution.value === "time";
      let top = timeMode ? (entry.time / interval) * spacing : bottom;
      entry.top = top;
      row.style.top = top + "px";
      const label = el("span", entry.time.toFixed(1) + " 秒", "simulation-axis-time");
      if (
        timeMode &&
        !entry.tick &&
        (top - lastLabel < 20 ||
          (Math.min(entry.time % interval, interval - (entry.time % interval)) * spacing) /
            interval <
            20)
      ) {
        label.className += " axis-label-crowded";
      } else lastLabel = top;
      label.title = entry.time.toFixed(1) + " 秒";
      row.append(label, el("span", undefined, "simulation-axis-mark"));
      const dots = el("div", undefined, "simulation-axis-events");
      row.append(dots);
      if (entry.frame)
        entry.frame.events.forEach((event, index) => {
          const dot = el(
            "button",
            undefined,
            "simulation-event-dot actor-" +
              eventActor(event) +
              (isAction(event) ? " action-event" : ""),
          );
          dot.type = "button";
          dot.classList.toggle("skill-highlighted", skillHighlighted(event));
          if (selectedBuff) dot.classList.toggle("buff-affected", buffAffected(event, entry.frame));
          if (timeMode) {
            let lane = laneEnds.findIndex((end) => end <= top);
            if (lane < 0) lane = laneEnds.length;
            laneEnds[lane] = top + 24;
            dot.style.gridColumn = String(lane + 1);
            dot.style.gridRow = "1";
            maxLanes = Math.max(maxLanes, lane + 1);
          }
          dot.dataset.time = String(entry.time);
          dot.dataset.event = String(index);
          dot.title = entry.time.toFixed(1) + " 秒 · " + eventText(event);
          dot.setAttribute("aria-label", dot.title);
          dot.append(el("span", String(index + 1), "visually-hidden"));
          dot.addEventListener("click", () => {
            selectedTime = entry.time;
            selectedEvent = event;
            renderSnapshot(entry.frame, event);
          });
          dots.append(dot);
        });
      axis.append(row);
      bottom = timeMode
        ? Math.max(bottom, top + 32)
        : top +
          Math.max(24, Math.ceil((entry.frame?.events.length || 0) / 10) * 24) +
          Math.max(8, spacing / 4);
    }
    if (distribution.value === "time") {
      axis.style.minWidth = 100 + maxLanes * 22 + "px";
      for (const dots of axis.querySelectorAll(".simulation-axis-events"))
        dots.style.gridTemplateColumns = "repeat(" + maxLanes + ",22px)";
    }
    drawBuffCoverage(axis, ordered);
    axis.style.height = bottom + 12 + "px";
    const current = frames.find(
      (frame) =>
        frame.time === selectedTime &&
        frame.events.some((event) => event.groupKey === selectedEvent?.groupKey),
    );
    const frame = current || frames[0];
    selectedTime = frame.time;
    selectedEvent = current
      ? frame.events.find((event) => event.groupKey === selectedEvent.groupKey)
      : frame.events[0];
    renderSnapshot(frame, selectedEvent);
  }

  function eventText(event) {
    const actor = "角色" + event.character;
    switch (event.type) {
      case "equipment_start":
        return actor + "的开战装备效果（" + event.groupEvents.length + "条记录）。";
      case "character_died":
        return actor + "（" + event.job + "）死亡，无法复活。";
      case "contract_disabled":
        return actor + "死亡，契约「" + event.name + "」停止生效。";
      case "ring_equipped":
        return "角色" + event.character + "佩戴域之环「" + event.name + "」。";
      case "battle_started":
        return "战斗开始，加载开战增幅。";
      case "starting_life_deprivation":
        return (
          actor +
          "的「" +
          event.name +
          "」剥夺敌方当前生命值的 " +
          format(event.percentage) +
          "%，造成 " +
          format(event.damage) +
          " 点无属性伤害，剩余生命值 " +
          format(event.after) +
          "。"
        );
      case "starting_healing_reduction":
        return (
          actor +
          "给目标附加「" +
          event.name +
          "」：回复/吸血降低 " +
          format(event.amount) +
          "%，当前合计降低 " +
          format(event.combined_reduction) +
          "%，剩余 " +
          format(event.remaining_percent) +
          "%。"
        );
      case "enemy_healing":
      case "enemy_lifesteal":
        return (
          "敌方" +
          (event.type === "enemy_lifesteal" ? "吸血" : "回复") +
          "恢复 " +
          format(event.effective_amount) +
          " 点生命值。"
        );
      case "starting_dot":
        return (
          actor +
          "给目标附加「" +
          event.name +
          "」，每秒造成 " +
          format(event.damage) +
          " 点持续伤害" +
          (event.replaced ? "（覆盖原效果）" : "") +
          "。"
        );
      case "starting_vulnerability":
        return (
          actor +
          "的「" +
          event.equipment_name +
          "」给目标附加「" +
          event.name +
          "」" +
          format(event.amount) +
          "%" +
          (event.replaced ? "（覆盖原效果）" : "") +
          "。"
        );
      case "regeneration_applied":
        return (
          "角色" +
          event.target_character +
          "获得「" +
          event.name +
          "」回春，每秒回复 " +
          format(event.amount) +
          " 点生命值。"
        );
      case "contract_negative":
        return "角色" + event.target_character + "获得契约负面「" + event.name + "」。";
      case "starting_regeneration":
        return (
          "角色" +
          event.target_character +
          "获得「" +
          event.name +
          "」回春，每秒回复 " +
          format(event.amount) +
          " 点生命值。"
        );
      case "regeneration":
        return (
          "角色" +
          event.target_character +
          "的「" +
          event.name +
          "」回春回复 " +
          format(event.effective_amount) +
          " 点生命值。"
        );
      case "starting_buff":
        return (
          "角色" +
          event.target_character +
          "获得「" +
          (event.name || event.equipment_name) +
          "」开战增幅：" +
          (labels[event.attribute] || event.attribute) +
          "＋" +
          format(event.amount)
        );
      case "debuff_applied":
        return "角色" + event.target_character + "获得负面「" + event.name + "」。";
      case "boss_skill_released":
      case "enemy_skill_released":
      case "boss_action":
        return "Boss释放「" + (event.skill_name || event.name || "技能") + "」。";
      case "boss_skill_damage":
        return (
          "Boss「" +
          event.skill_name +
          "」对角色" +
          event.target_character +
          "造成 " +
          format(event.damage) +
          " 点" +
          (damageTypes[event.damage_type] || "") +
          "伤害。"
        );
      case "boss_dot_damage":
        return "角色" + event.target_character + "受到 " + format(event.damage) + " 点持续伤害。";
      case "boss_debuff_applied":
        return (
          "Boss给角色" +
          event.target_character +
          "附加「" +
          event.name +
          "」" +
          (event.stacks ? "（" + event.stacks + "层）" : "") +
          "，持续至 " +
          format(event.expires_at) +
          " 秒。"
        );
      case "boss_wait_started":
        return "Boss等待至 " + format(event.ends_at) + " 秒。";
      case "boss_periodic_kill":
        return (
          "Boss释放「定时击杀」：" +
          (event.target_characters || []).map((i) => "角色" + i).join("、") +
          "。"
        );
      case "boss_party_wipe":
        return "Boss释放「定时全队全灭」，我方全队死亡。";
      case "operation_started":
        return (
          actor +
          "开始为角色" +
          event.target_character +
          "操作「" +
          event.skill_name +
          "」，耗时 " +
          event.duration +
          " 秒，预计 " +
          format(event.ends_at) +
          " 秒释放。"
        );
      case "operation_finished":
        return actor + "对角色" + event.target_character + "的治疗操作完成。";
      case "operation_cancelled":
        return actor + "的治疗目标角色" + event.target_character + "已死亡，取消本次操作。";
      case "wait_started":
        return actor + "开始等待 " + event.duration + " 秒，至 " + event.ends_at + " 秒结束。";
      case "wait_finished":
        return actor + "等待结束。";
      case "skill_released":
        return actor + "（" + event.job + "）释放「" + event.skill_name + "」。";
      case "equipment_triggered":
        return actor + "触发「" + event.equipment_name + "」特效「" + event.name + "」。";
      case "skill_damage":
        return (
          actor +
          "的「" +
          event.skill_name +
          "」对目标造成 " +
          format(event.damage) +
          " " +
          damageTypes[event.damage_type] +
          "伤害" +
          (event.critical ? "（暴击）" : "") +
          "。"
        );
      case "equipment_damage":
        return (
          actor +
          "的装备特效「" +
          event.name +
          "」对目标造成 " +
          format(event.damage) +
          " " +
          damageTypes[event.damage_type] +
          "伤害。"
        );
      case "skill_missed":
        return actor + "的「" + event.skill_name + "」未命中。";
      case "lifesteal":
        return (
          actor + "的「" + event.skill_name + "」吸血回复自身 " + format(event.amount) + " 生命值。"
        );
      case "healing":
        return (
          actor +
          "的「" +
          event.skill_name +
          "」回复" +
          (event.target_character && event.target_character !== event.character
            ? "角色" + event.target_character
            : "自身") +
          " " +
          format(event.amount) +
          " 生命值。"
        );
      case "buff_applied":
        return (
          "角色" +
          event.target_character +
          "获得「" +
          event.name +
          "」" +
          event.stacks +
          "层：" +
          (labels[event.attribute] || event.attribute) +
          "＋" +
          format(event.amount) +
          "。"
        );
      case "buff_replaced":
        return "角色" + event.target_character + "的旧buff「" + event.name + "」被覆盖。";
      case "buff_expired":
        return (
          "角色" +
          event.target_character +
          "的「" +
          event.name +
          "」到期：" +
          (labels[event.attribute] || event.attribute) +
          "减少 " +
          format(-event.amount) +
          "。"
        );
      case "sacrifice_tick":
        return (
          "角色" + event.target_character + "因群体献祭损失 " + format(event.amount) + " 生命值。"
        );
      case "contract_dot_applied":
        return (
          "角色" + event.character + "的「" + event.name + "」触发，灼烧于1秒后跳伤害并覆盖原灼烧。"
        );
      case "contract_damage":
        return (
          "角色" +
          event.owner_character +
          "的「" +
          event.name +
          "」对目标造成 " +
          format(event.damage) +
          " 契约伤害。"
        );
      case "target_debuff_applied":
        return (
          actor +
          "给目标附加「" +
          event.name +
          "」" +
          event.stacks +
          "层" +
          (event.attribute
            ? "，" + (labels[event.attribute] || event.attribute) + "降低 " + format(event.amount)
            : "") +
          "。"
        );
      case "target_debuff_expired":
        return "目标的「" + event.name + "」到期。";
      case "dot_damage":
        return "目标的「" + event.name + "」造成 " + format(event.damage) + " 持续伤害。";
      case "debuff_failed":
        return actor + "的「" + event.name + "」未能附加负面效果。";
      case "debuff_immune":
        return "目标免疫" + event.debuff_name + "，未附加「" + event.name + "」。";
      default:
        return "";
    }
  }
  function renderSnapshot(frame, event) {
    detail.replaceChildren();
    detail.append(
      el("h3", frame.time.toFixed(1) + " 秒 · 结算后状态"),
      el(
        "p",
        "目标剩余生命值：" +
          (frame.snapshot.target_current_hp === null
            ? "未设置"
            : format(frame.snapshot.target_current_hp)),
      ),
    );
    detail.append(
      el(
        "p",
        eventText(event),
        "simulation-selected-event" + (skillHighlighted(event) ? " skill-highlighted-record" : ""),
      ),
    );
    const records = el("ol", undefined, "simulation-event-records");
    for (const child of event.groupEvents || [event]) {
      const text = eventText(child);
      if (text) records.append(el("li", text));
    }
    detail.append(records);
    const eventIndex = frame.events.indexOf(event);
    list.querySelectorAll(".simulation-event-dot").forEach((dot) => {
      const selected =
        Number(dot.dataset.time) === frame.time && Number(dot.dataset.event) === eventIndex;
      dot.classList.toggle("selected", selected);
      dot.setAttribute("aria-pressed", String(selected));
    });
    const relatedIndices = new Set(
      (event.groupEvents || [event])
        .flatMap((child) =>
          ["character", "source_character", "target_character", "owner_character"].map((k) =>
            Number(child[k]),
          ),
        )
        .filter((i) => i >= 1 && i <= 4),
    );
    if (event.type === "boss_periodic_kill")
      for (const index of event.target_characters || []) relatedIndices.add(index);
    if (event.type === "boss_party_wipe")
      for (const c of frame.snapshot.characters) if (c.enabled) relatedIndices.add(c.index);
    if (isBoss(event) || !relatedIndices.size) {
      const boss = el("article", undefined, "simulation-character simulation-boss");
      boss.append(
        el("h4", battleTarget.name || battleTarget.selectedBoss?.name || "Boss"),
        el(
          "p",
          "生命值 " +
            format(frame.snapshot.target_current_hp) +
            " / " +
            format(battleTarget.hitPoint),
        ),
      );
      const stats = el("dl", undefined, "simulation-stats");
      for (const [key, value] of Object.entries(
        frame.snapshot.boss_combat_stats ||
          frame.snapshot.target_attributes ||
          battleTarget.attributes ||
          {},
      )) {
        stats.append(
          el("dt", labels[key] || key),
          el("dd", format(value) + (percents.has(key) ? "%" : "")),
        );
      }
      for (const [key, label] of [
        ["armor", "护甲"],
        ["resistance", "抗性"],
        ["speed", "速度"],
        ["physicalReduction", "物理减伤 %"],
        ["magicReduction", "魔法减伤 %"],
        ["dotReduction", "持续减伤 %"],
        ["allyLifestealReduction", "吸血降低 %"],
        ["allyHealingReduction", "回复降低 %"],
        ["allyRegenerationReduction", "回春降低 %"],
      ])
        if (!(key in (battleTarget.attributes || {})) && battleTarget[key] !== undefined)
          stats.append(
            el("dt", label.replace(" %", "")),
            el("dd", format(battleTarget[key]) + (label.endsWith("%") ? "%" : "")),
          );
      boss.append(stats);
      detail.append(boss);
    }

    const cards = el("div", undefined, "simulation-characters");
    for (const c of frame.snapshot.characters.filter((c) => relatedIndices.has(c.index))) {
      const card = el("article", undefined, "simulation-character");
      card.append(
        el(
          "h4",
          "角色" +
            c.index +
            " · " +
            (c.job || "未选职业") +
            (!c.enabled ? "（未参战）" : c.alive === false ? "（已死亡）" : ""),
        ),
        el("p", "生命值 " + format(c.current_hp) + " / " + format(c.maximum_hp)),
      );
      const stats = el("dl", undefined, "simulation-stats");
      for (const [key, value] of Object.entries(c.stats)) {
        stats.append(
          el("dt", labels[key] || key),
          el("dd", format(value) + (percents.has(key) ? "%" : "")),
        );
      }
      card.append(stats);
      const immunityLabels = window.EquipmentModel?.immunityLabels || {};
      const immunityNames = Object.keys(c.negative_immunities || {})
        .filter((k) => c.negative_immunities[k])
        .map((k) => immunityLabels[k] || k);
      if (immunityNames.length) card.append(el("p", "免疫负面：" + immunityNames.join("、")));
      card.append(el("h5", "当前buff"));
      const groups = new Map();
      for (const buff of c.buffs) {
        const key = buff.name + "|" + buff.source_character + "|" + buff.applied_at;
        const values = groups.get(key) || [];
        values.push(buff);
        groups.set(key, values);
      }
      if (!groups.size) card.append(el("p", "无属性buff", "muted"));
      for (const buffs of groups.values()) {
        const buff = buffs[0],
          remaining =
            buff.expires_at === null
              ? "永久"
              : format(Math.max(0, buff.expires_at - frame.time)) + "秒";
        const buffButton = el(
          "button",
          buff.name +
            " · " +
            buff.stacks +
            "层 · 剩余" +
            remaining +
            "\n" +
            buffs
              .map((b) => (labels[b.attribute] || b.attribute) + "＋" + format(b.amount))
              .join("，"),
          "simulation-buff simulation-buff-button",
        );
        buffButton.type = "button";
        buffButton.title =
          "追踪整场战斗中角色" + buff.source_character + "施加的「" + buff.name + "」";
        buffButton.setAttribute(
          "aria-pressed",
          String(
            selectedBuff?.name === buff.name &&
              selectedBuff?.source === Number(buff.source_character),
          ),
        );
        buffButton.addEventListener("click", () => {
          selectedBuff = { name: buff.name, source: Number(buff.source_character) };
          buffCoverage = collectBuffCoverage();
          const scroll = list.scrollTop;
          renderTimeline();
          list.scrollTop = scroll;
        });
        card.append(buffButton);
      }
      for (const buff of c.regeneration_buffs || [])
        card.append(
          el(
            "p",
            buff.name + " · 回春 · 每秒回复 " + format(buff.amount) + " · 重伤后失效",
            "simulation-buff",
          ),
        );
      for (const debuff of c.debuffs)
        card.append(
          el(
            "p",
            debuff.name +
              " · 持续生效 · 下次扣血 " +
              format(Math.max(0, debuff.next_tick_at - frame.time)) +
              "秒后",
            "simulation-buff negative",
          ),
        );
      cards.append(card);
    }
    detail.append(cards);
    if (frame.snapshot.target_healing_reduction > 0)
      detail.append(
        el(
          "p",
          "敌方回复/吸血：合计降低 " +
            format(frame.snapshot.target_healing_reduction) +
            "%，剩余 " +
            format(frame.snapshot.target_recovery_multiplier * 100) +
            "%。",
        ),
      );
    if (frame.snapshot.target_debuffs.length) {
      detail.append(el("h4", "目标负面效果"));
      for (const buff of frame.snapshot.target_debuffs)
        detail.append(
          el(
            "p",
            (buff.effect_name ? buff.effect_name + " · " : "") +
              buff.name +
              (buff.damage !== undefined ? " 每秒 " + format(buff.damage) + " 点" : "") +
              (buff.amount !== undefined
                ? buff.attribute
                  ? " · " +
                    (labels[buff.attribute] || buff.attribute) +
                    "降低 " +
                    format(buff.amount)
                  : " " + format(buff.amount) + "%"
                : "") +
              " · " +
              buff.stacks +
              "层 · " +
              (buff.expires_at === null
                ? "持续整场"
                : "剩余" + format(Math.max(0, buff.expires_at - frame.time)) + "秒"),
          ),
        );
    }
  }
  function render(data) {
    result = data;
    selectedBuff = null;
    buffCoverage = [];
    buffTracker.hidden = true;
    summary.textContent =
      "累计伤害 " +
      format(data.total_damage) +
      " · 战斗 " +
      data.duration.toFixed(1) +
      " 秒 · 随机种子 " +
      data.seed +
      " · " +
      (data.end_reason === "target_defeated"
        ? "目标被击败"
        : data.end_reason === "party_defeated"
          ? "全队死亡"
          : "达到设置时长");
    warnings.replaceChildren();
    for (const warning of data.warnings) warnings.append(el("p", warning));
    warnings.hidden = !data.warnings.length;
    list.replaceChildren();
    const menu = el("div", undefined, "simulation-role-menu");
    roleChecks = [];
    selectedRoles = new Set();
    function roleOption(value, text) {
      const label = el("label"),
        input = el("input");
      input.type = "checkbox";
      input.value = value;
      input.checked = true;
      input.setAttribute("aria-label", text);
      label.append(input, el("span", text));
      menu.append(label);
      return input;
    }
    allRolesCheck = roleOption("all", "全选");
    allRolesCheck.addEventListener("change", () => {
      for (const input of roleChecks) input.checked = allRolesCheck.checked;
      updateRoles();
    });
    const characters = data.timeline[0]?.snapshot.characters || [];
    for (const c of characters)
      roleChecks.push(
        roleOption(String(c.index), "角色" + c.index + " · " + (c.job || "未选职业")),
      );
    roleChecks.push(roleOption("boss", "Boss"));
    for (const input of roleChecks) {
      selectedRoles.add(input.value);
      input.addEventListener("change", updateRoles);
    }
    roleSummary.textContent = "全部角色 / Boss";
    roleFilter.open = false;
    roleFilter.replaceChildren(roleSummary, menu);
    eventFilter.value = "all";
    selectedTime = undefined;
    selectedEvent = undefined;
    refreshSkillFilter();
    renderTimeline();
    dialog.showModal();
  }
  // 是否包含Boss攻击由后端按所选Boss有无技能组决定。
  const button = document.querySelector("#simulate-single");
  if (button) {
    const title = button.textContent;
    button.addEventListener("click", async () => {
      const config = window.getTeamConfiguration();
      if (!config) return;
      battleTarget = config.target || {};
      button.disabled = true;
      button.textContent = "模拟中…";
      try {
        const response = await (window.AppRequests?.fetch || fetch)("/api/battle/simulate-single", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(config),
        });
        const data = await response.json();
        if (!response.ok) throw Error(data.error || "单次模拟失败");
        render(data);
      } catch (error) {
        window.showToast(error.message);
      } finally {
        button.disabled = false;
        button.textContent = title;
      }
    });
  }
})();
