"""Tests for agent.retry_utils jittered backoff."""

import threading

import agent.retry_utils as retry_utils
from types import SimpleNamespace

from agent.retry_utils import adaptive_rate_limit_backoff, is_zai_coding_overload_error, jittered_backoff


def test_backoff_is_exponential():
    """Base delay should double each attempt (before jitter)."""
    for attempt in (1, 2, 3, 4):
        delays = [jittered_backoff(attempt, base_delay=5.0, max_delay=120.0, jitter_ratio=0.0) for _ in range(100)]
        expected = min(5.0 * (2 ** (attempt - 1)), 120.0)
        mean = sum(delays) / len(delays)
        assert abs(mean - expected) < 0.01, f"attempt {attempt}: expected {expected}, got {mean}"


def test_backoff_respects_max_delay():
    """Even with high attempt numbers, delay should not exceed max_delay."""
    for attempt in (10, 20, 100):
        delay = jittered_backoff(attempt, base_delay=5.0, max_delay=60.0, jitter_ratio=0.0)
        assert delay <= 60.0, f"attempt {attempt}: delay {delay} exceeds max 60s"




def test_backoff_attempt_1_is_base():
    """First attempt delay should equal base_delay (with no jitter)."""
    delay = jittered_backoff(1, base_delay=3.0, max_delay=120.0, jitter_ratio=0.0)
    assert delay == 3.0








def test_backoff_thread_safety():
    """Concurrent calls should generally produce different delays."""
    results = []
    barrier = threading.Barrier(8)

    def _call_backoff():
        barrier.wait()
        results.append(jittered_backoff(1, base_delay=10.0, max_delay=120.0, jitter_ratio=0.5))

    threads = [threading.Thread(target=_call_backoff) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(results) == 8
    unique = len(set(results))
    assert unique >= 6, f"Expected mostly unique delays, got {unique}/8 unique"


def test_backoff_uses_locked_tick_for_seed(monkeypatch):
    """Seed derivation should use per-call tick captured under lock."""
    import time

    monkeypatch.setattr(retry_utils, "_jitter_counter", 0)

    recorded_seeds = []

    class _RecordingRandom:
        def __init__(self, seed):
            recorded_seeds.append(seed)

        def uniform(self, a, b):
            return 0.0

    monkeypatch.setattr(retry_utils.random, "Random", _RecordingRandom)

    fixed_time_ns = 123456789

    def _time_ns_wait_for_two_ticks():
        deadline = time.time() + 2.0
        while retry_utils._jitter_counter < 2 and time.time() < deadline:
            time.sleep(0.001)
        return fixed_time_ns

    monkeypatch.setattr(retry_utils.time, "time_ns", _time_ns_wait_for_two_ticks)

    barrier = threading.Barrier(2)

    def _call():
        barrier.wait()
        jittered_backoff(1, base_delay=10.0, max_delay=120.0, jitter_ratio=0.5)

    threads = [threading.Thread(target=_call) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(recorded_seeds) == 2
    assert len(set(recorded_seeds)) == 2, f"Expected unique seeds, got {recorded_seeds}"


def _zai_overload_error():
    return SimpleNamespace(
        status_code=429,
        body={
            "error": {
                "code": "1305",
                "message": "The service may be temporarily overloaded, please try again later",
            }
        },
    )










def test_zai_overload_retry_ceiling_exceeds_short_attempts():
    """Invariant: the ceiling must sit above the short-retry threshold, or the
    long-backoff tier is unreachable and the whole schedule is dead code
    (the original bug: default api_max_retries == short_attempts == 3)."""
    from agent.retry_utils import (
        zai_coding_overload_retry_ceiling,
        _ZAI_CODING_OVERLOAD_LONG_BACKOFF,
    )

    short_attempts = 3
    ceiling = zai_coding_overload_retry_ceiling(short_attempts)
    assert ceiling > short_attempts
    # Invariant (not a formula mirror): the loop's give-up check
    # (retry_count >= ceiling) runs *before* the attempt's backoff, so the
    # ceiling must leave headroom for every long-backoff entry to execute —
    # i.e. the largest attempt the loop still computes backoff for
    # (ceiling - 1) must reach the final long-tier index.
    last_attempt_with_backoff = ceiling - 1
    assert last_attempt_with_backoff - short_attempts >= len(_ZAI_CODING_OVERLOAD_LONG_BACKOFF)


def test_zai_overload_ceiling_makes_long_tier_reachable(monkeypatch):
    """End-to-end over the attempt range the retry loop actually walks: with the
    extended ceiling, at least one attempt reaches the long-backoff tier and the
    full 30/60/90/120s schedule is exercised."""
    monkeypatch.setattr(retry_utils, "jittered_backoff", lambda *a, **kw: kw["base_delay"])
    from agent.retry_utils import zai_coding_overload_retry_ceiling

    err = _zai_overload_error()
    ceiling = zai_coding_overload_retry_ceiling()

    long_waits = []
    # The loop computes backoff for attempts 1..ceiling-1 (it gives up at ceiling).
    for attempt in range(1, ceiling):
        _wait, policy = adaptive_rate_limit_backoff(
            attempt,
            base_url="https://api.z.ai/api/coding/paas/v4",
            model="glm-5.2",
            error=err,
            default_wait=1.0,
        )
        if policy == "zai_coding_overload_long":
            long_waits.append(_wait)

    assert long_waits, "long-backoff tier never reached within the retry ceiling"
    assert long_waits == [30.0, 60.0, 90.0, 120.0]


# ---------------------------------------------------------------------------
# parse_retry_after_seconds — shared Retry-After parser
# ---------------------------------------------------------------------------


class TestParseRetryAfterSeconds:
    def test_numeric_string(self):
        from agent.retry_utils import parse_retry_after_seconds
        assert parse_retry_after_seconds("120") == 120.0
        assert parse_retry_after_seconds(" 4.5 ") == 4.5

    def test_numeric_value(self):
        from agent.retry_utils import parse_retry_after_seconds
        assert parse_retry_after_seconds(45) == 45.0
        assert parse_retry_after_seconds(3.25) == 3.25


    def test_http_date(self):
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime
        from agent.retry_utils import parse_retry_after_seconds

        future = datetime.now(timezone.utc) + timedelta(seconds=90)
        seconds = parse_retry_after_seconds(format_datetime(future, usegmt=True))
        assert seconds is not None and 80 <= seconds <= 91

        past = datetime.now(timezone.utc) - timedelta(seconds=90)
        assert parse_retry_after_seconds(format_datetime(past, usegmt=True)) == 0.0



    def test_headers_get_raises(self):
        from agent.retry_utils import parse_retry_after_seconds

        class Explosive:
            def get(self, _key):
                raise RuntimeError("boom")

        assert parse_retry_after_seconds(Explosive()) is None


# ---------------------------------------------------------------------------
# Default retry schedule (opencode parity) — gaps, retry-after, status text
# ---------------------------------------------------------------------------


class TestRetrySchedule:
    def test_gap_doubles_then_settles_at_the_cap(self):
        """2s, 4s, 8s, then the 10s ceiling for every later attempt."""
        from agent.retry_utils import retry_gap_seconds

        gaps = [retry_gap_seconds(attempt, jitter_ratio=0.0) for attempt in range(1, 11)]

        assert gaps[:3] == [2.0, 4.0, 8.0]
        assert gaps[3:] == [10.0] * 7

    def test_gap_is_jittered_within_ratio_bounds(self):
        """Jitter decorrelates concurrent sessions but never leaves ±20%."""
        from agent.retry_utils import RETRY_JITTER_RATIO, retry_gap_seconds

        launcher = 1.0 - RETRY_JITTER_RATIO
        ceiling = 1.0 + RETRY_JITTER_RATIO
        for attempt, nominal in ((1, 2.0), (2, 4.0), (3, 8.0), (4, 10.0), (11, 10.0)):
            samples = [retry_gap_seconds(attempt) for _ in range(200)]
            assert all(nominal * launcher <= s <= nominal * ceiling for s in samples)
            # A constant would defeat the point of jitter.
            assert len(set(samples)) > 1

    def test_huge_attempt_stays_at_the_cap(self):
        from agent.retry_utils import retry_gap_seconds

        assert retry_gap_seconds(10_000) <= 10.0 * (1 + 0.2)

    def test_retry_after_is_a_floor_not_a_replacement(self):
        """A short provider ask never shortens the schedule's own gap."""
        from agent.retry_utils import retry_delay_seconds

        assert retry_delay_seconds(1, retry_after=30.0) == 30.0
        assert retry_delay_seconds(1, retry_after=0.5, jitter_ratio=0.0) == 2.0
        assert (
            retry_delay_seconds(4, retry_after=3.0, jitter_ratio=0.0) == 10.0
        ), "attempt 4's own gap (10s) is longer than the provider's ask"

    def test_retry_after_is_capped(self):
        """A buggy upstream asking for hours cannot stall the turn for hours."""
        from agent.retry_utils import RETRY_AFTER_MAX_SECONDS, retry_delay_seconds

        assert retry_delay_seconds(1, retry_after=10**9) == RETRY_AFTER_MAX_SECONDS

    def test_unusable_retry_after_falls_back_to_the_schedule(self):
        from agent.retry_utils import retry_delay_seconds

        for value in (None, "not-a-number", -5, 0, False, object()):
            assert retry_delay_seconds(1, retry_after=value, jitter_ratio=0.0) == 2.0


class TestRetryStatusText:
    def test_carries_attempt_countdown_and_error(self):
        from agent.retry_utils import retry_status_text

        text = retry_status_text(
            attempt=2,
            max_attempts=10,
            seconds=8.4,
            error="Error code: 429 - rate limit exceeded",
        )

        assert text.startswith("⏳ Retrying in 8s (attempt 2/10)")
        assert "429" in text and "rate limit" in text

    def test_rounds_down_partial_seconds_so_it_never_overstates(self):
        from agent.retry_utils import retry_status_text

        assert "Retrying in 0s" in retry_status_text(attempt=1, max_attempts=3, seconds=0.4)

    def test_omits_missing_error_and_keeps_policy_note(self):
        from agent.retry_utils import retry_status_text

        text = retry_status_text(
            attempt=4,
            max_attempts=8,
            seconds=30,
            note="(Z.AI Coding overload adaptive long backoff)",
        )

        assert text.endswith("(Z.AI Coding overload adaptive long backoff)")
        assert "—" not in text

    def test_collapses_whitespace_and_truncates_long_errors(self):
        from agent.retry_utils import retry_status_text

        text = retry_status_text(
            attempt=1,
            max_attempts=10,
            seconds=2,
            error="  500   internal\n\nerror   " + "x" * 1000,
        )

        assert "500 internal error" in text
        detail = text.split("— ", 1)[1]
        assert len(detail) <= 160
        assert detail.endswith("…")
