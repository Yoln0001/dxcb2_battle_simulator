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
        from backend.configurations.special import calculate

        for kind, selection, group in [
            ("holies", "selectedHoly", "holy"),
            ("imprints", "selectedImprint", "imprint"),
        ]:
            code, data = req("/api/" + kind)
            assert code == 200 and len(data[kind]) >= 6, data
            seed = next(i for i in data[kind] if i["kind"] == "法师")
            item = {**seed, "name": "自定义" + kind}
            item.pop("id")
            attr = "magic" if group == "holy" else "finalMagicDamage"
            item["attributes"][attr] = 222 if group == "holy" else 23.5
            if kind in ("holies", "imprints"):
                assert req("/api/" + kind, "POST", item)[0] == 405
                item["name"] = seed["name"]
                code, data = req("/api/" + kind + "/" + seed["id"], "PUT", item)
                assert code == 200, data
            else:
                code, data = req("/api/" + kind, "POST", item)
                assert code == 201, data
            saved = data["item"]
            value = saved["attributes"][attr]
            stats, sources = calculate({selection: saved}, {}, [], "寒霜法师")
            assert stats[attr] == value and sources[group + "Custom"]
            assert (
                req("/api/" + kind + "/" + saved["id"], "PUT", {**saved, "name": "修改名称"})[0]
                == 400
            )
            assert (
                req("/api/" + kind + "/" + saved["id"], "PUT", {**item, "attributes": {attr: -1}})[
                    0
                ]
                == 400
            )
            code, data = req(
                "/api/library-sets/" + kind, "POST", {"name": "独立" + kind, "copy": True}
            )
            assert code == 201, data
            library_id = data["item"]["id"]
            copied = req("/api/" + kind + "?library=" + library_id)[1][kind]
            assert any(i["attributes"][attr] == value for i in copied)
            assert (
                req("/api/library-sets/" + kind + "/" + library_id, "PUT", {"name": "重新命名"})[0]
                == 200
            )
            assert req("/api/" + kind + "/" + saved["id"], "DELETE")[0] == 405
            if kind in ("holies", "imprints"):
                assert len(req("/api/holies")[1]["holies"]) == 6
                assert req("/api/holies/" + saved["id"], "PUT", {**saved, "kind": "战士"})[0] == 400
        print(
            "PASS: holy/imprint presets, CRUD, invalid input, independent libraries, rename and selected snapshot panel calculation"
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
