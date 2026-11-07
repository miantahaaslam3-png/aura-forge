"""Tests for agent.api_max_retries config surface.

Closes #11616 — make the agent's API retry count user-configurable so
fallback-provider setups can fail over faster on flaky primaries instead of
burning ~3x180s on the same stall.

The default itself is owned by ``agent.retry_utils.DEFAULT_API_MAX_RETRIES``
(opencode parity: 10 attempts on the 2s→10s capped schedule). Asserting the
relationship instead of the literal keeps the default and the schedule from
drifting apart without freezing a number here.
"""
from unittest.mock import patch

from agent.retry_utils import DEFAULT_API_MAX_RETRIES
from run_agent import AIAgent


def _make_agent(api_max_retries=None):
    """Build an AIAgent with a mocked config.load_config that returns a
    config tree containing the given agent.api_max_retries (or default)."""
    cfg = {"agent": {}}
    if api_max_retries is not None:
        cfg["agent"]["api_max_retries"] = api_max_retries

    with patch("run_agent.OpenAI"), \
         patch("auraforge_cli.config.load_config", return_value=cfg), \
         patch("auraforge_cli.config.load_config_readonly", return_value=cfg):
        return AIAgent(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="test/model",
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
        )


def test_default_api_max_retries_matches_retry_schedule():
    """No config override → the schedule's designed attempt count."""
    agent = _make_agent()
    assert agent._api_max_retries == DEFAULT_API_MAX_RETRIES


def test_api_max_retries_honors_config_override():
    """Setting agent.api_max_retries in config propagates to the agent."""
    agent = _make_agent(api_max_retries=1)
    assert agent._api_max_retries == 1

    agent2 = _make_agent(api_max_retries=5)
    assert agent2._api_max_retries == 5




