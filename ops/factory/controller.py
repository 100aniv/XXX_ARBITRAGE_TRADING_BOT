from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Dict, List

from ops.factory.schema import (
    SCHEMA_VERSION,
    FactoryPlan,
    PlanScope,
    plan_to_dict,
    utc_now_iso,
    write_json,
)

ROOT = Path(__file__).resolve().parents[2]

LOW_RISK_KEYWORDS = [
    "docops",
    "document",
    "docs",
    "readme",
    "evidence",
    "guard",
    "ledger",
    "report",
    "gate",
]

HIGH_RISK_KEYWORDS = [
    "arbitrage/v2",
    "core",
    "engine",
    "pnl",
    "friction",
    "slippage",
    "latency",
    "trade",
    "executor",
]
LEDGER_PATH = ROOT / "docs" / "v2" / "design" / "AC_LEDGER.md"
DEFAULT_PLAN_PATH = ROOT / "logs" / "autopilot" / "plan.json"

CLAUDE_CODE_INTENT_KEYWORDS = [
    "design", "architecture", "ssot", "docops", "roadmap",
    "refactor", "audit", "migrate", "restructure", "overhaul",
    "governance", "meta",
]

AIDER_INTENT_KEYWORDS = [
    "implement", "fix", "test", "bug", "add", "patch",
    "hotfix", "small", "update", "modify", "correct",
    "calibrat", "guard", "smoke",
]

FILE_SCOPE_THRESHOLD = 5

_PATH_PATTERN = re.compile(
    r'(?:^|\s|,|;|\(|\[)'
    r'('
    r'(?:arbitrage|ops|tests|scripts|docs|logs|config)[/\\][\w./\\-]+'
    r'|'
    r'[\w./\\-]+\.(?:py|md|json|yaml|yml|txt|sh)'
    r')'
    r'(?:$|\s|,|;|\)|\])',
    re.IGNORECASE
)


def extract_paths_from_notes(title: str, notes: str) -> list[str]:
    """NOTES/TITLE에서 파일/디렉토리 경로 토큰 추출 (결정론적).

    패턴:
    - arbitrage/v2/..., ops/..., tests/..., scripts/..., docs/..., logs/..., config/...
    - *.py, *.md, *.json, *.yaml 등 확장자 파일

    Returns: unique paths list (fallback=[] if none found)
    """
    text = f"{title} {notes}"
    matches = _PATH_PATTERN.findall(text)
    paths = set()
    for m in matches:
        cleaned = m.strip().rstrip(',;)].').lstrip('([,')
        if cleaned and len(cleaned) > 2:
            paths.add(cleaned)
    if ' + ' in notes:
        for segment in notes.split(' + '):
            segment = segment.strip()
            if '/' in segment and not segment.startswith('http'):
                paths.add(segment)
    return sorted(paths)


def classify_intent(title: str, notes: str = "") -> str:
    """키워드 기반 Intent 분류 (결정론적, LLM 금지).

    Returns: 'design' | 'implementation' | 'test' | 'ops'
    """
    text = f"{title} {notes}".lower()
    for kw in CLAUDE_CODE_INTENT_KEYWORDS:
        if kw in text:
            return "design"
    for kw in AIDER_INTENT_KEYWORDS:
        if kw in text:
            return "implementation"
    return "implementation"


def select_agent(intent: str, affected_files_count: int) -> str:
    """결정론적 Agent 선택.

    Rules:
    1. 파일 5개 이상 수정 -> claude_code 강제 (File-Scope Heuristic)
    2. intent == 'design' -> claude_code
    3. 그 외 -> aider (default)
    """
    if affected_files_count >= FILE_SCOPE_THRESHOLD:
        return "claude_code"
    if intent == "design":
        return "claude_code"
    return "aider"

def parse_ledger_rows(ledger_path: Path) -> List[Dict[str, str]]:
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    rows: List[Dict[str, str]] = []

    for line in lines:
        if not line.startswith("| "):
            continue
        if "| AC_ID |" in line or "|---|" in line:
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue

        rows.append(
            {
                "ac_id": cells[0],
                "title": cells[1],
                "stage": cells[2],
                "status": cells[3],
                "canonical_evidence": cells[4],
                "last_commit": cells[5],
                "dup_group_key": cells[6],
                "notes": cells[7],
            }
        )
    return rows


_LEGACY_D_NUMBER = re.compile(r'\bD([0-9]+)\b')


def _is_v2_alpha_ticket(row: Dict[str, str]) -> bool:
    """V2/ALPHA 트랙 티켓만 허용. D200 미만 번호 또는 레거시 단계 제외.

    허용: D_ALPHA-x, D2xx+, ALPHA 단계
    차단: D8x, D9x, D1xx(D200 미만), V1 단계
    """
    ac_id = str(row.get("ac_id", "")).strip()
    stage = str(row.get("stage", "")).strip().upper()

    if stage.startswith("D_ALPHA") or "ALPHA" in stage:
        return True

    matches = _LEGACY_D_NUMBER.findall(ac_id + " " + stage)
    for m in matches:
        n = int(m)
        if n < 200:
            return False
        return True

    return True


EVIDENCE_ROOT = ROOT / "logs" / "evidence"


def _has_physical_evidence(row: Dict[str, str]) -> bool:
    """물리적 증거 폴더 존재 여부 확인 (TASK 11: Deterministic Pointer Sync).

    DONE 판정은 로드맵 텍스트보다 물리적 증거가 우선.
    canonical_evidence 컬럼에 경로가 있고, 해당 폴더가 실제로 존재하면 True.
    """
    evidence_path = str(row.get("canonical_evidence", "")).strip()
    if not evidence_path or evidence_path in ("NONE", "—", "-"):
        return False

    if evidence_path.startswith("logs/evidence/"):
        folder_name = evidence_path.replace("logs/evidence/", "").split("/")[0]
        if "*" in folder_name:
            import glob
            pattern = str(EVIDENCE_ROOT / folder_name)
            matches = glob.glob(pattern)
            return len(matches) > 0
        full_path = EVIDENCE_ROOT / folder_name
        return full_path.exists()

    if evidence_path.startswith("tests/"):
        test_file = ROOT / evidence_path
        return test_file.exists()

    return False


def pick_safe_open_ticket(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Sequential queue pointer: pick the first OPEN V2/ALPHA ticket.

    Rules:
    - AC_LEDGER.md is a sequential queue (D_ROADMAP order).
    - D200 미만/legacy AC_ID는 큐에서 제외.
    - 첫 번째 OPEN + V2/ALPHA 항목을 자동 포인팅.
    - TASK 11: DONE이지만 물리적 증거가 없으면 OPEN으로 취급.
    """
    for row in rows:
        if not _is_v2_alpha_ticket(row):
            continue

        status = row.get("status", "").strip()

        if status == "DONE":
            if not _has_physical_evidence(row):
                print(f"[POINTER_SYNC] {row['ac_id']} is DONE but no physical evidence. Treating as OPEN.")
                return row
            continue

        if status == "OPEN" or status == "LOST_EVIDENCE":
            return row

    raise RuntimeError("No OPEN V2/ALPHA ticket found in AC_LEDGER (all D200+ items done or ledger empty)")


def infer_risk_level(ticket: Dict[str, str]) -> str:
    text = f"{ticket.get('ac_id', '')} {ticket.get('title', '')} {ticket.get('notes', '')}".lower()
    if any(token in text for token in HIGH_RISK_KEYWORDS):
        return "high"
    if any(token in text for token in LOW_RISK_KEYWORDS):
        return "low"
    return "mid"


def infer_model_budget(risk_level: str) -> str:
    if risk_level == "low":
        return "low"
    if risk_level == "high":
        return "high"
    return "mid"


def build_plan(ticket: Dict[str, str]) -> FactoryPlan:
    risk_level = infer_risk_level(ticket)
    model_budget = infer_model_budget(risk_level)
    title = ticket["title"]
    notes_text = ticket.get("notes", "")
    intent = classify_intent(title, notes_text)

    touched_paths = extract_paths_from_notes(title, notes_text)
    affected_files_count = len(touched_paths) if touched_paths else 1

    agent_preference = select_agent(intent, affected_files_count)

    modify_files = touched_paths if touched_paths else [
        "ops/factory/controller.py",
        "ops/factory/worker.py",
        "ops/factory_supervisor.py",
    ]
    return FactoryPlan(
        schema_version=SCHEMA_VERSION,
        mode="BIKIT",
        ticket_id=f"SAFE::{ticket['ac_id']}",
        ac_id=ticket["ac_id"],
        title=title,
        created_at_utc=utc_now_iso(),
        scope=PlanScope(
            modify=modify_files,
            readonly=[
                "docs/v2/design/AC_LEDGER.md",
                "docs/v2/design/AGENTIC_FACTORY_WORKFLOW.md",
            ],
            forbidden=[
                "arbitrage/v2/**",
                "D_ROADMAP.md",
                "docs/v2/SSOT_RULES.md",
            ],
        ),
        done_criteria="Bikit PLAN/DO/CHECK 완료 + make gate 성공 + check_ssot_docs.py exit_code==0 + machine-readable result.json/report 생성",
        notes=[
            "Smart Routing: intent 기반 Agent 자동 선택 (결정론적)",
            "Container worker 우선, 코어 엔진(arbitrage/v2/**) 대량 변경 금지",
            "API cost cap(기본 5 USD) 초과 시 supervisor 즉시 종료",
            "Escalation: Gate 실패 시 1회 tier 상향 재시도 (Budget Guard 내)",
        ],
        risk_level=risk_level,
        model_budget=model_budget,
        model_overrides={},
        agent_preference=agent_preference,
        intent=intent,
        affected_files_count=affected_files_count,
        touched_paths=touched_paths,
    )


DISK_MIN_FREE_GB = 5.0


def check_disk_guard(min_free_gb: float = DISK_MIN_FREE_GB) -> None:
    """디스크 여유 공간 체크. min_free_gb 미만이면 Fail-Fast.

    CTO ADD-ON: 0GB 마비 사태 원천 봉쇄.
    """
    usage = shutil.disk_usage("/")
    free_gb = usage.free / (1024 ** 3)
    print(f"[DISK_GUARD] {free_gb:.1f} GB free (minimum: {min_free_gb} GB)")
    if free_gb < min_free_gb:
        raise RuntimeError(
            f"[DISK_GUARD] FAIL-FAST: 디스크 여유 {free_gb:.1f} GB < {min_free_gb} GB. "
            f"'just cleanup_storage' 실행 후 재시도하세요."
        )


def verify_sequential_integrity(rows: List[Dict[str, str]]) -> None:
    """Automated Pointer Handover: 장부 순서대로 순차 진행 보장.

    규칙: DONE 뒤에 다시 DONE이 아닌 행이 나온 후, 또 DONE이 나오면 안 됨.
    (= 건너뛰기 금지, 위에서 아래로 기차 레일 방식)
    """
    found_open_after_done = False
    for row in rows:
        if not _is_v2_alpha_ticket(row):
            continue
        status = row.get("status", "").strip()
        if status == "OPEN" or status == "LOST_EVIDENCE":
            found_open_after_done = True
        elif status == "DONE" and found_open_after_done:
            print(
                f"[WARN] Sequential integrity violation: {row['ac_id']} is DONE "
                f"but appears after OPEN items. Ledger 순서 점검 필요."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Controller (DRY-RUN)")
    parser.add_argument("--ledger", default=str(LEDGER_PATH), help="AC ledger path")
    parser.add_argument("--output", default=str(DEFAULT_PLAN_PATH), help="plan.json output path")
    parser.add_argument("--skip-disk-guard", action="store_true", help="Skip disk guard check")
    args = parser.parse_args()

    if not args.skip_disk_guard:
        check_disk_guard()

    ledger_path = Path(args.ledger)
    output_path = Path(args.output)

    rows = parse_ledger_rows(ledger_path)
    verify_sequential_integrity(rows)
    ticket = pick_safe_open_ticket(rows)
    plan = build_plan(ticket)

    write_json(output_path, plan_to_dict(plan))

    print("[CONTROLLER] plan.json generated")
    print(f"  - ticket: {plan.ticket_id}")
    print(f"  - ac_id: {plan.ac_id}")
    print(f"  - intent: {plan.intent}")
    print(f"  - agent: {plan.agent_preference}")
    print(f"  - affected_files: {plan.affected_files_count}")
    print(f"  - touched_paths: {plan.touched_paths}")
    print(f"  - output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
