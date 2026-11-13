const fs = require("fs"),
  vm = require("vm"),
  assert = require("assert");
const calls = [];
let version = 1,
  release,
  fail = false;
const configurations = new Promise((resolve) => (release = resolve));
const context = {
  URL,
  location: { protocol: "http:", href: "http://127.0.0.1:8000/", origin: "http://127.0.0.1:8000" },
  window: { PlayerLibraries: { current: {} } },
  fetch: async (url, options = {}) => {
    calls.push([url, options.method || "GET"]);
    if (url === "/api/configurations") return configurations;
    if ((options.method || "GET") !== "GET") version++;
    if (fail) {
      fail = false;
      throw Error("offline");
    }
    return new Response(JSON.stringify({ version }), { status: 200 });
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync("frontend/js/ui/requests.js", "utf8"), context);
(async () => {
  const api = context.window.AppRequests;
  const initial = api.fetch("/api/rings?library=selected");
  assert.equal(calls.length, 1);
  release(
    new Response(
      JSON.stringify({
        activeId: "chosen",
        configurations: [
          {
            id: "chosen",
            configuration: { librarySelections: { rings: "selected", equipment: "gear" } },
          },
        ],
      }),
    ),
  );
  await api.ready;
  assert.equal(context.window.PlayerLibraries.current.rings, "selected");
  assert.equal(api.selections.equipment, "gear");
  const response = await initial;
  assert.equal((await response.json()).version, 1);
  const [a, b] = await Promise.all([
    api.fetch("/api/rings?library=selected"),
    api.fetch("/api/rings?library=selected"),
  ]);
  assert.equal((await a.json()).version, 1);
  assert.equal((await b.json()).version, 1);
  assert.equal(calls.filter(([u]) => u.startsWith("/api/rings")).length, 1);
  await api.fetch("/api/configurations");
  assert.equal(calls.filter(([u]) => u === "/api/configurations").length, 1);
  await api.fetch("/api/rings?library=");
  await api.fetch("/api/rings");
  assert.equal(calls.filter(([u]) => u === "/api/rings" || u === "/api/rings?library=").length, 1);
  await api.fetch("/api/rings", { method: "POST", body: "{}" });
  assert.equal((await (await api.fetch("/api/rings?library=selected")).json()).version, 2);
  api.finish();
  const before = calls.length;
  await api.fetch("/api/rings");
  await api.fetch("/api/rings");
  assert.equal(calls.length, before + 2);
  fail = true;
  await assert.rejects(api.fetch("/api/people"), /offline/);
  await api.fetch("/api/people");
  console.log(
    "PASS: saved library selections precede reads; startup duplicates coalesced; independent response bodies; writes invalidate; live reads resume after startup; failures retry",
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
