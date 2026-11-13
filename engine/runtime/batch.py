"""Batch statistics using the same combat engine without timeline snapshots."""

import random
import os
import time
import math
from .simulation import SingleBattle
from .initialization import BattleConfigurationError, nonnegative


def percentile(sorted_values, percent):
    percent = nonnegative(percent, "分位数")
    if percent > 100:
        raise BattleConfigurationError("分位数应为0到100%")
    position = (len(sorted_values) - 1) * (100 - percent) / 100
    low = math.floor(position)
    high = math.ceil(position)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def batch_parameters(config):
    count = config.get("battle", {}).get("simulations", 100)
    if type(count) is not int or not 1 <= count <= 1000000:
        raise BattleConfigurationError("模拟次数应为1到1000000的整数")
    custom = nonnegative(config.get("customPercentile", 50), "自定义分位数")
    if custom > 100:
        raise BattleConfigurationError("自定义分位数应为0到100%")
    if nonnegative(config.get("target", {}).get("hitPoint", 0), "目标生命值") <= 0:
        raise BattleConfigurationError("批量模拟需要大于0的目标生命值，以判断达标")
    return count, custom


def simulate_batch(
    config,
    equipment,
    skills,
    groups,
    *,
    progress=None,
    parallel=None,
    workers=None,
    cancel_event=None,
    engine="auto",
    boss_attacks=False,
):
    started = time.perf_counter()
    count, custom = batch_parameters(config)
    seed = config.get("seed")
    battle_class = SingleBattle
    if boss_attacks:
        from .boss_simulation import BossBattle

        battle_class = BossBattle
    # Validate with the same constructor before running.
    battle_class(config, equipment, skills, groups, seed=seed, record_timeline=False)
    seed = seed if seed is not None else random.SystemRandom().randrange(2**53)
    rng = random.Random(seed)
    damage = []
    passed = 0
    all_alive = 0
    char_survived = [0] * 4
    char_damage = [0.0] * 4
    effects = [{} for _ in range(4)]
    warnings = set()
    for i, row in enumerate(config["characters"]):
        if not row["enabled"]:
            continue
        for slot in ("weapon", "armor", "accessory1", "accessory2", "stone"):
            item = equipment.get(row["equipment"].get(slot))
            if item and item.get("triggerEnabled"):
                for effect in item.get("triggerEffects", []):
                    if effect.get("effect"):
                        key = (
                            slot,
                            item["id"],
                            effect["name"] or item["name"],
                            effect["triggerType"],
                            effect["effect"]["kind"],
                        )
                        effects[i].setdefault(key, 0)
    worker_count = min(32, max(1, (os.cpu_count() or 1) - 2)) if workers is None else workers
    if type(worker_count) is not int or not 1 <= worker_count <= 32:
        raise BattleConfigurationError("并行进程数应为1到32")
    metadata = {"engine": "python", "compilation_seconds": 0.0}
    compiled = None
    if engine not in ("auto", "python", "numba"):
        raise BattleConfigurationError("未知批量计算内核")
    if engine != "python":
        try:
            # prepare本身不依赖Numba，这里先确认已安装，缺失时才能正确回退到Python内核。
            from importlib.util import find_spec

            if find_spec("numba") is None:
                raise ImportError("numba")
            from .compiled.prepare import prepare, UnsupportedConfiguration

            compiled = prepare(config, equipment, skills, groups, boss_attacks=boss_attacks)
        except ImportError:
            if engine == "numba":
                raise BattleConfigurationError("Numba未安装，请安装项目requirements.txt")
            warnings.add("Numba不可用，本次使用Python批量计算。")
        except UnsupportedConfiguration as error:
            if engine == "numba":
                raise BattleConfigurationError(str(error)) from error
            warnings.add("此配置暂不支持编译内核，使用Python：" + str(error))
    use_parallel = (count >= 500 if parallel is None else parallel) and worker_count > 1

    def serial_results():
        for _ in range(count):
            battle = battle_class(
                config, equipment, skills, groups, seed=rng.randrange(2**53), record_timeline=False
            )
            result = battle.run(cancel_event=cancel_event)
            result["passed"] = (
                battle.state.target_current_hp is not None and battle.state.target_current_hp <= 0
            )
            result["character_alive"] = (
                battle.survival_at_all_kill
                if battle.survival_at_all_kill is not None
                else [c.enabled and c.alive for c in battle.state.characters]
            )
            result["all_alive"] = len(result["character_alive"]) == 4 and all(
                result["character_alive"]
            )
            yield result

    if compiled is not None:
        from .compiled.runner import results as compiled_results

        seeds = [rng.randrange(2**53) for _ in range(count)]
        arrays, keys, compiled_warnings = compiled[:3]
        boss_data = compiled[3] if boss_attacks else None
        results = compiled_results(
            arrays,
            keys,
            compiled_warnings,
            seeds,
            worker_count if parallel is not False else 1,
            metadata,
            cancel_event,
            boss_data=boss_data,
        )
    elif use_parallel and not boss_attacks:
        from .batch_workers import parallel_results

        seeds = [rng.randrange(2**53) for _ in range(count)]
        results = parallel_results(
            config, equipment, skills, groups, seeds, worker_count, cancel_event=cancel_event
        )
    else:
        results = serial_results()
    for run, result in enumerate(results):
        from .cancellation import check_cancelled

        check_cancelled(cancel_event)
        damage.append(result["total_damage"])
        passed += result["passed"]
        all_alive += result["all_alive"]
        for i, alive in enumerate(result["character_alive"]):
            char_survived[i] += int(alive)
        warnings.update(result["warnings"])
        for i, value in enumerate(result["character_damage"]):
            char_damage[i] += value
        for i, rows in enumerate(result["effect_counts"]):
            for effect in rows:
                key = (
                    effect["slot"],
                    effect["equipment_id"],
                    effect["name"],
                    effect["trigger_type"],
                    effect["kind"],
                )
                effects[i][key] = effects[i].get(key, 0) + effect["count"]
        if progress:
            progress(run + 1, count)
    damage.sort()
    characters = []
    for i, row in enumerate(config["characters"]):
        characters.append(
            {
                **{
                    "survived_battles": char_survived[i],
                    "survival_rate": char_survived[i] / count * 100 if row["enabled"] else None,
                },
                "index": i + 1,
                "job": row["job"],
                "enabled": row["enabled"],
                "expected_damage": char_damage[i] / count,
                "effects": [
                    {
                        "slot": key[0],
                        "equipment_id": key[1],
                        "equipment_name": equipment[key[1]]["name"],
                        "name": key[2],
                        "trigger_type": key[3],
                        "kind": key[4],
                        "mean_count": value / count,
                    }
                    for key, value in effects[i].items()
                ],
            }
        )
    survival = {"all_alive_battles": all_alive, "all_alive_rate": all_alive / count * 100}
    return {
        **survival,
        "boss_attacks": boss_attacks,
        "engine": metadata["engine"],
        "compilation_seconds": metadata["compilation_seconds"],
        "worker_count": metadata.get("worker_count", worker_count if use_parallel else 1),
        "elapsed_seconds": time.perf_counter() - started,
        "total_battles": count,
        "passed_battles": passed,
        "pass_rate": passed / count * 100,
        "seed": seed,
        "expected_damage": math.fsum(damage) / count,
        "max_damage": damage[-1],
        "min_damage": damage[0],
        "percentiles": {
            "1": percentile(damage, 1),
            "5": percentile(damage, 5),
            "10": percentile(damage, 10),
        },
        "custom_percentile": custom,
        "custom_percentile_damage": percentile(damage, custom),
        "characters": characters,
        "warnings": sorted(warnings),
        "sorted_damage": damage,
        "qualification": "在设定时间内击败目标",
        "quantile_method": "按伤害从高到低排列，线性插值（0%为最高，100%为最低）",
    }
