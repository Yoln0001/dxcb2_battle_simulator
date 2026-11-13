"use strict";
(() => {
  const E = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };
  const format = (n) => Number(n).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  const slots = {
    weapon: "武器",
    armor: "防具",
    accessory1: "饰品1",
    accessory2: "饰品2",
    stone: "魔石",
  };
  const dialog = E("dialog", undefined, "batch-dialog"),
    head = E("div", undefined, "dialog-head"),
    close = E("button", "×");
  close.type = "button";
  close.setAttribute("aria-label", "关闭批量模拟结果");
  close.addEventListener("click", cancelCurrent);
  const controls = E("div", undefined, "batch-window-controls"),
    minimize = E("button", "−");
  minimize.type = "button";
  minimize.setAttribute("aria-label", "最小化模拟窗口");
  const exportButton = E("button", undefined, "batch-export-button");
  const exportIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg"),
    exportPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  exportIcon.setAttribute("viewBox", "0 0 24 24");
  exportIcon.setAttribute("width", "20");
  exportIcon.setAttribute("height", "20");
  exportIcon.setAttribute("aria-hidden", "true");
  exportPath.setAttribute("d", "M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5");
  exportPath.setAttribute("fill", "none");
  exportPath.setAttribute("stroke", "currentColor");
  exportPath.setAttribute("stroke-width", "1.8");
  exportPath.setAttribute("stroke-linecap", "round");
  exportPath.setAttribute("stroke-linejoin", "round");
  exportIcon.append(exportPath);
  exportButton.append(exportIcon);
  exportButton.title = "导出战斗结果 PNG";
  exportButton.type = "button";
  exportButton.hidden = true;
  exportButton.setAttribute("aria-label", "导出战斗结果 PNG");
  const xlsxButton = E("button", undefined, "batch-export-button");
  const xlsxIcon = exportIcon.cloneNode(true);
  xlsxIcon.querySelector("path").setAttribute("d", "M4 3h16v18H4zM4 9h16M10 9v12M4 15h16");
  xlsxButton.append(xlsxIcon);
  xlsxButton.type = "button";
  xlsxButton.title = "导出战斗结果 XLSX";
  xlsxButton.setAttribute("aria-label", "导出战斗结果 XLSX");
  xlsxButton.hidden = true;
  controls.append(exportButton, xlsxButton, minimize, close);
  head.append(E("h2", "批量模拟结果"), controls);
  let exportResult = null,
    exportConfig = null;
  exportButton.addEventListener("click", async () => {
    if (!exportResult) return;
    exportButton.disabled = true;
    try {
      await window.BatchResultExport.download(exportResult, exportConfig);
    } catch (error) {
      window.showToast(error.message);
    } finally {
      exportButton.disabled = false;
    }
  });
  xlsxButton.addEventListener("click", async () => {
    if (!exportResult) return;
    xlsxButton.disabled = true;
    try {
      await window.BatchResultXlsx.download(exportResult, exportConfig);
    } catch (error) {
      window.showToast(error.message);
    } finally {
      xlsxButton.disabled = false;
    }
  });
  let activeTask = null,
    minimized = false;
  const restore = E("button", "查看模拟进度", "batch-restore");
  restore.type = "button";
  restore.hidden = true;
  restore.setAttribute("aria-label", "恢复模拟窗口");
  document.body.append(restore);
  minimize.addEventListener("click", () => {
    minimized = true;
    dialog.close();
    restore.hidden = false;
  });
  restore.addEventListener("click", () => {
    minimized = false;
    restore.hidden = true;
    if (!dialog.open) dialog.showModal();
  });
  async function cancelCurrent() {
    minimized = false;
    restore.hidden = true;
    dialog.close();
    const task = activeTask;
    if (!task) return;
    task.cancelled = true;
    if (task.id) {
      try {
        const response = await (window.AppRequests?.fetch || fetch)(
          "/api/battle/batch/" + encodeURIComponent(task.id) + "/cancel",
          { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
        );
        if (!response.ok) {
          const data = await response.json();
          throw Error(data.error || "取消模拟失败");
        }
        window.showToast("批量模拟已取消");
      } catch (error) {
        window.showToast(error.message);
      }
    }
  }
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    cancelCurrent();
  });
  const progress = E("p", undefined, "batch-progress");
  progress.setAttribute("role", "status");
  progress.setAttribute("aria-live", "polite");
  const content = E("div");
  dialog.append(head, progress, content);
  document.body.append(dialog);
  const metric = (name, value) => {
    const item = E("div", undefined, "batch-metric");
    item.append(E("span", name), E("strong", value));
    return item;
  };
  const row = () => E("div", undefined, "batch-stat-row");
  const dataMode = (data) => (data.boss_attacks ? "包含Boss攻击 · " : "");
  function render(data, config) {
    exportResult = data;
    exportConfig = config;
    exportButton.hidden = false;
    xlsxButton.hidden = false;
    content.replaceChildren();
    const counts = row();
    counts.append(
      metric("总战斗次数", format(data.total_battles)),
      metric("达标次数", format(data.passed_battles)),
      metric("通过率", format(data.pass_rate) + "%"),
      metric("模拟用时", format(data.elapsed_seconds) + " 秒"),
    );
    content.append(counts);
    if (typeof data.all_alive_rate === "number") {
      const survival = row();
      survival.append(
        metric("全员存活场次", format(data.all_alive_battles)),
        metric("全员存活比例", format(data.all_alive_rate) + "%"),
      );
      content.append(
        survival,
        E(
          "p",
          "存活率按全体定时击杀释放前的状态统计，因该技能死亡仍算存活；未触发则按战斗结束状态。全员存活要求四名队员均参战，比例按总场次计算。",
          "batch-help",
        ),
      );
    }
    if (data.engine === "numba_njit")
      content.append(
        E(
          "p",
          "计算内核：Numba njit · " +
            data.worker_count +
            " 个线程" +
            (data.compilation_seconds > 0
              ? " · 内核加载/编译 " + format(data.compilation_seconds) + " 秒（已计入模拟用时）"
              : ""),
          "batch-help",
        ),
      );
    const damage = row();
    damage.append(
      metric("期望伤害", format(data.expected_damage)),
      metric("最高伤害", format(data.max_damage)),
      metric("最低伤害", format(data.min_damage)),
    );
    content.append(damage);
    const quantiles = row();
    for (const percent of ["1", "5", "10"])
      quantiles.append(metric(percent + "% 分位", format(data.percentiles[percent])));
    const custom = E("label", undefined, "batch-custom"),
      input = E("input");
    input.type = "number";
    input.min = "0";
    input.max = "100";
    input.step = "any";
    input.value = data.custom_percentile;
    input.setAttribute("aria-label", "自定义分位数百分比");
    const value = E("strong", format(data.custom_percentile_damage));
    custom.append(E("span", "自定义分位"), input, E("span", "%"), value);
    quantiles.append(custom);
    content.append(quantiles);
    input.addEventListener("input", () => {
      if (input.value === "" || !input.checkValidity()) return;
      const percent = Number(input.value);
      if (!Number.isFinite(percent) || percent < 0 || percent > 100) return;
      const pos = ((data.sorted_damage.length - 1) * (100 - percent)) / 100,
        lo = Math.floor(pos),
        hi = Math.ceil(pos);
      value.textContent = format(
        data.sorted_damage[lo] + (data.sorted_damage[hi] - data.sorted_damage[lo]) * (pos - lo),
      );
    });
    content.append(
      E(
        "p",
        "达标：" + data.qualification + "。分位数：" + data.quantile_method + "。",
        "batch-help",
      ),
    );
    if (typeof data.all_alive_rate === "number") {
      content.append(E("h3", "角色存活率"));
      const survivalCards = E("div", undefined, "batch-character-means");
      for (const c of data.characters) {
        const card = metric(
          "角色" + c.index + " · " + (c.job || "未选职业"),
          c.enabled ? format(c.survival_rate) + "%" : "未参战",
        );
        if (c.enabled)
          card.append(
            E(
              "span",
              "存活 " + format(c.survived_battles) + " / " + format(data.total_battles) + " 场",
            ),
          );
        survivalCards.append(card);
      }
      content.append(survivalCards);
    }
    content.append(E("h3", "角色期望伤害"));
    const characters = E("div", undefined, "batch-character-means");
    for (const c of data.characters)
      characters.append(
        metric(
          "角色" + c.index + " · " + (c.job || "未选职业") + (c.enabled ? "" : "（未参战）"),
          format(c.expected_damage),
        ),
      );
    content.append(characters);
    content.append(E("h3", "装备特效平均触发次数"));
    for (const c of data.characters) {
      const section = E("section", undefined, "batch-effects");
      section.append(E("h4", "角色" + c.index + " · " + (c.job || "未选职业")));
      if (!c.effects.length)
        section.append(E("p", c.enabled ? "没有启用的装备触发特效" : "未参战"));
      else {
        const list = E("div", undefined, "batch-effect-list");
        for (const effect of c.effects) {
          const item = E("div", undefined, "batch-effect");
          item.append(
            E("span", slots[effect.slot] + " · " + effect.equipment_name + " · " + effect.name),
            E("strong", format(effect.mean_count) + " 次/场"),
          );
          list.append(item);
        }
        section.append(list);
      }
      content.append(section);
    }
    for (const warning of data.warnings) content.append(E("p", warning, "batch-warning"));
  }
  // 是否包含Boss攻击由后端按所选Boss有无技能组决定，结果中的 boss_attacks 标明实际模式。
  const button = document.querySelector("#simulate-batch");
  if (button) {
    // 批量按钮位于“开始单次模拟”右侧的下拉菜单里：选中后或点击菜单外部时收起菜单。
    const menu = button.closest?.("details");
    document.addEventListener?.("click", (event) => {
      if (menu?.open && !menu.contains(event.target)) menu.open = false;
    });
    button.addEventListener("click", async () => {
      if (menu) menu.open = false;
      if (activeTask) return;
      const sourceConfig = window.getTeamConfiguration();
      if (!sourceConfig) return;
      const config = JSON.parse(JSON.stringify(sourceConfig));
      exportResult = null;
      exportConfig = null;
      exportButton.hidden = true;
      xlsxButton.hidden = true;
      button.disabled = true;
      const current = { id: null, cancelled: false };
      activeTask = current;
      minimized = false;
      restore.hidden = true;
      restore.textContent = "查看模拟进度";
      content.replaceChildren();
      progress.textContent = "正在准备批量计算内核，首次运行需要加载或编译…";
      dialog.showModal();
      try {
        const response = await (window.AppRequests?.fetch || fetch)("/api/battle/simulate-batch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(config),
        });
        const task = await response.json();
        if (!response.ok) throw Error(task.error || "批量模拟启动失败");
        current.id = task.job_id;
        if (current.cancelled) {
          await (window.AppRequests?.fetch || fetch)(
            "/api/battle/batch/" + encodeURIComponent(task.job_id) + "/cancel",
            { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" },
          );
          return;
        }
        while (!current.cancelled) {
          const response = await (window.AppRequests?.fetch || fetch)(
            "/api/battle/batch/" + encodeURIComponent(task.job_id),
          );
          const job = await response.json();
          if (!response.ok) throw Error(job.error || "读取模拟进度失败");
          if (current.cancelled || job.status === "cancelled") break;
          progress.textContent =
            job.status === "running" && !job.completed
              ? "正在准备计算内核（首次运行需编译，约30～60秒，之后无需等待）· 已等待 " +
                format(job.elapsed_seconds) +
                " 秒"
              : "已完成 " +
                format(job.completed) +
                " / " +
                format(job.total) +
                " 场 · 用时 " +
                format(job.elapsed_seconds) +
                " 秒";
          restore.textContent =
            "查看模拟进度 · " + format(job.completed) + " / " + format(job.total);
          if (job.status === "failed") throw Error(job.error || "批量模拟失败");
          if (job.status === "complete") {
            render(job.result, config);
            progress.textContent = dataMode(job.result) + "模拟完成";
            restore.textContent = "模拟完成 · 查看结果";
            if (!dialog.open && !minimized) dialog.showModal();
            break;
          }
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
      } catch (error) {
        progress.textContent = error.message;
        restore.textContent = "模拟异常 · 查看详情";
        window.showToast(error.message);
      } finally {
        if (activeTask === current) activeTask = null;
        button.disabled = false;
      }
    });
  }
})();
