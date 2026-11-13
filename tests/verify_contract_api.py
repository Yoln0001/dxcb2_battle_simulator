import sys, tempfile, socket, threading, time, json, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from backend.app import create_app

with tempfile.TemporaryDirectory() as d:
    app = create_app(configuration_file=Path(d) / "configurations.json")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)

    def req(path, method="GET", body=None):
        request = urllib.request.Request(
            "http://127.0.0.1:" + str(port) + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        code, data = req("/api/contracts")
        assert code == 200 and len(data["contracts"]) == 14
        bodies = [i for i in data["contracts"] if i["category"] == "constitution"]
        assert {i["archetype"] for i in bodies} == {"安详女神", "吸血伯爵", "月之宗主"}
        assert all(i["baseBonus"] == 12 for i in bodies)
        item = {
            **data["contracts"][0],
            "id": "",
            "name": "我的二级狂怒兽神",
            "level": 2,
            "baseBonus": 17.5,
        }
        code, data = req("/api/contracts", "POST", item)
        assert code == 201, data
        saved = data["item"]
        saved["negativeEffect"] = "痴愚"
        assert req("/api/contracts/" + saved["id"], "PUT", saved)[0] == 200
        assert req("/api/contracts", "POST", {**item, "baseBonus": -1})[0] == 400
        assert req("/api/contracts", "POST", {**item, "negativeEffect": "群体献祭"})[0] == 400
        code, sets = req(
            "/api/library-sets/contracts", "POST", {"name": "另一玩家契约库", "copy": True}
        )
        assert code == 201, sets
        library_id = sets["item"]["id"]
        code, data = req("/api/contracts?library=" + library_id)
        assert len(data["contracts"]) == 15
        copied = data["contracts"][-1]
        copied["name"] = "副库契约"
        assert (
            req("/api/contracts/" + copied["id"] + "?library=" + library_id, "PUT", copied)[0]
            == 200
        )
        assert req("/api/contracts")[1]["contracts"][-1]["name"] == "我的二级狂怒兽神"
        config = {
            "schemaVersion": 1,
            "battle": {"duration": 56, "simulations": 1},
            "target": {"hitPoint": 1e9},
            "librarySelections": {"contracts": library_id},
            "characters": [
                {
                    "name": "角色",
                    "enabled": True,
                    "firstStrike": False,
                    "job": "寒霜法师",
                    "skillGroup": "",
                    "contract": "不激活",
                    "negativeEffect": "无",
                    "stats": {"strength": 100},
                    "equipment": {},
                    "selectedContract": saved,
                }
                for _ in range(4)
            ],
        }
        from backend.configurations.store import validate_config

        cleaned = validate_config(config)
        assert (
            cleaned["characters"][0]["selectedContract"]["baseBonus"] == 17.5
            and cleaned["librarySelections"]["contracts"] == library_id
        )
        assert req("/api/contracts/" + saved["id"], "DELETE")[0] == 200
        assert (
            req("/api/library-sets/contracts/" + library_id, "PUT", {"name": "重命名契约库"})[0]
            == 200
        )
        assert req("/api/library-sets/contracts/" + library_id, "DELETE")[0] == 200
        print(
            "PASS: contract HTTP presets/create/update/delete, invalid rejection, independent named-library copy/rename/delete and configuration snapshots"
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
