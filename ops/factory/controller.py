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


def pick_safe_open_ticket(rows: List[Dict[str, str]]) -> Dict[str, str]:
    """Sequential queue pointer: pick the first OPEN V2/ALPHA ticket.

    Rules:
    - AC_LEDGER.md is a sequential queue (D_ROADMAP order).
    - D200 미만/legacy AC_ID는 큐에서 제외.
    - 첫 번째 OPEN + V2/ALPHA 항목을 자동 포인팅.
    """
    for row in rows:
        if row.get("status") == "OPEN" and _is_v2_alpha_ticket(row):
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
    return FactoryPlan(
        schema_version=SCHEMA_VERSION,
        mode="BIKIT",
        ticket_id=f"SAFE::{ticket['ac_id']}",
        ac_id=ticket["ac_id"],
        title=ticket["title"],
        created_at_utc=utc_now_iso(),
        scope=PlanScope(
            modify=[
                "ops/factory/controller.py",
                "ops/factory/worker.py",
                "ops/factory_supervisor.py",
                "ops/factory/Dockerfile.worker",
                "ops/prompts/worker_instruction.md",
                "ops/factory/schema.py",
                "ops/factory/README.md",
                "Makefile",
                ".dockerignore",
                ".gitignore",
                ".env.factory.local.example",
                "docs/plan/*.md",
                "docs/report/*_analyze.md",
                "logs/autopilot/plan.json",
                "logs/autopilot/result.json",
                "justfile",
            ],
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
            "Master 1인 운영: Claude Code(PLAN/CHECK), Aider(DO)",
            "Container worker 우선, 코어 엔진(arbitrage/v2/**) 대량 변경 금지",
            "API cost cap(기본 5 USD) 초과 시 supervisor 즉시 종료",
            "Dynamic model routing: plan override > env max-tier > policy default",
        ],
        risk_level=risk_level,
        model_budget=model_budget,
        model_overrides={},
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
    print(f"  - output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
