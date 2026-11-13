import json
import sys
import tempfile
import threading
import socket
import time
import uvicorn
import urllib.error
import urllib.request
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.app import create_app
from backend.skills.store import SkillStore


def sample(name="测试技能"):
    return {
        "schemaVersion": 1,
        "id": "",
        "name": name,
        "job": "寒霜法师",
        "damageType": "magic",
        "cooldown": 1.5,
        "hitRate": 41,
        "criticalRate": 20,
        "coefficients": dict.fromkeys(
            ["strength", "magic", "technique", "speed", "constitution", "hitPoint", "weaponPower"],
            0,
        ),
        "raceBonus": {"race": "none", "multiplier": 0},
        "effect": None,
    }


with tempfile.TemporaryDirectory() as temp:
    file = Path(temp) / "skills.json"
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(file), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        raise RuntimeError("Uvicorn启动失败")
    base = f"http://127.0.0.1:{port}"

    def request(path, method="GET", body=None, extra=None):
        headers = {"Content-Type": "application/json", **(extra or {})}
        req = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    try:
        assert request("/")[0] == 200
        for asset in [
            "/css/styles.css",
            "/css/skill-editor.css",
            "/js/app.js",
            "/js/skills/model.js",
            "/js/skills/editor.js",
        ]:
            assert request(asset)[0] == 200, asset
        assert request("/docs")[0] == 200
        assert "/api/skills" in json.loads(request("/openapi.json")[1])["paths"]
        assert json.loads(request("/api/skills")[1])["skills"] == []
        code, raw = request("/api/skills", "POST", sample())
        assert code == 201
        saved = json.loads(raw)["skill"]
        assert saved["id"].startswith("skill_")
        assert saved["healingRecipient"] == "self"
        assert saved["targeting"] == "single"
        assert request("/api/skills/" + saved["id"])[0] == 200
        assert request("/api/skills", "POST", saved)[0] == 409
        changed = {
            **saved,
            "name": "更新后的冰锥术",
            "damageType": "none",
            "healingRecipient": "allAllies",
            "targeting": "all",
        }
        assert request("/api/skills/" + saved["id"], "PUT", changed)[0] == 200
        assert SkillStore(file).read()["skills"][0]["name"] == changed["name"]
        assert SkillStore(file).read()["skills"][0]["healingRecipient"] == "allAllies"
        assert (
            json.loads(request("/api/skills/" + saved["id"])[1])["healingRecipient"] == "allAllies"
        )
        assert json.loads(request("/api/skills")[1])["skills"][0]["healingRecipient"] == "allAllies"
        assert (
            json.loads(file.read_text(encoding="utf-8"))["skills"][0]["healingRecipient"]
            == "allAllies"
        )
        assert json.loads(request("/api/skills/" + saved["id"])[1])["targeting"] == "all"
        assert SkillStore(file).read()["skills"][0]["targeting"] == "all"
        before = file.read_bytes()
        assert request("/api/skills", "POST", {**sample(), "hitRate": 101})[0] == 400
        assert file.read_bytes() == before
        assert request("/api/skills/missing", "PUT", {**saved, "id": "missing"})[0] == 404
        assert (
            request("/api/skills/import", "POST", {"schemaVersion": 1, "skills": [saved]})[0] == 409
        )
        assert file.read_bytes() == before
        assert request("/api/skills", "POST", sample(), {"Origin": "https://example.com"})[0] == 403
        assert request("/skill_store.py")[0] == 404
        negative = {**sample("负冷却技能"), "cooldown": -1.2, "lifesteal": 15}
        code, raw = request("/api/skills", "POST", negative)
        assert code == 201, raw
        negative = json.loads(raw)["skill"]
        assert negative["cooldown"] == -1.2 and negative["lifesteal"] == 15
        negative["cooldown"] = -2
        code, raw = request("/api/skills/" + negative["id"], "PUT", negative)
        assert code == 200, raw
        assert json.loads(request("/api/skills/" + negative["id"])[1])["cooldown"] == -2
        imported = {
            **negative,
            "id": "negative-import",
            "name": "导入负冷却技能",
            "cooldown": -1.2,
            "lifesteal": 15,
        }
        code, raw = request(
            "/api/skills/import", "POST", {"schemaVersion": 1, "skills": [imported]}
        )
        assert code == 200, raw
        assert json.loads(request("/api/skills/negative-import")[1])["cooldown"] == -1.2
        assert json.loads(request("/api/skills/negative-import")[1])["lifesteal"] == 15
        assert request("/api/skills", "POST", {**sample(), "lifesteal": 101})[0] == 400
        print(
            "PASS: negative cooldown HTTP create/update/read/import preserves -1.2 and -2 seconds"
        )
        regen = {
            **sample("技能回春"),
            "damageType": "none",
            "effect": {
                "kind": "buff",
                "type": "regeneration",
                "triggerRate": 100,
                "recipient": "healingTargets",
                "skillType": "support",
                "baseValue": 2500,
                "duration": 15,
                "coefficients": dict.fromkeys(
                    ["strength", "magic", "technique", "speed", "constitution"], 0.15
                ),
            },
        }
        code, raw = request("/api/skills", "POST", regen)
        assert code == 201, raw
        regen = json.loads(raw)["skill"]
        assert regen["effect"]["coefficients"]["magic"] == 0.15
        assert (
            json.loads(request("/api/skills/" + regen["id"])[1])["effect"]["recipient"]
            == "healingTargets"
        )
        regen["effect"]["baseValue"] = 2000
        assert request("/api/skills/" + regen["id"], "PUT", regen)[0] == 200
        assert SkillStore(file).read()["skills"][-1]["effect"]["baseValue"] == 2000
        imported_regen = {**regen, "id": "regen-import"}
        assert (
            request("/api/skills/import", "POST", {"schemaVersion": 1, "skills": [imported_regen]})[
                0
            ]
            == 200
        )
        print("PASS: regeneration skill HTTP create/update/read/import and percentage coefficients")
        file.write_text("broken", encoding="utf-8")
        assert request("/api/skills", "POST", sample())[0] == 500
        assert file.read_text() == "broken"
        print(
            "PASS: page, create, read, update, persistence, duplicate/invalid rejection, import conflicts, origin restriction, corrupt-file preservation"
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        assert not thread.is_alive()
