"""Spawn-safe process workers for independent battles."""
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from .simulation import SingleBattle

_CONTEXT=None


def _initialize(config,equipment,skills,groups,cancel_event):
    global _CONTEXT
    _CONTEXT=(config,equipment,skills,groups,cancel_event)


def _chunk(seeds):
    config,equipment,skills,groups,cancel_event=_CONTEXT
    results=[]
    for seed in seeds:
        battle=SingleBattle(config,equipment,skills,groups,seed=seed,record_timeline=False)
        result=battle.run(cancel_event=cancel_event)
        result['passed']=battle.state.target_current_hp is not None and battle.state.target_current_hp<=0
        result['character_alive']=battle.survival_at_all_kill if battle.survival_at_all_kill is not None else [c.enabled and c.alive for c in battle.state.characters]
        result['all_alive']=len(result['character_alive'])==4 and all(result['character_alive'])
        results.append(result)
    return results


def parallel_results(config,equipment,skills,groups,seeds,workers,cancel_event=None):
    # Ordered delivery preserves the serial accumulation order and exact results.
    chunks=(seeds[i:i+64] for i in range(0,len(seeds),64))
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn'),
                             initializer=_initialize,initargs=(config,equipment,skills,groups,cancel_event)) as pool:
        for results in pool.map(_chunk,chunks):
            yield from results
