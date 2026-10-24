class SimulationCancelled(Exception):
    """Cooperative cancellation of a batch and its worker battles."""


def check_cancelled(event):
    if event is not None and event.is_set():
        raise SimulationCancelled("批量模拟已取消")
