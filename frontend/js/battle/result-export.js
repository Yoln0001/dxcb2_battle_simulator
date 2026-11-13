"use strict";
(() => {
  const format = (n) => Number(n ?? 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
  const integer = (n) =>
    Number(n ?? 0).toLocaleString("zh-CN", { maximumFractionDigits: 0, useGrouping: false });
  const roundedAttributes = new Set([
    "strength",
    "magic",
    "technique",
    "speed",
    "constitution",
    "armor",
    "resistance",
    "weaponPower",
  ]);
  const pairs = [
    ["strength", "力量", "constitution", "体质"],
    ["magic", "魔力", "armor", "护甲"],
    ["technique", "技巧", "resistance", "抗性"],
    ["speed", "速度", "weaponPower", "武威"],
    ["hitRate", "命中率", "criticalMultiplier", "暴击伤害系数"],
    ["physicalDamage", "物理伤害", "magicDamage", "魔法伤害"],
  ];
  const percents = new Set(["hitRate", "criticalMultiplier", "physicalDamage", "magicDamage"]);
  function draw(data, config) {
    const canvas = document.createElement("canvas"),
      scale = 2,
      width = 1600,
      height = 790;
    canvas.width = width * scale;
    canvas.height = height * scale;
    const ctx = canvas.getContext("2d");
    ctx.scale(scale, scale);
    const text = (value, x, y, size = 18, color = "#284553", bold = false) => {
      ctx.font = (bold ? "600 " : "") + size + 'px "Microsoft YaHei", "PingFang SC", sans-serif';
      ctx.fillStyle = color;
      ctx.fillText(String(value), x, y);
    };
    ctx.fillStyle = "#f4f7f8";
    ctx.fillRect(0, 0, width, height);
    text("批量战斗结果", 40, 58, 30, "#284553", true);
    const boss = config.target?.selectedBoss?.name || config.target?.name || "未命名目标";
    text(boss + " · " + (data.boss_attacks ? "包含 Boss 攻击" : "普通批量模拟"), 40, 94, 19);
    text("战斗场次：" + format(data.total_battles), 40, 147, 22);
    text("通过率：" + format(data.pass_rate) + "%", 430, 147, 22);
    text(
      "全员存活比例：" +
        (typeof data.all_alive_rate === "number" ? format(data.all_alive_rate) + "%" : "未统计"),
      820,
      147,
      22,
    );
    text("达标场次：" + format(data.passed_battles), 40, 182, 16, "#607781");
    if (typeof data.all_alive_rate === "number")
      text("全员存活场次：" + format(data.all_alive_battles), 820, 182, 16, "#607781");
    text("队伍期望伤害：" + format(data.expected_damage), 40, 221, 22, "#008f83", true);
    for (let i = 0; i < 4; i++) {
      const c = data.characters.find((row) => row.index === i + 1) || {},
        source = config.characters?.[i] || {},
        stats = source.stats || {},
        x = 40 + i * 385,
        y = 253,
        w = 365;
      ctx.fillStyle = "#fff";
      ctx.fillRect(x, y, w, 427);
      ctx.strokeStyle = "#dbe5e9";
      ctx.strokeRect(x, y, w, 427);
      text(
        "角色" + (i + 1) + " · " + (c.job || source.job || "未选职业"),
        x + 16,
        y + 34,
        20,
        "#284553",
        true,
      );
      text(c.enabled ? "参战" : "未参战", x + 16, y + 64, 15, "#607781");
      text("期望伤害", x + 16, y + 101, 16, "#607781");
      text(integer(c.expected_damage), x + 16, y + 133, 24, "#008f83", true);
      if (typeof c.survival_rate === "number" && c.enabled)
        text("存活率：" + format(c.survival_rate) + "%", x + 16, y + 82, 14, "#607781");
      text("面板属性 · 开战前数值", x + 16, y + 169, 15, "#607781");
      pairs.forEach((pair, r) => {
        for (let col = 0; col < 2; col++) {
          const key = pair[col * 2],
            label = pair[col * 2 + 1],
            left = x + 16 + col * 173,
            top = y + 188 + r * 35;
          ctx.fillStyle = r % 2 ? "#fff" : "#f1f5f6";
          ctx.fillRect(left, top, 166, 32);
          text(label, left + 6, top + 13, key === "criticalMultiplier" ? 11 : 12, "#607781");
          const value = Object.hasOwn(stats, key)
            ? (roundedAttributes.has(key) ? integer(stats[key]) : String(Number(stats[key]))) +
              (percents.has(key) ? "%" : "")
            : "—";
          text(value, left + 6, top + 28, 14);
        }
      });
    }
    text("通过率：在设定时间内击败目标的场次 / 总场次。", 40, 718, 16, "#607781");
    text(
      typeof data.all_alive_rate === "number"
        ? "全员存活：四名队员均参战且存活至全体定时击杀前（未触发则按战斗结束状态），占总场次的比例。"
        : "全员存活比例：未统计。",
      40,
      748,
      16,
      "#607781",
    );
    return canvas;
  }
  async function download(data, config) {
    if (document.fonts?.ready) await document.fonts.ready;
    const canvas = draw(data, config);
    const blob = await new Promise((resolve, reject) =>
      canvas.toBlob(
        (value) => (value ? resolve(value) : reject(Error("生成 PNG 失败"))),
        "image/png",
      ),
    );
    const url = URL.createObjectURL(blob),
      link = document.createElement("a");
    link.href = url;
    link.download = "战斗结果-" + data.total_battles + "场-" + (data.seed ?? Date.now()) + ".png";
    document.body.append(link);
    try {
      link.click();
    } finally {
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  }
  window.BatchResultExport = { draw, download };
})();
