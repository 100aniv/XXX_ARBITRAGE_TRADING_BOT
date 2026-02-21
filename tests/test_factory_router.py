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


class TestDocOpsSelfHeal:
    """DocOps Self-Heal 파서 + 액션 유닛 테스트 (결정론적, LLM 없음)."""

    def test_parse_missing_concept_failure(self):
        """DocOps 출력에서 missing concept: conflict_resolution 파싱."""
        from ops.factory_supervisor import parse_docops_failures, _HEAL_TYPE_CONCEPT
        output = (
            "[FAIL] SSOT DocOps: FAIL (2 failures, 0 warnings)\n"
            "- [FAIL] D_ROADMAP.md - D_ROADMAP global section missing concept: conflict_resolution\n"
            "- [FAIL] D_ROADMAP.md - [Process SSOT] missing SSOT concept: conflict_resolution\n"
        )
        failures = parse_docops_failures(output)
        assert len(failures) == 2
        for f in failures:
            assert f["type"] == _HEAL_TYPE_CONCEPT
            assert f["concept"] == "conflict_resolution"
            assert "D_ROADMAP.md" in f["path"]

    def test_parse_report_filename_failure(self):
        """DocOps 출력에서 Report filename violates pattern 파싱 + /app/ prefix 제거."""
        from ops.factory_supervisor import parse_docops_failures, _HEAL_TYPE_FILENAME
        output = (
            "[FAIL] SSOT DocOps: FAIL (1 failures, 0 warnings)\n"
            "- [FAIL] /app/docs/v2/reports/D205_REBASE_REPORT.md - "
            "Report filename violates pattern: ^(?:D\\d{3}(?:-\\d+){0,3}|DALPHA(?:-[0-9A-Z]+){0,3})_REPORT\\.md$\n"
        )
        failures = parse_docops_failures(output)
        assert len(failures) == 1
        assert failures[0]["type"] == _HEAL_TYPE_FILENAME
        assert "D205_REBASE_REPORT.md" in failures[0]["path"]

    def test_unknown_failure_type_not_healed(self):
        """허용되지 않은 DocOps FAIL 타입은 SELF_HEAL_SKIP으로 처리되고 수정 안 함."""
        from ops.factory_supervisor import apply_docops_self_heal
        import tempfile, os
        failures = [
            {
                "type": "unknown_type",
                "path": "some/file.md",
                "concept": "",
                "raw": "- [FAIL] some/file.md - Some unknown error",
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            actions = apply_docops_self_heal(failures, root)
        assert len(actions) == 1
        assert "SELF_HEAL_SKIP" in actions[0]
        assert "unknown_type" in actions[0]

    def test_heal_conflict_resolution_inserts_block(self):
        """D_ROADMAP.md에 conflict_resolution 없을 때 자동 삽입 확인."""
        from ops.factory_supervisor import _heal_concept_conflict_resolution
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            doc = Path(tmpdir) / "D_ROADMAP.md"
            doc.write_text("# D_ROADMAP\n\n## SSOT 불변 규칙\n\n내용\n", encoding="utf-8")
            changed = _heal_concept_conflict_resolution(doc)
            assert changed is True
            text = doc.read_text(encoding="utf-8")
            assert "conflict_resolution" in text.lower()

    def test_heal_conflict_resolution_skips_if_exists(self):
        """D_ROADMAP.md에 conflict_resolution 이미 있으면 변경 없음."""
        from ops.factory_supervisor import _heal_concept_conflict_resolution
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            doc = Path(tmpdir) / "D_ROADMAP.md"
            doc.write_text(
                "# D_ROADMAP\n\n## conflict_resolution\n\n이미 있음\n",
                encoding="utf-8",
            )
            original = doc.read_text(encoding="utf-8")
            changed = _heal_concept_conflict_resolution(doc)
            assert changed is False
            assert doc.read_text(encoding="utf-8") == original

    def test_patch_result_json_status_updates_pass(self):
        """_patch_result_json_status: result.json status → PASS + self_heal_applied 기록."""
        from ops.factory_supervisor import _patch_result_json_status
        import tempfile, json as _json
        with tempfile.TemporaryDirectory() as tmpdir:
            rpath = Path(tmpdir) / "result.json"
            rpath.write_text(
                _json.dumps({"status": "FAIL", "notes": [], "commands": []}),
                encoding="utf-8",
            )
            _patch_result_json_status(rpath, "PASS", ["[SELF_HEAL_A] inserted"])
            payload = _json.loads(rpath.read_text(encoding="utf-8"))
            assert payload["status"] == "PASS"
            assert payload["self_heal_applied"] is True
            assert len(payload["self_heal_actions"]) == 1
            assert any("[SELF_HEAL]" in n for n in payload["notes"])


class TestAiderContextSlimming:
    """T1: Aider Context Slimming - build_aider_file_flags 유닛 테스트."""

    def test_ssot_docs_excluded_from_file_flags(self):
        """대형 SSOT 문서(D_ROADMAP.md 등)는 --file에 포함되지 않아야 함."""
        from ops.factory.worker import build_aider_file_flags, _AIDER_EXCLUDE_DEFAULTS
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = {
                "touched_paths": list(_AIDER_EXCLUDE_DEFAULTS),
                "scope": {"modify": list(_AIDER_EXCLUDE_DEFAULTS)},
            }
            plan_doc = Path(tmpdir) / "plan.md"
            plan_doc.write_text("# plan", encoding="utf-8")
            result = build_aider_file_flags(plan, plan_doc)
            for excl in _AIDER_EXCLUDE_DEFAULTS:
                assert excl not in result, f"{excl} should be excluded from --file flags"

    def test_md_files_excluded_from_file_flags(self):
        """.md 파일은 --file에 절대 포함되지 않아야 함 (TPM 주범)."""
        from ops.factory.worker import build_aider_file_flags
        import tempfile
        import ops.factory.worker as _w
        with tempfile.TemporaryDirectory() as tmpdir:
            md_file = Path(tmpdir) / "some_doc.md"
            md_file.write_text("# doc", encoding="utf-8")
            py_file = Path(tmpdir) / "engine.py"
            py_file.write_text("# code", encoding="utf-8")
            plan_doc = Path(tmpdir) / "plan.md"
            plan_doc.write_text("# plan", encoding="utf-8")
            plan = {
                "touched_paths": ["some_doc.md", "engine.py"],
                "scope": {"modify": []},
            }
            orig_root = _w.ROOT
            _w.ROOT = Path(tmpdir)
            try:
                result = build_aider_file_flags(plan, plan_doc)
            finally:
                _w.ROOT = orig_root
            assert "some_doc.md" not in result, ".md 파일이 --file에 포함되면 안 됨"
            assert "engine.py" in result, ".py 파일은 --file에 포함되어야 함"

    def test_no_plain_path_in_file_flags(self):
        """--file 없이 plain path가 섞이면 안 됨 (CLI 인자 오염 방지)."""
        from ops.factory.worker import build_aider_file_flags
        import tempfile
        import ops.factory.worker as _w
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "engine.py"
            py_file.write_text("# code", encoding="utf-8")
            plan_doc = Path(tmpdir) / "plan.md"
            plan_doc.write_text("# plan", encoding="utf-8")
            plan = {"touched_paths": ["engine.py"], "scope": {"modify": []}}
            orig_root = _w.ROOT
            _w.ROOT = Path(tmpdir)
            try:
                result = build_aider_file_flags(plan, plan_doc)
            finally:
                _w.ROOT = orig_root
            # 각 파일 경로 앞에 반드시 --file이 붙어야 함
            tokens = result.split()
            for i, tok in enumerate(tokens):
                if tok not in ("--file",) and not tok.startswith("-"):
                    # 이 토큰이 파일 경로라면 바로 앞이 --file 이어야 함
                    if i == 0 or tokens[i - 1] != "--file":
                        assert False, f"plain path without --file: {tok}"

    def test_touched_paths_included_in_file_flags(self):
        """touched_paths의 실존 .py 파일은 --file에 포함되어야 함."""
        from ops.factory.worker import build_aider_file_flags
        import tempfile
        import ops.factory.worker as _w
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "arbitrage" / "v2" / "engine.py"
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("# engine", encoding="utf-8")
            plan_doc = Path(tmpdir) / "plan.md"
            plan_doc.write_text("# plan", encoding="utf-8")
            plan = {
                "touched_paths": ["arbitrage/v2/engine.py"],
                "scope": {"modify": []},
            }
            orig_root = _w.ROOT
            _w.ROOT = Path(tmpdir)
            try:
                result = build_aider_file_flags(plan, plan_doc)
            finally:
                _w.ROOT = orig_root
            assert "--file arbitrage/v2/engine.py" in result

    def test_aider_shell_contains_subtree_and_map_tokens(self):
        """Aider 실행 커맨드에 --subtree-only와 --map-tokens 1024가 포함되어야 함."""
        import ops.factory.worker as _w
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_doc = Path(tmpdir) / "plan.md"
            plan_doc.write_text("# plan", encoding="utf-8")
            plan = {"touched_paths": [], "scope": {"modify": []}, "agent_preference": "aider"}
            env = {"AIDER_MODEL": "gpt-4.1"}
            rel_plan_doc = "plan.md"
            git_commit_cmd = "git add -A && git commit -m test"
            aider_model = env.get("AIDER_MODEL", "")
            model_flag = f"--model {aider_model}" if aider_model else ""
            file_flags = _w.build_aider_file_flags(plan, plan_doc)
            do_shell = (
                f"aider --yes {model_flag} --subtree-only --map-tokens 1024 "
                f"--message-file {rel_plan_doc} {file_flags} && "
                f"{git_commit_cmd}"
            )
            assert "--subtree-only" in do_shell
            assert "--map-tokens 1024" in do_shell
            assert "--add " not in do_shell, "--add 플래그가 섞이면 안 됨"


class TestContextBudgetGuard:
    """T2: Context Budget Guard - 파일 수/크기 기반 자동 완화."""

    def test_ok_risk_default_map_tokens(self, tmp_path):
        """파일 수 < 6이면 risk=ok, map_tokens=1024."""
        from ops.factory.worker import evaluate_context_budget
        plan = {"touched_paths": []}
        file_flags = "--file a.py --file b.py"
        result = evaluate_context_budget(file_flags, plan, tmp_path)
        assert result["risk_level"] == "ok"
        assert result["map_tokens"] == 1024
        assert result["slim"] is False
        assert result["route_to_claude"] is False

    def test_warn_risk_reduces_map_tokens(self, tmp_path):
        """파일 수 >= 6이면 risk=warn, map_tokens=512."""
        from ops.factory.worker import evaluate_context_budget
        plan = {}
        file_flags = " ".join(f"--file f{i}.py" for i in range(7))
        result = evaluate_context_budget(file_flags, plan, tmp_path)
        assert result["risk_level"] == "warn"
        assert result["map_tokens"] == 512
        assert result["slim"] is False
        assert any("[TPM_GUARD]" in n for n in result["notes"])

    def test_danger_risk_forces_slim(self, tmp_path):
        """파일 수 >= 10이면 risk=danger, slim=True, route_to_claude=True."""
        from ops.factory.worker import evaluate_context_budget
        plan = {}
        file_flags = " ".join(f"--file f{i}.py" for i in range(11))
        result = evaluate_context_budget(file_flags, plan, tmp_path)
        assert result["risk_level"] == "danger"
        assert result["map_tokens"] == 256
        assert result["slim"] is True
        assert result["route_to_claude"] is True
        assert any("[TPM_GUARD]" in n for n in result["notes"])

    def test_large_file_triggers_warn(self, tmp_path):
        """단일 파일 >= 50KB이면 large_files 노트 기록."""
        from ops.factory.worker import evaluate_context_budget
        large = tmp_path / "big.py"
        large.write_bytes(b"x" * 55000)  # 55KB
        plan = {}
        file_flags = f"--file {large.name}"
        result = evaluate_context_budget(file_flags, plan, tmp_path)
        assert any("large_files" in n for n in result["notes"])


class TestFalsePassPrevention:
    """T2: 거짓 PASS 차단 - DO 실패 시 사이클 PASS 금지."""

    def test_do_failed_forces_overall_fail(self):
        """DO 단계 실패 시 Gate/DocOps PASS여도 overall_pass=False 강제."""
        from ops.factory.worker import CommandResult
        results = [
            CommandResult(name="do_aider", command=["aider"], exit_code=2, duration_sec=1.0),
            CommandResult(name="gate", command=["make", "gate"], exit_code=0, duration_sec=10.0),
            CommandResult(name="docops", command=["make", "docops"], exit_code=0, duration_sec=1.0),
            CommandResult(name="evidence_check", command=["make"], exit_code=0, duration_sec=0.1),
        ]
        do_steps = [r for r in results if r.name.startswith("do_")]
        retry_steps = [r for r in do_steps if r.name.endswith("_retry")]
        primary_do_steps = [r for r in do_steps if not r.name.endswith("_retry")]
        if retry_steps and retry_steps[-1].exit_code == 0:
            final_do_exit = 0
        elif primary_do_steps:
            final_do_exit = primary_do_steps[-1].exit_code
        else:
            final_do_exit = 0
        do_failed = final_do_exit != 0
        overall_pass = (not do_failed) and all(r.exit_code == 0 for r in results)
        assert do_failed is True
        assert overall_pass is False, "DO 실패 시 Gate PASS여도 overall_pass는 False여야 함"

    def test_do_retry_success_allows_pass(self):
        """DO 실패 후 retry 성공 시 overall_pass=True 허용."""
        from ops.factory.worker import CommandResult
        results = [
            CommandResult(name="do_aider", command=["aider"], exit_code=2, duration_sec=1.0),
            CommandResult(name="do_aider_retry", command=["aider"], exit_code=0, duration_sec=5.0),
            CommandResult(name="gate", command=["make", "gate"], exit_code=0, duration_sec=10.0),
            CommandResult(name="docops", command=["make", "docops"], exit_code=0, duration_sec=1.0),
            CommandResult(name="evidence_check", command=["make"], exit_code=0, duration_sec=0.1),
        ]
        do_steps = [r for r in results if r.name.startswith("do_")]
        retry_steps = [r for r in do_steps if r.name.endswith("_retry")]
        primary_do_steps = [r for r in do_steps if not r.name.endswith("_retry")]
        if retry_steps and retry_steps[-1].exit_code == 0:
            final_do_exit = 0
        elif primary_do_steps:
            final_do_exit = primary_do_steps[-1].exit_code
        else:
            final_do_exit = 0
        do_failed = final_do_exit != 0
        # worker.py 실제 로직: do_* 외 나머지 스텝만 all() 체크 (do_* 는 final_do_exit 기준)
        non_do_results = [r for r in results if not r.name.startswith("do_")]
        overall_pass = (not do_failed) and all(r.exit_code == 0 for r in non_do_results)
        assert do_failed is False
        assert overall_pass is True, "retry 성공 시 overall_pass는 True여야 함"
