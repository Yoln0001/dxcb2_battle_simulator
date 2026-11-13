"""对比两种给每场战斗准备随机数状态的方式，使用与 benchmark_compiled_batch.py 相同的队伍。

旧：在Python里为每场创建 random.Random(seed) 并导出状态，再交给内核（单线程）。
新：只把种子交给内核，由内核在各线程里播种。两者每场结果必须完全相同。

    python tests/benchmark_seeding.py [场次，默认20000]
"""

import ast
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.equipment.jobs import JOB_FAMILIES
from engine.runtime.compiled.kernel import chunk, chunk_seeded
from engine.runtime.compiled.prepare import prepare


def fixture():
    path = Path(__file__).with_name("benchmark_compiled_batch.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = []
    for statement in function.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "reference" for t in statement.targets
        ):
            break
        body.append(statement)
    ns = {"__file__": str(path), "Path": Path, "json": json}
    exec(compile(ast.Module(body=body, type_ignores=[]), "saved_fixture", "exec"), ns)
    config, eq, sl, gl = [ns[k] for k in ("config", "eq", "sl", "gl")]
    # 原基准按装备在库文件里的位置取装备，库内容变化后位置会对不上；
    # 这里和 benchmark_boss_combat.py 一样，位置失效时按槽位类型和武器职业重新挑一件。
    for row in config["characters"]:
        used = set()
        for slot, old in row["equipment"].items():
            category = "accessory" if slot.startswith("accessory") else slot
            choices = [
                e
                for e in eq.values()
                if e["id"] not in used
                and e["category"] == category
                and (
                    slot != "weapon"
                    or not e.get("weaponJob")
                    or e["weaponJob"] == JOB_FAMILIES[row["job"]]
                )
            ]
            row["equipment"][slot] = (
                old if any(e["id"] == old for e in choices) else choices[0]["id"] if choices else ""
            )
            used.add(row["equipment"][slot])
    return config, eq, sl, gl


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    config, eq, sl, gl = fixture()
    arrays = prepare(config, eq, sl, gl)[0]
    rng = random.Random(345)
    seeds = [rng.randrange(2**53) for _ in range(count)]
    warm = np.array(seeds[:1], dtype=np.int64)
    chunk(*arrays, np.array([random.Random(seeds[0]).getstate()[1]], dtype=np.uint32))
    chunk_seeded(*arrays, warm)

    started = time.perf_counter()
    building = 0.0
    old = []
    for begin in range(0, count, 128):
        mark = time.perf_counter()
        states = np.array(
            [random.Random(seed).getstate()[1] for seed in seeds[begin : begin + 128]],
            dtype=np.uint32,
        )
        building += time.perf_counter() - mark
        old.append(chunk(*arrays, states)[0])
    old_seconds = time.perf_counter() - started

    started = time.perf_counter()
    new = []
    for begin in range(0, count, 128):
        new.append(chunk_seeded(*arrays, np.array(seeds[begin : begin + 128], dtype=np.int64))[0])
    new_seconds = time.perf_counter() - started

    assert np.array_equal(np.concatenate(old), np.concatenate(new)), "两种方式的结果不一致"
    print(count, "场，每场结果完全相同")
    print(
        "旧：%.3f 秒（其中在Python里准备随机数状态 %.3f 秒，占 %.0f%%）"
        % (old_seconds, building, building / old_seconds * 100)
    )
    print("新：%.3f 秒，为旧的 %.0f%%" % (new_seconds, new_seconds / old_seconds * 100))


if __name__ == "__main__":
    main()
