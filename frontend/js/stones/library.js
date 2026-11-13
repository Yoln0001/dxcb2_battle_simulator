"use strict";
(() => {
  const el = (tag, text) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const attrs = [
    ["strength", "力量"],
    ["magic", "魔力"],
    ["technique", "技巧"],
    ["speed", "速度"],
    ["constitution", "体质"],
    ["hitRate", "命中率"],
  ];
  const types = ["暴君之石", "古精灵之石", "乌鸦之石", "猎神者之石", "巨龙之石", "唯一魔石"];
  const blank = () => ({
    name: "",
    kind: types[0],
    attributes: Object.fromEntries(attrs.map(([k]) => [k, 0])),
  });
  let items = [],
    selected = "",
    draft = blank();
  const subscribers = new Set();
  let loaded = false,
    loadedLibrary = null;
  const dialog = el("dialog");
  dialog.id = "stones-library";
  dialog.className = "configuration-dialog";
  const heading = el("div");
  heading.className = "configuration-heading";
  heading.append(el("h2", "魔石库"));
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
  search.placeholder = "搜索魔石名称";
  search.setAttribute("aria-label", "搜索魔石名称");
  const filter = el("select");
  filter.setAttribute("aria-label", "筛选魔石种类");
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
    const library = window.PlayerLibraries?.current.stones || "";
    const r = await (window.AppRequests?.fetch || fetch)(
      "/api/stones" +
        path +
        (window.PlayerLibraries?.current.stones
          ? "?library=" + encodeURIComponent(window.PlayerLibraries.current.stones)
          : ""),
      {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        body: body ? JSON.stringify(body) : undefined,
        cache: "no-store",
      },
    );
    const v = await r.json();
    if (!r.ok) throw Error(v.error || "魔石库接口失败");
    if (library !== (window.PlayerLibraries?.current.stones || "")) return v;
    items = v.stones;
    loaded = true;
    loadedLibrary = library;
    for (const update of subscribers) update();
    return v;
  }
  function drawList() {
    if (!sidebar.children.length) {
      const add = el("button", "＋ 新增魔石");
      add.type = "button";
      add.onclick = () => {
        selected = "";
        draft = blank();
        drawForm();
      };
      sidebar.append(add, search, filter, list);
    }
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
    if (!matching.length) list.append(el("p", "没有匹配的魔石"));
  }
  function drawForm() {
    form.replaceChildren();
    form.append(el("h3", selected ? "编辑魔石" : "新增魔石"));
    const name = el("input");
    name.placeholder = "魔石名称";
    name.required = true;
    name.maxLength = 120;
    name.setAttribute("aria-label", "魔石名称");
    name.value = draft.name;
    name.oninput = () => (draft.name = name.value);
    form.append(name);
    const job = el("select");
    job.required = true;
    job.setAttribute("aria-label", "魔石种类");
    for (const kind of types) {
      const o = el("option", kind);
      o.value = kind;
      job.append(o);
    }
    job.value = draft.kind;
    job.onchange = () => (draft.kind = job.value);
    form.append(job);
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
    const save = el("button", "保存魔石");
    save.type = "submit";
    save.className = "primary";
    actions.append(save);
    if (selected) {
      const copy = el("button", "另存为副本");
      copy.type = "button";
      copy.onclick = () => {
        draft = structuredClone(draft);
        selected = "";
        delete draft.id;
        const base = draft.name + "（副本）";
        let name = base,
          index = 2;
        while (items.some((item) => item.name === name)) name = base + " " + index++;
        draft.name = name.slice(0, 120);
        drawForm();
        window.showToast("已复制，请修改后点击保存魔石");
      };
      actions.append(copy);
      const del = el("button", "删除魔石");
      del.type = "button";
      del.onclick = async () => {
        if (!confirm("确认删除魔石“" + draft.name + "”？")) return;
        try {
          await request("/" + encodeURIComponent(selected), "DELETE");
          selected = "";
          draft = blank();
          drawList();
          drawForm();
          window.showToast("魔石已删除");
        } catch (e) {
          window.showToast(e.message);
        }
      };
      actions.append(del);
    }
    form.append(actions);
    form.onsubmit = async (e) => {
      e.preventDefault();
      save.disabled = true;
      try {
        const result = await request(
          selected ? "/" + encodeURIComponent(selected) : "",
          selected ? "PUT" : "POST",
          draft,
        );
        selected = result.item.id;
        draft = structuredClone(result.item);
        drawList();
        drawForm();
        window.showToast("魔石已保存");
      } catch (e) {
        window.showToast(e.message);
        save.disabled = false;
      }
    };
  }
  window.StoneLibrary = {
    attach(host, s, onChange) {
      const picker = el("select");
      picker.setAttribute("aria-label", "从魔石库选择");
      host.append(picker);
      function render(sync = false) {
        if (sync && loaded && s.selectedStone) {
          const latest =
            items.find((i) => i.id === s.selectedStone.id) ||
            items.find((i) => i.name === s.selectedStone.name) ||
            null;
          if (JSON.stringify(latest) !== JSON.stringify(s.selectedStone)) {
            picker.value = latest?.id || "";
            picker.onchange();
          }
        }
        picker.replaceChildren();
        const empty = el("option", "请选择魔石");
        empty.value = "";
        picker.append(empty);
        for (const item of items) {
          const o = el("option", item.name + " · " + item.kind);
          o.value = item.id;
          picker.append(o);
        }
        if (s.selectedStone && !items.some((i) => i.id === s.selectedStone.id)) {
          const o = el("option", s.selectedStone.name + "（已保存属性）");
          o.value = s.selectedStone.id;
          picker.append(o);
        }
        picker.value = s.selectedStone?.id || "";
      }
      picker.onchange = () => {
        const item = items.find((i) => i.id === picker.value);
        s.selectedStone = item ? structuredClone(item) : null;
        s.stone = item ? structuredClone(item.attributes) : {};
        onChange();
      };
      subscribers.add(() => render(true));
      render();
      if (loadedLibrary === (window.PlayerLibraries?.current.stones || "")) render(true);
      else request().catch((e) => window.showToast(e.message));
    },
  };
  if (window.PlayerLibraries) {
    const bar = document.createElement("div");
    heading.after(bar);
    window.PlayerLibraries.mount(bar, "stones", "默认魔石库", async () => {
      await request();
      selected = "";
      draft = blank();
      drawList();
      drawForm();
    });
  }
  document.querySelector("#open-stones-library").onclick = async () => {
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
