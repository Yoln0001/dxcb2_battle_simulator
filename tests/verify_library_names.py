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
        for kind in ("equipment", "stones", "people", "contracts", "trophies", "bosses"):
            route = "/api/library-sets/" + kind
            code, data = req(route + "/__default__", "PUT", {"name": kind + "默认改名"})
            assert code == 200, data
            assert req(route)[1]["displayNames"]["__default__"] == kind + "默认改名"
            assert req(route + "/__default__", "PUT", {"name": "  "})[0] == 400
            code, data = req(route, "POST", {"name": kind + "分库"})
            assert code == 201, data
            library_id = data["item"]["id"]
            assert req(route + "/" + library_id, "PUT", {"name": kind + "默认改名"})[0] == 409
            assert req(route + "/" + library_id, "PUT", {"name": kind + "分库改名"})[0] == 200
            assert req(route)[1]["displayNames"]["__default__"] == kind + "默认改名"
        assert req("/api/library-sets/equipment/__wiki__", "PUT", {"name": "百科新名称"})[0] == 200
        assert req("/api/library-sets/equipment")[1]["displayNames"]["__wiki__"] == "百科新名称"
        assert req("/api/library-sets/people/__wiki__", "PUT", {"name": "无效"})[0] == 404
        assert not list(Path(d).glob("*.json")) == []
        print(
            "PASS: six default and named libraries rename persistently; wiki rename; empty and duplicate rejection"
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
