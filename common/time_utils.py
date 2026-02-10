"""
Time utility helpers for task-queue services.

This module centralizes:
- UTC epoch timestamps in milliseconds (wall clock),
- monotonic timestamps in milliseconds (for durations),
- elapsed-time calculation in milliseconds.
"""

import time
from typing import Optional


def now_ms() -> int:
    """
    Return current wall-clock time as Unix epoch milliseconds.

    Note:
        This is suitable for event/log timestamps, not for duration math.
    """
    return time.time_ns() // 1_000_000


def monotonic_ms() -> int:
    """
    Return current monotonic clock time in milliseconds.

    Note:
        Monotonic values are only meaningful for differences (durations),
        not as real-world timestamps.
    """
    return time.monotonic_ns() // 1_000_000


def elapsed_ms(start_monotonic_ms: int, end_monotonic_ms: Optional[int] = None) -> int:
    """
    Compute elapsed milliseconds using monotonic clock values.

    Args:
        start_monotonic_ms: start timestamp from monotonic_ms().
        end_monotonic_ms: optional end timestamp from monotonic_ms();
            if None, current monotonic_ms() is used.

    Returns:
        Non-negative elapsed milliseconds. If end < start, clamps to 0.

    Raises:
        TypeError: if provided arguments are not integers.
    """
    if not isinstance(start_monotonic_ms, int) or isinstance(start_monotonic_ms, bool):
        raise TypeError("start_monotonic_ms must be an int")

    if end_monotonic_ms is None:
        end_val = monotonic_ms()
    else:
        if not isinstance(end_monotonic_ms, int) or isinstance(end_monotonic_ms, bool):
            raise TypeError("end_monotonic_ms must be an int or None")
        end_val = end_monotonic_ms

    delta = end_val - start_monotonic_ms
    return delta if delta >= 0 else 0


__all__ = ["now_ms", "monotonic_ms", "elapsed_ms"]
