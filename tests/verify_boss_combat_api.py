"""Real HTTP checks for the isolated Boss routes using temporary libraries."""

import sys, json, tempfile, socket, threading, time, urllib.request, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app import create_app
import uvicorn
from verify_boss_combat import fixture


def main():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        app = create_app(
            root / "skills.json",
            root / "equipment.json",
            root / "groups.json",
            configuration_file=root / "config.json",
        )
        cfg, _, skills, groups = fixture()
        for c in cfg["characters"]:
            c["job"] = "寒霜法师"
        skills["s"]["job"] = "寒霜法师"
        groups["g"]["job"] = "寒霜法师"
        skill = {
            **skills["s"],
            "schemaVersion": 1,
            "id": "s",
            "raceBonus": {"race": "none", "multiplier": 0},
        }
        skill["coefficients"] = {
            k: skill["coefficients"].get(k, 0)
            for k in (
                "strength",
                "magic",
                "technique",
                "speed",
                "constitution",
                "hitPoint",
                "weaponPower",
            )
        }
        app.state.skill_store.save(skill)
        app.state.group_store.save(
            {
                **groups["g"],
                "schemaVersion": 2,
                "id": "g",
                "name": "测试",
                "opening": [],
                "selfBuff": [],
            }
        )
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        until = time.monotonic() + 10
        while not server.started and time.monotonic() < until:
            time.sleep(0.02)

        def req(path, payload=None):
            request = urllib.request.Request(
                "http://127.0.0.1:" + str(port) + path,
                method="POST" if payload is not None else "GET",
                data=json.dumps(payload).encode() if payload is not None else None,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request) as response:
                return json.load(response)

        try:

            def boss_damage(result):
                return any(
                    e["type"] == "boss_skill_damage"
                    for f in result["timeline"]
                    for e in f["events"]
                )

            def batch(path, config):
                job = req(path, config)
                until = time.monotonic() + 120
                while True:
                    status = req("/api/battle/batch/" + job["job_id"])
                    if status["status"] != "running":
                        break
                    assert time.monotonic() < until
                    time.sleep(0.05)
                assert status["status"] == "complete", status
                assert status["result"]["engine"] == "numba_njit"
                return status["result"]

            # 所选Boss有技能组：新路径和旧别名都包含Boss攻击。
            for path in ("/api/battle/simulate-single", "/api/battle/simulate-single-with-boss"):
                result = req(path, cfg)
                assert result["boss_attacks"] is True and boss_damage(result), path
            for path in ("/api/battle/simulate-batch", "/api/battle/simulate-batch-with-boss"):
                assert batch(path, cfg)["boss_attacks"] is True, path
            # 所选Boss没有技能组：自动按普通模拟计算，不报错。
            cfg["target"]["selectedBoss"]["skillGroup"]["entry"] = ""
            cfg["target"]["selectedBoss"]["skillGroup"]["subgroups"] = []
            for path in ("/api/battle/simulate-single", "/api/battle/simulate-single-with-boss"):
                result = req(path, cfg)
                assert result["boss_attacks"] is False and not boss_damage(result), path
            for path in ("/api/battle/simulate-batch", "/api/battle/simulate-batch-with-boss"):
                assert batch(path, cfg)["boss_attacks"] is False, path
            print(
                "PASS: merged HTTP routes choose Boss combat from the selected Boss skill group; "
                "legacy aliases, njit batch in both modes and shared polling"
            )
        finally:
            server.should_exit = True
            thread.join(5)
            sock.close()


if __name__ == "__main__":
    main()
