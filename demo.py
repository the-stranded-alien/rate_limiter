import time
from collections import defaultdict

from algorithms.fixed_window import FixedWindowRateLimiter
from algorithms.sliding_window import SlidingWindowRateLimiter


def print_result(user: str, result) -> None:
    status = "✅ ALLOWED" if result.allowed else "❌ REJECTED"
    extra = (
        f"remaining={result.remaining}"
        if result.allowed
        else f"retry_after={result.retry_after:.2f}s"
    )
    print(f"  [{user:10}]  {status}  |  {extra}")


def demo_basic():
    print("=" * 60)
    print("  SLIDING WINDOW — 5 req / 60s per user")
    print("=" * 60)
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)

    requests = [
        "alice", "alice", "alice", "bob",
        "alice", "alice", "alice",   # alice hits limit here
        "bob", "bob", "charlie",
    ]
    for user in requests:
        print_result(user, limiter.is_allowed(user))

    print(f"\n  Peek remaining (no consume):")
    print(f"    alice    → {limiter.get_remaining('alice')}")
    print(f"    bob      → {limiter.get_remaining('bob')}")
    print(f"    charlie  → {limiter.get_remaining('charlie')}")

def demo_sliding_vs_fixed():
    print("\n" + "=" * 60)
    print("  SLIDING vs FIXED — boundary burst comparison")
    print("  Limit: 3 req / 1s window")
    print("=" * 60)

    sliding = SlidingWindowRateLimiter(max_requests=3, window_seconds=1)
    fixed   = FixedWindowRateLimiter(max_requests=3, window_seconds=1)

    # Fill both windows at t=0
    print("\n  Step 1: 3 requests at t=0 (fills both windows)")
    for _ in range(3):
        sliding.is_allowed("u")
        fixed.is_allowed("u")

    # Sleep just past 1s so fixed window resets
    # but sliding still has entries from ~0.0s that expire at ~1.0s
    print("  Step 2: Sleep 1.05s — fixed window boundary crossed")
    time.sleep(1.05)

    # At t=1.05s:
    #   fixed  → new window started, quota = 3 (BURST possible)
    #   sliding → entries from t=0 just expired (1.05 > 1.0), quota = 3 too
    # Fill sliding window now
    print("  Step 3: 2 quick requests at t=1.05s")
    for _ in range(2):
        sliding.is_allowed("u")
        fixed.is_allowed("u")

    # Now immediately burst — sliding has 2 in window, fixed has 2 in window
    # Sleep tiny amount so fixed window doesn't reset but sliding entries age
    print("  Step 4: Sleep 0.6s")
    time.sleep(0.6)

    # At t=1.65s:
    #   fixed  → window started at 1.05s, expires at 2.05s → still active, 1 slot left
    #   sliding → entries from t=1.05s are 0.6s old, still in 1s window → 1 slot left
    # Both same here. Now sleep past fixed boundary only
    print("  Step 5: Sleep 0.45s (fixed window resets at t=2.05s, sliding entries still alive)")
    time.sleep(0.45)

    # At t=2.1s:
    #   fixed  → NEW window (reset at 2.05s), full quota = 3 available  ← BURST
    #   sliding → entries from t=1.05s are 1.05s old → just expired
    #             but entries would need to be fresher to show difference
    #
    # Better approach — fill right before boundary, burst right after

    # Reset and redo with precise timing
    sliding = SlidingWindowRateLimiter(max_requests=3, window_seconds=1)
    fixed   = FixedWindowRateLimiter(max_requests=3, window_seconds=1)

    print("\n  --- Reset, demonstrating burst precisely ---")
    print("  Fill 3 requests, sleep to just before window end, then burst\n")

    for _ in range(3):
        sliding.is_allowed("v")
        fixed.is_allowed("v")

    time.sleep(0.95)   # almost at window boundary

    # At t=0.95s: fixed window expires at t=1.0s (0.05s away)
    # Sleep just 0.1s more to cross fixed boundary
    time.sleep(0.1)

    # At t=1.05s: fixed resets, sliding entries from t=0 just expired too
    # This is the same problem — both reset together

    # THE REAL TRICK: requests must be sent at t=0.9s (near end of window)
    # then again at t=1.1s (just after fixed resets but within sliding's memory)

    sliding = SlidingWindowRateLimiter(max_requests=3, window_seconds=1)
    fixed   = FixedWindowRateLimiter(max_requests=3, window_seconds=1)

    # Key insight: Start the fixed window at t=0, then make more requests
    # at t=0.5. When t=1.05 comes:
    #   - Fixed window started at t=0, resets at t=1.0 → full quota
    #   - Sliding: t=0 entry expired, but t=0.5 entries still in 1s window
    t0 = time.time()
    print(f"  [t=0.0s] 1 request — starts both windows at t=0")
    sliding.is_allowed("w")
    fixed.is_allowed("w")

    time.sleep(0.5)
    print(f"  [t={time.time()-t0:.1f}s] 2 more requests — fills window (3 total)")
    for _ in range(2):
        sliding.is_allowed("w")
        fixed.is_allowed("w")

    # Sleep past t=1.0s — fixed window resets but sliding still has t=0.5 entries
    time.sleep(0.55)
    print(f"\n  [t={time.time()-t0:.1f}s] BURST WINDOW")
    print("    Fixed: window reset at t=1.0, full quota available")
    print("    Sliding: t=0 entry expired, but t=0.5 entries still in window\n")
    for i in range(3):
        sr = sliding.is_allowed("w")
        fr = fixed.is_allowed("w")
        slide_icon = '✅' if sr.allowed else '❌'
        fixed_icon = '✅' if fr.allowed else '❌'
        print(f"    req {i+1}  →  sliding={slide_icon}  fixed={fixed_icon}")

    print()
    print("  ⚠️  Fixed allows 3 — up to 5 req in 3s window = burst!")
    print("  ✅  Sliding allows only 1 then rejects")

def demo_concurrency():
    print("\n" + "=" * 60)
    print("  CONCURRENCY — 20 threads, limit=5")
    print("=" * 60)
    import threading

    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
    results = []
    lock = threading.Lock()

    def call():
        r = limiter.is_allowed("shared_key")
        with lock:
            results.append(r.allowed)

    threads = [threading.Thread(target=call) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    allowed = sum(results)
    print(f"  Threads fired : 20")
    print(f"  Allowed       : {allowed}  (expected 5)")
    print(f"  Rejected      : {20 - allowed}")


if __name__ == "__main__":
    demo_basic()
    demo_sliding_vs_fixed()
    demo_concurrency()