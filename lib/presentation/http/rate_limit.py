from __future__ import annotations

import time
from collections import OrderedDict, deque
from hashlib import sha256
from threading import Lock


class SlidingWindowRateLimiter:
    """Процессный лимит запросов. Между репликами состояние не разделяется."""

    def __init__(self, *, limit: int, window_seconds: float, max_keys: int = 10_000) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def allow(self, keys: list[str]) -> bool:
        now = time.monotonic()
        with self._lock:
            unique_keys = list(dict.fromkeys(keys))
            buckets: list[tuple[str, deque[float]]] = []
            for key in unique_keys:
                events = self._events.get(key)
                if events is None:
                    events = deque()
                else:
                    self._drop_expired(events, now)
                if len(events) >= self._limit:
                    return False
                buckets.append((key, events))
            for key, events in buckets:
                events.append(now)
                self._events[key] = events
                self._events.move_to_end(key)
            while len(self._events) > self._max_keys:
                self._events.popitem(last=False)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _drop_expired(self, events: deque[float], now: float) -> None:
        cutoff = now - self._window_seconds
        while events and events[0] <= cutoff:
            events.popleft()


def caller_keys(*, host: str | None, authorization: str) -> list[str]:
    resolved_host = host or "unknown"
    keys = [f"ip:{resolved_host}"]
    token = authorization.removeprefix("Bearer ").strip()
    if token:
        digest = sha256(token.encode("utf-8")).hexdigest()
        keys.append(f"token:{digest}")
    return keys


LIST_ROUTE_LIMIT = 60
LIST_ROUTE_WINDOW_SECONDS = 60.0

list_route_limiter = SlidingWindowRateLimiter(
    limit=LIST_ROUTE_LIMIT,
    window_seconds=LIST_ROUTE_WINDOW_SECONDS,
)
