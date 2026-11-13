"""一次运行全部验证脚本并汇总结果。

用法（在项目根目录）：
    python tests/run_all.py                 运行全部 verify_*.py 和 verify_*.cjs
    python tests/run_all.py batch boss      只运行文件名包含这些关键字的脚本
    python tests/run_all.py --jobs 4        并行运行（接口测试各自使用空闲端口时才安全，默认1）

结果写入 tests/_results/summary.txt（汇总）和 tests/_results/results.json（含失败输出），
每完成一个脚本就更新一次；有失败时退出码为1。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
RESULTS = TESTS / "_results"
# 需要仓库之外的原始参考脚本，默认不运行。
SKIPPED = {"verify_equivalence.py": "需要原始参考脚本"}


def project_python():
    """优先使用项目虚拟环境的解释器，避免用到没装依赖的系统Python。"""
    for folder in (".venv", "venv"):
        for relative in ("Scripts/python.exe", "bin/python"):
            candidate = ROOT / folder / relative
            if candidate.exists():
                return str(candidate)
    return sys.executable


PYTHON = project_python()


def run_one(path, node, timeout):
    command = [PYTHON, str(path)] if path.suffix == ".py" else [node, str(path)]
    # 个别脚本没有自行把项目根目录加入模块搜索路径。
    search = os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH", "")]))
    environment = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONPATH": search,
    }
    started = time.perf_counter()
    try:
        done = subprocess.run(
            command, cwd=ROOT, env=environment, capture_output=True, timeout=timeout
        )
        code = done.returncode
        output = (done.stdout + done.stderr).decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as error:
        code = "timeout"
        output = ((error.stdout or b"") + (error.stderr or b"")).decode("utf-8", errors="replace")
    seconds = round(time.perf_counter() - started, 2)
    status = "pass" if code == 0 else "timeout" if code == "timeout" else "fail"
    return {
        "name": path.name,
        "status": status,
        "seconds": seconds,
        "returncode": code,
        "output": output[-4000:]
        if status != "pass"
        else output.strip().splitlines()[-1:] and output.strip().splitlines()[-1][:300] or "",
    }


def write_results(rows, total, started, finished):
    RESULTS.mkdir(exist_ok=True)
    counts = {
        key: sum(row["status"] == key for row in rows)
        for key in ("pass", "fail", "timeout", "skip")
    }
    lines = [
        ("已完成" if finished else "运行中") + f"：{len(rows)}/{total}",
        f"通过 {counts['pass']}，失败 {counts['fail']}，超时 {counts['timeout']}，跳过 {counts['skip']}",
        f"用时 {time.perf_counter() - started:.1f} 秒；解释器 {PYTHON}",
        "",
    ]
    for row in sorted(rows, key=lambda row: (row["status"] == "pass", row["name"])):
        lines.append(f"{row['status'].upper():8}{row['seconds']:8.2f}s  {row['name']}")
    (RESULTS / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (RESULTS / "results.json").write_text(
        json.dumps(
            {"finished": finished, "total": total, "counts": counts, "results": rows},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return counts


def main():
    parser = argparse.ArgumentParser(description="运行全部验证脚本")
    parser.add_argument("keywords", nargs="*", help="只运行文件名包含任一关键字的脚本")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=900, help="单个脚本的超时秒数")
    parser.add_argument("--no-node", action="store_true", help="不运行前端 .cjs 脚本")
    args = parser.parse_args()
    node = None if args.no_node else shutil.which("node")
    paths = sorted(TESTS.glob("verify_*.py")) + (sorted(TESTS.glob("verify_*.cjs")) if node else [])
    if args.keywords:
        paths = [path for path in paths if any(word in path.name for word in args.keywords)]
    rows = [
        {
            "name": path.name,
            "status": "skip",
            "seconds": 0.0,
            "returncode": None,
            "output": SKIPPED[path.name],
        }
        for path in paths
        if path.name in SKIPPED
    ]
    paths = [path for path in paths if path.name not in SKIPPED]
    total = len(paths) + len(rows)
    started = time.perf_counter()
    print("解释器：" + PYTHON, flush=True)
    write_results(rows, total, started, False)
    if not node and not args.no_node:
        print("未找到 node，跳过前端 .cjs 脚本")
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for row in pool.map(lambda path: run_one(path, node, args.timeout), paths):
            rows.append(row)
            print(f"{row['status'].upper():8}{row['seconds']:8.2f}s  {row['name']}", flush=True)
            write_results(rows, total, started, False)
    counts = write_results(rows, total, started, True)
    print(
        f"通过 {counts['pass']}，失败 {counts['fail']}，超时 {counts['timeout']}，跳过 {counts['skip']}；详情见 tests/_results/"
    )
    return 1 if counts["fail"] or counts["timeout"] else 0


if __name__ == "__main__":
    sys.exit(main())
