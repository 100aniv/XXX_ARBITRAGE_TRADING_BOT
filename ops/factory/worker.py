from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List

from ops.factory.schema import (
    SCHEMA_VERSION,
    CommandResult,
    FactoryResult,
    read_json,
    result_to_dict,
    utc_now_iso,
    validate_plan,
    write_json,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN_PATH = ROOT / "logs" / "autopilot" / "plan.json"
DEFAULT_RESULT_PATH = ROOT / "logs" / "autopilot" / "result.json"
EVIDENCE_ROOT = ROOT / "logs" / "evidence"


def latest_evidence_dir() -> str:
    if not EVIDENCE_ROOT.exists():
        return "NONE"
    dirs = [p for p in EVIDENCE_ROOT.iterdir() if p.is_dir()]
    if not dirs:
        return "NONE"
    latest = max(dirs, key=lambda p: p.stat().st_mtime)
    return str(latest.relative_to(ROOT)).replace("\\", "/")


def run_cmd(command: List[str], env: Dict[str, str]) -> CommandResult:
    start = time.time()
    proc = subprocess.run(command, cwd=str(ROOT), env=env)
    duration = round(time.time() - start, 3)
    return CommandResult(
        name=command[1] if len(command) > 1 else command[0],
        command=command,
        exit_code=proc.returncode,
        duration_sec=duration,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Worker (DRY-RUN)")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="input plan.json")
    parser.add_argument("--result", default=str(DEFAULT_RESULT_PATH), help="output result.json")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    result_path = Path(args.result)

    plan = read_json(plan_path)
    validate_plan(plan)

    env = os.environ.copy()
    env["BOOTSTRAP_FLAG"] = "1"

    cmd_specs = [
        ["just", "gate"],
        ["just", "docops"],
        ["just", "evidence_check"],
    ]

    results: List[CommandResult] = []
    for cmd in cmd_specs:
        result = run_cmd(cmd, env)
        results.append(result)

    gate_exit_code = results[0].exit_code
    docops_exit_code = results[1].exit_code
    evidence_exit_code = results[2].exit_code

    overall_pass = all(r.exit_code == 0 for r in results)
    summary = FactoryResult(
        schema_version=SCHEMA_VERSION,
        mode="DRY_RUN",
        ticket_id=plan["ticket_id"],
        ac_id=plan["ac_id"],
        status="PASS" if overall_pass else "FAIL",
        created_at_utc=utc_now_iso(),
        commands=results,
        gate_exit_code=gate_exit_code,
        docops_exit_code=docops_exit_code,
        evidence_check_exit_code=evidence_exit_code,
        evidence_latest=latest_evidence_dir(),
        notes=[
            "Worker executes local validation loop only",
            "No Docker/Claude Code/Aider live integration in DRY-RUN",
        ],
    )

    write_json(result_path, result_to_dict(summary))

    print("[WORKER] result.json generated")
    print(f"  - status: {summary.status}")
    print(f"  - result: {result_path}")
    print(f"  - evidence_latest: {summary.evidence_latest}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
