"use strict";
(() => {
  const E = (tag, text, cls) => {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  };
  const button = (text, fn) => {
    const b = E("button", text);
    b.type = "button";
    b.addEventListener("click", fn);
    return b;
  };
  const option = (value, text) => {
    const e = E("option", text);
    e.value = value;
    return e;
  };
  const http = ["http:", "https:"].includes(location.protocol),
    key = "dungeon2-skill-groups-v1";
  let groups = [],
    skills = [],
    equipment = [],
    id = "",
    changed = false,
    loading = false,
    libraryReady = false;
  const dialog = E("dialog", undefined, "group-dialog");
  dialog.id = "skill-group-dialog";
  document.body.append(dialog);
  const head = E("div", undefined, "dialog-head");
  head.append(
    E("h2", "技能组"),
    button("×", () => close()),
  );
  dialog.append(head);
  const form = E("form");
  dialog.append(form);
  const libraryBar = E("div", undefined, "group-library-bar"),
    saved = E("select");
  saved.setAttribute("aria-label", "已保存的技能组");
  libraryBar.append(
    E("span", "技能组列表"),
    saved,
    button("＋ 创建技能组", () => {
      if (!discard()) return;
      if (!filterJob.value) {
        status.textContent = "请先在顶部选择细分职业，再创建技能组";
        return;
      }
      const selected = groups.find((g) => g.id === saved.value);
      const g = selected ? structuredClone(selected) : blank();
      g.id = "";
      if (!selected) g.job = filterJob.value;
      load(g);
      saved.value = "";
      if (selected) {
        status.textContent = "已复制所选技能组，请更换一个未使用的名称后保存。";
        changed = true;
      }
    }),
  );
  form.append(libraryBar);
  const filters = E("div", undefined, "group-library-filters"),
    filterFamily = E("select"),
    filterJob = E("select");
  filterFamily.setAttribute("aria-label", "筛选技能组职业大类");
  filterJob.setAttribute("aria-label", "筛选技能组转职");
  filterFamily.append(option("", "全部职业"));
  SkillModel.professions.forEach((p) => filterFamily.append(option(p.name, p.name)));
  filterFamily.value = "";
  filters.append(field("职业", filterFamily), field("转职", filterJob));
  form.prepend(filters);
  function updateFilterJobs() {
    filterJob.replaceChildren(option("", "全部转职"));
    const p = SkillModel.professions.find((p) => p.name === filterFamily.value);
    (p ? p.jobs : SkillModel.professions.flatMap((p) => p.jobs)).forEach((j) =>
      filterJob.append(option(j, j)),
    );
    filterJob.value = "";
  }
  updateFilterJobs();
  filterFamily.addEventListener("change", () => {
    if (!discard()) {
      filterFamily.value = SkillModel.findProfession(draft.job)?.name || "";
      return;
    }
    updateFilterJobs();
    hideEditor();
    renderLibrary();
  });
  filterJob.addEventListener("change", () => {
    if (!discard()) {
      filterJob.value = draft.job;
      return;
    }
    hideEditor();
    renderLibrary();
  });
  function field(label, control) {
    const row = E("label", undefined, "field");
    row.append(E("span", label), control);
    return row;
  }
  const top = E("div", undefined, "group-top"),
    family = E("select"),
    job = E("select"),
    name = E("input");
  name.type = "text";
  name.maxLength = 120;
  name.required = true;
  name.setAttribute("aria-label", "技能组名称");
  family.append(option("", "请选择职业"));
  SkillModel.professions.forEach((p) => family.append(option(p.name, p.name)));
  top.append(field("技能组名称", name));
  form.append(top);

  const scene = E("div", undefined, "group-scene-settings"),
    scope = E("select"),
    bossLibrary = E("select"),
    sceneBoss = E("select");
  scope.setAttribute("aria-label", "技能适用范围");
  scope.append(option("general", "通用"), option("boss", "特定场景"));
  scope.value = "general";
  bossLibrary.setAttribute("aria-label", "适用Boss库");
  sceneBoss.setAttribute("aria-label", "适用Boss");
  const bossLibraryField = field("Boss库", bossLibrary),
    sceneBossField = field("适用Boss", sceneBoss);
  scene.append(field("技能适用范围", scope), bossLibraryField, sceneBossField);
  top.append(scene);
  let bossBanks = [],
    sceneItems = [],
    sceneLoaded = false,
    sceneLoading = null,
    stateControls = [];
  function renderScene() {
    const value = draft?.scope || { kind: "general" };
    scope.value = value.kind;
    bossLibraryField.hidden = sceneBossField.hidden = scope.value !== "boss";
    bossLibrary.replaceChildren(option("", "默认Boss库"));
    for (const bank of bossBanks) bossLibrary.append(option(bank.id, bank.name));
    if (value.libraryId && !bossBanks.some((b) => b.id === value.libraryId))
      bossLibrary.append(option(value.libraryId, value.libraryName || "已保存的Boss库"));
    bossLibrary.value = value.libraryId || "";
    sceneBoss.replaceChildren(option("", "请选择Boss"));
    for (const item of sceneItems.filter((b) => b.libraryId === bossLibrary.value))
      sceneBoss.append(option(item.id, item.name));
    if (
      value.bossId &&
      !sceneItems.some((b) => b.libraryId === bossLibrary.value && b.id === value.bossId)
    )
      sceneBoss.append(
        option(value.bossId, (value.bossName || "已保存的Boss") + "（请确认库中仍存在）"),
      );
    sceneBoss.value = value.bossId || "";
  }
  async function loadScenes() {
    if (sceneLoaded || !http) return;
    if (sceneLoading) return sceneLoading;
    sceneLoading = (async () => {
      const registry = await request("/api/library-sets/bosses");
      bossBanks = registry.libraries;
      const banks = [{ id: "", name: registry.displayNames?.[""] || "默认Boss库" }, ...bossBanks];
      const results = await Promise.all(
        banks.map((bank) =>
          request("/api/bosses" + (bank.id ? "?library=" + encodeURIComponent(bank.id) : "")),
        ),
      );
      sceneItems = results.flatMap((result, i) =>
        (result.bosses || []).map((item) => ({
          ...item,
          libraryId: banks[i].id,
          libraryName: banks[i].name,
        })),
      );
      sceneLoaded = true;
      renderScene();
      renderSubgroups();
    })().finally(() => (sceneLoading = null));
    return sceneLoading;
  }
  function captureScene() {
    draft.scope =
      scope.value === "boss"
        ? {
            kind: "boss",
            libraryId: bossLibrary.value,
            libraryName:
              [...bossLibrary.options].find((o) => o.value === bossLibrary.value)?.textContent ||
              "默认Boss库",
            bossId: sceneBoss.value,
            bossName:
              [...sceneBoss.options].find((o) => o.value === sceneBoss.value)?.textContent || "",
          }
        : { kind: "general" };
  }
  scope.addEventListener("change", async () => {
    capture();
    renderScene();
    renderSubgroups();
    changed = true;
    if (scope.value === "boss")
      try {
        await loadScenes();
      } catch (e) {
        status.textContent = "Boss库读取失败：" + e.message;
      }
  });
  bossLibrary.addEventListener("change", () => {
    capture();
    draft.scope.bossId = "";
    draft.scope.bossName = "";
    for (const sub of draft.subgroups)
      for (const node of sub.skills)
        for (const c of node.decision?.cases || []) c.requiredDebuff = null;
    renderScene();
    renderSubgroups();
    changed = true;
  });
  sceneBoss.addEventListener("change", () => {
    capture();
    for (const sub of draft.subgroups)
      for (const node of sub.skills)
        for (const c of node.decision?.cases || []) c.requiredDebuff = null;
    renderSubgroups();
    changed = true;
  });
  function stateFields(box, caseItem, prefix) {
    const members = E("select");
    members.setAttribute("aria-label", prefix + "检查对象");
    members.append(option("all", "己方存活成员（含自身）"), option("others", "其他存活队友"));
    members.value = caseItem.includeSelf === false ? "others" : "all";
    box.append(field("检查对象", members));
    const negative = E("select"),
      positive = E("select");
    negative.setAttribute("aria-label", prefix + "指定负面");
    positive.setAttribute("aria-label", prefix + "指定增益");
    negative.append(option("", "不检查负面"));
    positive.append(option("", "不检查增益"));
    const selected = sceneItems.find(
      (b) => b.id === sceneBoss.value && b.libraryId === bossLibrary.value,
    );
    const labels = {
      burn: "灼烧",
      bleeding: "流血",
      plague: "瘟疫",
      slow: "减速",
      stun: "眩晕",
      weakness: "虚弱",
      fear: "恐惧",
      lifeLoss: "生命流逝",
      strengthDecay: "力量衰减",
      magicDecay: "魔力衰减",
      techniqueDecay: "技巧衰减",
      speedDecay: "速度衰减",
      armorDecay: "护甲衰减",
      resistanceDecay: "抗性衰减",
      regeneration: "回春",
      strength: "力量提升",
      magic: "魔力提升",
      technique: "技巧提升",
      speed: "速度提升",
      armor: "护甲提升",
      resistance: "抗性提升",
    };
    for (const skill of selected?.skillGroup?.skills || [])
      if (skill.effect?.kind === "debuff")
        negative.append(
          option(
            JSON.stringify({ type: skill.effect.type, skillId: skill.id, skillName: skill.name }),
            skill.name + " · " + (labels[skill.effect.type] || skill.effect.type),
          ),
        );
    for (const skill of skills.filter((s) => s.job === draft.job && s.effect?.kind === "buff"))
      positive.append(
        option(
          JSON.stringify({ type: skill.effect.type, skillId: skill.id, skillName: skill.name }),
          skill.name + " · " + (labels[skill.effect.type] || skill.effect.type),
        ),
      );
    for (const [select, value] of [
      [negative, caseItem.requiredDebuff],
      [positive, caseItem.absentBuff],
    ]) {
      const encoded = value
        ? JSON.stringify({ type: value.type, skillId: value.skillId, skillName: value.skillName })
        : "";
      if (encoded && ![...select.options].some((o) => o.value === encoded))
        select.append(option(encoded, value.skillName + "（原条件，请核对）"));
      select.value = encoded;
    }
    box.append(
      field("存在指定负面", negative),
      field("不存在指定增益", positive),
      E("p", "同一名成员同时满足以上条件；多人符合时选择当前血量最低者。", "group-status-hint"),
    );
    const delays = {};
    for (const [key, title] of [
      ["recognitionDelay", "状态识别延迟"],
      ["operationDelay", "操作耗时"],
    ]) {
      const input = E("input");
      input.type = "number";
      input.min = "0";
      input.max = "3600";
      input.step = "0.1";
      input.value = caseItem[key] ?? 0;
      input.setAttribute("aria-label", prefix + title);
      box.append(field(title + "（秒）", input));
      delays[key] = input;
    }
    box.append(
      E(
        "p",
        "识别延迟从指定负面首次施加时计时，可与CD重叠；操作耗时从CD转好且条件命中时开始，锁定目标，结束后才释放治疗并进入下一轮CD。目标死亡则取消本次操作。两项填0关闭。",
        "group-status-hint",
      ),
    );
    stateControls.push(() => {
      for (const [key, input] of Object.entries(delays)) caseItem[key] = Number(input.value);
      caseItem.includeSelf = members.value === "all";
      caseItem.requiredDebuff = negative.value ? JSON.parse(negative.value) : null;
      caseItem.absentBuff = positive.value ? JSON.parse(positive.value) : null;
    });
  }
  const columns = E("div", undefined, "group-columns");
  form.append(columns);
  let draft,
    skillControls = [],
    jumpControls = [],
    groupJumpControls = [],
    conditionControls = [],
    branchControls = [],
    releaseControls = [],
    decisionControls = [],
    waitControls = [],
    targetControls = [];
  const uid = (prefix) => prefix + "_" + crypto.randomUUID();
  function newSubgroup() {
    const nodeId = uid("node");
    return { id: uid("subgroup"), nextGroup: "", skills: [{ id: nodeId, skillId: "", next: "" }] };
  }
  const addGroup = button("＋ 添加子技能组", () => {
    capture();
    draft.subgroups.push(newSubgroup());
    renderSubgroups();
    changed = true;
  });
  form.append(addGroup);
  form.append(
    E(
      "p",
      "等待在当前CD结束后开始计时，期间不行动、不触发装备特效，结束后继续下一项。默认从子技能组1的技能1开始。技能不跳转时顺序执行下一技能；设置跳转时进入指定技能。需要装备特效时，仅本次技能触发指定装备特效才跳转，否则按原顺序继续。组末不跳转则结束此组的执行；设置组末跳转则进入目标组第一个技能，选择自身即可循环本组。最后一个技能的单独跳转优先于组末跳转。条件子技能组只有一个技能位置：每次行动依次判断if / else if，使用第一条满足条件的技能，否则使用else技能。",
      "group-help",
    ),
  );
  const status = E("p", undefined, "group-status");
  status.setAttribute("role", "status");
  form.append(status);
  const actions = E("div", undefined, "group-actions"),
    save = E("button", "保存", "primary");
  save.type = "submit";
  const deleteGroupButton = button("删除技能组", async () => {
    if (loading || !id) return;
    const selected = groups.find((g) => g.id === id);
    if (
      !confirm(
        "确认删除技能组“" + selected.name + "”？" + (changed ? "未保存的修改也会丢弃。" : ""),
      )
    )
      return;
    loading = true;
    deleteGroupButton.disabled = true;
    save.disabled = true;
    try {
      if (http) {
        const result = await request("/api/skill-groups/" + encodeURIComponent(id), "DELETE");
        groups = result.groups.map(migrate);
      } else {
        groups = groups.filter((g) => g.id !== id);
        localStorage.setItem(key, JSON.stringify({ schemaVersion: 2, groups }));
      }
      hideEditor();
      renderLibrary();
      window.showToast("技能组已删除");
    } catch (error) {
      status.textContent = "删除失败：" + error.message;
      window.showToast(status.textContent);
    } finally {
      loading = false;
      deleteGroupButton.disabled = !id;
      save.disabled = false;
    }
  });
  actions.append(
    save,
    deleteGroupButton,
    button("重置技能组", () => {
      if (confirm("清空当前技能顺序？")) {
        const g = blank();
        g.id = id;
        g.job = job.value;
        g.name = name.value;
        g.scope = structuredClone(draft.scope || { kind: "general" });
        load(g);
        changed = true;
      }
    }),
    button("取消", close),
  );
  form.append(actions);
  const editor = E("div", undefined, "group-edit-area");
  for (const node of [top, columns, addGroup, ...form.querySelectorAll(".group-help")])
    editor.append(node);
  form.append(editor);
  const scroll = E("div", undefined, "group-form-scroll");
  scroll.append(filters, libraryBar, editor);
  form.replaceChildren(scroll, status, actions);
  function hideEditor() {
    editor.hidden = true;
    actions.hidden = true;
    changed = false;
    id = "";
    deleteGroupButton.disabled = true;
    saved.value = "";
    status.textContent = "";
  }
  function blank() {
    const subgroup = newSubgroup();
    return {
      scope: { kind: "general" },
      schemaVersion: 2,
      id: "",
      name: "",
      job: "",
      entry: subgroup.skills[0].id,
      subgroups: [subgroup],
      selfBuff: [],
      opening: [],
    };
  }
  function migrate(g) {
    if (g.schemaVersion === 2) return upgradeBranches(structuredClone(g));
    const subgroups = [];
    for (const [i, loop] of g.loops.entries()) {
      if (!loop.skills.length) continue;
      subgroups.push({
        id: "legacy_group_" + i,
        skills: loop.skills.map((skillId, j) => ({
          id: "legacy_" + i + "_" + j,
          skillId,
          next:
            j + 1 < loop.skills.length
              ? "legacy_" + i + "_" + (j + 1)
              : "legacy_" + (loop.next === "loop2" ? 1 : 0) + "_0",
        })),
      });
    }
    return { ...g, schemaVersion: 2, subgroups, entry: "legacy_0_0" };
  }
  function upgradeBranches(g) {
    const originals = g.subgroups.map((sub) => ({ ...sub, skills: sub.skills.slice() }));
    const nodes = new Map(
      originals.flatMap((sub) =>
        sub.skills.map((node, i) => [
          node.id,
          {
            node,
            next:
              node.next ||
              sub.skills[i + 1]?.id ||
              originals.find((s) => s.id === sub.nextGroup)?.skills[0]?.id ||
              "",
          },
        ]),
      ),
    );
    for (const sub of g.subgroups) {
      const branch = sub.healthBranch;
      if (!branch) continue;
      const yes = nodes.get(branch.whenTrue),
        no = nodes.get(branch.whenFalse);
      if (!yes || !no) continue;
      if (
        yes.node.id !== no.node.id &&
        sub.skills.some((n) => n.id === yes.node.id) &&
        sub.skills.some((n) => n.id === no.node.id)
      ) {
        for (const n of sub.skills) {
          n.next = nodes.get(n.id).next;
          n.releaseCondition = {
            kind:
              n.id === yes.node.id ? "allyHealthBelow" : n.id === no.node.id ? "always" : "never",
            threshold: n.id === yes.node.id ? branch.threshold : 20,
          };
        }
        const a = sub.skills.find((n) => n.id === yes.node.id),
          b = sub.skills.find((n) => n.id === no.node.id);
        sub.skills = [a, b, ...sub.skills.filter((n) => n !== a && n !== b)];
        sub.conditionsEnabled = true;
        sub.healthBranch = null;
        continue;
      }
      const a = {
          ...structuredClone(yes.node),
          id: uid("node"),
          next: yes.next,
          releaseCondition: { kind: "allyHealthBelow", threshold: branch.threshold },
        },
        b = {
          ...structuredClone(no.node),
          id: uid("node"),
          next: no.next,
          releaseCondition: { kind: "always", threshold: 20 },
        };
      sub.skills.forEach((n) => (n.releaseCondition = { kind: "never", threshold: 20 }));
      sub.skills = [a, b, ...sub.skills];
      sub.conditionsEnabled = true;
      sub.healthBranch = null;
    }
    return g;
  }
  function makeDecision(g) {
    if (!g.conditionsEnabled) return;
    const first = g.skills[0];
    if (first.decision) return;
    const old = g.skills.slice(),
      fallback =
        old.find((n) => !n.releaseCondition || n.releaseCondition.kind === "always") ||
        old[old.length - 1];
    const cases = old
      .filter((n) => ["allyHealthBelow", "noAllyHealthBelow"].includes(n.releaseCondition?.kind))
      .map((n) => ({
        ...n.releaseCondition,
        skillId: n.skillId,
        targetSelection: n.targetSelection || "lowestHp",
      }));
    first.decision = {
      cases: cases.length
        ? cases
        : [{ kind: "allyHealthBelow", threshold: 20, skillId: old[0].skillId }],
      elseSkillId: fallback.skillId,
      elseTargetSelection: fallback.targetSelection || "lowestHp",
    };
    first.skillId = fallback.skillId;
    first.releaseCondition = null;
    const removed = new Set(old.slice(1).map((n) => n.id));
    g.skills = [first];
    for (const sub of draft.subgroups)
      for (const n of sub.skills) if (removed.has(n.next)) n.next = first.id;
    if (removed.has(first.next)) first.next = "";
  }
  function discard() {
    return editor.hidden || !changed || confirm("技能组有未保存的修改，是否放弃？");
  }
  function close() {
    if (discard()) dialog.close();
  }
  dialog.addEventListener("cancel", (e) => {
    if (!discard()) e.preventDefault();
  });
  function populateJobs(selected = "") {
    job.replaceChildren(option("", "请选择转职"));
    const p = SkillModel.professions.find((p) => p.name === family.value);
    p?.jobs.forEach((j) => job.append(option(j, j)));
    job.disabled = !p;
    job.value = selected;
  }
  function capture() {
    if (!draft) return;
    for (const saveState of stateControls) saveState();
    captureScene();
    for (const c of waitControls) c.save(Number(c.input.value));
    for (const c of targetControls) c.save(c.select.value);
    for (const { node, select } of skillControls) node.skillId = select.value;
    for (const c of decisionControls) {
      c.case.skillId = c.skill.value;
      if (c.kind) {
        c.case.kind = c.kind.value;
        c.case.threshold = Number(c.threshold.value);
      } else {
        c.node.decision.elseSkillId = c.skill.value;
        c.node.skillId = c.skill.value;
      }
    }
    for (const { node, select } of jumpControls) node.next = select.value;
    for (const { node, required, effect } of conditionControls) {
      node.jumpCondition =
        required.value === "yes" && effect.value ? JSON.parse(effect.value) : null;
    }
    for (const { group, select } of groupJumpControls) group.nextGroup = select.value;
    for (const { group, enabled } of branchControls) {
      group.conditionsEnabled = enabled.value === "yes";
      group.healthBranch = null;
    }
    for (const { node, kind, threshold } of releaseControls)
      node.releaseCondition = { kind: kind.value, threshold: Number(threshold.value) };
    draft.job = job.value;
    draft.name = name.value;
  }
  function targetField(parent, skillSelect, value, save, label, enabled = true, matched = false) {
    const select = E("select");
    select.setAttribute("aria-label", label + "释放对象");
    for (const [key, text] of [
      ["lowestHp", "当前血量最低"],
      ["highestHp", "当前血量最高"],
      ["lowestArmor", "当前护甲最低"],
      ["highestArmor", "当前护甲最高"],
      ["lowestResistance", "当前抗性最低"],
      ["highestResistance", "当前抗性最高"],
      ["random", "随机"],
    ])
      select.append(option(key, text));
    if (matched) select.append(option("matchedMember", "条件命中的成员"));
    select.value = value || "lowestHp";
    const row = field("释放对象", select);
    row.classList.add("group-target-selection");
    const update = () => {
      const skill = skills.find((s) => s.id === skillSelect.value);
      const applicable =
        enabled &&
        skill &&
        ((["physical", "magic"].includes(skill.damageType) &&
          (skill.targeting || "single") === "single") ||
          (matched && skill.damageType === "none" && skill.healingRecipient !== "allAllies"));
      select.disabled = !applicable;
      row.hidden = !enabled;
      select.title = matched
        ? "条件命中的成员：同一名成员满足全部条件，多人符合时选择当前血量最低者"
        : applicable
          ? "按释放时当前数值选择攻击目标"
          : "仅单体攻击技能可选择释放对象";
    };
    skillSelect.addEventListener("change", update);
    update();
    parent.append(row);
    targetControls.push({ select, save });
  }
  function waitField(parent, select, value, save, label, enabled = true) {
    const input = E("input");
    input.type = "number";
    input.min = "0.1";
    input.max = "3600";
    input.step = "any";
    input.value = value ?? 1;
    input.setAttribute("aria-label", label + "等待时间");
    const row = field("等待时间（秒）", input);
    const update = () => {
      row.hidden = !enabled || select.value !== "__wait__";
      input.disabled = row.hidden;
    };
    select.addEventListener("change", update);
    update();
    parent.append(row);
    waitControls.push({ select, input, save });
  }
  function renderSubgroups() {
    columns.replaceChildren();
    skillControls = [];
    jumpControls = [];
    groupJumpControls = [];
    conditionControls = [];
    branchControls = [];
    releaseControls = [];
    decisionControls = [];
    ((waitControls = []), (targetControls = []));
    stateControls = [];
    draft.subgroups.forEach(makeDecision);
    const available = [
        ...skills.filter((s) => s.job === job.value),
        { id: "__wait__", name: "等待", job: job.value, damageType: "wait" },
      ],
      targets = draft.subgroups.flatMap((g, i) =>
        g.skills.map((n, j) => ({ id: n.id, label: "子技能组" + (i + 1) + " · 技能" + (j + 1) })),
      );
    draft.subgroups.forEach((g, i) => {
      const panel = E("section", undefined, "group-column");
      const heading = E("div", undefined, "group-subheading");
      heading.append(E("h3", "子技能组" + (i + 1) + (i === 0 ? "（默认入口）" : "")));
      if (draft.subgroups.length > 1)
        heading.append(
          button("删除子技能组", () => {
            capture();
            removeGroup(g.id);
          }),
        );
      panel.append(heading);
      const branchBox = E("div", undefined, "group-health-branch"),
        enabled = E("select");
      enabled.setAttribute("aria-label", "子技能组" + (i + 1) + "子技能组类型");
      enabled.append(option("no", "普通子技能组"), option("yes", "条件子技能组"));
      enabled.value = g.conditionsEnabled ? "yes" : "no";
      enabled.classList.toggle("default-value", enabled.value === "no");
      enabled.addEventListener("change", () => {
        capture();
        if (enabled.value === "yes") makeDecision(g);
        else delete g.skills[0].decision;
        renderSubgroups();
        changed = true;
      });
      branchBox.append(field("子技能组类型", enabled));
      if (g.conditionsEnabled)
        branchBox.append(
          E(
            "p",
            "只有技能1一个位置，可添加多个if / else if，最后由else兜底。血量条件检查其他队友；状态条件可包含自身。死亡或未参战成员不参与检查。",
          ),
        );
      branchControls.push({ group: g, enabled });
      panel.append(branchBox);

      g.skills.forEach((node, j) => {
        const row = E("div", undefined, "group-skill-row"),
          select = E("select"),
          jump = E("select");
        select.setAttribute("aria-label", "子技能组" + (i + 1) + "技能" + (j + 1));
        select.append(option("", "请选择技能"));
        available.forEach((s) => select.append(option(s.id, s.name)));
        if (node.skillId && !available.some((s) => s.id === node.skillId)) {
          const missing = option(node.skillId, "原技能不可用，请重新选择");
          missing.disabled = true;
          select.append(missing);
        }
        select.value = node.skillId;
        select.disabled = !job.value;
        skillControls.push({ node, select });
        waitField(
          row,
          select,
          node.waitDuration,
          (v) => (node.waitDuration = v),
          "子技能组" + (i + 1) + "技能" + (j + 1),
          !g.conditionsEnabled,
        );
        jump.setAttribute("aria-label", "子技能组" + (i + 1) + "技能" + (j + 1) + "跳转到");
        jump.append(option("", "不跳转"));
        targets.forEach((t) => jump.append(option(t.id, t.label)));
        jump.value = node.next;
        styleJump(jump);
        jumpControls.push({ node, select: jump });
        const required = E("select"),
          effect = E("select"),
          conditionBox = E("div", undefined, "group-proc-condition");
        required.setAttribute("aria-label", "是否需要触发装备特效");
        required.append(option("no", "否"), option("yes", "是"));
        required.value = node.jumpCondition ? "yes" : "no";
        effect.setAttribute("aria-label", "选择装备特效");
        function populateEffects(value = "", preserveMissing = false) {
          if (value) {
            const c = JSON.parse(value),
              name = c.equipmentName || equipment.find((e) => e.id === c.equipmentId)?.name;
            if (name)
              value = JSON.stringify({
                equipmentName: name,
                effectIndex: c.effectIndex,
                effectName: c.effectName || "",
              });
          }
          effect.replaceChildren(option("", "请选择装备特效"));
          const selectedIds = node.decision
            ? [node.decision.elseSkillId, ...node.decision.cases.map((c) => c.skillId)]
            : [select.value];
          const selectedSkills = available.filter((s) => selectedIds.includes(s.id)),
            skill = selectedSkills[0];
          equipment.forEach((item) => {
            if (item.triggerEnabled)
              (item.triggerEffects || []).forEach((r, index) => {
                if (r.effect && skill && selectedSkills.some((s) => r.triggerType === s.damageType))
                  effect.append(
                    option(
                      JSON.stringify({
                        equipmentName: item.name,
                        effectIndex: index,
                        effectName: r.name || "",
                      }),
                      item.name + " · " + (r.name || "特效" + (index + 1)),
                    ),
                  );
              });
          });
          const valid = [...effect.options].some((o) => o.value === value);
          if (value && !valid && preserveMissing) {
            const missing = option(value, "原特效与技能类型不匹配或不可用，请重新选择");
            missing.disabled = true;
            effect.append(missing);
          }
          effect.value = valid || preserveMissing ? value : "";
          if (value && !valid && !preserveMissing)
            status.textContent = "技能类型已改变，原装备特效条件已清空，请重新选择。";
          effect.disabled = !skill;
        }
        populateEffects(node.jumpCondition ? JSON.stringify(node.jumpCondition) : "", true);
        select.addEventListener("change", () => {
          populateEffects(effect.value);
          node.jumpCondition = null;
        });
        const toggle = () => {
          effect.hidden = required.value !== "yes";
          required.classList.toggle("default-value", required.value === "no");
        };
        toggle();
        required.addEventListener("change", () => {
          if (required.value === "no") effect.value = "";
          toggle();
        });
        conditionControls.push({ node, required, effect });
        const effectField = field("装备特效", effect);
        targetField(
          conditionBox,
          select,
          node.targetSelection,
          (v) => (node.targetSelection = v),
          "子技能组" + (i + 1) + "技能" + (j + 1),
          !g.conditionsEnabled,
        );
        conditionBox.append(field("是否需要触发装备特效", required), effectField);
        effectField.hidden = required.value !== "yes";
        required.addEventListener("change", () => {
          effectField.hidden = required.value !== "yes";
        });
        const skillField = field("技能" + (j + 1), select);
        skillField.hidden = !!g.conditionsEnabled;
        row.append(skillField);
        if (g.conditionsEnabled) {
          const choices = E("div", undefined, "group-decision");
          choices.append(E("h4", "技能1"));
          const d = node.decision;
          function choice(caseItem, index, isElse = false) {
            const box = E("div", undefined, "group-decision-case"),
              skill = E("select");
            skill.setAttribute(
              "aria-label",
              "子技能组" + (i + 1) + (isElse ? "else技能" : "条件" + (index + 1) + "技能"),
            );
            skill.append(option("", "请选择技能"));
            available.forEach((s) => skill.append(option(s.id, s.name)));
            skill.value = isElse ? d.elseSkillId : caseItem.skillId;
            skill.disabled = !job.value;
            box.append(E("strong", isElse ? "else" : index === 0 ? "if" : "else if"));
            if (!isElse) {
              const kind = E("select"),
                threshold = E("input");
              kind.append(
                option("allyHealthBelow", "有其他队友血量低于"),
                option("noAllyHealthBelow", "没有其他队友血量低于"),
                option("memberStatus", "成员状态：存在负面 / 不存在增益"),
              );
              kind.value = caseItem.kind;
              threshold.type = "number";
              threshold.min = "0";
              threshold.max = "100";
              threshold.value = caseItem.threshold;
              threshold.setAttribute("aria-label", "条件" + (index + 1) + "血量阈值");
              const thresholdInput = E("div", undefined, "group-threshold-input");
              thresholdInput.append(threshold, E("span", "%"));
              const thresholdRow = field("血量", thresholdInput);
              thresholdRow.classList.add("group-health-threshold");
              thresholdRow.hidden = caseItem.kind === "memberStatus";
              box.append(field("条件", kind), thresholdRow);
              kind.setAttribute("aria-label", "子技能组" + (i + 1) + "条件" + (index + 1) + "类型");
              kind.addEventListener("change", () => {
                capture();
                if (kind.value === "memberStatus") caseItem.targetSelection = "matchedMember";
                else if (caseItem.targetSelection === "matchedMember")
                  caseItem.targetSelection = "lowestHp";
                renderSubgroups();
                changed = true;
              });
              if (caseItem.kind === "memberStatus")
                stateFields(box, caseItem, "子技能组" + (i + 1) + "条件" + (index + 1));
              decisionControls.push({ node, case: caseItem, kind, threshold, skill });
              if (d.cases.length > 1)
                box.append(
                  button("删除条件", () => {
                    capture();
                    d.cases.splice(index, 1);
                    renderSubgroups();
                    changed = true;
                  }),
                );
            } else decisionControls.push({ node, case: {}, skill });
            box.append(field("使用技能", skill));
            targetField(
              box,
              skill,
              isElse ? d.elseTargetSelection : caseItem.targetSelection,
              (v) => {
                if (isElse) d.elseTargetSelection = v;
                else caseItem.targetSelection = v;
              },
              "子技能组" + (i + 1) + (isElse ? "else技能" : "条件" + (index + 1) + "技能"),
              true,
              !isElse && caseItem.kind === "memberStatus",
            );
            waitField(
              box,
              skill,
              isElse ? d.elseWaitDuration : caseItem.waitDuration,
              (v) => {
                if (isElse) {
                  d.elseWaitDuration = v;
                  node.waitDuration = v;
                } else caseItem.waitDuration = v;
              },
              "子技能组" + (i + 1) + (isElse ? "else技能" : "条件" + (index + 1) + "技能"),
            );
            skill.addEventListener("change", () => {
              capture();
              populateEffects(effect.value);
            });
            choices.append(box);
          }
          d.cases.forEach((c, index) => choice(c, index));
          choices.append(
            button("＋ 添加else if", () => {
              capture();
              d.cases.push({ kind: "allyHealthBelow", threshold: 20, skillId: "" });
              renderSubgroups();
              changed = true;
            }),
          );
          choice(null, 0, true);
          row.append(choices);
        }
        const releaseBox = E("div", undefined, "group-release-condition"),
          kind = E("select"),
          threshold = E("input");
        kind.setAttribute("aria-label", "子技能组" + (i + 1) + "技能" + (j + 1) + "释放条件");
        for (const [value, label] of [
          ["always", "无条件"],
          ["allyHealthBelow", "有其他队友血量低于阈值"],
          ["noAllyHealthBelow", "没有其他队友血量低于阈值"],
          ["never", "不释放"],
        ])
          kind.append(option(value, label));
        kind.value = node.releaseCondition?.kind || "always";
        threshold.type = "number";
        threshold.min = "0";
        threshold.max = "100";
        threshold.step = "any";
        threshold.value = node.releaseCondition?.threshold ?? 20;
        threshold.setAttribute("aria-label", "子技能组" + (i + 1) + "技能" + (j + 1) + "血量阈值");
        const thresholdField = field("血量低于（%）", threshold);
        const releaseState = () => {
          const numeric = ["allyHealthBelow", "noAllyHealthBelow"].includes(kind.value);
          thresholdField.hidden = !numeric;
          threshold.disabled = !g.conditionsEnabled || !numeric;
        };
        releaseState();
        kind.addEventListener("change", releaseState);
        releaseBox.append(field("释放条件", kind), thresholdField);
        releaseBox.hidden = true;
        releaseControls.push({ node, kind, threshold });
        row.append(releaseBox, conditionBox, field("跳转到", jump));
        if (g.conditionsEnabled) row.classList.add("conditional");
        if (g.skills.length > 1)
          row.append(
            button("删除", () => {
              capture();
              removeNode(g.id, node.id);
            }),
          );
        panel.append(row);
      });
      if (!g.conditionsEnabled)
        panel.append(
          button("＋ 添加技能", () => {
            capture();
            const nodeId = uid("node");
            g.skills.push({ id: nodeId, skillId: "", next: "" });
            renderSubgroups();
            changed = true;
          }),
        );
      const groupJump = E("select");
      groupJump.setAttribute("aria-label", "子技能组" + (i + 1) + "结束后跳转到");
      groupJump.append(option("", "不跳转"));
      draft.subgroups.forEach((target, index) => {
        groupJump.append(
          option(target.id, "子技能组" + (index + 1) + (target.id === g.id ? "（自身）" : "")),
        );
      });
      groupJump.value = g.nextGroup || "";
      styleJump(groupJump);
      groupJumpControls.push({ group: g, select: groupJump });
      const footer = field("跳转到", groupJump);
      footer.classList.add("group-jump-footer");
      panel.append(footer);
      columns.append(panel);
    });
  }
  function styleJump(select) {
    const update = () => select.classList.toggle("default-value", !select.value);
    update();
    select.addEventListener("change", update);
  }
  function repairRemoved(ids) {
    for (const g of draft.subgroups) {
      if (g.healthBranch) {
        if (ids.has(g.healthBranch.whenTrue)) g.healthBranch.whenTrue = "";
        if (ids.has(g.healthBranch.whenFalse)) g.healthBranch.whenFalse = "";
      }
    }
    for (const g of draft.subgroups)
      for (const node of g.skills) if (ids.has(node.next)) node.next = "";
    draft.entry = draft.subgroups[0].skills[0].id;
    status.textContent = "已删除；指向被删除技能的跳转已清空，请重新选择。";
    renderSubgroups();
    changed = true;
  }
  function removeGroup(groupId) {
    if (!confirm("删除此子技能组？")) return;
    const group = draft.subgroups.find((g) => g.id === groupId);
    draft.subgroups = draft.subgroups.filter((g) => g.id !== groupId);
    draft.subgroups.forEach((g) => {
      if (g.nextGroup === groupId) g.nextGroup = "";
    });
    repairRemoved(new Set(group.skills.map((n) => n.id)));
  }
  function removeNode(groupId, nodeId) {
    const group = draft.subgroups.find((g) => g.id === groupId);
    group.skills = group.skills.filter((n) => n.id !== nodeId);
    repairRemoved(new Set([nodeId]));
  }
  function renderLibrary() {
    saved.replaceChildren(option("", "请选择已保存技能组"));
    groups
      .filter(
        (g) =>
          (!filterFamily.value || SkillModel.findProfession(g.job)?.name === filterFamily.value) &&
          (!filterJob.value || g.job === filterJob.value),
      )
      .forEach((g) =>
        saved.append(
          option(
            g.id,
            g.name +
              " · " +
              g.job +
              " · " +
              (g.scope?.kind === "boss" ? g.scope.bossName + "专用" : "通用"),
          ),
        ),
      );
    saved.value = [...saved.options].some((o) => o.value === id) ? id : "";
    if (libraryReady) window.onSkillGroupLibraryChange?.(groups);
  }
  function load(g) {
    editor.hidden = false;
    actions.hidden = false;
    draft = migrate(g);
    if (draft.job) {
      filterFamily.value = SkillModel.findProfession(draft.job)?.name || "";
      updateFilterJobs();
      filterJob.value = draft.job;
    }
    id = draft.id;
    deleteGroupButton.disabled = !id;
    name.value = draft.name;
    family.value = SkillModel.findProfession(draft.job)?.name || "";
    populateJobs(draft.job);
    renderScene();
    renderSubgroups();
    if (draft.scope?.kind === "boss") loadScenes().catch((e) => (status.textContent = e.message));
    saved.value = id;
    changed = false;
    status.textContent = "";
  }
  function collect() {
    capture();
    const g = structuredClone(draft);
    g.id = id || uid("group");
    g.name = name.value.trim();
    g.job = job.value;
    g.entry = g.subgroups[0].skills[0].id;
    if (g.scope?.kind === "boss" && !g.scope.bossId) throw Error("请选择特定场景的Boss");
    if (!g.name || !g.job) throw Error("请填写技能组名称并选择转职");
    if (groups.some((item) => item.id !== id && item.name.trim() === g.name))
      throw Error("技能组名称已存在，请更换名称");
    const available = new Set([
      "__wait__",
      ...skills.filter((s) => s.job === g.job).map((s) => s.id),
    ]);
    for (const c of waitControls)
      if (
        c.select.value === "__wait__" &&
        (!Number.isFinite(Number(c.input.value)) ||
          Number(c.input.value) < 0.1 ||
          Number(c.input.value) > 3600)
      )
        throw Error("等待时间应为0.1到3600秒");
    const nodeIds = new Set(g.subgroups.flatMap((s) => s.skills.map((n) => n.id)));
    for (const subgroup of g.subgroups)
      if (subgroup.conditionsEnabled)
        for (const node of subgroup.skills) {
          const c = node.releaseCondition;
          if (c && (!Number.isFinite(c.threshold) || c.threshold < 0 || c.threshold > 100))
            throw Error("请设置0到100之间的血量阈值");
        }
    for (const subgroup of g.subgroups)
      for (const node of subgroup.skills) {
        if (!available.has(node.skillId)) throw Error("请为每个技能位置选择有效技能");
        if (node.decision) {
          if (
            !node.decision.cases.length ||
            !available.has(node.decision.elseSkillId) ||
            node.decision.cases.some((c) => !available.has(c.skillId))
          )
            throw Error("请为每个if / else if和else选择有效技能");
          for (const c of node.decision.cases)
            if (c.kind === "memberStatus") {
              for (const key of ["recognitionDelay", "operationDelay"]) {
                const value = c[key] ?? 0;
                if (
                  !Number.isFinite(value) ||
                  value < 0 ||
                  value > 3600 ||
                  Math.abs(value * 10 - Math.round(value * 10)) > 1e-8
                )
                  throw Error("延迟时间请按0.1秒填写，范围0到3600秒");
              }
              if (c.recognitionDelay && !c.requiredDebuff)
                throw Error("状态识别延迟需要选择指定负面");
              if (c.operationDelay && c.targetSelection !== "matchedMember")
                throw Error("操作耗时需要对条件命中的成员释放单体回复技能");
              if (!c.requiredDebuff && !c.absentBuff) throw Error("请选择至少一个状态条件");
              if (c.requiredDebuff && g.scope?.kind !== "boss")
                throw Error("负面来源条件需要先选择特定场景和Boss");
              if (
                c.targetSelection === "matchedMember" &&
                (skills.find((s) => s.id === c.skillId)?.damageType !== "none" ||
                  skills.find((s) => s.id === c.skillId)?.healingRecipient === "allAllies")
              )
                throw Error("对条件命中的成员释放需要选择单体回复技能");
            }
          if (
            node.decision.cases.some(
              (c) => !Number.isFinite(c.threshold) || c.threshold < 0 || c.threshold > 100,
            )
          )
            throw Error("请设置0到100之间的血量阈值");
        }
        if (
          conditionControls.some(
            (c) => c.node.id === node.id && c.required.value === "yes" && !c.effect.value,
          )
        )
          throw Error("请选择跳转条件的装备特效");
        if (
          node.jumpCondition &&
          !equipment.some(
            (e) =>
              (node.jumpCondition.equipmentName
                ? e.name === node.jumpCondition.equipmentName
                : e.id === node.jumpCondition.equipmentId) &&
              e.triggerEnabled &&
              e.triggerEffects?.[node.jumpCondition.effectIndex]?.effect &&
              (node.decision
                ? [node.decision.elseSkillId, ...node.decision.cases.map((c) => c.skillId)]
                : [node.skillId]
              ).some(
                (id) =>
                  e.triggerEffects[node.jumpCondition.effectIndex].triggerType ===
                  skills.find((s) => s.id === id)?.damageType,
              ) &&
              (e.triggerEffects[node.jumpCondition.effectIndex].name || "") ===
                node.jumpCondition.effectName,
          )
        )
          throw Error("条件装备特效已变更，请重新选择");
        if (node.jumpCondition && !node.next) throw Error("请为装备特效条件选择跳转目标");
        if (node.next && !nodeIds.has(node.next)) throw Error("请为每个技能选择有效跳转目标");
      }
    return g;
  }
  async function request(path, method = "GET", body) {
    if (window.AppRequests) await window.AppRequests.ready;
    const response = await (window.AppRequests?.fetch || fetch)(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) throw Error(data.error || "接口失败");
    return data;
  }
  family.addEventListener("change", () => {
    capture();
    populateJobs();
    draft.subgroups.forEach((g) =>
      g.skills.forEach((n) => {
        n.skillId = "";
        if (n.decision) {
          n.decision.elseSkillId = "";
          n.decision.cases.forEach((c) => (c.skillId = ""));
        }
      }),
    );
    renderSubgroups();
    changed = true;
  });
  job.addEventListener("change", () => {
    capture();
    draft.subgroups.forEach((g) =>
      g.skills.forEach((n) => {
        n.skillId = "";
        if (n.decision) {
          n.decision.elseSkillId = "";
          n.decision.cases.forEach((c) => (c.skillId = ""));
        }
      }),
    );
    renderSubgroups();
    changed = true;
  });
  saved.addEventListener("change", () => {
    const selected = groups.find((g) => g.id === saved.value);
    if (selected && discard()) load(selected);
    else if (!saved.value && discard()) hideEditor();
    else saved.value = id;
  });
  const markEdited = (event) => {
    if (!editor.hidden && editor.contains(event.target)) changed = true;
  };
  form.addEventListener("input", markEdited);
  form.addEventListener("change", markEdited);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (loading || !form.reportValidity()) return;
    save.disabled = true;
    try {
      const g = collect();
      if (http) {
        const result = await request(
          id ? "/api/skill-groups/" + encodeURIComponent(id) : "/api/skill-groups",
          id ? "PUT" : "POST",
          g,
        );
        groups = result.groups;
        libraryReady = true;
      } else {
        groups = groups.filter((item) => item.id !== g.id).concat(g);
        localStorage.setItem(key, JSON.stringify({ schemaVersion: 2, groups }));
        libraryReady = true;
      }
      load(g);
      renderLibrary();
      status.textContent = "技能组已保存";
      window.showToast("技能组已保存");
    } catch (error) {
      status.textContent = error.message;
      window.showToast("保存失败：" + error.message);
    } finally {
      save.disabled = false;
    }
  });
  window.onSkillLibraryChange = (items) => {
    capture();
    skills = items;
    renderSubgroups();
  };
  document.querySelector("#open-skill-group-editor").addEventListener("click", async () => {
    dialog.showModal();
    if (http) {
      loading = true;
      save.disabled = true;
      try {
        capture();
        const [s, g, e] = await Promise.all([
          request("/api/skills"),
          request("/api/skill-groups"),
          request("/api/equipment"),
        ]);
        equipment = e.equipment;
        skills = s.skills;
        groups = g.groups.map(migrate);
        libraryReady = true;
        renderSubgroups();
        renderLibrary();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        loading = false;
        save.disabled = false;
      }
    }
  });
  load(blank());
  hideEditor();
  renderLibrary();
  (async () => {
    try {
      if (http) {
        const [s, g, e] = await Promise.all([
          request("/api/skills"),
          request("/api/skill-groups"),
          request("/api/equipment"),
        ]);
        equipment = e.equipment;
        skills = s.skills;
        groups = g.groups.map(migrate);
        libraryReady = true;
      } else {
        equipment = JSON.parse(
          localStorage.getItem("dungeon2-equipment-library-v1") || '{"equipment":[]}',
        ).equipment;
        skills = JSON.parse(
          localStorage.getItem("dungeon2-skill-library-v1") || '{"skills":[]}',
        ).skills;
        groups = JSON.parse(localStorage.getItem(key) || '{"groups":[]}').groups.map(migrate);
        libraryReady = true;
      }
      capture();
      renderSubgroups();
      renderLibrary();
    } catch (error) {
      status.textContent = "技能组库读取失败：" + error.message;
    }
  })();
})();
