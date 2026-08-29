"""Tests for the Nous-Aura Forge-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"aura"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``aura-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "aura" tag namespace.

``is_nous_aura_non_agentic`` should only match the actual Nous Research
Aura Forge-3 / Aura Forge-4 chat family.
"""

from __future__ import annotations

import pytest

from aura_cli.model_switch import (
    _AURA_MODEL_WARNING,
    _check_aura_forge_model_warning,
    is_nous_aura_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Aura Forge-3-Llama-3.1-70B",
        "NousResearch/Aura Forge-3-Llama-3.1-405B",
        "aura-3",
        "Aura Forge-3",
        "aura-4",
        "aura-4-405b",
        "aura_forge_4_70b",
        "openrouter/aura3:70b",
        "openrouter/nousresearch/aura-4-405b",
        "NousResearch/Aura Forge3",
        "aura-3.1",
    ],
)
def test_matches_real_nous_aura_forge_chat_models(model_name: str) -> None:
    assert is_nous_aura_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Aura 3/4"
    )
    assert _check_aura_forge_model_warning(model_name) == _AURA_MODEL_WARNING


@pytest.mark.parametrize(
    "model_name",
    [
        # Kyle's local Modelfile — qwen3:14b under a custom tag
        "aura-brain:qwen3-14b-ctx16k",
        "aura-brain:qwen3-14b-ctx32k",
        "aura-honcho:qwen3-8b-ctx8k",
        # Plain unrelated models
        "qwen3:14b",
        "qwen3-coder:30b",
        "qwen2.5:14b",
        "claude-opus-4-6",
        "anthropic/claude-sonnet-4.5",
        "gpt-5",
        "openai/gpt-4o",
        "google/gemini-2.5-flash",
        "deepseek-chat",
        # Non-chat Aura models we don't warn about
        "aura-llm-2",
        "aura-forge2-pro",
        "nous-hermes-2-mistral",
        # Edge cases
        "",
        "aura",  # bare "aura" isn't the 3/4 family
        "aura-brain",
        "brain-aura-forge-3-impostor",  # "3" not preceded by /: boundary
    ],
)
def test_does_not_match_unrelated_models(model_name: str) -> None:
    assert not is_nous_aura_non_agentic(model_name), (
        f"expected {model_name!r} NOT to be flagged as Nous Aura 3/4"
    )
    assert _check_aura_forge_model_warning(model_name) == ""


def test_none_like_inputs_are_safe() -> None:
    assert is_nous_aura_non_agentic("") is False
    # Defensive: the helper shouldn't crash on None-ish falsy input either.
    assert _check_aura_forge_model_warning("") == ""
