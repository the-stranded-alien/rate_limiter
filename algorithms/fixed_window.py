import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from rate_limiter import RateLimitResult, RateLimiter

@dataclass
class WindowState:
    count: int = 0
    window_start: float = field(default_factory=time.time)

class FixedWindowRateLimiter(RateLimiter):
    """
    Fixed Window Rate Limiter.

    Divides time into fixed windows of `window_seconds` each.
    Counts requests per key within the current window.
    Resets count at the start of each new window.

    Pros:  Simple, O(1) memory per key
    Cons:  Allows up to 2x burst at window boundaries
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        super().__init__(max_requests, window_seconds)
        self._store: Dict[str, WindowState] = defaultdict(WindowState)
        self._locks: Dict[str, threading.Lock] = {}
        self._meta_lock: threading.Lock = threading.Lock()

    def _get_key_lock(self, key: str) -> threading.Lock:
        with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def _get_or_reset_window(self, key: str) -> WindowState:
        now = time.time()
        state = self._store[key]
        if now - state.window_start >= self.window_seconds:
            del self._store[key]          # evict stale entry
            state = self._store[key]      # defaultdict creates fresh WindowState
        return state

    def is_allowed(self, key: str) -> RateLimitResult:
        with self._get_key_lock(key):
            state = self._get_or_reset_window(key)
            reset_at = state.window_start + self.window_seconds
            if state.count < self.max_requests:
                state.count += 1
                return RateLimitResult(
                    allowed=True,
                    remaining=self.max_requests - state.count,
                    reset_at=reset_at,
                )
            else:
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=max(0.0, reset_at - time.time()),
                )

    def reset(self, key: str) -> None:
        with self._get_key_lock(key):
            self._store[key] = WindowState()

    def get_remaining(self, key: str) -> int:
        with self._get_key_lock(key):
            state = self._get_or_reset_window(key)
            return max(0, self.max_requests - state.count)