"""Retry utilities — jittered backoff for decorrelated retries.

Replaces fixed exponential backoff with jittered delays to prevent
thundering-herd retry spikes when multiple sessions hit the same
rate-limited provider concurrently.
"""

import random
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

# Monotonic counter for jitter seed uniqueness within the same process.
# Protected by a lock to avoid race conditions in concurrent retry paths
# (e.g. multiple gateway sessions retrying simultaneously).
_jitter_counter = 0
_jitter_lock = threading.Lock()

# Z.AI Coding Plan's GLM-5.2 endpoint often returns HTTP 429 code 1305
# ("The service may be temporarily overloaded...") for otherwise valid
# Aura Forge requests. Short retries tend to hammer the same overloaded window;
# after a few normal retries, progressively widen the wait window. Keep the
# cap interactive-friendly: a simple TUI message should fail visibly in minutes,
# not sit silent for 20+ minutes.
_ZAI_CODING_OVERLOAD_LONG_BACKOFF = (30.0, 60.0, 90.0, 120.0)

# Number of initial short retries before the adaptive long-backoff tier kicks
# in. Shared by ``adaptive_rate_limit_backoff`` (which walks the long table
# starting at attempt ``short_attempts + 1``) and
# ``zai_coding_overload_retry_ceiling`` (which sizes the retry loop so every
# long-tier entry is reachable). Keeping it a single module constant prevents
# the two from silently desyncing if the short-retry count is ever tuned.
_ZAI_CODING_OVERLOAD_SHORT_ATTEMPTS = 3

# ── Default retry schedule (opencode parity) ────────────────────────────────
# Reference: opencode's `packages/core/src/model-retry.ts`. A transient
# provider/model failure is retried ten times on a schedule that starts short
# and settles into a steady cadence: 2s, 4s, 8s, then 10s for each remaining
# gap (~84s of waiting when every attempt fails, 67-101s with jitter). A
# provider-supplied `retry-after` is honored as a *minimum* delay (never a
# shorter wait than asked), capped at 15 minutes so a buggy upstream cannot
# stall a turn for hours.
#
# Why this shape: the old 2s→60s exponential made the first retries snappy but
# pushed late attempts a full minute apart, so a brief provider blip either
# recovered fast or felt like a hang. A flat 10s ceiling keeps the whole retry
# window inside ~1.5 minutes while still backing off enough to let a throttled
# backend breathe.
RETRY_BASE_GAP_SECONDS = 2.0
RETRY_MAX_GAP_SECONDS = 10.0
RETRY_AFTER_MAX_SECONDS = 900.0
# Effect's `Schedule.jittered` (used by opencode) scales each gap by ±20%.
RETRY_JITTER_RATIO = 0.2
DEFAULT_API_MAX_RETRIES = 10


def retry_gap_seconds(
    attempt: int,
    *,
    jitter_ratio: float = RETRY_JITTER_RATIO,
) -> float:
    """Gap before one retry of the opencode-style schedule.

    ``attempt`` is 1-based (1 → ~2s, 2 → ~4s, 3 → ~8s, 4+ → ~10s), matching the
    attempt number shown to the user. The gap is jittered by ``±jitter_ratio``
    so concurrent sessions hitting the same throttle do not retry in lockstep.
    """
    exponent = max(0, attempt - 1)
    if exponent >= 63 or RETRY_BASE_GAP_SECONDS <= 0:
        gap = RETRY_MAX_GAP_SECONDS
    else:
        gap = min(RETRY_BASE_GAP_SECONDS * (2 ** exponent), RETRY_MAX_GAP_SECONDS)

    if jitter_ratio <= 0:
        return gap

    global _jitter_counter
    with _jitter_lock:
        _jitter_counter += 1
        tick = _jitter_counter

    seed = (time.time_ns() ^ (tick * 0x9E3779B9)) & 0xFFFFFFFF
    rng = random.Random(seed)

    return gap * rng.uniform(1.0 - jitter_ratio, 1.0 + jitter_ratio)


def retry_delay_seconds(
    attempt: int,
    *,
    retry_after: Optional[float] = None,
    jitter_ratio: float = RETRY_JITTER_RATIO,
) -> float:
    """Total wait before the next attempt, honoring a provider ``retry-after``.

    ``retry_after`` is a floor, not a replacement: if the provider asks for less
    than the schedule's gap we still wait the gap (so the backoff keeps growing),
    and if it asks for more we wait what it asked (capped at
    ``RETRY_AFTER_MAX_SECONDS``). Non-numeric/negative values are ignored.
    """
    delay = retry_gap_seconds(attempt, jitter_ratio=jitter_ratio)
    if retry_after is None:
        return delay
    if isinstance(retry_after, bool):
        return delay
    try:
        floor = float(retry_after)
    except (TypeError, ValueError):
        return delay
    if floor <= 0:
        return delay
    return max(delay, min(floor, RETRY_AFTER_MAX_SECONDS))


_RETRY_ERROR_SUMMARY_MAX_CHARS = 160


def retry_status_text(
    *,
    attempt: int,
    max_attempts: int,
    seconds: float,
    error: Any = None,
    note: str = "",
) -> str:
    """One-line retry progress shared by every Aura Forge surface.

    Shape: ``⏳ Retrying in 8s (attempt 2/10) — rate limited``.

    This is what the CLI spinner, the TUI status line, and the desktop status
    row show while a provider error is being retried. It deliberately carries
    the error summary so the user sees *why* the turn is waiting, and the
    attempt countdown so the wait reads as progress rather than a hang.
    """
    # Floor, not round: the same value feeds the once-per-second countdown, and
    # a floor never overstates how long the user still has to wait.
    remaining = max(0, int(float(seconds)))
    text = f"⏳ Retrying in {remaining}s (attempt {attempt}/{max_attempts})"
    if note:
        text += f" {note}"
    detail = " ".join(str(error or "").split())
    if detail:
        if len(detail) > _RETRY_ERROR_SUMMARY_MAX_CHARS:
            detail = detail[: _RETRY_ERROR_SUMMARY_MAX_CHARS - 1].rstrip() + "…"
        text += f" — {detail}"
    return text


def parse_retry_after_seconds(value_or_headers: Any) -> Optional[float]:
    """Parse a ``Retry-After`` value into non-negative seconds.

    Accepts either a raw header value (numeric string / HTTP-date / number)
    or a headers mapping, in which case the ``Retry-After`` key is looked up
    case-insensitively (``.get`` on dict-like objects tries both common
    casings; real HTTP header containers like httpx/requests are already
    case-insensitive).

    Returns:
        Seconds as a ``float`` (negative deltas clamped to ``0.0``), or
        ``None`` when the header is absent or unparseable.
    """
    raw = value_or_headers
    if raw is not None and not isinstance(raw, (str, int, float)):
        # Looks like a headers mapping — pull the header out of it.
        getter = getattr(raw, "get", None)
        if callable(getter):
            try:
                value = getter("Retry-After")
                if value is None:
                    value = getter("retry-after")
            except Exception:
                return None
            raw = value
        else:
            return None
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return max(0.0, float(raw))
    text = str(raw).strip()
    if not text:
        return None
    try:
        return max(0.0, float(text))
    except (TypeError, ValueError):
        pass
    # HTTP-date form (RFC 7231): seconds until that instant, clamped at 0.
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def jittered_backoff(
    attempt: int,
    *,
    base_delay: float = 5.0,
    max_delay: float = 120.0,
    jitter_ratio: float = 0.5,
) -> float:
    """Compute a jittered exponential backoff delay.

    Args:
        attempt: 1-based retry attempt number.
        base_delay: Base delay in seconds for attempt 1.
        max_delay: Maximum delay cap in seconds.
        jitter_ratio: Fraction of computed delay to use as random jitter
            range.  0.5 means jitter is uniform in [0, 0.5 * delay].

    Returns:
        Delay in seconds: min(base * 2^(attempt-1), max_delay) + jitter.

    The jitter decorrelates concurrent retries so multiple sessions
    hitting the same provider don't all retry at the same instant.
    """
    global _jitter_counter
    with _jitter_lock:
        _jitter_counter += 1
        tick = _jitter_counter

    exponent = max(0, attempt - 1)
    if exponent >= 63 or base_delay <= 0:
        delay = max_delay
    else:
        delay = min(base_delay * (2 ** exponent), max_delay)

    # Seed from time + counter for decorrelation even with coarse clocks.
    seed = (time.time_ns() ^ (tick * 0x9E3779B9)) & 0xFFFFFFFF
    rng = random.Random(seed)
    jitter = rng.uniform(0, jitter_ratio * delay)

    return delay + jitter


def _error_text(error: Any) -> str:
    """Best-effort flattened provider error text for retry classification."""
    parts = [
        error,
        getattr(error, "message", None),
        getattr(error, "body", None),
        getattr(error, "response", None),
    ]
    return " ".join(str(part) for part in parts if part is not None).lower()


def is_zai_coding_overload_error(*, base_url: str | None, model: str | None, error: Any) -> bool:
    """Return True for Z.AI Coding Plan transient overload 429s.

    The coding-plan endpoint reports overload as HTTP 429 with body code 1305
    and message "The service may be temporarily overloaded...". Treat only
    that narrow shape specially so ordinary quota/billing 429s still fail fast
    through the existing classifier.
    """
    base = (base_url or "").lower()
    model_name = (model or "").lower()
    status = getattr(error, "status_code", None)
    text = _error_text(error)
    return (
        status == 429
        and "api.z.ai/api/coding/paas/v4" in base
        and "glm-5.2" in model_name
        and ("1305" in text or "temporarily overloaded" in text)
    )


def adaptive_rate_limit_backoff(
    attempt: int,
    *,
    base_url: str | None,
    model: str | None,
    error: Any,
    default_wait: float,
    short_attempts: int = _ZAI_CODING_OVERLOAD_SHORT_ATTEMPTS,
) -> tuple[float, str | None]:
    """Provider-aware rate-limit backoff.

    For most providers this returns ``default_wait`` unchanged. For Z.AI
    Coding Plan GLM-5.2 overloads, keep the first ``short_attempts`` retries on
    the normal short exponential schedule, then switch to progressively longer
    waits (30s → 60s → 90s → 120s, capped) plus light jitter.

    ``attempt`` is 1-based, matching the retry loop's logged attempt number.
    Returns ``(wait_seconds, reason_label)`` where ``reason_label`` is suitable
    for status/log decoration when a provider-specific policy fired.
    """
    if not is_zai_coding_overload_error(base_url=base_url, model=model, error=error):
        return default_wait, None
    if attempt <= short_attempts:
        return default_wait, "zai_coding_overload_short"

    idx = min(attempt - short_attempts - 1, len(_ZAI_CODING_OVERLOAD_LONG_BACKOFF) - 1)
    base_delay = _ZAI_CODING_OVERLOAD_LONG_BACKOFF[idx]
    # A smaller jitter ratio keeps long waits readable while still avoiding
    # synchronized retry storms across concurrent Aura Forge sessions.
    return jittered_backoff(1, base_delay=base_delay, max_delay=base_delay, jitter_ratio=0.2), "zai_coding_overload_long"


def zai_coding_overload_retry_ceiling(short_attempts: int = _ZAI_CODING_OVERLOAD_SHORT_ATTEMPTS) -> int:
    """Retry-loop ceiling needed for the full Z.AI overload backoff schedule.

    The adaptive policy runs ``short_attempts`` short retries, then walks the
    long-backoff table one entry per subsequent attempt. The retry loop gives
    up as soon as ``retry_count >= ceiling`` — and that check runs *before* the
    attempt's backoff is computed — so the ceiling must sit one past the final
    long-backoff entry for every long tier to actually execute.

    With the historical ``api_max_retries`` default (3) equal to
    ``short_attempts`` (3), the loop always gave up before reaching the long
    tier, leaving the whole long-backoff schedule as dead code. Callers extend
    the ceiling to this value for Z.AI Coding overload 429s so the
    30/60/90/120s waits run. The current default (10) already clears it; the
    call site keeps the guard so a user who lowers the ceiling still gets the
    full schedule.
    """
    return short_attempts + len(_ZAI_CODING_OVERLOAD_LONG_BACKOFF) + 1
