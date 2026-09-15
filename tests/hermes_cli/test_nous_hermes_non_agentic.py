"""Tests for the Nous-Aura Forge-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"auraforge"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``auraforge-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "auraforge" tag namespace.

``is_nous_hermes_non_agentic`` should only match the actual Nous Research
Aura Forge-3 / Aura Forge-4 chat family.
"""

from __future__ import annotations

import pytest

from hermes_cli.model_switch import (
    _HERMES_MODEL_WARNING,
    _check_hermes_model_warning,
    is_nous_hermes_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Aura Forge-3-Llama-3.1-70B",
        "NousResearch/Aura Forge-3-Llama-3.1-405B",
        "auraforge-3",
        "Aura Forge-3",
        "auraforge-4",
        "auraforge-4-405b",
        "hermes_4_70b",
        "openrouter/hermes3:70b",
        "openrouter/nousresearch/auraforge-4-405b",
        "NousResearch/Hermes3",
        "auraforge-3.1",
    ],
)
def test_matches_real_nous_hermes_chat_models(model_name: str) -> None:
    assert is_nous_hermes_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Aura Forge 3/4"
    )
    assert _check_hermes_model_warning(model_name) == _HERMES_MODEL_WARNING


