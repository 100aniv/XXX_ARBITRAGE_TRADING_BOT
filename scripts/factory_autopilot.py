#!/usr/bin/env python3
"""Factory Autopilot — True autonomous AC-by-AC development loop.

Reads AC_LEDGER.md, picks the first OPEN AC, generates plan.json dynamically,
maps AC to plan doc (find or generate), runs supervisor (1 cycle), marks DONE
on PASS, and halts on FAIL.  Repeats for --max-cycles.

Usage:
    python3 scripts/factory_autopilot.py --max-cycles 3
    just factory_autopilot
    just factory_autopilot --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "docs" / "v2" / "design" / "AC_LEDGER.md"
PLAN_JSON_PATH = ROOT / "logs" / "autopilot" / "plan.json"
RESULT_JSON_PATH = ROOT / "logs" / "autopilot" / "result.json"
PLAN_DOC_ROOT = ROOT / "docs" / "plan"
REPORT_DOC_ROOT = ROOT / "docs" / "report"
EVIDENCE_ROOT = ROOT / "logs" / "evidence"


# ---------------------------------------------------------------------------
# Ledger Parsing
# ---------------------------------------------------------------------------

def parse_ledger_rows(ledger_path: Path = LEDGER_PATH) -> List[Dict[str, str]]:
    """Parse AC_LEDGER.md markdown table into list of row dicts."""
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


_LEGACY_D_RE = re.compile(r"\bD([0-9]+)\b")


def _is_v2_alpha(row: Dict[str, str]) -> bool:
    """V2/ALPHA track only. Exclude D<200 legacy."""
    ac_id = row.get("ac_id", "").strip()
    stage = row.get("stage", "").strip().upper()
    if stage.startswith("D_ALPHA") or "ALPHA" in stage:
        return True
    for m in _LEGACY_D_RE.findall(f"{ac_id} {stage}"):
        return int(m) >= 200
    return True


def pick_next_open_ac(rows: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Pick the first OPEN V2/ALPHA AC. Returns None if all done."""
    for row in rows:
        if not _is_v2_alpha(row):
            continue
        status = row.get("status", "").strip()
        if status in ("OPEN", "LOST_EVIDENCE"):
            return row
    return None


# ---------------------------------------------------------------------------
# Plan Doc Mapping (Add-on 1: AC_LEDGER -> docs/plan/*.md)
# ---------------------------------------------------------------------------

_PATH_PATTERN = re.compile(
    r"(?:^|\s|,|;|\(|\[)"
    r"("
    r"(?:arbitrage|ops|tests|scripts|docs|logs|config)[/\\][\w./\\-]+"
    r"|"
    r"[\w./\\-]+\.(?:py|md|json|yaml|yml|txt|sh)"
    r")"
    r"(?:$|\s|,|;|\)|\])",
    re.IGNORECASE,
)


def extract_paths(title: str, notes: str) -> List[str]:
    """Extract file/dir paths from title+notes text."""
    text = f"{title} {notes}"
    matches = _PATH_PATTERN.findall(text)
    paths: set[str] = set()
    for m in matches:
        cleaned = m.strip().rstrip(",;)].").lstrip("([,")
        if cleaned and len(cleaned) > 2:
            paths.add(cleaned)
    return sorted(paths)


def find_existing_plan_doc(ac_id: str) -> Optional[Path]:
    """Search docs/plan/ for an existing plan doc matching ac_id."""
    if not PLAN_DOC_ROOT.exists():
        return None
    slug = ac_id.replace("::", "__")
    for p in PLAN_DOC_ROOT.glob("*.md"):
        if slug in p.stem or f"SAFE__{slug}" in p.stem:
            return p
    return None


def parse_plan_doc_scope(doc_path: Path) -> Dict[str, List[str]]:
    """Parse ### modify / readonly / forbidden sections from plan doc."""
    scope: Dict[str, List[str]] = {"modify": [], "readonly": [], "forbidden": []}
    if not doc_path or not doc_path.exists():
        return scope
    current_section = ""
    for line in doc_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "### modify":
            current_section = "modify"
        elif stripped == "### readonly":
            current_section = "readonly"
        elif stripped == "### forbidden":
            current_section = "forbidden"
        elif stripped.startswith("##"):
            current_section = ""
        elif current_section and stripped.startswith("- "):
            item = stripped[2:].strip()
            if item and item not in ("(none)", "(auto-inferred)"):
                scope[current_section].append(item)
    return scope


def generate_plan_doc(ac_row: Dict[str, str], touched_paths: List[str]) -> Path:
    """Auto-generate a plan doc from ledger row metadata."""
    ac_id = ac_row["ac_id"]
    slug = ac_id.replace("::", "__")
    doc_path = PLAN_DOC_ROOT / f"{slug}.md"
    PLAN_DOC_ROOT.mkdir(parents=True, exist_ok=True)

    is_meta = "D000" in ac_id
    forbidden = ["D_ROADMAP.md", "docs/v2/SSOT_RULES.md"]
    if is_meta:
        forbidden.append("arbitrage/v2/**")

    modify_items = touched_paths if touched_paths else ["(auto-inferred)"]
    lines = [
        f"# PLAN: {ac_id}",
        "",
        "## Bikit Workflow",
        "- PLAN: AC_LEDGER + 본 문서 기준으로 설계한다.",
        "- DO: Aider 또는 Claude Code로 구현 후 커밋한다.",
        "- CHECK: Gate 3단 + DocOps + Evidence 검증으로 완료 판정한다.",
        "",
        "## Ticket",
        f"- ac_id: {ac_id}",
        f"- title: {ac_row['title']}",
        f"- stage: {ac_row.get('stage', '')}",
        f"- done_criteria: Gate 3단 PASS + DocOps ExitCode=0 + Evidence 생성",
        "",
        "## System Prompt",
        "- ops/prompts/worker_instruction.md",
        "",
        "## Scope/Allowlist",
        "### modify",
    ]
    lines.extend([f"- {p}" for p in modify_items])
    lines.extend([
        "",
        "### readonly",
        "- docs/v2/design/AC_LEDGER.md",
        "- docs/v2/design/AGENTIC_FACTORY_WORKFLOW.md",
        "",
        "### forbidden",
    ])
    lines.extend([f"- {p}" for p in forbidden])
    lines.append("")

    doc_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return doc_path


# ---------------------------------------------------------------------------
# Plan JSON Generation
# ---------------------------------------------------------------------------

CLAUDE_KEYWORDS = [
    "design", "architecture", "ssot", "docops", "roadmap",
    "refactor", "audit", "meta", "restructure",
]
AIDER_KEYWORDS = [
    "implement", "fix", "test", "bug", "add", "patch",
    "guard", "smoke", "calibrat", "hotfix", "update",
]
HIGH_RISK_KW = [
    "core", "engine", "pnl", "friction", "slippage",
    "trade", "executor", "arbitrage/v2",
]
LOW_RISK_KW = [
    "docops", "document", "docs", "readme", "evidence",
    "guard", "ledger", "report", "gate",
]


def _classify_intent(title: str, notes: str = "") -> str:
    text = f"{title} {notes}".lower()
    for kw in CLAUDE_KEYWORDS:
        if kw in text:
            return "design"
    for kw in AIDER_KEYWORDS:
        if kw in text:
            return "implementation"
    return "implementation"


def _infer_risk(title: str, notes: str) -> str:
    text = f"{title} {notes}".lower()
    if any(kw in text for kw in HIGH_RISK_KW):
        return "high"
    if any(kw in text for kw in LOW_RISK_KW):
        return "low"
    return "mid"


def build_plan_json(
    ac_row: Dict[str, str],
    scope: Dict[str, List[str]],
    touched_paths: List[str],
) -> Dict[str, Any]:
    """Build plan.json content dict for the AC (no SAFE:: prefix)."""
    ac_id = ac_row["ac_id"]
    title = ac_row["title"]
    notes = ac_row.get("notes", "")

    intent = _classify_intent(title, notes)
    risk = _infer_risk(title, notes)
    budget = risk
    file_count = len(touched_paths) or 1
    agent = "claude_code" if (intent == "design" or file_count >= 5) else "aider"

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    return {
        "schema_version": "1.0",
        "mode": "AUTOPILOT",
        "ticket_id": ac_id,
        "ac_id": ac_id,
        "title": title,
        "created_at_utc": stamp,
        "scope": {
            "modify": scope.get("modify") or touched_paths or [],
            "readonly": scope.get("readonly") or ["docs/v2/design/AC_LEDGER.md"],
            "forbidden": scope.get("forbidden") or ["D_ROADMAP.md", "docs/v2/SSOT_RULES.md"],
        },
        "done_criteria": "Gate 3단 PASS + DocOps ExitCode=0 + Evidence 생성",
        "notes": [
            "AUTOPILOT: Autonomous AC execution",
            f"Intent: {intent}",
            f"Risk: {risk}",
        ],
        "risk_level": risk,
        "model_budget": budget,
        "model_overrides": {},
        "agent_preference": agent,
        "intent": intent,
        "affected_files_count": file_count,
        "touched_paths": touched_paths,
    }


# ---------------------------------------------------------------------------
# Ledger Update (Add-on 2: OPEN -> DONE + evidence, preserving table)
# ---------------------------------------------------------------------------

def update_ledger_done(
    ac_id: str,
    evidence_path: str,
    commit_hash: str,
    ledger_path: Path = LEDGER_PATH,
) -> bool:
    """Mark ac_id row OPEN -> DONE in AC_LEDGER.md, preserving table structure."""
    text = ledger_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    updated = False

    for i, line in enumerate(lines):
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        if cells[0] != ac_id:
            continue
        if cells[3] not in ("OPEN", "LOST_EVIDENCE"):
            continue

        cells[3] = "DONE"
        if evidence_path and evidence_path != "NONE":
            cells[4] = evidence_path
        if commit_hash and commit_hash != "UNKNOWN":
            cells[5] = commit_hash

        lines[i] = "| " + " | ".join(cells) + " |"
        updated = True
        break

    if updated:
        ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


# ---------------------------------------------------------------------------
# Git Helpers
# ---------------------------------------------------------------------------

def get_head_hash() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except Exception:
        return "UNKNOWN"


def _stage_specific_paths(paths: List[Path]) -> None:
    rels = []
    for p in paths:
        if p is None:
            continue
        if not p.exists():
            continue
        rels.append(str(p.relative_to(ROOT)))
    if not rels:
        return
    subprocess.run(
        [sys.executable, "scripts/git_safe_stage.py", "--only", *rels],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
    )


def git_commit_push(message: str, stage_paths: List[Path]) -> bool:
    try:
        _stage_specific_paths(stage_paths)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(ROOT), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push"], cwd=str(ROOT), check=False, capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------------------------------------------------------------------
# Supervisor Execution
# ---------------------------------------------------------------------------

def run_supervisor(
    container_mode: str = "docker",
    docker_network: str = "docker_arbitrage-network",
    env_file: str = ".env.factory.local",
    docker_image: str = "arbitrage-factory-worker:latest",
    max_credit_usd: float = 5.0,
    dry_run: bool = False,
) -> int:
    """Run supervisor for 1 cycle with --skip-plan-gen (we provide plan.json)."""
    cmd = [
        "python3", "ops/factory_supervisor.py",
        "--max-cycles", "1",
        "--container-mode", container_mode,
        "--docker-network", docker_network,
        "--env-file", env_file,
        "--docker-image", docker_image,
        "--max-credit-usd", str(max_credit_usd),
        "--skip-plan-gen",
    ]
    if dry_run:
        cmd.append("--dry-run")

    proc = subprocess.run(cmd, cwd=str(ROOT))
    return proc.returncode


def read_result() -> Optional[Dict[str, Any]]:
    if not RESULT_JSON_PATH.exists():
        return None
    try:
        return json.loads(RESULT_JSON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main Autopilot Loop
# ---------------------------------------------------------------------------

@dataclass
class CycleState:
    last_ac_id: str = ""
    last_status: str = ""
    completed: int = 0
    failed: int = 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Factory Autopilot: Autonomous AC-by-AC development loop",
    )
    parser.add_argument("--max-cycles", type=int, default=3)
    parser.add_argument("--container-mode", default="docker", choices=["docker", "local"])
    parser.add_argument("--docker-network", default="docker_arbitrage-network")
    parser.add_argument("--env-file", default=".env.factory.local")
    parser.add_argument("--docker-image", default="arbitrage-factory-worker:latest")
    parser.add_argument("--max-credit-usd", type=float, default=5.0)
    parser.add_argument("--dry-run", action="store_true", help="Preview without execution")
    args = parser.parse_args()

    state = CycleState()

    print("=" * 72)
    print("  FACTORY AUTOPILOT (Autonomous AC Loop)")
    print(f"  max_cycles={args.max_cycles}  mode={args.container_mode}  dry_run={args.dry_run}")
    print("=" * 72)

    for cycle_num in range(1, args.max_cycles + 1):
        print(f"\n{'─' * 72}")
        print(f"  [CYCLE {cycle_num}/{args.max_cycles}]")
        print(f"{'─' * 72}")

        # 1. Parse ledger, pick next OPEN AC
        rows = parse_ledger_rows()
        ac_row = pick_next_open_ac(rows)
        if ac_row is None:
            print("[AUTOPILOT] No more OPEN ACs in ledger. All done!")
            break

        ac_id = ac_row["ac_id"]
        print(f"[AUTOPILOT] Selected: {ac_id} — {ac_row['title']}")

        # 2. Fail-safe guards (Add-on 3: infinite loop / duplicate prevention)
        if ac_id == state.last_ac_id:
            if state.last_status == "FAIL":
                print(f"[AUTOPILOT] HALT: {ac_id} failed in previous cycle.")
                print(f"[AUTOPILOT] Manual fix needed. Check logs/autopilot/result.json")
                return 1
            if state.last_status == "PASS":
                print(f"[AUTOPILOT] HALT: {ac_id} selected again after PASS.")
                print(f"[AUTOPILOT] Ledger advancement failed. Check AC_LEDGER.md")
                return 1

        # 3. Find or generate plan doc (Add-on 1: AC_LEDGER -> plan doc mapping)
        touched_paths = extract_paths(ac_row["title"], ac_row.get("notes", ""))
        slug = ac_id.replace("::", "__")
        plan_doc_path = find_existing_plan_doc(ac_id)
        plan_doc_created = False
        if plan_doc_path:
            print(f"[AUTOPILOT] Found plan doc: {plan_doc_path.relative_to(ROOT)}")
            scope = parse_plan_doc_scope(plan_doc_path)
        else:
            plan_doc_path = generate_plan_doc(ac_row, touched_paths)
            plan_doc_created = True
            scope = parse_plan_doc_scope(plan_doc_path)
            print(f"[AUTOPILOT] Generated plan doc: {plan_doc_path.relative_to(ROOT)}")

        # 4. Build & write plan.json (dynamic, no SAFE:: prefix)
        plan = build_plan_json(ac_row, scope, touched_paths)
        PLAN_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        PLAN_JSON_PATH.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        print(
            f"[AUTOPILOT] plan.json: ticket={plan['ticket_id']} "
            f"agent={plan['agent_preference']} risk={plan['risk_level']}"
        )

        # 5. Run supervisor (1 cycle, skip controller plan gen)
        exit_code = run_supervisor(
            container_mode=args.container_mode,
            docker_network=args.docker_network,
            env_file=args.env_file,
            docker_image=args.docker_image,
            max_credit_usd=args.max_credit_usd,
            dry_run=args.dry_run,
        )

        # 6. Read result (exit_code is authoritative, result.json is metadata)
        result = read_result()
        if exit_code == 0:
            status = "PASS"
        else:
            status = "FAIL"
            if result:
                status = result.get("status", status)

        # 7. Handle outcome
        state.last_ac_id = ac_id
        state.last_status = status

        if status == "PASS" and exit_code == 0:
            # (Add-on 2: Ledger DONE marking + evidence)
            evidence = result.get("evidence_latest", "NONE") if result else "NONE"
            commit_hash = get_head_hash()
            report_doc = REPORT_DOC_ROOT / f"{slug}_analyze.md"

            if args.dry_run:
                print(f"[AUTOPILOT] DRY-RUN: Would mark {ac_id} -> DONE (skipping ledger/git)")
            else:
                updated = update_ledger_done(ac_id, evidence, commit_hash)
                if updated:
                    print(f"[AUTOPILOT] LEDGER: {ac_id} -> DONE (evidence={evidence})")
                else:
                    print(f"[AUTOPILOT] WARN: Could not update ledger for {ac_id}")

                stage_targets: List[Path] = [LEDGER_PATH]
                if plan_doc_created:
                    stage_targets.append(plan_doc_path)
                if report_doc.exists():
                    stage_targets.append(report_doc)

                committed = git_commit_push(
                    f"autopilot: {ac_id} DONE [evidence={evidence}]",
                    stage_targets,
                )
                if committed:
                    print(f"[AUTOPILOT] Git: committed + pushed")

            state.completed += 1
            print(f"[AUTOPILOT] PASS: {ac_id} (cycle {cycle_num})")
        else:
            state.failed += 1
            notes = result.get("notes", []) if result else []
            fail_notes = [n for n in notes if "FAIL" in n or "ERROR" in n]
            print(f"[AUTOPILOT] FAIL: {ac_id} (exit_code={exit_code})")
            if fail_notes:
                for n in fail_notes[:5]:
                    print(f"  {n}")
            print(f"[AUTOPILOT] HALT: Stopping on FAIL. Fix manually, then re-run.")
            return 1

    # Summary
    print(f"\n{'=' * 72}")
    print(f"  AUTOPILOT COMPLETE")
    print(f"  Cycles: {state.completed} PASS / {state.failed} FAIL")
    final_rows = parse_ledger_rows()
    open_n = sum(1 for r in final_rows if r["status"] == "OPEN" and _is_v2_alpha(r))
    done_n = sum(1 for r in final_rows if r["status"] == "DONE" and _is_v2_alpha(r))
    print(f"  Ledger: {done_n} DONE / {open_n} OPEN")
    print(f"{'=' * 72}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
