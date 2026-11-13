"use strict";
(() => {
  const el = (tag, text) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const attrs = [
    ["finalPhysicalDamage", "辉印物伤"],
    ["finalMagicDamage", "辉印魔伤"],
    ["finalDotDamage", "辉印持续伤害"],
    ["finalHealingBonus", "辉印回复"],
    ["hitRate", "命中率"],
    ["criticalRate", "暴击率"],
    ["abnormalBonus", "异常附加率"],
  ];
  const types = ["战士", "法师", "潜行者", "火枪手", "圣职", "野蛮人"];
  const blank = () => ({
    name: "",
    kind: types[0],
    attributes: Object.fromEntries(attrs.map(([k]) => [k, 0])),
  });
  let items = [],
    selected = "",
    draft = blank();
  const subscribers = new Set();
  let loadedLibrary = null;
  const currentLibrary = () => window.PlayerLibraries?.current.imprints || "";
  const dialog = el("dialog");
  dialog.id = "imprints-library";
  dialog.className = "configuration-dialog";
  const heading = el("div");
  heading.className = "configuration-heading";
  heading.append(el("h2", "辉印库"));
  const close = el("button", "×");
  close.type = "button";
  close.onclick = () => dialog.close();
  heading.append(close);
  dialog.append(heading);
  const layout = el("div");
  layout.className = "trophy-layout";
  const sidebar = el("div"),
    form = el("form");
  layout.append(sidebar, form);
  dialog.append(layout);
  document.body.append(dialog);
  const search = el("input");
  search.placeholder = "搜索辉印名称";
  search.setAttribute("aria-label", "搜索辉印名称");
  const filter = el("select");
  filter.setAttribute("aria-label", "筛选辉印种类");
  filter.append(el("option", "全部种类"));
  filter.children[0].value = "";
  for (const kind of types) {
    const o = el("option", kind);
    o.value = kind;
    filter.append(o);
  }
  filter.value = "";
  const list = el("div");
  list.className = "trophy-list-results";
  let composing = false;
  search.addEventListener("compositionstart", () => {
    composing = true;
  });
  search.addEventListener("compositionend", () => {
    composing = false;
    drawList();
  });
  search.oninput = () => {
    if (!composing) drawList();
  };
  filter.onchange = drawList;
  async function request(path = "", method = "GET", body) {
    if (window.AppRequests) await window.AppRequests.ready;
    const library = currentLibrary();
    const r = await (window.AppRequests?.fetch || fetch)(
      "/api/imprints" +
        path +
        (window.PlayerLibraries?.current.imprints
          ? "?library=" + encodeURIComponent(window.PlayerLibraries.current.imprints)
          : ""),
      {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
        cache: "no-store",
      },
    );
    const v = await r.json();
    if (!r.ok) throw Error(v.error || "辉印库接口失败");
    if (library !== currentLibrary()) return v;
    items = v.imprints;
    loadedLibrary = library;
    if (!items.some((i) => i.id === selected)) {
      selected = items[0]?.id || "";
      draft = selected ? structuredClone(items[0]) : blank();
    }
    for (const update of subscribers) update();
    return v;
  }
  function drawList() {
    if (!sidebar.children.length) sidebar.append(search, filter, list);
    list.replaceChildren();
    const matching = items.filter(
      (i) =>
        i.name.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase()) &&
        (!filter.value || i.kind === filter.value),
    );
    for (const item of matching) {
      const b = el("button", item.name + " · " + item.kind);
      b.type = "button";
      b.onclick = () => {
        selected = item.id;
        draft = structuredClone(item);
        drawForm();
      };
      list.append(b);
    }
    if (!matching.length) list.append(el("p", "没有匹配的辉印"));
  }
  function drawForm() {
    form.replaceChildren();
    form.append(
      el("h3", "编辑" + draft.name),
      el(
        "p",
        draft.scope === "extra"
          ? "仅记录该转职的额外加成，与大类基础辉印相加。"
          : "记录该大类的基础加成。辉印为固定条目，只能修改数值。",
      ),
    );
    const grid = el("div");
    grid.className = "special-source-grid";
    form.append(grid);
    for (const [k, label] of attrs) {
      const row = el("label");
      row.className = "field";
      const input = el("input");
      input.type = "number";
      input.min = 0;
      input.step = "any";
      input.required = true;
      input.value = draft.attributes[k] ?? 0;
      input.setAttribute("aria-label", label);
      input.oninput = () => (draft.attributes[k] = Number(input.value));
      row.append(el("span", label), input);
      const unit = el("span", "%");
      unit.className = "field-unit";
      row.append(unit);
      grid.append(row);
    }
    const actions = el("div");
    actions.className = "configuration-actions";
    const save = el("button", "保存辉印");
    save.type = "submit";
    save.className = "primary";
    actions.append(save);
    form.append(actions);
    form.onsubmit = async (e) => {
      e.preventDefault();
      save.disabled = true;
      try {
        const result = await request("/" + encodeURIComponent(selected), "PUT", draft);
        selected = result.item.id;
        draft = structuredClone(result.item);
        drawList();
        drawForm();
        window.showToast("辉印已保存");
      } catch (e) {
        window.showToast(e.message);
        save.disabled = false;
      }
    };
  }
  window.ImprintLibrary = {
    isReady: () => loadedLibrary === currentLibrary(),
    resolve(s, profession, job) {
      if (loadedLibrary !== currentLibrary()) return false;
      const base = items.find((i) => i.kind === profession && i.scope === "base");
      const aliases = { 霜寒法师: "寒霜法师", 夜魔: "夜魇" };
      const extra =
        items.find((i) => i.kind === profession && i.scope === "extra" && i.job === job) ||
        items.find((i) => i.kind === profession && i.scope === "extra" && i.job === aliases[job]);
      s.selectedImprint = base ? structuredClone(base) : null;
      s.selectedExtraImprint = extra ? structuredClone(extra) : null;
      s.imprint = Object.fromEntries(
        attrs.map(([k]) => [k, (base?.attributes[k] ?? 0) + (extra?.attributes[k] ?? 0)]),
      );
      s.imprintCustom = true;
      return true;
    },
    attach(host, s, onChange) {
      const pickers = {};
      function apply() {
        const base = s.selectedImprint,
          extra = s.selectedExtraImprint;
        const profession = base?.kind || extra?.kind || "";
        const automatic = window.SpecialConfiguration?.imprintFor(profession, profession) || {};
        s.imprint = Object.fromEntries(
          attrs.map(([k]) => [
            k,
            (base?.attributes[k] ?? automatic[k] ?? 0) + (extra?.attributes[k] || 0),
          ]),
        );
        s.imprintCustom = !!(base || extra);
        onChange();
      }
      for (const [scope, key, title] of [
        ["base", "selectedImprint", "基础辉印"],
        ["extra", "selectedExtraImprint", "额外辉印"],
      ]) {
        const row = el("label");
        row.className = "imprint-picker";
        row.append(el("span", title));
        const picker = el("select");
        picker.setAttribute("aria-label", title);
        row.append(picker);
        host.append(row);
        pickers[scope] = picker;
        function render() {
          picker.replaceChildren();
          const empty = el("option", scope === "base" ? "自动按职业设置" : "无额外辉印");
          empty.value = "";
          picker.append(empty);
          for (const item of items.filter((i) => i.scope === scope)) {
            const o = el("option", item.name);
            o.value = item.id;
            picker.append(o);
          }
          if (s[key] && !items.some((i) => i.id === s[key].id)) {
            const o = el("option", s[key].name + "（已保存属性）");
            o.value = s[key].id;
            picker.append(o);
          }
          picker.value = s[key]?.id || "";
        }
        picker.onchange = () => {
          const item = items.find((i) => i.id === picker.value);
          s[key] = item ? structuredClone(item) : null;
          if (
            scope === "base" &&
            s.selectedExtraImprint &&
            s.selectedExtraImprint.kind !== item?.kind
          ) {
            s.selectedExtraImprint = null;
            pickers.extra.value = "";
          }
          apply();
        };
        render();
        pickers[scope].render = render;
      }
      subscribers.add(() => {
        onChange();
        for (const picker of Object.values(pickers)) picker.render();
      });
      if (loadedLibrary !== currentLibrary()) request().catch((e) => window.showToast(e.message));
    },
  };
  if (window.PlayerLibraries) {
    const bar = document.createElement("div");
    heading.after(bar);
    window.PlayerLibraries.mount(bar, "imprints", "默认辉印库", async () => {
      selected = "";
      await request();
      drawList();
      drawForm();
    });
  }
  document.querySelector("#open-imprints-library").onclick = async () => {
    try {
      await request();
      drawList();
      drawForm();
      dialog.showModal();
    } catch (e) {
      window.showToast(e.message);
    }
  };
})();
