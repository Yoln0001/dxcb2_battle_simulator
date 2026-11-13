"""大批量时查询任务不回传完整伤害列表，自定义分位数由服务端按同一份数据精确计算。"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import backend.batch_jobs as module
from backend.batch_jobs import BatchJobs
from engine.runtime.batch import percentile
from engine.runtime.initialization import BattleConfigurationError


def finished(damage):
    return {
        "status": "complete",
        "completed": len(damage),
        "total": len(damage),
        "started": 0.0,
        "elapsed_seconds": 1.5,
        "cancel_event": None,
        "result": {"total_battles": len(damage), "sorted_damage": damage, "pass_rate": 50.0},
    }


def browser_percentile(damage, percent):
    # 与 frontend/js/battle/batch.js 中的本地算法相同。
    position = (len(damage) - 1) * (100 - percent) / 100
    low, high = math.floor(position), math.ceil(position)
    return damage[low] + (damage[high] - damage[low]) * (position - low)


jobs = BatchJobs()
small = [float(i * i) for i in range(1000)]
large = [float(i) * 1.5 for i in range(module.SORTED_DAMAGE_LIMIT + 1)]
jobs.jobs["small"] = finished(small)
jobs.jobs["large"] = finished(large)
jobs.jobs["running"] = {**finished(small), "status": "running", "result": None}

# 场次不超过上限：结果与原来一样带完整列表。
value = jobs.get("small")
assert value["result"]["sorted_damage"] == small
assert "sorted_damage_omitted" not in value["result"]
assert "started" not in value and "cancel_event" not in value and value["elapsed_seconds"] == 1.5

# 场次超过上限：不回传列表，其余字段不变，服务端保存的数据不受影响。
value = jobs.get("large")
assert "sorted_damage" not in value["result"] and value["result"]["sorted_damage_omitted"] is True
assert value["result"]["total_battles"] == len(large) and value["result"]["pass_rate"] == 50.0
assert jobs.jobs["large"]["result"]["sorted_damage"] is large
assert jobs.get("running")["result"] is None

# 服务端分位数与引擎算法、浏览器本地算法逐位相同，包括极端分位。
for name, damage in (("small", small), ("large", large)):
    for percent in (0, 0.001, 0.1, 1, 5, 33.333, 50, 99, 99.9, 99.999, 100):
        answer = jobs.percentile(name, percent)
        assert answer == {"percent": percent, "damage": percentile(damage, percent)}
        assert answer["damage"] == browser_percentile(damage, percent), (name, percent)
assert jobs.percentile("large", 0)["damage"] == large[-1]
assert jobs.percentile("large", 100)["damage"] == large[0]

for key, percent in (("missing", 50), ("running", 50), ("small", 101), ("small", -1)):
    try:
        jobs.percentile(key, percent)
    except BattleConfigurationError:
        pass
    else:
        raise AssertionError((key, percent))
print(
    "PASS: large batch results omit the damage list; server percentiles match the engine and "
    "browser formulas exactly at extreme quantiles; small batches unchanged"
)
