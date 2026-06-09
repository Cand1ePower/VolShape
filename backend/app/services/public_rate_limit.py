from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic


@dataclass
class SlidingWindowLimiter:
    max_requests: int
    window_seconds: int
    _buckets: dict[str, deque[float]] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def allow(self, key: str) -> tuple[bool, int]:
        now = monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
                return False, retry_after

            bucket.append(now)
            return True, 0


public_rag_limiter = SlidingWindowLimiter(max_requests=10, window_seconds=5 * 60)
