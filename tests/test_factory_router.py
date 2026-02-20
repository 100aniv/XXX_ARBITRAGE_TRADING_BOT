"""Factory Smart Router tests (deterministic, LLM-free).

Tests:
- Intent keyword classification
- Agent selection (keyword + file-scope heuristic)
- Tier cap enforcement
- Escalation condition checks
- Dual-provider model resolution
"""
from __future__ import annotations

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.factory.controller import (
    classify_intent,
    select_agent,
    FILE_SCOPE_THRESHOLD,
)
from ops.factory_supervisor import (
    normalize_tier,
    clamp_tier,
    tier_index,
    infer_model_tier,
    escalate_tier,
    can_escalate_check,
    resolve_agent_provider,
    resolve_model_selection,
    AGENT_DEFAULT_PROVIDER,
    DEFAULT_MODELS,
    MODEL_TIERS,
)


class TestClassifyIntent:
    def test_design_keywords(self):
        assert classify_intent("SSOT Architecture Refactor") == "design"
        assert classify_intent("DocOps token policy") == "design"
        assert classify_intent("Roadmap restructure") == "design"
        assert classify_intent("Audit legacy modules") == "design"
        assert classify_intent("Migrate to V2") == "design"

    def test_implementation_keywords(self):
        assert classify_intent("Implement OBI calculator") == "implementation"
        assert classify_intent("Fix winrate bug") == "implementation"
        assert classify_intent("Add test for engine") == "implementation"
        assert classify_intent("Patch rate limiter") == "implementation"
        assert classify_intent("Hotfix trade closure") == "implementation"

    def test_default_is_implementation(self):
        assert classify_intent("Unknown task type") == "implementation"
        assert classify_intent("") == "implementation"

    def test_notes_also_checked(self):
        assert classify_intent("Task", "needs refactor") == "design"
        assert classify_intent("Task", "fix the bug") == "implementation"


class TestSelectAgent:
    def test_design_intent_selects_claude_code(self):
        assert select_agent("design", 3) == "claude_code"

    def test_implementation_intent_selects_aider(self):
        assert select_agent("implementation", 3) == "aider"

    def test_file_scope_heuristic_overrides(self):
        assert select_agent("implementation", FILE_SCOPE_THRESHOLD) == "claude_code"
        assert select_agent("implementation", FILE_SCOPE_THRESHOLD + 5) == "claude_code"

    def test_below_threshold_uses_intent(self):
        assert select_agent("implementation", FILE_SCOPE_THRESHOLD - 1) == "aider"
        assert select_agent("design", FILE_SCOPE_THRESHOLD - 1) == "claude_code"

    def test_default_is_aider(self):
        assert select_agent("unknown_intent", 2) == "aider"


class TestTierOperations:
    def test_normalize_tier(self):
        assert normalize_tier("low") == "low"
        assert normalize_tier("mid") == "mid"
        assert normalize_tier("high") == "high"
        assert normalize_tier("invalid") == "high"
        assert normalize_tier("") == "high"

    def test_clamp_tier(self):
        assert clamp_tier("high", "mid") == "mid"
        assert clamp_tier("high", "high") == "high"
        assert clamp_tier("low", "high") == "low"
        assert clamp_tier("mid", "low") == "low"

    def test_tier_index_ordering(self):
        assert tier_index("low") < tier_index("mid") < tier_index("high")

    def test_infer_model_tier_openai(self):
        assert infer_model_tier("gpt-4.1-mini") == "low"
        assert infer_model_tier("gpt-4.1") == "mid"
        assert infer_model_tier("gpt-4o") == "mid"
        assert infer_model_tier("o3") == "high"

    def test_infer_model_tier_anthropic(self):
        assert infer_model_tier("claude-sonnet-4-20250514") == "mid"
        assert infer_model_tier("claude-opus-4-20250514") == "high"
        assert infer_model_tier("claude-haiku-3") == "low"

    def test_infer_empty_is_high(self):
        assert infer_model_tier("") == "high"


class TestEscalation:
    def test_escalate_tier_low_to_mid(self):
        assert escalate_tier("low") == "mid"

    def test_escalate_tier_mid_to_high(self):
        assert escalate_tier("mid") == "high"

    def test_escalate_tier_high_stays(self):
        assert escalate_tier("high") == "high"

    def test_can_escalate_enabled(self):
        env = {"ROUTER_ESCALATE_ON_GATE_FAIL": "1", "ROUTER_ESCALATE_MAX_STEP": "1"}
        assert can_escalate_check("mid", "high", 0, env) is True

    def test_can_escalate_disabled(self):
        env = {"ROUTER_ESCALATE_ON_GATE_FAIL": "0", "ROUTER_ESCALATE_MAX_STEP": "1"}
        assert can_escalate_check("mid", "high", 0, env) is False

    def test_can_escalate_max_step_reached(self):
        env = {"ROUTER_ESCALATE_ON_GATE_FAIL": "1", "ROUTER_ESCALATE_MAX_STEP": "1"}
        assert can_escalate_check("mid", "high", 1, env) is False

    def test_can_escalate_already_at_max_tier(self):
        env = {"ROUTER_ESCALATE_ON_GATE_FAIL": "1", "ROUTER_ESCALATE_MAX_STEP": "1"}
        assert can_escalate_check("high", "high", 0, env) is False

    def test_can_escalate_blocked_by_tier_cap(self):
        env = {"ROUTER_ESCALATE_ON_GATE_FAIL": "1", "ROUTER_ESCALATE_MAX_STEP": "1"}
        assert can_escalate_check("mid", "mid", 0, env) is False


class TestDualProviderResolution:
    def test_default_providers(self):
        assert resolve_agent_provider("aider", {}) == "openai"
        assert resolve_agent_provider("claude_code", {}) == "anthropic"

    def test_env_provider_override(self):
        env = {"AIDER_PROVIDER": "anthropic"}
        assert resolve_agent_provider("aider", env) == "anthropic"

    def test_invalid_provider_falls_back(self):
        env = {"AIDER_PROVIDER": "invalid"}
        assert resolve_agent_provider("aider", env) == "openai"

    def test_resolve_model_selection_defaults(self):
        plan = {"risk_level": "mid", "model_budget": "mid"}
        env = {}
        result = resolve_model_selection(plan, env)
        assert result["aider_provider"] == "openai"
        assert result["claude_code_provider"] == "anthropic"
        assert result["aider_model"] == DEFAULT_MODELS["openai"]["mid"]
        assert result["claude_code_model"] == DEFAULT_MODELS["anthropic"]["mid"]

    def test_resolve_model_tier_cap(self):
        plan = {"risk_level": "high", "model_budget": "high"}
        env = {"AIDER_MODEL_MAX_TIER": "mid"}
        result = resolve_model_selection(plan, env)
        assert result["aider_model"] == DEFAULT_MODELS["openai"]["mid"]
        assert result["claude_code_model"] == DEFAULT_MODELS["anthropic"]["high"]

    def test_resolve_model_env_per_tier_override(self):
        plan = {"risk_level": "mid", "model_budget": "mid"}
        env = {"AIDER_MODEL_MID": "custom-gpt-model"}
        result = resolve_model_selection(plan, env)
        assert result["aider_model"] == "custom-gpt-model"

    def test_resolve_model_override_tier(self):
        plan = {"risk_level": "mid", "model_budget": "low"}
        env = {}
        result = resolve_model_selection(plan, env, override_tier="mid")
        assert result["aider_model"] == DEFAULT_MODELS["openai"]["mid"]

    def test_provider_override_changes_defaults(self):
        plan = {"risk_level": "mid", "model_budget": "mid"}
        env = {"AIDER_PROVIDER": "anthropic"}
        result = resolve_model_selection(plan, env)
        assert result["aider_provider"] == "anthropic"
        assert result["aider_model"] == DEFAULT_MODELS["anthropic"]["mid"]


from ops.factory.controller import extract_paths_from_notes


class TestPathExtraction:
    """NOTES에서 경로 추출 -> file_count 산출 -> agent 분기 테스트."""

    def test_extract_single_py_file(self):
        paths = extract_paths_from_notes("테스트 보장", "tests/test_d_alpha_0_universe_truth.py")
        assert "tests/test_d_alpha_0_universe_truth.py" in paths
        assert len(paths) == 1

    def test_extract_multiple_paths_with_plus(self):
        paths = extract_paths_from_notes("돈 로직", "arbitrage/domain + arbitrage/v2/core/opportunity")
        assert "arbitrage/domain" in paths
        assert "arbitrage/v2/core/opportunity" in paths
        assert len(paths) == 2

    def test_extract_script_path(self):
        paths = extract_paths_from_notes("Canonical entrypoint", "scripts/run_alpha_pipeline.py")
        assert "scripts/run_alpha_pipeline.py" in paths

    def test_empty_notes_returns_empty(self):
        paths = extract_paths_from_notes("REAL survey 증거 필요", "")
        assert paths == []

    def test_no_path_in_notes(self):
        paths = extract_paths_from_notes("Redis 연결 실패 시 SystemExit(1)", "—")
        assert paths == []

    def test_file_count_1_implement_selects_aider(self):
        """file_count=1 + intent=implementation => aider."""
        paths = extract_paths_from_notes("Implement OBI calculator", "")
        file_count = len(paths) if paths else 1
        intent = classify_intent("Implement OBI calculator", "")
        agent = select_agent(intent, file_count)
        assert file_count == 1
        assert intent == "implementation"
        assert agent == "aider"

    def test_file_count_6_selects_claude_code(self):
        """file_count=6 => claude_code (File-Scope Heuristic)."""
        notes = "arbitrage/v2/a.py, arbitrage/v2/b.py, tests/t1.py, tests/t2.py, scripts/s1.py, docs/d.md"
        paths = extract_paths_from_notes("Multi-file change", notes)
        file_count = len(paths) if paths else 1
        intent = classify_intent("Multi-file change", notes)
        agent = select_agent(intent, file_count)
        assert file_count >= 5
        assert agent == "claude_code"

    def test_empty_notes_fallback_design_selects_claude_code(self):
        """notes 비어있음(fallback=1) + intent=design => claude_code."""
        paths = extract_paths_from_notes("SSOT Architecture Refactor", "")
        file_count = len(paths) if paths else 1
        intent = classify_intent("SSOT Architecture Refactor", "")
        agent = select_agent(intent, file_count)
        assert file_count == 1
        assert intent == "design"
        assert agent == "claude_code"

    def test_real_ledger_row_ac1(self):
        """실제 AC_LEDGER row: D_ALPHA-0::AC-1."""
        title = "universe(top=100) 로딩 시 universe_size=100 아티팩트 기록"
        notes = "tests/test_d_alpha_0_universe_truth.py"
        paths = extract_paths_from_notes(title, notes)
        file_count = len(paths) if paths else 1
        intent = classify_intent(title, notes)
        agent = select_agent(intent, file_count)
        assert file_count == 1
        assert intent == "implementation"  # "test" keyword
        assert agent == "aider"

    def test_real_ledger_row_ac4(self):
        """실제 AC_LEDGER row: D_ALPHA-1::AC-4."""
        title = "돈 로직 변경은 엔진(core/domain)에만 존재"
        notes = "arbitrage/domain + arbitrage/v2/core/opportunity"
        paths = extract_paths_from_notes(title, notes)
        file_count = len(paths) if paths else 1
        intent = classify_intent(title, notes)
        agent = select_agent(intent, file_count)
        assert file_count == 2
        assert agent == "aider"  # file_count < 5, intent != design
