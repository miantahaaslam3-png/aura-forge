"""Live retry progress on every driver (opencode parity).

When a provider call fails transiently the agent retries on the 2s→10s
schedule, but the wait must not look like a hang. Before this, retry lines
were *buffered* — a user saw a frozen spinner for the whole backoff and then
either a late success or a terminal error.

These tests drive the real conversation loop and assert the contract the
surfaces rely on:

- the error + attempt count + countdown are published live *before* the wait,
- the countdown ticks down while the agent sleeps,
- once an attempt succeeds the live line is retired (empty thinking delta),
  so the response takes over — the error "disappears" and the turn continues.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from run_agent import AIAgent


class ReadTimeout(Exception):
    pass


def _make_tool_defs():
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "search",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def _make_agent(max_retries: int = 3) -> AIAgent:
    with (
        patch("run_agent.get_tool_definitions", return_value=_make_tool_defs()),
        patch("run_agent.check_toolset_requirements", return_value={}),
        patch("run_agent.OpenAI", return_value=MagicMock()),
    ):
        agent = AIAgent(
            api_key="primary-key-abcdef12",
            base_url="https://example.com/v1",
            model="test/model",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )
    agent.client = MagicMock()
    agent._api_max_retries = max_retries
    return agent


def _mock_response(content: str):
    msg = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    return SimpleNamespace(choices=[choice], model="test/model", usage=None)


def _retry_frames(notices: list[str], attempt: int, max_retries: int) -> list[int]:
    """Seconds announced by ``Retrying in Ns (attempt n/m)`` frames."""
    pattern = re.compile(
        rf"Retrying in (\d+)s \(attempt {attempt}/{max_retries}\)"
    )
    return [int(m.group(1)) for m in (pattern.search(n) for n in notices) if m]


def test_retry_publishes_live_countdown_and_clears_after_success():
    agent = _make_agent(max_retries=3)
    notices: list[str] = []
    agent.thinking_callback = notices.append
    calls: list[int] = []

    def fake_api_call(_api_kwargs):
        calls.append(1)
        if len(calls) <= 2:
            raise ReadTimeout("read timed out")
        return _mock_response("recovered after retries")

    # The backoff length is unit-tested separately; here keep each wait short
    # but non-zero so the once-per-second countdown actually emits a tick.
    with (
        patch.object(agent, "_interruptible_api_call", side_effect=fake_api_call),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
        patch("agent.conversation_loop.retry_delay_seconds", side_effect=lambda _a, **_k: 1.0),
        patch("agent.model_metadata.get_model_context_length", return_value=200000),
    ):
        result = agent.run_conversation("hello")

    assert result["completed"] is True
    assert result["final_response"] == "recovered after retries"
    assert len(calls) == 3

    retry_lines = [n for n in notices if "Retrying in" in n]
    assert retry_lines, f"no live retry progress published: {notices!r}"

    # Both failed attempts announced themselves, labelled with the attempt
    # number the user sees (1-based, out of the configured budget).
    assert _retry_frames(notices, 1, 3), notices
    assert _retry_frames(notices, 2, 3), notices

    # The wait is a countdown, not a single frozen line: attempt 1 starts at
    # 1s and ticks to 0s while the agent sleeps.
    assert _retry_frames(notices, 1, 3)[0] == 1
    assert _retry_frames(notices, 1, 3)[-1] == 0

    # The error stays visible on the retry line (that is what the user reads
    # to know why the turn is waiting).
    assert any("timed out" in line for line in retry_lines), retry_lines

    # Success retires the live line so the response — not a stale countdown —
    # is what remains on screen.
    last_retry = max(i for i, n in enumerate(notices) if "Retrying in" in n)
    assert "" in notices[last_retry:], (
        "a successful retry must clear the live retry line so the response "
        f"can take over; notices were {notices!r}"
    )


def test_exhausted_retries_clear_the_live_line_before_the_failure_surface():
    """Terminal failure must not leave a stale countdown on a surface."""
    agent = _make_agent(max_retries=2)
    notices: list[str] = []
    agent.thinking_callback = notices.append

    def always_timeout(_api_kwargs):
        raise ReadTimeout("read timed out")

    with (
        patch.object(agent, "_interruptible_api_call", side_effect=always_timeout),
        patch.object(agent, "_persist_session"),
        patch.object(agent, "_save_trajectory"),
        patch.object(agent, "_cleanup_task_resources"),
        patch("agent.conversation_loop.retry_delay_seconds", side_effect=lambda _a, **_k: 0.4),
        patch("agent.model_metadata.get_model_context_length", return_value=200000),
    ):
        result = agent.run_conversation("hello")

    assert result.get("completed") is False
    retry_lines = [n for n in notices if "Retrying in" in n]
    assert retry_lines, f"no live retry progress published: {notices!r}"
    last_retry = max(i for i, n in enumerate(notices) if "Retrying in" in n)
    assert "" in notices[last_retry:], (
        "the live retry line must be cleared before the terminal error is "
        f"surfaced; notices were {notices!r}"
    )
