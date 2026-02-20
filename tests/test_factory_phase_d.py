# -*- coding: utf-8 -*-
"""Factory Phase D minimal validation tests."""

from __future__ import annotations

from pathlib import Path

from ops import factory_supervisor as supervisor


def test_model_policy_blocks_high_on_low_risk() -> None:
    plan = {
        "risk_level": "low",
        "model_budget": "high",
        "model_overrides": {
            "aider": "claude-4-6-apex",
            "claude_code": "claude-4-6-apex",
        },
    }
    env_keys = {
        "AIDER_MODEL_MAX_TIER": "high",
        "CLAUDE_CODE_MODEL_MAX_TIER": "high",
    }

    selected = supervisor.resolve_model_selection(plan, env_keys)

    assert selected["aider_model"] != "claude-4-6-apex"
    assert selected["claude_code_model"] != "claude-4-6-apex"


def test_model_policy_allows_high_when_risk_high() -> None:
    plan = {
        "risk_level": "high",
        "model_budget": "high",
        "model_overrides": {
            "aider": "claude-4-6-apex",
            "claude_code": "claude-4-6-apex",
        },
    }
    env_keys = {
        "AIDER_MODEL_MAX_TIER": "high",
        "CLAUDE_CODE_MODEL_MAX_TIER": "high",
    }

    selected = supervisor.resolve_model_selection(plan, env_keys)

    assert selected["aider_model"] == "claude-4-6-apex"
    assert selected["claude_code_model"] == "claude-4-6-apex"


def test_resolve_env_file_no_fallback(tmp_path: Path) -> None:
    missing_env = tmp_path / "missing.factory.env"
    resolved, warnings, missing = supervisor.resolve_env_file(str(missing_env))

    assert missing is True
    assert resolved == missing_env
    assert warnings
