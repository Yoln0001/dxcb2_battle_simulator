import sys, json, tempfile, socket, threading, time, urllib.request, urllib.error
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import uvicorn
from backend.app import create_app

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        app = create_app(temp / "skills.json", temp / "equipment.json", temp / "groups.json")
        skill = {
            "schemaVersion": 1,
            "id": "ice",
            "name": "冰锥术",
            "job": "寒霜法师",
            "damageType": "magic",
            "cooldown": -1,
            "hitRate": 100,
            "criticalRate": 0,
            "coefficients": {
                k: (1 if k == "magic" else 0)
                for k in [
                    "strength",
                    "magic",
                    "technique",
                    "speed",
                    "constitution",
                    "hitPoint",
                    "weaponPower",
                ]
            },
            "raceBonus": {"race": "none", "multiplier": 0},
            "effect": None,
        }
        app.state.skill_store.save(skill)
        group = {
            "schemaVersion": 2,
            "id": "loop",
            "name": "测试循环",
            "job": "寒霜法师",
            "entry": "node",
            "subgroups": [
                {
                    "id": "sub",
                    "nextGroup": "sub",
                    "skills": [{"id": "node", "skillId": "ice", "next": ""}],
                }
            ],
            "opening": [],
            "selfBuff": [],
        }
        app.state.group_store.save(group)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        url = f"http://127.0.0.1:{port}"

        def post(payload):
            req = urllib.request.Request(
                url + "/api/battle/simulate-single",
                method="POST",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload).encode(),
            )
            try:
                with urllib.request.urlopen(req) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        try:
            config = {
                "seed": 9,
                "battle": {"duration": 3},
                "target": {"hitPoint": 100000, "magicVulnerability": 1, "physicalVulnerability": 1},
                "characters": [
                    {
                        "enabled": True,
                        "job": "寒霜法师",
                        "stats": {"magic": 100, "constitution": 100, "strength": 0, "speed": 99},
                        "equipment": {},
                        "skillGroup": "loop",
                    }
                    for _ in range(4)
                ],
            }
            code, data = post(config)
            assert code == 200, data
            assert data == post(config)[1]
            assert [f["time"] for f in data["timeline"]] == [0, 1.5, 2, 2.5, 3]
            assert data["total_damage"] == 1600
            config["battle"]["simulations"] = 10
            req = urllib.request.Request(
                url + "/api/battle/simulate-batch",
                method="POST",
                headers={"Content-Type": "application/json"},
                data=json.dumps(config).encode(),
            )
            with urllib.request.urlopen(req) as response:
                task = json.load(response)
            deadline = time.monotonic() + 10
            while True:
                with urllib.request.urlopen(
                    url + "/api/battle/batch/" + task["job_id"]
                ) as response:
                    job = json.load(response)
                if job["status"] != "running":
                    break
                assert time.monotonic() < deadline
                time.sleep(0.02)
            assert job["status"] == "complete", job
            assert job["result"]["total_battles"] == 10 and job["result"]["expected_damage"] == 1600
            assert job["result"]["elapsed_seconds"] >= 0
            print("PASS: live batch HTTP start/progress/result and elapsed")
            cancel_config = json.loads(json.dumps(config))
            cancel_config["battle"].update(simulations=10000, duration=200)
            req = urllib.request.Request(
                url + "/api/battle/simulate-batch",
                method="POST",
                headers={"Content-Type": "application/json"},
                data=json.dumps(cancel_config).encode(),
            )
            with urllib.request.urlopen(req) as response:
                cancel_task = json.load(response)
            req = urllib.request.Request(
                url + "/api/battle/batch/" + cancel_task["job_id"] + "/cancel",
                method="POST",
                headers={"Content-Type": "application/json"},
                data=b"{}",
            )
            with urllib.request.urlopen(req) as response:
                assert response.status == 200
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with urllib.request.urlopen(
                    url + "/api/battle/batch/" + cancel_task["job_id"]
                ) as response:
                    cancelled = json.load(response)
                if cancelled["status"] != "running":
                    break
                time.sleep(0.05)
            assert cancelled["status"] == "cancelled", cancelled
            print("PASS: live HTTP JSON cancellation accepted and background workers stopped")

            config["characters"][0]["skillGroup"] = "missing"
            assert post(config)[0] == 400
            with urllib.request.urlopen(url) as response:
                html = response.read().decode()
                assert 'id="simulate-single"' in html and "js/battle/timeline.js?v=" in html
                assert response.headers["Cache-Control"] == "no-store"
            with urllib.request.urlopen(url + "/js/battle/timeline.js") as response:
                assert "renderSnapshot" in response.read().decode()
            assert len(app.state.skill_store.read()["skills"]) == 1
            print(
                "PASS: live HTTP single simulation, negative cooldown persistence, deterministic seed, validation, UI assets and isolated libraries"
            )
        finally:
            server.should_exit = True
            thread.join(5)
