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
HISTORY_PATH = ROOT / "logs" / "autopilot" / "history.jsonl"

MAX_BUDGET_PER_SESSION = 5.0  # USD
MODEL_COST_PER_1K = {
    "openai": {"low": 0.00015, "mid": 0.002, "high": 0.01},
    "anthropic": {"low": 0.003, "mid": 0.003, "high": 0.015},
}


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


def read_ticket_history(n: int = 5) -> list[dict]:
    """logs/autopilot/history.jsonl에서 최근 N회 티켓 히스토리 읽기.

    history.jsonl이 없으면 result.json 1개만 반환.
    """
    records: list[dict] = []
    if HISTORY_PATH.exists():
        try:
            lines = HISTORY_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
                if len(records) >= n:
                    break
        except Exception:
            pass
    if not records and RESULT_PATH.exists():
        try:
            data = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
            records.append(data)
        except Exception:
            pass
    return records


def estimate_cost_from_result(data: dict) -> float:
    """result.json 데이터에서 대략적 비용 추정 (USD)."""
    agent = data.get("agent_used", "aider")
    provider = "anthropic" if "claude" in agent.lower() else "openai"
    tier = "mid"
    notes = data.get("notes", [])
    if any("danger" in n for n in notes):
        tier = "high"
    elif any("warn" in n for n in notes):
        tier = "mid"
    else:
        tier = "low"
    rate = MODEL_COST_PER_1K[provider][tier]
    return round(rate * 5, 4)  # ~5K tokens 추정


def get_value_watch(history: list[dict]) -> list[str]:
    """VALUE_WATCH: 세션 예산 상태 + 가성비 조언 1줄."""
    lines: list[str] = []
    if not history:
        lines.append("  [VALUE_WATCH]  No session data")
        return lines

    total_cost = sum(estimate_cost_from_result(d) for d in history)
    budget_pct = (total_cost / MAX_BUDGET_PER_SESSION) * 100
    bar_len = int(budget_pct / 5)  # 20칸 바
    bar = "#" * min(bar_len, 20) + "-" * max(0, 20 - bar_len)
    lines.append(f"  [VALUE_WATCH]  세션예산 [{bar}] ${total_cost:.4f}/${MAX_BUDGET_PER_SESSION:.2f} ({budget_pct:.1f}%)")

    # Section O 임계값 (SSOT Appendix Section O 기준)
    # CHEAP: est_cost < 0.05 → aider low (gpt-4.1-mini)
    # MEDIUM: 0.05 <= est_cost < 0.50 → aider mid (gpt-4.1)
    # HEAVY: est_cost >= 0.50 OR context_risk == "danger" → claude_code (claude-sonnet-4)
    last = history[0] if history else {}
    last_cost = estimate_cost_from_result(last) if last else 0.0
    notes = last.get("notes", [])
    is_danger = any("danger" in n for n in notes)
    is_routed = any("[ROUTING]" in n for n in notes)

    if is_danger or is_routed or last_cost >= 0.50:
        tier_label = "HEAVY → claude_code (Anthropic)"
    elif last_cost >= 0.05:
        tier_label = "MEDIUM → aider mid (gpt-4.1)"
    else:
        tier_label = "CHEAP → aider low (gpt-4.1-mini)"
    lines.append(f"  [VALUE_WATCH]  Tier: {tier_label}")

    tpm_notes = [n for n in notes if "[TPM_GUARD]" in n or "[RATE_LIMIT_GUARD]" in n or "[ROUTING]" in n]
    if tpm_notes:
        lines.append(f"  [VALUE_WATCH]  ⚠️ Guard: {tpm_notes[0][:80]}")

    lines.append("  [VALUE_WATCH]  Based on SSOT Appendix Section O")
    return lines


def get_parallel_candidates(ledger_rows: list[dict]) -> int:
    """T4) OPEN 티켓 중 touched_paths가 disjoint인 후보 수 반환 (씨앗만)."""
    open_rows = [r for r in ledger_rows if r.get("status") == "OPEN"]
    if len(open_rows) < 2:
        return 0
    # AC_LEDGER에서 touched_paths는 notes 컴럼에 포함될 수 있음
    # 간단하게: ac_id 접두사가 다른 시리즈면 병렬 후보로 간주
    prefixes = set()
    candidates = 0
    for row in open_rows[:10]:
        ac_id = row.get("ac_id", "")
        prefix = ac_id.split("-")[0] if "-" in ac_id else ac_id[:6]
        if prefix not in prefixes:
            prefixes.add(prefix)
            candidates += 1
    return max(0, candidates - 1)


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


def format_history_table(history: list[dict]) -> list[str]:
    """최근 N회 티켓 히스토리를 테이블 형식으로 포맷."""
    if not history:
        return ["  (no history)"]
    lines = []
    header = f"  {'TICKET_ID':<30} {'AGENT':<14} {'STATUS':<6} {'HEAL':<5} {'RETRY':<5} {'TPM':<4}"
    lines.append(header)
    lines.append("  " + "-" * 68)
    for d in history:
        tid = str(d.get("ticket_id", d.get("ac_id", "?")))[:30]
        agent = str(d.get("agent_used", "?"))[:14]
        status = str(d.get("status", "?"))[:6]
        notes = d.get("notes", [])
        heal = "Y" if d.get("self_heal_applied") else "N"
        retry = "Y" if any("_retry" in str(c.get("name", "")) for c in d.get("commands", [])) else "N"
        tpm = "Y" if any("[TPM_GUARD]" in n or "[RATE_LIMIT_GUARD]" in n for n in notes) else "N"
        lines.append(f"  {tid:<30} {agent:<14} {status:<6} {heal:<5} {retry:<5} {tpm:<4}")
    return lines


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
    history = read_ticket_history(5)
    parallel_n = get_parallel_candidates(rows)

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
    print(f"  [PARALLEL_CANDIDATES] {parallel_n} (기본 OFF, 씨앗만)")
    print(f"  [TIME]  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    print("  [RECENT HISTORY] (최근 5회)")
    for line in format_history_table(history):
        print(line)
    print()
    for vw in get_value_watch(history):
        print(vw)
    print()
    print("  [FEEDBACK LOOP]")
    for fb in read_feedback_summary():
        print(fb)
    print()
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
