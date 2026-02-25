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

    def __init__(self, max_requests: int, window_seconds: int = 60):
        super().__init__(max_requests, window_seconds)
        self._store: Dict[str, WindowState] = defaultdict(WindowState)
        self._lock: threading.Lock = threading.Lock()

    def _get_or_reset_window(self, key: str) -> WindowState:
        now = time.time()
        state = self._store[key]
        if now - state.window_start >= self.window_seconds:
            state.count = 0
            state.window_start = now
        return state

    def is_allowed(self, key: str) -> RateLimitResult:
        with self._lock:
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
                    retry_after=reset_at - time.time(),
                )
    
    def reset(self, key: str) -> None:
        with self._lock:
            self._store[key] = WindowState()

    def get_remaining(self, key: str) -> int:
        with self._lock:
            state = self._get_or_reset_window(key)
            return max(0, self.max_requests - state.count)