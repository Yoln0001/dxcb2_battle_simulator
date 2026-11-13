import json, socket, sys, tempfile, threading, time, urllib.request, urllib.error
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import uvicorn
from backend.app import create_app
from backend.skills.store import ATTRS

with tempfile.TemporaryDirectory() as temp:
    app = create_app(
        Path(temp) / "skills.json", Path(temp) / "equipment.json", Path(temp) / "groups.json"
    )
    skill = {
        "schemaVersion": 1,
        "id": "skill_a",
        "name": "冰锥",
        "job": "寒霜法师",
        "damageType": "magic",
        "cooldown": 2,
        "hitRate": 100,
        "criticalRate": 0,
        "coefficients": dict.fromkeys(ATTRS + ["weaponPower"], 0),
        "raceBonus": {"race": "none", "multiplier": 0},
        "effect": None,
    }
    app.state.skill_store.save(skill)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)

    def request(method, route, body=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}" + route,
            method=method,
            headers={"Content-Type": "application/json"},
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    try:
        group = {
            "schemaVersion": 1,
            "name": "冰锥循环",
            "job": "寒霜法师",
            "selfBuff": [],
            "opening": ["skill_a"],
            "loops": [
                {"skills": ["skill_a", "skill_a"], "next": "loop2"},
                {"skills": ["skill_a"], "next": "loop1"},
            ],
        }
        code, result = request("POST", "/api/skill-groups", group)
        assert code == 201, result
        item = result["item"]
        assert item["schemaVersion"] == 2
        assert item["subgroups"][0]["skills"][1]["next"] == "legacy_1_0"
        assert request("GET", "/api/skill-groups")[1]["groups"][0] == item
        item["name"] = "修改后"
        assert request("PUT", "/api/skill-groups/" + item["id"], item)[0] == 200
        assert len(app.state.group_store.read()["groups"]) == 1
        bad = dict(group, job="夜魇")
        assert request("POST", "/api/skill-groups", bad)[0] == 400
        bad = dict(group, loops=[{"skills": [], "next": "loop1"}, {"skills": [], "next": "loop2"}])
        assert request("POST", "/api/skill-groups", bad)[0] == 400
        bad = dict(
            group, loops=[{"skills": ["skill_a"], "next": "loop2"}, {"skills": [], "next": "loop1"}]
        )
        assert request("POST", "/api/skill-groups", bad)[0] == 400
        bad = dict(group, opening=["missing"])
        assert request("POST", "/api/skill-groups", bad)[0] == 400
        assert request("POST", "/api/skill-groups", item)[0] == 409
        dynamic = {
            "schemaVersion": 2,
            "name": "动态子组",
            "job": "寒霜法师",
            "entry": "n0",
            "subgroups": [
                {"id": "g0", "skills": [{"id": "n0", "skillId": "skill_a", "next": "n1"}]},
                {"id": "g1", "skills": [{"id": "n1", "skillId": "skill_a", "next": "n0"}]},
            ],
        }
        code, result = request("POST", "/api/skill-groups", dynamic)
        assert code == 201, result
        assert result["item"]["subgroups"][0]["skills"][0]["targetSelection"] == "lowestHp"
        assert [
            {
                k: v
                for k, v in n.items()
                if k not in ("jumpCondition", "releaseCondition", "targetSelection")
            }
            for n in result["item"]["subgroups"][0]["skills"]
        ] == dynamic["subgroups"][0]["skills"]
        assert result["item"]["subgroups"][0]["nextGroup"] == ""
        invalid = dict(dynamic, entry="missing")
        assert request("POST", "/api/skill-groups", invalid)[0] == 400
        invalid = dict(
            dynamic,
            subgroups=[
                {"id": "g0", "skills": [{"id": "n0", "skillId": "skill_a", "next": "missing"}]}
            ],
        )
        assert request("POST", "/api/skill-groups", invalid)[0] == 400
        many = dict(
            dynamic,
            name="多子组",
            subgroups=[
                {
                    "id": f"g{i}",
                    "skills": [{"id": f"n{i}", "skillId": "skill_a", "next": f"n{(i + 1) % 12}"}],
                }
                for i in range(12)
            ],
        )
        assert request("POST", "/api/skill-groups", many)[0] == 201
        plain = dict(
            dynamic,
            name="不跳转",
            subgroups=[
                {
                    "id": "g0",
                    "nextGroup": "g1",
                    "skills": [{"id": "n0", "skillId": "skill_a", "next": ""}],
                },
                {
                    "id": "g1",
                    "nextGroup": "",
                    "skills": [{"id": "n1", "skillId": "skill_a", "next": ""}],
                },
            ],
        )
        code, result = request("POST", "/api/skill-groups", plain)
        assert code == 201, result
        assert result["item"]["subgroups"][0]["nextGroup"] == "g1"
        assert result["item"]["subgroups"][0]["skills"][0]["next"] == ""
        own = dict(
            dynamic,
            name="自身循环",
            subgroups=[
                {
                    "id": "g0",
                    "nextGroup": "g0",
                    "skills": [{"id": "n0", "skillId": "skill_a", "next": ""}],
                }
            ],
        )
        code, result = request("POST", "/api/skill-groups", own)
        assert code == 201, result
        assert result["item"]["subgroups"][0]["nextGroup"] == "g0"
        before = (Path(temp) / "groups.json").read_bytes()
        assert request("POST", "/api/skill-groups", dict(dynamic, name="动态子组"))[0] == 409
        assert (Path(temp) / "groups.json").read_bytes() == before
        copied = dict(dynamic, name="动态子组副本")
        code, created = request("POST", "/api/skill-groups", copied)
        assert code == 201
        assert created["item"]["id"] != item["id"]
        assert (
            request(
                "PUT",
                "/api/skill-groups/" + created["item"]["id"],
                dict(created["item"], name="动态子组"),
            )[0]
            == 409
        )
        assert len(app.state.skill_store.read()["skills"]) == 1
        wait_group = {
            "schemaVersion": 2,
            "name": "等待技能组",
            "job": "寒霜法师",
            "entry": "wait",
            "subgroups": [
                {
                    "id": "wait-sub",
                    "skills": [
                        {"id": "wait", "skillId": "__wait__", "waitDuration": 2.5, "next": ""}
                    ],
                }
            ],
        }
        code, waiting = request("POST", "/api/skill-groups", wait_group)
        assert code == 201, waiting
        assert waiting["item"]["subgroups"][0]["skills"][0]["waitDuration"] == 2.5
        wait_group["name"] = "错误等待"
        wait_group["subgroups"][0]["skills"][0]["waitDuration"] = 0
        assert request("POST", "/api/skill-groups", wait_group)[0] == 400
        print(
            "PASS: skill group create/read/update, ordered repeats, transitions, persistence, invalid and cross-job rejection"
        )
    finally:
        server.should_exit = True
        thread.join(5)
