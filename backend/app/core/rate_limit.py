from collections import defaultdict, deque
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Any

# Increment and expiration must be atomic: a worker crash between INCR and EXPIRE
# would otherwise leave a permanent limit. Keys contain no IP addresses or user IDs.
_REDIS_WINDOW = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {count, redis.call('TTL', KEYS[1])}
"""


class RateLimitUnavailable(RuntimeError):
    pass


def allow_request(
    key: str,
    limit: int,
    *,
    redis_client: Any = None,
    required: bool = False,
    window_seconds: int = 60,
) -> tuple[bool, int, int]:
    """Share quotas across workers; production fails closed if Redis is unavailable."""
    if redis_client is not None:
        try:
            redis_key = f"matriva:rate:{sha256(key.encode()).hexdigest()}"
            count, ttl = redis_client.eval(_REDIS_WINDOW, 1, redis_key, window_seconds)
            allowed = int(count) <= limit
            return allowed, max(0, limit - int(count)), 0 if allowed else max(1, int(ttl))
        except Exception as exc:
            if required:
                raise RateLimitUnavailable("Rate limiting unavailable") from exc
    elif required:
        raise RateLimitUnavailable("Rate limiting unavailable")
    return rate_limiter.allow(key, limit, window_seconds)


class InMemoryRateLimiter:
    """Dependency-free fallback for local development without Redis."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int, int]:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])) + 1)
                return False, 0, retry_after
            events.append(now)
            if len(self._events) > 10_000:
                stale_keys = [key for key, values in self._events.items() if not values or values[-1] < cutoff]
                for stale_key in stale_keys:
                    self._events.pop(stale_key, None)
            return True, max(0, limit - len(events)), 0

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


rate_limiter = InMemoryRateLimiter()
