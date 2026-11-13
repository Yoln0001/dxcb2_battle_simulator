"use strict";
(() => {
  const E = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };
  const dialog = E("dialog", undefined, "raw-equipment-dialog"),
    head = E("div", undefined, "raw-equipment-header"),
    close = E("button", "×");
  close.type = "button";
  head.append(E("h2", "未分类装备库"), close);
  dialog.append(head);
  document.body.append(dialog);
  close.onclick = () => dialog.close();
  const info = E("p"),
    bar = E("div", undefined, "raw-equipment-bar"),
    search = E("input"),
    category = E("select"),
    refresh = E("button", "刷新百科资料"),
    host = E("div", undefined, "raw-equipment-table");
  search.placeholder = "搜索装备名称、属性或特效";
  refresh.type = "button";
  bar.append(search, category, refresh);
  dialog.append(info, bar, host);
  let items = [];
  async function request(update = false) {
    const response = await (window.AppRequests?.fetch || fetch)(
      "/api/unclassified-equipment" + (update ? "/refresh" : ""),
      update
        ? { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }
        : { cache: "no-store" },
    );
    const data = await response.json();
    if (!response.ok) throw Error(data.error || "资料读取失败");
    return data;
  }
  function render() {
    host.replaceChildren();
    const table = E("table"),
      header = E("tr");
    for (const label of ["装备名称", "种类／职业", "属性", "特效"]) header.append(E("th", label));
    table.append(header);
    const query = search.value.trim().toLowerCase();
    for (const item of items.filter(
      (i) =>
        (!category.value || i.category === category.value) &&
        (i.name + " " + i.attributes + " " + i.effects).toLowerCase().includes(query),
    )) {
      const row = E("tr"),
        name = E("td"),
        link = E("a", item.name);
      link.href = item.sourceUrl;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      name.append(link);
      row.append(
        name,
        E("td", item.categoryLabel + "／" + (item.weaponJob || "不限职业")),
        E("td", item.attributes || "暂无属性"),
        E("td", item.effects || "无"),
      );
      table.append(row);
    }
    host.append(table);
  }
  async function load(update = false) {
    refresh.disabled = true;
    try {
      const data = await request(update);
      items = data.equipment;
      const old = category.value;
      category.replaceChildren();
      const all = E("option", "全部种类");
      all.value = "";
      category.append(all);
      for (const [value, label] of new Map(items.map((i) => [i.category, i.categoryLabel]))) {
        const option = E("option", label);
        option.value = value;
        category.append(option);
      }
      category.value = old;
      info.textContent =
        "共 " +
        items.length +
        " 件装备" +
        (data.updatedAt ? " · 更新于 " + new Date(data.updatedAt).toLocaleString() : "") +
        "。此处保留百科原始属性与特效。";
      render();
    } catch (e) {
      window.showToast(e.message);
    } finally {
      refresh.disabled = false;
    }
  }
  search.oninput = category.onchange = render;
  refresh.onclick = () => load(true);
  document.querySelector("#open-unclassified-equipment").addEventListener("click", () => {
    dialog.showModal();
    load();
  });
})();
