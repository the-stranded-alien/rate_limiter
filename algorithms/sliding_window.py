import threading
import time
from collections import defaultdict, deque
from typing import Dict, Deque

from rate_limiter import RateLimiter, RateLimitResult


class SlidingWindowRateLimiter(RateLimiter):
    """
    Sliding Window Log Rate Limiter.

    Tracks the exact timestamp of every request within a rolling
    window of `window_seconds`. Evicts expired timestamps on each call.

    Pros:  Perfectly accurate, no boundary burst
    Cons:  Memory O(max_requests) per key
    """
    
    def __init__(self, max_requests: int, window_seconds: int = 60):
        super().__init__(max_requests, window_seconds)
        self._store: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock: threading.Lock = threading.Lock()

    def _evict_expired(self, timestamps: Deque[float], now: float) -> None:
        """Remove timestamps outside the current window. Deque is sorted oldest→newest."""
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

    def is_allowed(self, key: str) -> RateLimitResult:
        with self._lock:
            now = time.time()
            timestamps = self._store[key]
            self._evict_expired(timestamps, now)

            if len(timestamps) < self.max_requests:
                timestamps.append(now)
                reset_at = timestamps[0] + self.window_seconds
                return RateLimitResult(
                    allowed=True,
                    remaining=self.max_requests - len(timestamps),
                    reset_at=reset_at,
                )
            else:
                oldest = timestamps[0]
                reset_at = oldest + self.window_seconds
                retry_after = max(0.0, reset_at - now)
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after,
                )

    def reset(self, key: str) -> None:
        with self._lock:
            self._store[key] = deque()

    def get_remaining(self, key: str) -> int:
        with self._lock:
            now = time.time()
            timestamps = self._store[key]
            self._evict_expired(timestamps, now)
            return max(0, self.max_requests - len(timestamps))