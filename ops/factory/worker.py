from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
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
DEFAULT_PLAN_DOC_ROOT = ROOT / "docs" / "plan"
DEFAULT_REPORT_ROOT = ROOT / "docs" / "report"


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


def run_shell(name: str, shell_cmd: str, env: Dict[str, str]) -> CommandResult:
    start = time.time()
    proc = subprocess.run(["bash", "-lc", shell_cmd], cwd=str(ROOT), env=env)
    duration = round(time.time() - start, 3)
    return CommandResult(
        name=name,
        command=["bash", "-lc", shell_cmd],
        exit_code=proc.returncode,
        duration_sec=duration,
    )


def ensure_git_safe_directory(env: Dict[str, str]) -> None:
    try:
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", str(ROOT)],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return


def ensure_python_alias(env: Dict[str, str]) -> None:
    if shutil.which("python"):
        return
    python3_bin = shutil.which("python3") or sys.executable
    if not python3_bin:
        return
    system_alias = Path("/usr/local/bin/python")
    try:
        if not system_alias.exists():
            system_alias.symlink_to(python3_bin)
        if shutil.which("python"):
            return
    except OSError:
        pass

    alias_dir = ROOT / ".factory_bin"
    alias_dir.mkdir(parents=True, exist_ok=True)
    alias_path = alias_dir / "python"
    try:
        if alias_path.exists() or alias_path.is_symlink():
            alias_path.unlink()
        alias_path.symlink_to(python3_bin)
    except OSError:
        return
    env["PATH"] = f"{alias_dir}:{env.get('PATH', '')}"


def sanitize_ticket_id(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return slug.strip("_") or "ticket"


def ensure_report(report_path: Path, ticket_id: str, commands: List[CommandResult], status: str) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Factory Analyze Report - {ticket_id}",
        "",
        f"- status: {status}",
        f"- created_at_utc: {utc_now_iso()}",
        "",
        "## Command Results",
    ]
    for result in commands:
        lines.append(
            f"- {result.name}: exit_code={result.exit_code}, duration_sec={result.duration_sec}, command={' '.join(result.command)}"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Worker (Bikit DO/CHECK)")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN_PATH), help="input plan.json")
    parser.add_argument("--result", default=str(DEFAULT_RESULT_PATH), help="output result.json")
    parser.add_argument("--ticket-id", default="", help="ticket id override")
    parser.add_argument("--plan-doc", default="", help="PLAN markdown path")
    parser.add_argument("--report", default="", help="CHECK analyze markdown path")
    parser.add_argument("--skip-do", action="store_true", help="skip DO step (dry-run preview)")
    parser.add_argument("--do-command", default="", help="custom shell command for DO step")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    result_path = Path(args.result)

    plan = read_json(plan_path)
    validate_plan(plan)

    ticket_id = args.ticket_id.strip() or str(plan.get("ticket_id", "SAFE::UNKNOWN"))
    ticket_slug = sanitize_ticket_id(ticket_id)

    plan_doc_path = Path(args.plan_doc) if args.plan_doc else DEFAULT_PLAN_DOC_ROOT / f"{ticket_slug}.md"
    report_path = Path(args.report) if args.report else DEFAULT_REPORT_ROOT / f"{ticket_slug}_analyze.md"
    if not plan_doc_path.is_absolute():
        plan_doc_path = ROOT / plan_doc_path
    if not report_path.is_absolute():
        report_path = ROOT / report_path

    env = os.environ.copy()
    env["BOOTSTRAP_FLAG"] = "1"
    redis_host = env.get("REDIS_HOST", "").strip()
    redis_port = env.get("REDIS_PORT", "").strip()
    if redis_host and "FACTORY_REDIS_HOST" not in env:
        env["FACTORY_REDIS_HOST"] = redis_host
    if redis_port and "FACTORY_REDIS_PORT" not in env:
        env["FACTORY_REDIS_PORT"] = redis_port

    if "FACTORY_POSTGRES_CONNECTION_STRING" not in env:
        pg_host = env.get("POSTGRES_HOST", "localhost").strip() or "localhost"
        pg_port = env.get("POSTGRES_PORT", "5432").strip() or "5432"
        pg_user = env.get("POSTGRES_USER", "arbitrage").strip() or "arbitrage"
        pg_password = env.get("POSTGRES_PASSWORD", "arbitrage").strip() or "arbitrage"
        pg_db = env.get("POSTGRES_DB", "arbitrage").strip() or "arbitrage"
        env["FACTORY_POSTGRES_CONNECTION_STRING"] = (
            f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
        )
    ensure_python_alias(env)
    ensure_git_safe_directory(env)

    results: List[CommandResult] = []

    agent_preference = plan.get("agent_preference", "aider")
    agent_used = agent_preference

    if not args.skip_do:
        if args.do_command.strip():
            do_shell = args.do_command.strip()
            agent_used = "custom"
        else:
            rel_plan_doc = str(plan_doc_path.relative_to(ROOT)).replace("\\", "/")
            git_commit_cmd = f"git add -A && (git diff --cached --quiet || git commit -m \"factory: apply {ticket_slug}\")"

            if agent_preference == "claude_code":
                claude_model = env.get("CLAUDE_CODE_MODEL", "")
                model_flag = f"--model {claude_model}" if claude_model else ""
                do_shell = (
                    f"claude {model_flag} -p \"$(cat {rel_plan_doc})\" "
                    f"--dangerously-skip-permissions && {git_commit_cmd}"
                )
            else:
                aider_model = env.get("AIDER_MODEL", "")
                model_flag = f"--model {aider_model}" if aider_model else ""
                do_shell = (
                    f"aider --yes {model_flag} --message-file {rel_plan_doc} && "
                    f"{git_commit_cmd}"
                )
        do_step_name = f"do_{agent_used}"
        results.append(run_shell(do_step_name, do_shell, env))

    gate_cmd = (
        "make gate || "
        "(python3 scripts/run_gate_with_evidence.py doctor && "
        "python3 scripts/run_gate_with_evidence.py fast && "
        "python3 scripts/run_gate_with_evidence.py regression)"
    )
    docops_cmd = (
        "make docops || "
        "(python3 scripts/check_ssot_docs.py && "
        "python3 scripts/check_docops_tokens.py --config config/docops_token_allowlist.yml && "
        "git status --short && git diff --stat)"
    )
    evidence_check_cmd = (
        "make evidence_check || "
        "python3 -c \"from pathlib import Path; import sys; root=Path('logs/evidence'); "
        "required=['manifest.json','gate.log','git_info.json','cmd_history.txt']; "
        "runs=sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []; "
        "candidate=next((p for p in runs if all((p / f).exists() for f in required)), None); "
        "missing=[] if candidate else required; print('latest=%s' % candidate); "
        "print('missing=' + ','.join(missing)) if missing else print('PASS'); sys.exit(1 if missing else 0)\""
    )

    results.append(run_shell("gate", gate_cmd, env))
    results.append(run_shell("docops", docops_cmd, env))
    results.append(run_shell("evidence_check", evidence_check_cmd, env))

    gate_result = next((r for r in results if r.name == "gate"), None)
    docops_result = next((r for r in results if r.name == "docops"), None)
    evidence_result = next((r for r in results if r.name == "evidence_check"), None)
    gate_exit_code = gate_result.exit_code if gate_result else 1
    docops_exit_code = docops_result.exit_code if docops_result else 1
    evidence_exit_code = evidence_result.exit_code if evidence_result else 1

    overall_pass = all(r.exit_code == 0 for r in results)
    ensure_report(report_path, ticket_id, results, "PASS" if overall_pass else "FAIL")

    summary = FactoryResult(
        schema_version=SCHEMA_VERSION,
        mode="RUN" if not args.skip_do else "DRY_RUN",
        ticket_id=ticket_id,
        ac_id=plan["ac_id"],
        status="PASS" if overall_pass else "FAIL",
        created_at_utc=utc_now_iso(),
        commands=results,
        gate_exit_code=gate_exit_code,
        docops_exit_code=docops_exit_code,
        evidence_check_exit_code=evidence_exit_code,
        evidence_latest=latest_evidence_dir(),
        notes=[
            "Bikit CHECK uses make gate/docops/evidence_check",
            f"plan_doc={plan_doc_path.relative_to(ROOT)}",
            f"report={report_path.relative_to(ROOT)}",
        ],
        agent_used=agent_used,
    )

    write_json(result_path, result_to_dict(summary))

    print("[WORKER] result.json generated")
    print(f"  - status: {summary.status}")
    print(f"  - result: {result_path}")
    print(f"  - report: {report_path}")
    print(f"  - evidence_latest: {summary.evidence_latest}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
