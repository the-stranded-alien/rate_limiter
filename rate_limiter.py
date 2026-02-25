from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None

class RateLimiter(ABC):
    def __init__(self, max_requests: int, window_seconds: int = 60):
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0")
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    @abstractmethod
    def is_allowed(self, key: str) -> RateLimitResult:
        """Check if request for given key is allowed. Thread-safe."""
        pass

    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset rate limit state for a key."""
        pass

    @abstractmethod
    def get_remaining(self, key: str) -> int:
        """Peek remaining requests without consuming a slot."""
        pass