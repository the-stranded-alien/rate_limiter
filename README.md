# Rate Limiter

A Python implementation of rate limiting algorithms, featuring both **Fixed Window** and **Sliding Window Log** strategies. This project demonstrates the trade-offs between different rate limiting approaches and provides thread-safe implementations suitable for concurrent environments.

## Overview

Rate limiting is a technique used to control the rate of requests a client can make to a service. This project implements two common algorithms:

| Algorithm | Memory | Accuracy | Burst Protection |
|-----------|--------|----------|------------------|
| Fixed Window | O(1) per key | Approximate | No (2x burst possible) |
| Sliding Window Log | O(n) per key | Exact | Yes |

## Algorithms

### Fixed Window

Divides time into discrete windows (e.g., 60-second intervals). Each window maintains a counter that resets when the window expires.

```
Window 1 [0s-60s]     Window 2 [60s-120s]
    ████░░░░              ██░░░░░░
    (4 req)               (2 req)
         ^                ^
         |                └── Counter resets to 0
         └── Window boundary
```

**Pros:**
- Simple implementation
- Constant O(1) memory per key
- Fast lookups

**Cons:**
- Allows up to 2x burst at window boundaries (e.g., 5 requests at t=59s + 5 at t=60s = 10 requests in 2 seconds)

### Sliding Window Log

Tracks the exact timestamp of every request within a rolling window. Expired timestamps are evicted on each request.

```
        ←————— 60s window —————→
Timeline: [t=5s] [t=20s] [t=45s] [t=62s] [t=65s]
                                    ↑
                              Current time (t=65s)
                              Window: [5s-65s]
                              Valid entries: t=5s, t=20s, t=45s, t=62s, t=65s
```

**Pros:**
- Perfectly accurate rate limiting
- No boundary burst vulnerability
- Smooth rate enforcement

**Cons:**
- Memory usage scales with request rate: O(max_requests) per key

## Project Structure

```
rate_limiter/
├── rate_limiter.py          # Base class and RateLimitResult dataclass
├── algorithms/
│   ├── __init__.py
│   ├── fixed_window.py      # Fixed Window implementation
│   └── sliding_window.py    # Sliding Window Log implementation
├── tests/
│   ├── __init__.py
│   └── test_rate_limiter.py # Comprehensive test suite
├── demo.py                  # Interactive demonstration
├── pyproject.toml           # Project configuration
└── README.md
```

## Setup

### Prerequisites

- Python 3.10 or higher

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd rate_limiter
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install pytest pytest-asyncio
   ```

## Usage

### Basic Example

```python
from algorithms.sliding_window import SlidingWindowRateLimiter
from algorithms.fixed_window import FixedWindowRateLimiter

# Create a limiter: 5 requests per 60 seconds
limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)

# Check if a request is allowed
result = limiter.is_allowed("user_123")

if result.allowed:
    print(f"Request allowed. Remaining: {result.remaining}")
else:
    print(f"Rate limited. Retry after: {result.retry_after:.2f}s")
```

### RateLimitResult Fields

| Field | Type | Description |
|-------|------|-------------|
| `allowed` | `bool` | Whether the request was allowed |
| `remaining` | `int` | Number of requests remaining in the window |
| `reset_at` | `float` | Unix timestamp when the window resets |
| `retry_after` | `float \| None` | Seconds until a request will be allowed (only set when rejected) |

### API Reference

```python
class RateLimiter(ABC):
    def __init__(self, max_requests: int, window_seconds: int = 60):
        """Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed per window (must be > 0)
            window_seconds: Window duration in seconds (must be > 0)
        """

    def is_allowed(self, key: str) -> RateLimitResult:
        """Check if a request is allowed and consume a slot if so.

        Thread-safe. Returns a RateLimitResult with the decision.
        """

    def reset(self, key: str) -> None:
        """Reset rate limit state for a specific key."""

    def get_remaining(self, key: str) -> int:
        """Peek at remaining requests without consuming a slot."""
```

## Running the Demo

The demo showcases all features including the boundary burst comparison:

```bash
python demo.py
```

**Sample Output:**

```
============================================================
  SLIDING WINDOW — 5 req / 60s per user
============================================================
  [alice     ]  ✅ ALLOWED  |  remaining=4
  [alice     ]  ✅ ALLOWED  |  remaining=3
  ...

============================================================
  SLIDING vs FIXED — boundary burst comparison
============================================================
  ...
  [t=1.1s] BURST WINDOW
    req 1  →  sliding=✅  fixed=✅
    req 2  →  sliding=❌  fixed=✅
    req 3  →  sliding=❌  fixed=✅

  ⚠️  Fixed allows 3 — up to 5 req in 3s window = burst!
  ✅  Sliding allows only 1 then rejects
```

## Running Tests

Run the full test suite:

```bash
pytest tests -v
```

Run with coverage (if pytest-cov is installed):

```bash
pytest tests -v --cov=algorithms --cov=rate_limiter
```

### Test Categories

| Category | Description |
|----------|-------------|
| `TestBasicBehavior` | Core functionality (allows, rejects, remaining, reset) |
| `TestConcurrency` | Thread safety with 20+ concurrent threads |
| `TestFixedWindowSpecific` | Fixed window reset behavior |
| `TestSlidingWindowSpecific` | Sliding window expiry and partial eviction |

## Thread Safety

Both implementations are thread-safe and use `threading.Lock` to protect shared state. The concurrency tests verify that exactly `max_requests` are allowed even when 20 threads race simultaneously.

```python
# Safe for concurrent use
limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60)

# Multiple threads can call is_allowed() concurrently
result = limiter.is_allowed("shared_key")
```

## When to Use Which Algorithm

| Use Case | Recommended |
|----------|-------------|
| High-traffic APIs with strict limits | Sliding Window |
| Simple rate limiting with low memory | Fixed Window |
| Preventing burst abuse | Sliding Window |
| Per-user request quotas | Either (depends on accuracy needs) |

## License

MIT License
