from __future__ import annotations

import argparse
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
LEDGER_PATH = ROOT / "docs" / "v2" / "design" / "AC_LEDGER.md"
DEFAULT_PLAN_PATH = ROOT / "logs" / "autopilot" / "plan.json"

SAFE_KEYWORDS = [
    "docops",
    "document",
    "docs",
    "ssot",
    "guard",
    "ledger",
    "evidence",
    "report",
    "gate",
    "문서",
    "증거",
    "가드",
]


def safety_score(row: Dict[str, str]) -> int:
    text = f"{row['ac_id']} {row['title']} {row['notes']}".lower()
    return sum(1 for keyword in SAFE_KEYWORDS if keyword in text)


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


def pick_safe_open_ticket(rows: List[Dict[str, str]]) -> Dict[str, str]:
    open_rows = [r for r in rows if r.get("status") == "OPEN"]
    if not open_rows:
        raise RuntimeError("No OPEN AC found in AC_LEDGER")

    scored = sorted(open_rows, key=safety_score, reverse=True)
    if safety_score(scored[0]) > 0:
        return scored[0]

    # fallback: first OPEN
    return open_rows[0]


def build_plan(ticket: Dict[str, str]) -> FactoryPlan:
    return FactoryPlan(
        schema_version=SCHEMA_VERSION,
        mode="DRY_RUN",
        ticket_id=f"SAFE::{ticket['ac_id']}",
        ac_id=ticket["ac_id"],
        title=ticket["title"],
        created_at_utc=utc_now_iso(),
        scope=PlanScope(
            modify=[
                "ops/factory/controller.py",
                "ops/factory/worker.py",
                "ops/factory/schema.py",
                "ops/factory/README.md",
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
        done_criteria="just gate/docops/evidence_check exit_code == 0 and machine-readable result.json generated",
        notes=[
            "Safety ticket only",
            "DRY-RUN only: no core engine changes",
            "Factory integration endpoints are placeholders",
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Controller (DRY-RUN)")
    parser.add_argument("--ledger", default=str(LEDGER_PATH), help="AC ledger path")
    parser.add_argument("--output", default=str(DEFAULT_PLAN_PATH), help="plan.json output path")
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    output_path = Path(args.output)

    rows = parse_ledger_rows(ledger_path)
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
