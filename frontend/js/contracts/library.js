"use strict";
(() => {
  const labels = {
      strength: "力量",
      magic: "魔力",
      technique: "技巧",
      speed: "速度",
      constitution: "体质",
    },
    rules = {
      狂怒兽神: [3.6, ["脆化", "污秽", "盲目", "痴愚"]],
      饮命者: [6.9, ["群体献祭", "群体盲目", "群体痴愚"]],
      旧日支配者: [7, ["群体献祭"]],
      炎钢羽神: [1.5, ["脆化", "污秽", "盲目", "痴愚"]],
      饮魂者: [2.5, ["群体献祭", "群体盲目", "群体痴愚"]],
    };
  const types = {
    狂怒兽神: "strength",
    饮命者: "strength",
    旧日支配者: "strength",
    炎钢羽神: "technique",
    饮魂者: "technique",
  };
  Object.assign(rules, {
    至高妖精: [2.3, ["脆化", "污秽", "盲目", "痴愚"]],
    "饮命者（魔力）": [3.4, ["群体献祭", "群体盲目", "群体痴愚"]],
    "旧日支配者（魔力）": [3.5, ["群体献祭"]],
    黑雾潜者: [1.3, ["脆化", "污秽", "盲目", "痴愚"]],
    "饮命者（速度）": [1.7, ["群体献祭", "群体盲目", "群体痴愚"]],
    "旧日支配者（速度）": [3.5, ["群体献祭"]],
  });
  Object.assign(types, {
    至高妖精: "magic",
    "饮命者（魔力）": "magic",
    "旧日支配者（魔力）": "magic",
    黑雾潜者: "speed",
    "饮命者（速度）": "speed",
    "旧日支配者（速度）": "speed",
  });
  for (const name of ["安详女神", "吸血伯爵", "月之宗主"]) {
    rules[name] = [0, ["群体脆化", "群体盲目", "群体污秽", "群体痴愚"]];
    types[name] = "constitution";
  }
  const normalize = (item) => {
    if (!item) return null;
    const result = { ...item, multiplier: item.multiplier * (item.level === 2 ? 1.2 : 1) };
    delete result.level;
    return result;
  };
  const activation = (item) =>
    item.archetype.replace(/（魔力）|（速度）/g, "") +
    ({ strength: "-力", magic: "-魔", technique: "-技", speed: "-速" }[item.category] || "");
  const E = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };
  const option = (value, text) => {
    const n = E("option", text);
    n.value = value;
    return n;
  };
  let library = [],
    editing = null,
    loaded = false;
  const useAPI = ["http:", "https:"].includes(location.protocol),
    key = "dungeon2-contract-library-v1";
  const defaults = () =>
    Object.entries(rules).map(([name, [multiplier, neg]], i) => ({
      id: types[name] + "_" + i,
      name,
      category: types[name],
      archetype: name,
      baseBonus: 12,
      multiplier,
      negativeEffect: neg[0],
    }));
  async function request(method = "GET", body, id = "") {
    if (window.AppRequests) await window.AppRequests.ready;
    const response = await (window.AppRequests?.fetch || fetch)(
      "/api/contracts" +
        (id ? "/" + encodeURIComponent(id) : "") +
        "?library=" +
        encodeURIComponent(window.PlayerLibraries?.current.contracts || ""),
      {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
      },
    );
    const data = await response.json();
    if (!response.ok) throw Error(data.error || "契约请求失败");
    return data;
  }
  function refreshRoles() {
    document.querySelectorAll(".character").forEach((card) => card.refreshContractOptions?.());
  }
  async function refresh() {
    library = useAPI
      ? (await request()).contracts
      : JSON.parse(localStorage.getItem(key) || JSON.stringify(defaults()));
    library = library.map(normalize);
    loaded = true;
    renderList();
    refreshRoles();
  }
  const dialog = E(
      "dialog",
      undefined,
      "configuration-dialog contract-library-dialog contract-editor-dialog",
    ),
    head = E("div", undefined, "dialog-head"),
    close = E("button", "×");
  close.type = "button";
  head.append(E("h2", "契约库"), close);
  dialog.append(head);
  document.body.append(dialog);
  close.onclick = () => dialog.close();
  const controls = E("div");
  dialog.append(controls);
  window.PlayerLibraries?.mount(controls, "contracts", "默认契约库", refresh);
  const workspace = E("div", undefined, "contract-library-workspace"),
    sidebar = E("aside"),
    content = E("form");
  workspace.append(sidebar, content);
  dialog.append(workspace);
  const add = E("button", "＋ 新增契约"),
    search = E("input"),
    filter = E("select"),
    list = E("div");
  add.type = "button";
  search.placeholder = "搜索契约名称";
  filter.append(
    option("", "全部类型"),
    ...Object.entries(labels).map(([k, v]) => option(k, v + "契约")),
  );
  sidebar.append(add, search, filter, list);
  const fields = {};
  function field(name, label, choices) {
    const row = E("label", undefined, "field");
    row.append(E("span", label));
    const input = E(choices ? "select" : "input");
    if (choices) input.append(...choices.map(([v, t]) => option(v, t)));
    else {
      input.type = name === "name" ? "text" : "number";
      input.step = "any";
      input.min = 0;
      input.required = true;
    }
    input.name = name;
    fields[name] = input;
    row.append(input);
    if (name === "baseBonus") row.append(E("span", "%", "field-unit"));
    content.append(row);
    return row;
  }
  content.append(E("h3", "契约设置"));
  field("name", "契约名称");
  field("category", "分类", Object.entries(labels));
  field("archetype", "种类", []);
  field("baseBonus", "基础属性加成");
  const multiplierRow = field("multiplier", "技能系数");
  field("negativeEffect", "负面效果", []);
  const explanation = E("p", undefined, "skill-help contract-description"),
    negativeHelp = E("p", undefined, "skill-help contract-description");
  content.append(explanation, negativeHelp);
  const footer = E("div", undefined, "contract-library-footer"),
    save = E("button", "保存契约", "primary"),
    duplicate = E("button", "另存为副本"),
    remove = E("button", "删除契约");
  save.type = "submit";
  duplicate.type = remove.type = "button";
  footer.append(save, duplicate, remove);
  content.append(footer);
  function archetypes(preferred = fields.archetype.value) {
    const names = Object.keys(types).filter((n) => types[n] === fields.category.value);
    fields.archetype.replaceChildren(...names.map((n) => option(n, n)));
    fields.archetype.value = names.includes(preferred) ? preferred : names[0] || "";
  }
  function negatives() {
    fields.negativeEffect.replaceChildren(
      ...rules[fields.archetype.value][1].map((n) => option(n, n)),
    );
  }
  function describe() {
    const n = fields.archetype.value,
      category = types[n],
      attr = labels[category];
    fields.category.value = category;
    multiplierRow.hidden = category === "constitution";
    const interval = { strength: 28, magic: 14, technique: 14, speed: 7 }[category];
    const team = n.startsWith("旧日支配者"),
      drinker = n.startsWith("饮命者") || n === "饮魂者";
    explanation.textContent =
      (category === "technique"
        ? "每14秒附加灼烧，施加1秒后首次造成技巧×系数的持续伤害，持续1秒并覆盖已有灼烧。"
        : "每" +
          interval +
          "秒" +
          (team ? "对敌方群体造成存活队伍" + attr + "总和" : "对敌方单体造成佩戴者" + attr) +
          "×系数的真实伤害。") +
      (drinker ? "敌方每损失25%生命，额外增加30%伤害。" : team ? "" : "首次伤害为4倍。") +
      " 所有契约从0.1秒开始计时。基础属性加成和实际技能系数均按填写数值生效。佩戴即有属性加成；激活后技能和所选负面生效，同队仅可激活一个。";
    if (category === "constitution")
      explanation.textContent =
        "佩戴即按填写比例增加体质，自动计入角色面板与战斗初始属性。当前仅接入佩戴属性加成，激活后的治疗、吸血、回春及减伤效果尚未接入。";
    const descriptions = {
      群体脆化: "友方全体受到物理、魔法、持续伤害增加20%。",
      群体污秽: "友方全体治疗、回春、吸血降低20%。",
      脆化: "受到物理、魔法、持续伤害增加30%。",
      污秽: "治疗、回春、吸血降低30%。",
      盲目: "命中率降低5%。",
      痴愚: "所有技能冷却增加0.3秒。",
      群体献祭: "友方全体每秒失去最大生命的5%。",
      群体盲目: "友方全体命中率降低3%。",
      群体痴愚: "友方全体技能冷却增加0.1秒。",
    };
    negativeHelp.textContent =
      "所选负面 · " +
      fields.negativeEffect.value +
      "：" +
      descriptions[fields.negativeEffect.value];
  }
  function load(item) {
    item = normalize(item);
    editing = item.id ? structuredClone(item) : null;
    for (const k of ["name", "category", "archetype", "baseBonus", "multiplier"])
      fields[k].value = item[k];
    archetypes(item.archetype);
    negatives();
    fields.negativeEffect.value = item.negativeEffect;
    describe();
  }
  fields.negativeEffect.onchange = describe;
  fields.archetype.onchange = () => {
    fields.multiplier.value = rules[fields.archetype.value][0];
    negatives();
    describe();
  };
  fields.category.onchange = () => {
    const name = Object.keys(types).find((n) => types[n] === fields.category.value);
    if (name) {
      archetypes(name);
      fields.archetype.onchange();
    } else {
      fields.category.value = types[fields.archetype.value];
      window.showToast("此类契约等待补充");
    }
  };
  function renderList() {
    list.replaceChildren();
    for (const item of library.filter(
      (i) => (!filter.value || i.category === filter.value) && i.name.includes(search.value.trim()),
    )) {
      const b = E("button", item.name + " · " + labels[item.category]);
      b.type = "button";
      b.onclick = () => load(item);
      list.append(b);
    }
    if (!list.children.length) list.append(E("p", "此分类尚无契约，等待补充。", "skill-help"));
  }
  add.onclick = () => load({ ...defaults()[0], id: "", name: "" });
  search.oninput = filter.onchange = renderList;
  duplicate.onclick = () => {
    editing = null;
    fields.name.value += "（副本）";
  };
  remove.onclick = async () => {
    if (!editing || !confirm("删除此契约？主界面佩戴的该契约也会移除。")) return;
    try {
      if (useAPI) library = (await request("DELETE", undefined, editing.id)).contracts;
      else {
        library = library.filter((i) => i.id !== editing.id);
        localStorage.setItem(key, JSON.stringify(library));
      }
      editing = null;
      renderList();
      refreshRoles();
    } catch (e) {
      window.showToast(e.message);
    }
  };
  content.onsubmit = async (event) => {
    event.preventDefault();
    if (!content.reportValidity()) return;
    const item = Object.fromEntries(
      Object.entries(fields).map(([k, n]) => [
        k,
        ["baseBonus", "multiplier"].includes(k) ? Number(n.value) : n.value,
      ]),
    );
    if (editing) item.id = editing.id;
    save.disabled = true;
    try {
      if (useAPI) {
        const data = await request(editing ? "PUT" : "POST", item, editing?.id || "");
        library = data.contracts;
        load(data.item);
      } else {
        item.id = item.id || "contract_" + crypto.randomUUID();
        library = library.filter((i) => i.id !== item.id);
        library.push(item);
        localStorage.setItem(key, JSON.stringify(library));
        load(item);
      }
      renderList();
      refreshRoles();
      window.showToast("契约已保存");
    } catch (e) {
      window.showToast(e.message);
    } finally {
      save.disabled = false;
    }
  };
  window.ContractLibrary = {
    attach(card, c) {
      const host = card.querySelector(".contract"),
        wearRow = E("label", undefined, "field"),
        wear = E("select");
      wear.setAttribute("aria-label", "选择契约");
      wearRow.append(E("span", "契约"), wear);
      card.selectedContract = structuredClone(normalize(c.selectedContract));
      if (card.specialSources) {
        card.specialSources.selectedContract = structuredClone(card.selectedContract);
        card.refreshSpecial?.();
      }
      const active = host.querySelector('[name="contract"]'),
        negative = host.querySelector('[name="negativeEffect"]'),
        multiplier = host.querySelector('[name="skillMultiplier"]');
      const stateRow = E("label", undefined, "field contract-state");
      const state = E("input", undefined, "switch");
      state.type = "checkbox";
      state.setAttribute("role", "switch");
      state.setAttribute("aria-label", "激活契约");
      const status = E("span", undefined, "contract-state-text");
      stateRow.append(E("span", "状态"), state, status);
      host.prepend(wearRow, stateRow);
      const previousStateRow = active.closest?.(".field");
      if (previousStateRow) {
        previousStateRow.hidden = true;
        previousStateRow.classList.add("contract-state-storage");
      }

      function updateState() {
        state.checked = active.value !== "不激活";
        state.disabled = ![...active.options].some((item) => item.value !== "不激活");
        status.textContent = state.checked ? "已激活" : "不激活";
      }

      card.deactivateContract = () => {
        active.value = "不激活";
        updateState();
      };
      state.onchange = () => {
        const available = [...active.options].find((item) => item.value !== "不激活");
        if (state.checked && available) {
          for (const other of document.querySelectorAll(".character")) {
            if (other !== card) other.deactivateContract?.();
          }
          active.value = available.value;
        } else {
          card.deactivateContract();
        }
        updateState();
      };
      function options() {
        const chosen = card.selectedContract;
        wear.replaceChildren(
          option("", "不佩戴"),
          ...library.map((i) => option(i.id, i.name + " · " + labels[i.category])),
        );
        if (chosen && !library.some((i) => i.id === chosen.id))
          wear.append(option(chosen.id, chosen.name + "（配置保存）"));
        wear.value = chosen?.id || "";
        const was = active.value;
        active.replaceChildren(option("不激活", "不激活"));
        if (!card.specialSources && !chosen) {
          const legacy = c.contract && c.contract !== "不激活" ? c.contract : "旧日支配者-魔";
          active.append(option(legacy, legacy + "（原配置）"));
        }
        if (chosen && chosen.category !== "constitution")
          active.append(option(activation(chosen), "激活 " + chosen.name));
        active.value = [...active.options].some((i) => i.value === was) ? was : "不激活";
        const old = negative.value;
        negative.replaceChildren(
          ...(chosen
            ? rules[chosen.archetype][1]
            : [
                ...new Set([
                  "无",
                  "群体献祭",
                  ...(!card.specialSources && c.negativeEffect ? [c.negativeEffect] : []),
                ]),
              ]
          ).map((n) => option(n, n)),
        );
        negative.value = [...negative.options].some((i) => i.value === old)
          ? old
          : chosen?.negativeEffect || "无";
        updateState();
      }
      wear.onchange = () => {
        if (wear.value !== (card.selectedContract?.id || "")) card.deactivateContract();
        card.selectedContract = structuredClone(library.find((i) => i.id === wear.value) || null);
        if (card.specialSources)
          card.specialSources.selectedContract = structuredClone(card.selectedContract);
        options();
        if (card.selectedContract) {
          negative.value = card.selectedContract.negativeEffect;
          multiplier.value = card.selectedContract.multiplier;
        }
        card.refreshSpecial?.();
        card.dispatchEvent(new Event("change", { bubbles: true }));
      };
      card.refreshContractOptions = () => {
        if (!loaded) return;
        const previous = card.selectedContract,
          wasActive = active.value !== "不激活";
        const latest = previous
          ? library.find((i) => i.id === previous.id) ||
            library.find((i) => i.name === previous.name) ||
            null
          : null;
        const changed = JSON.stringify(latest) !== JSON.stringify(previous);
        card.selectedContract = structuredClone(latest);
        if (card.specialSources) card.specialSources.selectedContract = structuredClone(latest);
        options();
        if (changed) {
          active.value =
            wasActive && latest && latest.category !== "constitution"
              ? activation(latest)
              : "不激活";
          negative.value = latest?.negativeEffect || "无";
          multiplier.value = latest?.multiplier || 0;
          updateState();
          card.refreshSpecial?.();
          card.dispatchEvent(new Event("change", { bubbles: true }));
        }
      };
      options();
      card.refreshContractOptions();
    },
  };
  document.querySelector("#open-contract-library").onclick = () => {
    renderList();
    if (!editing) load(defaults()[0]);
    dialog.showModal();
  };
  refresh().catch((e) => window.showToast("契约库加载失败：" + e.message));
})();
