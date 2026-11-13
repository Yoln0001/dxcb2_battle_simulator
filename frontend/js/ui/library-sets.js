"use strict";
(() => {
  const current = { ...(window.AppRequests?.selections || {}) },
    controls = new Map(),
    mountWaiters = new Map();
  const selectionKey = "dungeon2-library-selections-v1";
  function remember() {
    try {
      localStorage.setItem(selectionKey, JSON.stringify(current));
    } catch {}
  }
  function remembered(kind) {
    try {
      return JSON.parse(localStorage.getItem(selectionKey) || "{}")[kind] || "";
    } catch {
      return "";
    }
  }
  function nameDialog(
    title,
    value,
    description,
    save,
    percentageCopy = false,
    initialPercentages = {},
  ) {
    const dialog = document.createElement("dialog");
    dialog.className = "library-name-dialog";
    const form = document.createElement("form"),
      heading = document.createElement("h2"),
      hint = document.createElement("p"),
      label = document.createElement("label"),
      input = document.createElement("input"),
      error = document.createElement("p"),
      actions = document.createElement("div"),
      cancel = document.createElement("button"),
      submit = document.createElement("button");
    heading.id = "library-name-heading";
    heading.textContent = title;
    hint.id = "library-name-hint";
    hint.textContent = description;
    dialog.setAttribute("aria-labelledby", heading.id);
    dialog.setAttribute("aria-describedby", hint.id);
    label.textContent = "库名称";
    input.type = "text";
    input.value = value;
    input.maxLength = 120;
    input.placeholder = "输入库名称";
    input.autocomplete = "off";
    label.append(input);
    error.className = "library-name-error";
    error.setAttribute("role", "alert");
    actions.className = "library-name-actions";
    cancel.type = "button";
    cancel.textContent = "取消";
    submit.type = "submit";
    submit.className = "primary";
    submit.textContent = "保存名称";
    actions.append(cancel, submit);
    form.append(heading, hint, label, error, actions);
    dialog.append(form);
    document.body.append(dialog);
    const percentages = {};
    if (percentageCopy) {
      const fields = document.createElement("div");
      fields.className = "library-copy-percentages";
      for (const [key, title] of [
        ["main", "主属性百分比（%）"],
        ["other", "其余四维＋武威百分比（%）"],
        ["defense", "护甲＋抗性百分比（%）"],
      ]) {
        const row = document.createElement("label"),
          field = document.createElement("input");
        row.textContent = title;
        field.type = "number";
        field.min = "0";
        field.max = "100";
        field.step = "any";
        field.placeholder = "留空保留原值";
        field.value = initialPercentages[key] === undefined ? "" : String(initialPercentages[key]);
        field.setAttribute("aria-label", title);
        row.append(field);
        fields.append(row);
        percentages[key] = field;
      }
      form.insertBefore(fields, error);
      submit.textContent = percentageCopy === "edit" ? "保存修改" : "复制装备库";
    }
    const submitLabel = submit.textContent;
    let saving = false;
    cancel.addEventListener("click", () => dialog.close());
    dialog.addEventListener("cancel", (e) => {
      if (saving) e.preventDefault();
    });
    dialog.addEventListener("close", () => dialog.remove());
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (saving) return;
      const name = input.value.trim();
      if (!name) {
        error.textContent = "请输入库名称";
        input.focus();
        return;
      }
      const values = {};
      for (const [key, field] of Object.entries(percentages)) {
        if (field.value.trim() !== "") {
          const n = Number(field.value);
          if (!Number.isFinite(n) || n < 0 || n > 100) {
            error.textContent = "百分比请输入 0～100 之间的数值";
            field.focus();
            return;
          }
          values[key] = n;
        }
      }
      saving = true;
      cancel.disabled = submit.disabled = input.disabled = true;
      submit.textContent = "正在保存…";
      error.textContent = "";
      try {
        await save(name, values);
        dialog.close();
      } catch (e) {
        error.textContent = e.message;
      } finally {
        saving = false;
        cancel.disabled = submit.disabled = input.disabled = false;
        submit.textContent = submitLabel;
      }
    });
    dialog.showModal();
    input.focus();
    input.select();
  }
  window.PlayerLibraries = {
    current,
    nameDialog,
    pending: false,
    whenMounted(kind) {
      return controls.has(kind)
        ? Promise.resolve()
        : new Promise((resolve) => {
            const waiters = mountWaiters.get(kind) || [];
            waiters.push(resolve);
            mountWaiters.set(kind, waiters);
          });
    },
    async restore(value = {}) {
      if (this.pending) throw Error("正在加载所选库，请稍候");
      for (const kind of [
        "equipment",
        "stones",
        "people",
        "trophies",
        "bosses",
        "contracts",
        "rings",
        "holies",
        "imprints",
      ])
        current[kind] = value[kind] || "";
      this.pending = true;
      try {
        const results = await Promise.allSettled(
          [...controls].map(async ([kind, control]) => {
            await control.refresh();
            await control.switch();
          }),
        );
        const failure = results.find((result) => result.status === "rejected");
        if (failure) throw failure.reason;
      } finally {
        this.pending = false;
      }
    },
    mount(host, kind, defaultName, onSwitch, options = {}) {
      const bar = document.createElement("div");
      bar.className = "player-library-bar";
      const select = document.createElement("select");
      select.setAttribute("aria-label", "选择" + defaultName);
      const create = document.createElement("button"),
        copy = document.createElement("button"),
        rename = document.createElement("button"),
        remove = document.createElement("button");
      const buttons = [create, copy, rename, remove];
      for (const b of buttons) b.type = "button";
      create.textContent = "＋ 新建库";
      copy.textContent = "复制当前库";
      rename.textContent = kind === "equipment" ? "修改当前库属性" : "重命名库";
      remove.textContent = "删除库";
      bar.append(select, ...buttons);
      host.append(bar);
      let libraries = [],
        extra = "",
        busy = false,
        displayNames = {};
      function state() {
        select.disabled = busy;
        create.disabled = copy.disabled = busy || !!extra;
        rename.disabled = busy;
        remove.disabled = busy || !!extra || !current[kind];
      }
      function dirty() {
        remember();
        const status = document.querySelector("#save-state");
        if (status) status.textContent = "有未保存的修改";
      }
      async function request(method = "GET", body, id = "") {
        if (window.AppRequests) await window.AppRequests.ready;
        const r = await (window.AppRequests?.fetch || fetch)(
          "/api/library-sets/" + kind + (id ? "/" + encodeURIComponent(id) : ""),
          {
            method,
            headers: body ? { "Content-Type": "application/json" } : {},
            body: body ? JSON.stringify(body) : undefined,
          },
        );
        const data = await r.json();
        if (!r.ok) throw Error(data.error || "玩家库接口失败");
        return data;
      }
      function render(data, strict = false) {
        libraries = data.libraries;
        displayNames = data.displayNames || displayNames;
        if (current[kind] && !libraries.some((i) => i.id === current[kind])) {
          if (strict && kind !== "equipment")
            throw Error(
              "配置所选的" + defaultName + "不存在，请恢复原库或重新选择，原穿戴信息已保留",
            );
          const saved = remembered(kind);
          current[kind] =
            kind === "equipment" && libraries.some((i) => i.id === saved) ? saved : "";
          if (strict && kind === "equipment")
            window.showToast("配置原装备库已移除，装备身份已保留，现从当前可用库读取数值");
        }
        select.replaceChildren();
        for (const item of [
          { id: "", name: displayNames.__default__ || defaultName },
          ...libraries,
          ...(options.extraOptions || []).map((i) => ({
            ...i,
            name: displayNames[i.id] || i.name,
          })),
        ]) {
          const o = document.createElement("option");
          o.value = item.id;
          o.textContent = item.name;
          select.append(o);
        }
        select.value = extra || current[kind] || "";
        state();
      }
      select.addEventListener("change", async () => {
        const previous = current[kind] || "",
          previousExtra = extra;
        busy = true;
        state();
        try {
          if ((options.extraOptions || []).some((i) => i.id === select.value)) {
            extra = select.value;
            await options.onExtra?.(extra);
          } else {
            extra = "";
            current[kind] = select.value;
            await onSwitch();
            dirty();
          }
        } catch (e) {
          current[kind] = previous;
          extra = previousExtra;
          select.value = extra || previous;
          window.showToast(e.message);
        } finally {
          busy = false;
          state();
        }
      });
      function add(isCopy) {
        const percentageCopy = isCopy && kind === "equipment";
        nameDialog(
          isCopy ? "复制当前库" : "新建库",
          "",
          percentageCopy
            ? "0% 对应最小值，100% 对应最大值。三项分别设置主属性、其余四维＋武威、护甲＋抗性。主属性按装备标签判断；未标注时，五维均使用第二项百分比。留空保留原值，其他词条不变。"
            : isCopy
              ? "填写新库名称，复制当前库的全部内容。"
              : "为新建的独立库设置名称。",
          async (name, percentages) => {
            busy = true;
            state();
            try {
              const body = { name, copy: isCopy, copyFrom: current[kind] || "" };
              if (percentageCopy) body.attributePercentages = percentages;
              const data = await request("POST", body);
              current[kind] = data.item.id;
              extra = "";
              render(data);
              await onSwitch();
              dirty();
              window.showToast(isCopy ? "已复制为独立库" : "新库已创建");
            } finally {
              busy = false;
              state();
            }
          },
          percentageCopy,
        );
      }
      create.addEventListener("click", () => add(false));
      copy.addEventListener("click", () => add(true));
      rename.addEventListener("click", async () => {
        const id = extra || current[kind] || "__default__";
        const item = extra
          ? (options.extraOptions || []).find((i) => i.id === extra)
          : libraries.find((i) => i.id === current[kind]);
        const oldName = displayNames[id] || item?.name || defaultName;
        const equipment = kind === "equipment";
        let percentages = {};
        if (equipment) {
          busy = true;
          state();
          try {
            percentages = (await request("GET", undefined, id)).attributePercentages || {};
          } catch (e) {
            window.showToast(e.message);
            return;
          } finally {
            busy = false;
            state();
          }
        }
        nameDialog(
          equipment ? "修改当前库属性" : "重命名库",
          oldName,
          equipment
            ? "修改库名及三组属性百分比。0% 对应最小值，100% 对应最大值；留空保留原值。数值不统一的组显示为空，仅修改当前库。"
            : "设置一个便于辨认的名称，库内已有内容会保留。",
          async (name, values) => {
            if (!equipment && name === oldName) return;
            busy = true;
            state();
            try {
              const body = { name };
              if (equipment) body.attributePercentages = values;
              render(await request("PUT", body, id));
              if (equipment) {
                if (extra) {
                  await window.wikiEquipmentEditor?.refresh();
                  await options.onExtra?.(extra);
                } else await onSwitch();
                dirty();
              }
              window.showToast(equipment ? "当前库属性已修改" : "库已重命名");
            } finally {
              busy = false;
              state();
            }
          },
          equipment ? "edit" : false,
          percentages,
        );
      });
      remove.addEventListener("click", async () => {
        const item = libraries.find((i) => i.id === current[kind]);
        if (!item || !confirm("删除“" + item.name + "”？删除后将切换到" + defaultName + "。"))
          return;
        busy = true;
        state();
        try {
          const data = await request("DELETE", undefined, item.id);
          current[kind] = "";
          extra = "";
          render(data);
          await onSwitch();
          dirty();
          window.showToast("库已删除");
        } catch (e) {
          window.showToast(e.message);
        } finally {
          busy = false;
          state();
        }
      });
      for (const resolve of mountWaiters.get(kind) || []) resolve();
      mountWaiters.delete(kind);
      controls.set(kind, {
        refresh: async () => {
          extra = "";
          render(await request(), true);
        },
        switch: onSwitch,
      });
      state();
      request()
        .then((data) => render(data))
        .catch((e) => window.showToast(e.message));
      return bar;
    },
  };
})();
