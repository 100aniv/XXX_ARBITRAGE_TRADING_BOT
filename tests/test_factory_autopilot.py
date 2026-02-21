"""Unit tests for scripts/factory_autopilot.py — ledger parsing, AC selection, ledger update."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from scripts.factory_autopilot import (
    parse_ledger_rows,
    pick_next_open_ac,
    update_ledger_done,
    build_plan_json,
    extract_paths,
    _is_v2_alpha,
    _classify_intent,
    _infer_risk,
)


SAMPLE_LEDGER = textwrap.dedent("""\
generated_at: 2026-02-20T09:00:00Z
updated_at: 2026-02-20
sources: D_ROADMAP.md
rules: evidence-driven
queue_policy: SEQUENTIAL_QUEUE
legacy_policy: D200 미만 제외
| AC_ID | TITLE | STAGE | STATUS | CANONICAL_EVIDENCE | LAST_COMMIT | DUP_GROUP_KEY | NOTES |
|---|---|---|---|---|---|---|---|
| D_ALPHA-0::AC-1 | universe size 100 artifact | D_ALPHA | DONE | logs/evidence/test/ | abc1234 | — | tests/test_alpha.py |
| D_ALPHA-0::AC-2 | survey unique symbols >= 80 | D_ALPHA | OPEN | NONE | UNKNOWN | — | REAL survey |
| D_ALPHA-0::AC-3 | fix symbols path | D_ALPHA | OPEN | NONE | UNKNOWN | — | runtime fix |
| D206-0::AC-1 | Reality Scan | D206 | OPEN | NONE | UNKNOWN | — | — |
| D000-3::AC-1 | DOCOPS_TOKEN_POLICY | D000 | OPEN | NONE | UNKNOWN | — | [META] |
""")


@pytest.fixture
def ledger_file(tmp_path: Path) -> Path:
    p = tmp_path / "AC_LEDGER.md"
    p.write_text(SAMPLE_LEDGER, encoding="utf-8")
    return p


class TestParseLedgerRows:
    def test_parse_all_rows(self, ledger_file: Path):
        rows = parse_ledger_rows(ledger_file)
        assert len(rows) == 5

    def test_fields_correct(self, ledger_file: Path):
        rows = parse_ledger_rows(ledger_file)
        first = rows[0]
        assert first["ac_id"] == "D_ALPHA-0::AC-1"
        assert first["status"] == "DONE"
        assert first["stage"] == "D_ALPHA"

    def test_skip_header_separator(self, ledger_file: Path):
        rows = parse_ledger_rows(ledger_file)
        ac_ids = [r["ac_id"] for r in rows]
        assert "AC_ID" not in ac_ids


class TestPickNextOpenAC:
    def test_picks_first_open(self, ledger_file: Path):
        rows = parse_ledger_rows(ledger_file)
        ac = pick_next_open_ac(rows)
        assert ac is not None
        assert ac["ac_id"] == "D_ALPHA-0::AC-2"

    def test_skips_done(self, ledger_file: Path):
        rows = parse_ledger_rows(ledger_file)
        ac = pick_next_open_ac(rows)
        assert ac["status"] == "OPEN"

    def test_returns_none_when_all_done(self, tmp_path: Path):
        content = textwrap.dedent("""\
        | AC_ID | TITLE | STAGE | STATUS | CANONICAL_EVIDENCE | LAST_COMMIT | DUP_GROUP_KEY | NOTES |
        |---|---|---|---|---|---|---|---|
        | D_ALPHA-0::AC-1 | done item | D_ALPHA | DONE | logs/e/ | abc | — | — |
        """)
        p = tmp_path / "ledger.md"
        p.write_text(content, encoding="utf-8")
        rows = parse_ledger_rows(p)
        assert pick_next_open_ac(rows) is None


class TestUpdateLedgerDone:
    def test_marks_done_and_updates_evidence(self, ledger_file: Path):
        ok = update_ledger_done(
            "D_ALPHA-0::AC-2",
            "logs/evidence/new_evidence/",
            "def5678",
            ledger_file,
        )
        assert ok is True
        rows = parse_ledger_rows(ledger_file)
        updated = next(r for r in rows if r["ac_id"] == "D_ALPHA-0::AC-2")
        assert updated["status"] == "DONE"
        assert updated["canonical_evidence"] == "logs/evidence/new_evidence/"
        assert updated["last_commit"] == "def5678"

    def test_does_not_touch_already_done(self, ledger_file: Path):
        ok = update_ledger_done(
            "D_ALPHA-0::AC-1",
            "logs/evidence/whatever/",
            "xyz",
            ledger_file,
        )
        assert ok is False

    def test_preserves_other_rows(self, ledger_file: Path):
        update_ledger_done("D_ALPHA-0::AC-2", "logs/e/", "abc", ledger_file)
        rows = parse_ledger_rows(ledger_file)
        assert len(rows) == 5
        assert rows[2]["status"] == "OPEN"
        assert rows[2]["ac_id"] == "D_ALPHA-0::AC-3"

    def test_advance_after_done(self, ledger_file: Path):
        """After marking AC-2 DONE, pick_next_open_ac should return AC-3."""
        update_ledger_done("D_ALPHA-0::AC-2", "logs/e/", "abc", ledger_file)
        rows = parse_ledger_rows(ledger_file)
        ac = pick_next_open_ac(rows)
        assert ac is not None
        assert ac["ac_id"] == "D_ALPHA-0::AC-3"


class TestBuildPlanJson:
    def test_no_safe_prefix(self, ledger_file: Path):
        rows = parse_ledger_rows(ledger_file)
        ac = pick_next_open_ac(rows)
        plan = build_plan_json(ac, {"modify": [], "readonly": [], "forbidden": []}, [])
        assert plan["ticket_id"] == "D_ALPHA-0::AC-2"
        assert "SAFE::" not in plan["ticket_id"]

    def test_mode_autopilot(self, ledger_file: Path):
        rows = parse_ledger_rows(ledger_file)
        ac = pick_next_open_ac(rows)
        plan = build_plan_json(ac, {"modify": [], "readonly": [], "forbidden": []}, [])
        assert plan["mode"] == "AUTOPILOT"

    def test_schema_version(self, ledger_file: Path):
        rows = parse_ledger_rows(ledger_file)
        ac = pick_next_open_ac(rows)
        plan = build_plan_json(ac, {}, [])
        assert plan["schema_version"] == "1.0"


class TestIsV2Alpha:
    def test_alpha_stage(self):
        assert _is_v2_alpha({"ac_id": "D_ALPHA-0::AC-1", "stage": "D_ALPHA"}) is True

    def test_d206_stage(self):
        assert _is_v2_alpha({"ac_id": "D206-0::AC-1", "stage": "D206"}) is True

    def test_d000_meta_excluded(self):
        assert _is_v2_alpha({"ac_id": "D000-3::AC-1", "stage": "D000"}) is False


class TestExtractPaths:
    def test_finds_py_file(self):
        paths = extract_paths("fix runtime", "scripts/run_alpha_pipeline.py")
        assert "scripts/run_alpha_pipeline.py" in paths

    def test_finds_dir_path(self):
        paths = extract_paths("OBI data", "arbitrage/v2/core/engine.py needed")
        assert any("arbitrage/v2/core/engine.py" in p for p in paths)


class TestClassifyIntent:
    def test_design_keyword(self):
        assert _classify_intent("refactor engine architecture") == "design"

    def test_implementation_keyword(self):
        assert _classify_intent("fix bug in universe loader") == "implementation"

    def test_default_implementation(self):
        assert _classify_intent("something else entirely") == "implementation"


class TestInferRisk:
    def test_high_risk(self):
        assert _infer_risk("core engine pnl", "") == "high"

    def test_low_risk(self):
        assert _infer_risk("docops gate check", "") == "low"

    def test_mid_risk(self):
        assert _infer_risk("universe loader", "") == "mid"


class TestTwoCycleDryRun:
    """Integration-style test: simulate 2 cycles of autopilot logic."""

    def test_two_cycle_advance(self, ledger_file: Path):
        """Cycle 1: AC-2 PASS -> DONE. Cycle 2: AC-3 selected (not AC-2 again)."""
        rows = parse_ledger_rows(ledger_file)
        ac1 = pick_next_open_ac(rows)
        assert ac1["ac_id"] == "D_ALPHA-0::AC-2"

        update_ledger_done(ac1["ac_id"], "logs/evidence/cycle1/", "aaa1111", ledger_file)

        rows2 = parse_ledger_rows(ledger_file)
        ac2 = pick_next_open_ac(rows2)
        assert ac2 is not None
        assert ac2["ac_id"] == "D_ALPHA-0::AC-3"
        assert ac2["ac_id"] != ac1["ac_id"]

    def test_done_count_increments(self, ledger_file: Path):
        rows_before = parse_ledger_rows(ledger_file)
        done_before = sum(1 for r in rows_before if r["status"] == "DONE")

        update_ledger_done("D_ALPHA-0::AC-2", "logs/e/", "abc", ledger_file)
        rows_after = parse_ledger_rows(ledger_file)
        done_after = sum(1 for r in rows_after if r["status"] == "DONE")

        assert done_after == done_before + 1
