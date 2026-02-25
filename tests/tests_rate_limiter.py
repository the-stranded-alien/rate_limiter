import time
import threading
import pytest
from collections import defaultdict
from typing import Dict

from algorithms.fixed_window import FixedWindowRateLimiter
from algorithms.sliding_window import SlidingWindowRateLimiter

@pytest.fixture(params=["fixed_window", "sliding_window"])
def limiter(request):
    if request.param == "fixed_window":
        return FixedWindowRateLimiter(max_requests=5, window_seconds=60)
    elif request.param == "sliding_window":
        return SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
    else:
        raise ValueError(f"Invalid limiter type: {request.param}")

# ── Basic Behavior ────────────────────────────────────────────────────────────

class TestBasicBehavior:
    def test_allows_up_to_limit(self, limiter):
        for i in range(5):
            result = limiter.is_allowed("user1")
            assert result.allowed, f"Request {i + 1} should be allowed"

    def test_rejects_over_limit(self, limiter):
        for _ in range(5):
            limiter.is_allowed("user1")
        result = limiter.is_allowed("user1")
        assert not result.allowed
        assert result.remaining == 0
        assert result.retry_after is not None and result.retry_after > 0

    def test_different_keys_are_independent(self, limiter):
        for _ in range(5):
            limiter.is_allowed("userA")
        # userA exhausted — userB must still work
        assert limiter.is_allowed("userB").allowed

    def test_remaining_decrements_correctly(self, limiter):
        r1 = limiter.is_allowed("user2")
        r2 = limiter.is_allowed("user2")
        assert r2.remaining == r1.remaining - 1

    def test_reset_clears_state(self, limiter):
        for _ in range(5):
            limiter.is_allowed("user3")
        limiter.reset("user3")
        assert limiter.is_allowed("user3").allowed

    def test_get_remaining_has_no_side_effect(self, limiter):
        before = limiter.get_remaining("user4")
        limiter.get_remaining("user4")
        after = limiter.get_remaining("user4")
        assert before == after == 5

    def test_result_fields_on_allowed(self, limiter):
        result = limiter.is_allowed("user5")
        assert result.allowed is True
        assert result.remaining == 4
        assert result.reset_at > time.time()
        assert result.retry_after is None

    def test_result_fields_on_rejected(self, limiter):
        for _ in range(5):
            limiter.is_allowed("user6")
        result = limiter.is_allowed("user6")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0
        assert result.reset_at > time.time()
    
    def test_invalid_max_requests_raises(self):
        with pytest.raises(ValueError):
            SlidingWindowRateLimiter(max_requests=0)

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError):
            FixedWindowRateLimiter(max_requests=5, window_seconds=-1)

# ── Concurrency ───────────────────────────────────────────────────────────────

class TestConcurrency:
    def test_concurrent_requests_respect_limit(self, limiter):
        """20 concurrent threads on the same key — exactly 5 must be allowed."""
        results = []
        lock = threading.Lock()

        def make_request():
            r = limiter.is_allowed("concurrent_user")
            with lock:
                results.append(r.allowed)

        threads = [threading.Thread(target=make_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed = sum(results)
        assert allowed == 5, f"Expected exactly 5 allowed, got {allowed}"

    def test_concurrent_different_keys(self, limiter):
        """Each unique key should independently allow up to max_requests."""
        results: Dict[str, list] = defaultdict(list)
        lock = threading.Lock()

        def make_request(user_key):
            r = limiter.is_allowed(user_key)
            with lock:
                results[user_key].append(r.allowed)

        threads = []
        for i in range(3):         # 3 users
            for _ in range(10):    # 10 requests each
                threads.append(threading.Thread(target=make_request, args=(f"user_{i}",)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for user_key, allowed_list in results.items():
            assert sum(allowed_list) == 5, (
                f"{user_key}: expected 5 allowed, got {sum(allowed_list)}"
            )

# ── Fixed Window Specific ─────────────────────────────────────────────────────

class TestFixedWindowSpecific:
    def test_window_resets_after_expiry(self):
        """Counter should fully reset after the window expires."""
        limiter = FixedWindowRateLimiter(max_requests=3, window_seconds=1)

        for _ in range(3):
            limiter.is_allowed("fw_user")
        assert not limiter.is_allowed("fw_user").allowed

        time.sleep(1.1)
        result = limiter.is_allowed("fw_user")
        assert result.allowed
        assert result.remaining == 2   # 3 - 1 = 2 remaining

class TestSlidingWindowSpecific:
    def test_window_slides_and_refills(self):
        """Old requests should expire and free up slots in the sliding window."""
        limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=1)

        for _ in range(3):
            limiter.is_allowed("slide_user")

        assert not limiter.is_allowed("slide_user").allowed

        time.sleep(1.1)
        assert limiter.is_allowed("slide_user").allowed

    def test_partial_window_expiry(self):
        """Only expired entries should be evicted; remaining budget is partial."""
        limiter = SlidingWindowRateLimiter(max_requests=4, window_seconds=2)

        limiter.is_allowed("partial")
        limiter.is_allowed("partial")
        time.sleep(1.1)
        # 2 more — total in window = 4 (2 old still valid + 2 new)
        limiter.is_allowed("partial")
        limiter.is_allowed("partial")

        # Should be rejected now
        assert not limiter.is_allowed("partial").allowed

        time.sleep(1.1)
        # First 2 have expired — 2 slots open again
        assert limiter.get_remaining("partial") == 2
