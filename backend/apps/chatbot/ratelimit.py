"""Fixed-window rate limiting on Django's cache.

The default cache is per process; production with several workers needs a
shared cache backend (e.g. database or Redis cache) for limits to be exact.
"""

import time

from django.core.cache import cache


def allow(key, *, limit, window_seconds):
    """Count one hit for ``key``; ``False`` once ``limit`` is exceeded in the window."""
    bucket = f"ratelimit:{key}:{int(time.time() // window_seconds)}"
    if cache.add(bucket, 1, timeout=window_seconds):
        return True
    try:
        return cache.incr(bucket) <= limit
    except ValueError:  # expired between add() and incr()
        cache.set(bucket, 1, timeout=window_seconds)
        return True
