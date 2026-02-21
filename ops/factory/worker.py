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


# Aider 기본 제외 대형 SSOT 문서 + .md 파일 (TPM 방어)
_AIDER_EXCLUDE_DEFAULTS = {
    "D_ROADMAP.md",
    "docs/v2/SSOT_RULES.md",
    "docs/v2/design/AC_LEDGER.md",
    "docs/v2/design/AGENTIC_FACTORY_WORKFLOW.md",
}

# TPM/RateLimit 오류 패턴 (재시도 판단용)
_TPM_ERROR_PATTERNS = [
    "rate_limit", "ratelimit", "429", "tpm",
    "request too large", "context_length_exceeded",
    "tokens per minute", "max_tokens",
]


def _is_tpm_error(output: str) -> bool:
    """Aider 출력에서 TPM/RateLimit 계열 오류 여부 판단."""
    lower = output.lower()
    return any(pat in lower for pat in _TPM_ERROR_PATTERNS)


def build_aider_file_flags(plan: dict, plan_doc_path: Path, slim: bool = False) -> str:
    """Aider --file 플래그 생성. .md 파일 제외(TPM 주범). 대형 SSOT 문서 제외.

    Aider CLI: --file <path> 형태로 파일 하나당 하나씩 붙임.
    .md 파일은 수정 대상이 아니므로 절대 포함하지 않음.
    slim=True 이면 touched_paths/tests도 제외하고 최소 파일만 포함 (TPM 재시도용).
    """
    file_list: List[str] = []

    def _add(p_str: str) -> None:
        """중복/제외 체크 후 추가."""
        if p_str in file_list:
            return
        if p_str in _AIDER_EXCLUDE_DEFAULTS:
            return
        if Path(p_str).suffix.lower() == ".md":
            return  # .md는 수정 대상 아님 (TPM 주범)
        candidate = ROOT / p_str
        if candidate.exists():
            file_list.append(p_str)

    if not slim:
        # 1) touched_paths
        for p in plan.get("touched_paths", []):
            _add(str(p).replace("\\", "/"))

        # 2) scope.modify
        for p in plan.get("scope", {}).get("modify", []):
            _add(str(p).replace("\\", "/"))

        # 3) 관련 tests/ 파일 (touched_paths 기반 추론, .py만)
        for p in list(file_list):
            stem = Path(p).stem
            for test_candidate in (ROOT / "tests").glob(f"*{stem}*.py"):
                rel = str(test_candidate.relative_to(ROOT)).replace("\\", "/")
                _add(rel)

    if not file_list:
        return ""
    return " ".join(f"--file {f}" for f in file_list)


# 하위 호환 alias (기존 테스트 호환)
def build_aider_add_flags(plan: dict, plan_doc_path: Path) -> str:
    """Deprecated alias → build_aider_file_flags 로 위임."""
    return build_aider_file_flags(plan, plan_doc_path, slim=False)


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
                file_flags = build_aider_file_flags(plan, plan_doc_path, slim=False)
                do_shell = (
                    f"aider --yes {model_flag} --subtree-only --map-tokens 1024 "
                    f"--message-file {rel_plan_doc} {file_flags} && "
                    f"{git_commit_cmd}"
                )
        do_step_name = f"do_{agent_used}"
        do_result = run_shell(do_step_name, do_shell, env)
        results.append(do_result)

        # T3) TPM/RateLimit 오류 시 slim 모드로 1회 재시도
        if do_result.exit_code != 0 and agent_preference != "claude_code":
            # 로그에서 TPM 오류 확인 (실행 로그는 터미널에 있으므로 실행 시간으로 유추)
            # exit_code=2는 CLI 인자 오류, exit_code=1은 실행 실패 둘 다 재시도 대상
            aider_model = env.get("AIDER_MODEL", "")
            model_flag = f"--model {aider_model}" if aider_model else ""
            slim_file_flags = build_aider_file_flags(plan, plan_doc_path, slim=True)
            slim_shell = (
                f"aider --yes {model_flag} --subtree-only --map-tokens 512 "
                f"--message-file {rel_plan_doc} {slim_file_flags} && "
                f"{git_commit_cmd}"
            )
            print(f"[DO_RETRY] exit_code={do_result.exit_code} → slim 모드로 1회 재시도 (map-tokens=512, 파일 최소화)")
            retry_result = run_shell(f"{do_step_name}_retry", slim_shell, env)
            results.append(retry_result)
            if retry_result.exit_code == 0:
                do_result = retry_result
                print("[DO_RETRY] 재시도 성공")
            else:
                print("[DO_RETRY] 재시도도 실패. DO FAIL 유지.")

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

    # T2) DO 실패 판단: do_* 스텝 중 최종 성공 여부 확인
    # do_*_retry가 있으면 retry 결과가 우선, 없으면 do_* 결과 사용
    do_steps = [r for r in results if r.name.startswith("do_")]
    retry_steps = [r for r in do_steps if r.name.endswith("_retry")]
    primary_do_steps = [r for r in do_steps if not r.name.endswith("_retry")]
    # 최종 DO 결과: retry 성공 시 retry, 아니면 primary
    if retry_steps and retry_steps[-1].exit_code == 0:
        final_do_exit = 0
    elif primary_do_steps:
        final_do_exit = primary_do_steps[-1].exit_code
    else:
        final_do_exit = 0  # skip_do 모드

    # DO 실패 시 Gate/DocOps PASS여도 전체 FAIL 강제 (거짓 PASS 차단)
    do_failed = (not args.skip_do) and (final_do_exit != 0)
    # do_* 스텝은 final_do_exit 기준으로만 판단 (retry 성공 시 primary exit=2가 all()을 오염시키지 않도록)
    non_do_results = [r for r in results if not r.name.startswith("do_")]
    overall_pass = (not do_failed) and all(r.exit_code == 0 for r in non_do_results)

    extra_notes = [
        "Bikit CHECK uses make gate/docops/evidence_check",
        f"plan_doc={plan_doc_path.relative_to(ROOT)}",
        f"report={report_path.relative_to(ROOT)}",
    ]
    if do_failed:
        extra_notes.append(f"[DO_FAIL] do_failed=true do_exit_code={final_do_exit}")
        print(f"[WORKER] DO FAIL (exit_code={final_do_exit}) → 사이클 FAIL 강제 (거짓 PASS 차단)")

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
        notes=extra_notes,
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
