"""Clock selection and observational host metadata for benchmark reports."""

import math
import os
import time


def round_microseconds(value):
    return math.floor(value * 1000 + 0.5) / 1000


def make_timer(clock, *, wall_now=None, cpu_now=None):
    """Return a nanosecond clock; CPU time counts all threads in this process."""
    if clock == "wall":
        return wall_now if wall_now is not None else time.perf_counter_ns
    if clock == "cpu":
        return cpu_now if cpu_now is not None else time.process_time_ns
    raise ValueError("clock must be wall or cpu")


def environment_snapshot():
    try:
        load = list(os.getloadavg())
    except (AttributeError, OSError):
        load = None
    return {"logical_cpus": os.cpu_count(), "load_average": load}
