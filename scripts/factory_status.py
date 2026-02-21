#!/usr/bin/env python3
"""Factory Status Dashboard (Deterministic, LLM-free).

AC_LEDGER.md를 파싱하여 V2/ALPHA 진행률, 현재 포인터, 최근 Gate 결과를 출력.
LLM 호출 없이 결정론적으로 0.1초 내 결과 반환.

Usage:
    python3 scripts/factory_status.py
    just factory_status
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "docs" / "v2" / "design" / "AC_LEDGER.md"
EVIDENCE_ROOT = ROOT / "logs" / "evidence"
PLAN_PATH = ROOT / "logs" / "autopilot" / "plan.json"
RESULT_PATH = ROOT / "logs" / "autopilot" / "result.json"


def parse_ledger_v2_rows(ledger_path: Path) -> list[dict[str, str]]:
    """AC_LEDGER.md에서 V2/ALPHA 행만 파싱."""
    if not ledger_path.exists():
        return []
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, str]] = []
    for line in lines:
        if not line.startswith("| "):
            continue
        if "| AC_ID |" in line or "|---|" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        rows.append({
            "ac_id": cells[0],
            "title": cells[1],
            "stage": cells[2],
            "status": cells[3],
            "canonical_evidence": cells[4],
            "last_commit": cells[5],
            "dup_group_key": cells[6],
            "notes": cells[7],
        })
    return rows


def find_latest_evidence(evidence_root: Path) -> tuple[str, str]:
    """최근 evidence 디렉토리와 gate.log 경로 반환."""
    if not evidence_root.exists():
        return "NONE", "NONE"
    dirs = sorted(
        [p for p in evidence_root.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not dirs:
        return "NONE", "NONE"
    latest = dirs[0]
    gate_log = latest / "gate.log"
    return str(latest.relative_to(ROOT)), str(gate_log.relative_to(ROOT)) if gate_log.exists() else "NONE"


def find_latest_gate_result(evidence_root: Path) -> str:
    """최근 gate 증거에서 PASS/FAIL 판정."""
    if not evidence_root.exists():
        return "UNKNOWN"
    gate_dirs = sorted(
        [p for p in evidence_root.iterdir() if p.is_dir() and "gate" in p.name],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not gate_dirs:
        return "UNKNOWN"
    latest_gate = gate_dirs[0]
    exitcode_file = latest_gate / "exitcode.txt"
    if exitcode_file.exists():
        code = exitcode_file.read_text().strip()
        return "PASS" if code == "0" else f"FAIL(exit={code})"
    gate_log = latest_gate / "gate.log"
    if gate_log.exists():
        content = gate_log.read_text(errors="ignore")
        if "PASSED" in content and "FAILED" not in content:
            return "PASS"
        if "FAILED" in content:
            return "FAIL"
    return "UNKNOWN"


def read_plan_pointer() -> str:
    """plan.json에서 현재 티켓 ID 읽기."""
    if not PLAN_PATH.exists():
        return "NONE"
    try:
        data = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        return data.get("ticket_id", data.get("ac_id", "NONE"))
    except (json.JSONDecodeError, KeyError):
        return "NONE"


def read_last_result() -> str:
    """result.json에서 최근 결과 읽기."""
    if not RESULT_PATH.exists():
        return "NONE"
    try:
        data = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        return data.get("status", data.get("result", "NONE"))
    except (json.JSONDecodeError, KeyError):
        return "NONE"


def read_feedback_summary() -> list[str]:
    """result.json + model_routing.log에서 Self-Heal/DO재시도/agent 실패 피드백 5줄 요약."""
    lines: list[str] = []
    result_path = RESULT_PATH
    routing_log = ROOT / "logs" / "factory" / "model_routing.log"

    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            notes = data.get("notes", [])
            self_heal = data.get("self_heal_applied", False)
            do_failed = any("[DO_FAIL]" in n for n in notes)
            do_retry = any("_retry" in str(c.get("name", "")) for c in data.get("commands", []))
            agent = data.get("agent_used", "?")
            status = data.get("status", "?")
            lines.append(f"  [LAST_CYCLE]   status={status} agent={agent} do_failed={do_failed} do_retry={do_retry} self_heal={self_heal}")
            if do_failed:
                do_note = next((n for n in notes if "[DO_FAIL]" in n), "")
                lines.append(f"  [DO_FAIL_NOTE] {do_note}")
        except Exception:
            pass

    if routing_log.exists():
        try:
            log_lines = routing_log.read_text(encoding="utf-8", errors="ignore").splitlines()
            recent = [l for l in log_lines if l.strip()][-10:]
            aider_lines = [l for l in recent if "aider" in l.lower()]
            claude_lines = [l for l in recent if "claude" in l.lower()]
            lines.append(f"  [ROUTING_LOG]  recent={len(recent)} aider={len(aider_lines)} claude={len(claude_lines)}")
        except Exception:
            pass

    if not lines:
        lines.append("  [FEEDBACK]     No data yet")
    return lines[:5]


def main() -> int:
    rows = parse_ledger_v2_rows(LEDGER_PATH)

    total = len(rows)
    done_count = sum(1 for r in rows if r["status"] == "DONE")
    open_count = sum(1 for r in rows if r["status"] == "OPEN")

    progress_pct = (done_count / total * 100) if total > 0 else 0.0

    first_open = next((r for r in rows if r["status"] == "OPEN"), None)
    current_ac = first_open["ac_id"] if first_open else "ALL_DONE"

    next_3 = []
    found_current = False
    for r in rows:
        if r["status"] == "OPEN":
            if not found_current:
                found_current = True
                continue
            next_3.append(r["ac_id"])
            if len(next_3) >= 3:
                break

    latest_evidence, gate_log_path = find_latest_evidence(EVIDENCE_ROOT)
    last_gate = find_latest_gate_result(EVIDENCE_ROOT)
    plan_pointer = read_plan_pointer()
    last_result = read_last_result()

    print("=" * 72)
    print("  FACTORY STATUS DASHBOARD (Deterministic, LLM-free)")
    print("=" * 72)
    print()
    print(f"  [PROGRESS]     {done_count}/{total} ({progress_pct:.1f}%)")
    print(f"  [CURRENT]      {current_ac}")
    print(f"  [NEXT_3]       {', '.join(next_3) if next_3 else 'N/A'}")
    print(f"  [PLAN_POINTER] {plan_pointer}")
    print(f"  [LAST_GATE]    {last_gate}")
    print(f"  [LAST_RESULT]  {last_result}")
    print(f"  [EVIDENCE]     {latest_evidence}")
    print(f"  [GATE_LOG]     {gate_log_path}")
    print()
    print(f"  [DONE]  {done_count}  |  [OPEN]  {open_count}  |  [TOTAL]  {total}")
    print(f"  [TIME]  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    print("  [FEEDBACK LOOP]")
    for fb in read_feedback_summary():
        print(fb)
    print()
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
