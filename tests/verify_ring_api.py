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
        code, data = req("/api/rings")
        assert code == 200 and len(data["rings"]) == 12, data
        item = {**data["rings"][0], "id": "", "name": "手动空环", "gainValue": 13.7}
        code, data = req("/api/rings", "POST", item)
        assert code == 201, data
        assert data["item"]["gainValue"] == 13.7
        saved = data["item"]
        saved["gainValue"] = 19.5
        assert req("/api/rings/" + saved["id"], "PUT", saved)[1]["item"]["gainValue"] == 19.5
        assert req("/api/rings", "POST", {**item, "gainValue": -1})[0] == 400
        assert req("/api/rings", "POST", {**item, "mainAttribute": "invalid"})[0] == 400
        from backend.rings.store import validate_item, base_values, ATTRIBUTES

        for kind in ("sky", "water", "fire", "earth"):
            for first in ATTRIBUTES:
                for second in ATTRIBUTES:
                    ring = validate_item(
                        {
                            **item,
                            "kind": kind,
                            "mainAttribute": first,
                            "secondaryAttribute": second,
                            "mainValue": 810,
                            "secondaryValue": 580,
                            "restriction": "fragile" if kind == "fire" else "none",
                            "gain": "physicalBlock"
                            if kind == "earth"
                            else "abnormalBonus"
                            if kind == "water"
                            else "physicalMagicDamage",
                        }
                    )
                    values = base_values(ring)
                    assert sum(values.values()) == 1390
                    if first == second:
                        assert values[first] == 1390
        saved["mainAttribute"] = "constitution"
        saved["secondaryAttribute"] = "speed"
        saved["mainValue"] = 880
        saved["secondaryValue"] = 640
        updated = req("/api/rings/" + saved["id"], "PUT", saved)[1]["item"]
        assert updated["mainAttribute"] == "constitution" and updated["secondaryValue"] == 640
        code, data = req("/api/library-sets/rings", "POST", {"name": "我的域之环库", "copy": True})
        assert code == 201, data
        library_id = data["item"]["id"]
        assert len(req("/api/rings?library=" + library_id)[1]["rings"]) == 13
        assert (
            req("/api/library-sets/rings/" + library_id, "PUT", {"name": "改名域之环库"})[0] == 200
        )
        assert req("/api/rings/" + saved["id"], "DELETE")[0] == 200
        print(
            "PASS: ring presets, manual gain values, create/update/delete, independent library copy/rename and invalid rejection"
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
