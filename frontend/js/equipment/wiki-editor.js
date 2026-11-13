"use strict";
(() => {
  const custom = window.customEquipmentEditor,
    wiki = window.createEquipmentLibraryEditor({
      wiki: true,
      lazy: true,
      title: "百科装备库",
      api: "/api/wiki-equipment",
      dialogId: "wiki-equipment-editor-dialog",
      openButton: false,
      storageKey: "dungeon2-wiki-equipment-library-v1",
    });
  window.wikiEquipmentEditor = wiki;
  const shell = document.createElement("dialog");
  shell.className = "skill-editor-dialog";
  shell.id = "equipment-library-dialog";
  const header = document.createElement("div");
  header.className = "dialog-head";
  const title = document.createElement("h2");
  title.textContent = "装备库";
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "×";
  close.setAttribute("aria-label", "关闭装备库");
  close.addEventListener("click", () => shell.close());
  header.append(title, close);
  shell.append(header);
  const tabs = document.createElement("div");
  tabs.className = "equipment-trigger-bar";
  shell.append(tabs);
  let active = 0;
  const editors = [custom, wiki],
    panels = editors.map((editor) => {
      const panel = document.createElement("div");
      for (const child of Array.from(editor.dialog.children).slice(1)) panel.append(child);
      shell.append(panel);
      return panel;
    });
  const buttons = [];
  function select(index) {
    if (index !== active && !editors[active].canLeave()) return;
    active = index;
    panels.forEach((p, i) => (p.hidden = i !== index));
    buttons.forEach((b, i) => b.classList.toggle("selected", i === index));
    Promise.resolve(editors[index].render()).catch((e) => window.showToast(e.message));
  }
  if (window.PlayerLibraries) {
    window.PlayerLibraries.mount(
      tabs,
      "equipment",
      "自定义装备库",
      async () => {
        await custom.switchLibrary();
        select(0);
        await window.refreshPlayerEquipment(true);
      },
      { extraOptions: [{ id: "__wiki__", name: "百科装备库" }], onExtra: () => select(1) },
    );
    let refreshVersion = 0,
      equipmentRefresh = null;
    window.refreshPlayerEquipment = async (strict = false) => {
      if (window.AppRequests) await window.AppRequests.ready;
      const version = ++refreshVersion,
        library = window.PlayerLibraries.current.equipment || "";
      const loading = (async () => {
        const r = await (window.AppRequests?.fetch || fetch)(
          "/api/equipment/team" + (library ? "?library=" + encodeURIComponent(library) : ""),
          { cache: "no-store" },
        );
        const data = await r.json();
        if (!r.ok) throw Error(data.error);
        if (
          version !== refreshVersion ||
          library !== (window.PlayerLibraries.current.equipment || "")
        )
          return;
        window.onEquipmentLibraryChange?.(data.equipment);
      })();
      equipmentRefresh = loading;
      try {
        await loading;
        if (strict) {
          let pending;
          do {
            pending = equipmentRefresh;
            await pending;
          } while (pending !== equipmentRefresh);
        }
      } catch (e) {
        if (strict) throw e;
        window.showToast(e.message);
      }
    };
    window.refreshPlayerEquipment();
  }
  document.body.append(shell);
  select(0);
  document.querySelector("#open-equipment-editor").addEventListener("click", () => {
    Promise.resolve(editors[active].render()).catch((e) => window.showToast(e.message));
    shell.showModal();
  });
})();
