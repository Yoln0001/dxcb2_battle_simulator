"""Bounded compiled chunks preserve progress, cancellation and result compatibility."""

import time
import numpy as np
import numba
from .kernel import chunk_seeded
from ..cancellation import check_cancelled


def results(arrays, keys, warnings, seeds, workers, metadata, cancel_event=None, boss_data=None):
    threads = min(workers, numba.config.NUMBA_NUM_THREADS)
    numba.set_num_threads(threads)
    metadata.update(engine="numba_njit", worker_count=threads, compilation_seconds=0.0)

    def execute(chunk_seeds):
        if boss_data is None:
            return chunk_seeded(*arrays, chunk_seeds)
        return chunk_seeded(*arrays, chunk_seeds, boss_data)

    loaded = False
    for begin in range(0, len(seeds), 128):
        check_cancelled(cancel_event)
        # 只把种子交给内核：每场的随机数状态由内核在各线程里生成，与random.Random(seed)相同。
        states = np.array(seeds[begin : begin + 128], dtype=np.int64)
        if not loaded:
            started = time.perf_counter()
            execute(states[:1])
            loaded = True
            metadata["compilation_seconds"] = time.perf_counter() - started
            check_cancelled(cancel_event)
        damage, passed, characters, counts, all_alive, character_alive = execute(states)
        check_cancelled(cancel_event)
        for offset in range(len(states)):
            effect_counts = [[] for _ in range(4)]
            for p, key in enumerate(keys):
                if counts[offset, p]:
                    c, slot, item_id, name, trigger_type, kind = key
                    effect_counts[c].append(
                        {
                            "slot": slot,
                            "equipment_id": item_id,
                            "name": name,
                            "trigger_type": trigger_type,
                            "kind": kind,
                            "count": int(counts[offset, p]),
                        }
                    )
            yield {
                "total_damage": float(damage[offset]),
                "passed": bool(passed[offset]),
                "all_alive": bool(all_alive[offset]),
                "character_alive": character_alive[offset].tolist(),
                "character_damage": characters[offset].tolist(),
                "effect_counts": effect_counts,
                "warnings": warnings,
            }
