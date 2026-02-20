from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "logs" / "autopilot" / "plan.json"
RESULT_PATH = ROOT / "logs" / "autopilot" / "result.json"
PROMPT_PATH = ROOT / "ops" / "prompts" / "worker_instruction.md"
PLAN_DOC_ROOT = ROOT / "docs" / "plan"
REPORT_ROOT = ROOT / "docs" / "report"
FACTORY_LOG_PATH = ROOT / "logs" / "factory" / "init_test.log"
MODEL_ROUTING_LOG_PATH = ROOT / "logs" / "factory" / "model_routing.log"
MODEL_USAGE_LOG_PATH = ROOT / "logs" / "factory" / "model_usage.log"

MODEL_TIERS = ["low", "mid", "high"]
MODEL_POLICY = {
    "aider": {
        "low": "claude-4-6-sonnet",
        "mid": "claude-4-6-sonnet",
        "high": "claude-4-6-apex",
    },
    "claude_code": {
        "low": "claude-4-6-sonnet",
        "mid": "claude-4-6-sonnet",
        "high": "claude-4-6-apex",
    },
}

REQUIRED_AGENT_KEYS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
]


def run_cmd(command: List[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=check,
    )


def read_env_keys(env_file: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    if not env_file.exists():
        return data
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def ensure_credit_guard(session_cost_usd: float, max_credit_usd: float) -> None:
    if session_cost_usd <= max_credit_usd:
        return
    raise RuntimeError(
        "[CREDIT_GUARD] FAIL: session cost cap exceeded "
        f"(cost={session_cost_usd:.2f}, cap={max_credit_usd:.2f})"
    )


def ensure_secret_guard(env_keys: Dict[str, str], dry_run: bool, allow_missing: bool) -> List[str]:
    missing = [key for key in REQUIRED_AGENT_KEYS if not env_keys.get(key)]
    if not missing:
        return []

    print("[SECRET_GUARD] missing required keys. template only:")
    for key in missing:
        print(f"{key}=<REDACTED>")
    if not dry_run and not allow_missing:
        raise RuntimeError("[SECRET_GUARD] FAIL-FAST: required LLM keys are missing")
    if not dry_run and allow_missing:
        print("[SECRET_GUARD] WARN: missing keys may block DO step in runtime")
    return missing


def print_factory_env_template() -> None:
    print("ANTHROPIC_API_KEY=<REDACTED>")
    print("OPENAI_API_KEY=<REDACTED>")
    print("AIDER_MODEL=")
    print("CLAUDE_CODE_MODEL=")
    print("AIDER_MODEL_MAX_TIER=mid")
    print("CLAUDE_CODE_MODEL_MAX_TIER=mid")


def resolve_env_file(requested_env_file: str) -> tuple[Path, List[str], bool]:
    warnings: List[str] = []
    requested = Path(requested_env_file)
    requested_abs = requested if requested.is_absolute() else ROOT / requested
    if requested_abs.exists():
        return requested_abs, warnings, False

    warnings.append(f"requested env file not found: {requested_env_file}")
    return requested_abs, warnings, True


def normalize_tier(value: str) -> str:
    tier = value.strip().lower()
    if tier in MODEL_TIERS:
        return tier
    return "high"


def tier_index(value: str) -> int:
    return MODEL_TIERS.index(normalize_tier(value))


def clamp_tier(policy_tier: str, max_tier: str) -> str:
    bounded_index = min(tier_index(policy_tier), tier_index(max_tier))
    return MODEL_TIERS[bounded_index]


def infer_model_tier(model_name: str) -> str:
    value = model_name.strip().lower()
    if not value:
        return "high"
    if any(token in value for token in ["mini", "haiku", "small"]):
        return "low"
    if any(token in value for token in ["apex", "opus", "o3", "o1", "ultra", "max"]):
        return "high"
    if "sonnet" in value:
        return "mid"
    return "mid"


def resolve_model_selection(plan: Dict[str, str], env_keys: Dict[str, str]) -> Dict[str, str]:
    risk_level = str(plan.get("risk_level", "mid")).strip().lower() or "mid"
    model_budget = str(plan.get("model_budget", risk_level)).strip().lower() or risk_level
    policy_tier = normalize_tier(model_budget)
    risk_tier = normalize_tier(risk_level)
    high_allowed = risk_tier == "high"
    if not high_allowed and policy_tier == "high":
        policy_tier = "mid"

    aider_max_tier = normalize_tier(env_keys.get("AIDER_MODEL_MAX_TIER", "high"))
    claude_max_tier = normalize_tier(env_keys.get("CLAUDE_CODE_MODEL_MAX_TIER", "high"))

    aider_policy_tier = clamp_tier(policy_tier, aider_max_tier)
    claude_policy_tier = clamp_tier(policy_tier, claude_max_tier)

    selected_aider = MODEL_POLICY["aider"][aider_policy_tier]
    selected_claude = MODEL_POLICY["claude_code"][claude_policy_tier]

    overrides = plan.get("model_overrides", {}) if isinstance(plan.get("model_overrides", {}), dict) else {}

    plan_aider = str(overrides.get("aider", "")).strip()
    plan_claude = str(overrides.get("claude_code", "")).strip()
    env_aider = str(env_keys.get("AIDER_MODEL", "")).strip()
    env_claude = str(env_keys.get("CLAUDE_CODE_MODEL", "")).strip()

    def model_allowed(candidate: str, max_tier: str) -> bool:
        inferred = infer_model_tier(candidate)
        if inferred == "high" and not high_allowed:
            return False
        return tier_index(inferred) <= tier_index(max_tier)

    if plan_aider:
        if model_allowed(plan_aider, aider_max_tier):
            selected_aider = plan_aider
    elif env_aider:
        if model_allowed(env_aider, aider_max_tier):
            selected_aider = env_aider

    if plan_claude:
        if model_allowed(plan_claude, claude_max_tier):
            selected_claude = plan_claude
    elif env_claude:
        if model_allowed(env_claude, claude_max_tier):
            selected_claude = env_claude

    return {
        "risk_level": normalize_tier(risk_level),
        "model_budget": normalize_tier(model_budget),
        "aider_model": selected_aider,
        "claude_code_model": selected_claude,
        "aider_max_tier": aider_max_tier,
        "claude_max_tier": claude_max_tier,
    }


def extract_gate_failure_summary(max_lines: int = 10) -> List[str]:
    if not RESULT_PATH.exists():
        return []
    try:
        payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    latest = str(payload.get("evidence_latest", "")).strip()
    if not latest:
        return []
    gate_log = ROOT / latest / "gate.log"
    if not gate_log.exists():
        return []

    lines = gate_log.read_text(encoding="utf-8", errors="ignore").splitlines()
    filtered = [
        line.strip()
        for line in lines
        if line.strip() and ("FAIL" in line or "ERROR" in line or "Traceback" in line)
    ]
    return (filtered[-max_lines:] if filtered else lines[-max_lines:])


def extract_stage_exit_codes() -> Dict[str, int]:
    if not RESULT_PATH.exists():
        return {}
    try:
        payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    stage_exit_codes: Dict[str, int] = {}
    for item in payload.get("commands", []):
        name = str(item.get("name", "unknown"))
        code = int(item.get("exit_code", 1))
        stage_exit_codes[name] = code
    return stage_exit_codes


def append_model_routing_log(
    *,
    env_file: Path,
    ticket_id: str,
    selected_models: Dict[str, str],
) -> None:
    MODEL_ROUTING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    lines = [
        f"[{stamp}] ticket_id={ticket_id}",
        f"env_file={env_file.name}",
        f"risk_level={selected_models.get('risk_level', '')}",
        f"model_budget={selected_models.get('model_budget', '')}",
        f"aider_model={selected_models.get('aider_model', '')}",
        f"claude_code_model={selected_models.get('claude_code_model', '')}",
        f"aider_max_tier={selected_models.get('aider_max_tier', '')}",
        f"claude_max_tier={selected_models.get('claude_max_tier', '')}",
        "windsurf_reasoning_mode=high",
        "",
    ]
    with MODEL_ROUTING_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write("\n".join(lines))


def append_model_usage_log(ticket_id: str, selected_models: Dict[str, str]) -> None:
    MODEL_USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    records = [
        {
            "timestamp_utc": stamp,
            "ticket_id": ticket_id,
            "agent": "aider",
            "model_version": selected_models.get("aider_model", ""),
            "token_count": -1,
        },
        {
            "timestamp_utc": stamp,
            "ticket_id": ticket_id,
            "agent": "claude_code",
            "model_version": selected_models.get("claude_code_model", ""),
            "token_count": -1,
        },
    ]
    with MODEL_USAGE_LOG_PATH.open("a", encoding="utf-8") as fp:
        for row in records:
            fp.write(json.dumps(row, ensure_ascii=True) + "\n")


def append_init_log(
    *,
    mode: str,
    env_file: Path,
    docker_network: str,
    command_line: str,
    worker_exit_code: int,
    stage_exit_codes: Dict[str, int],
    selected_models: Dict[str, str],
    gate_failure_summary: List[str],
) -> None:
    FACTORY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "[factory_init_test]",
        f"mode={mode}",
        f"env_file={env_file.name}",
        f"docker_network={docker_network}",
        f"command={command_line}",
        f"worker_exit_code={worker_exit_code}",
        f"selected_aider_model={selected_models.get('aider_model', '')}",
        f"selected_claude_code_model={selected_models.get('claude_code_model', '')}",
        f"risk_level={selected_models.get('risk_level', '')}",
        f"model_budget={selected_models.get('model_budget', '')}",
    ]
    for stage_name, stage_code in stage_exit_codes.items():
        lines.append(f"stage_exit.{stage_name}={stage_code}")
    if gate_failure_summary:
        lines.append("gate_failure_summary_begin")
        lines.extend(gate_failure_summary)
        lines.append("gate_failure_summary_end")
    lines.append("")
    with FACTORY_LOG_PATH.open("a", encoding="utf-8") as fp:
        fp.write("\n".join(lines))


def detect_redis_network(default_network: str) -> str:
    try:
        result = run_cmd(
            [
                "docker",
                "inspect",
                "-f",
                "{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}",
                "arbitrage-redis",
            ],
            check=True,
        )
        network = result.stdout.strip().split()
        if network:
            return network[0]
    except Exception:
        pass
    return default_network


def sanitize_ticket(value: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in value)
    cleaned = cleaned.strip("_")
    return cleaned or "ticket"


def load_plan() -> Dict[str, str]:
    payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    return payload


def write_plan_doc(plan: Dict[str, str], ticket_slug: str) -> Path:
    PLAN_DOC_ROOT.mkdir(parents=True, exist_ok=True)
    plan_doc = PLAN_DOC_ROOT / f"{ticket_slug}.md"
    rel_prompt = PROMPT_PATH.relative_to(ROOT)

    scope = plan.get("scope", {})
    modify = scope.get("modify", [])
    readonly = scope.get("readonly", [])
    forbidden = scope.get("forbidden", [])

    lines = [
        f"# PLAN: {plan.get('ticket_id', ticket_slug)}",
        "",
        "## Bikit Workflow",
        "- PLAN: 본 문서 + 시스템 프롬프트를 기준으로 설계한다.",
        "- DO: Aider로 구현 후 커밋한다.",
        "- CHECK: make gate + SSOT 검증으로 완료 판정한다.",
        "",
        "## Ticket",
        f"- ac_id: {plan.get('ac_id', 'UNKNOWN')}",
        f"- title: {plan.get('title', 'UNKNOWN')}",
        f"- done_criteria: {plan.get('done_criteria', '')}",
        "",
        "## System Prompt",
        f"- {rel_prompt.as_posix()}",
        "",
        "## Scope/Allowlist",
        "### modify",
    ]
    lines.extend([f"- {item}" for item in modify] or ["- (none)"])
    lines.append("\n### readonly")
    lines.extend([f"- {item}" for item in readonly] or ["- (none)"])
    lines.append("\n### forbidden")
    lines.extend([f"- {item}" for item in forbidden] or ["- (none)"])

    plan_doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return plan_doc


def build_worker_command(
    args: argparse.Namespace,
    env_file: Path,
    selected_models: Dict[str, str],
    ticket_id: str,
    plan_doc: Path,
    report_doc: Path,
) -> List[str]:
    rel_plan_doc = plan_doc.relative_to(ROOT).as_posix()
    rel_report_doc = report_doc.relative_to(ROOT).as_posix()

    worker_args = [
        "python3",
        "-m",
        "ops.factory.worker",
        "--plan",
        "logs/autopilot/plan.json",
        "--result",
        "logs/autopilot/result.json",
        "--ticket-id",
        ticket_id,
        "--plan-doc",
        rel_plan_doc,
        "--report",
        rel_report_doc,
    ]
    if args.dry_run or args.skip_do:
        worker_args.append("--skip-do")
    if args.do_command.strip():
        worker_args.extend(["--do-command", args.do_command.strip()])

    if args.container_mode == "docker":
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            args.docker_network,
            "--env-file",
            str(env_file),
            "-e",
            "BOOTSTRAP_FLAG=1",
            "-e",
            f"FACTORY_MAX_CREDIT_USD={args.max_credit_usd}",
            "-e",
            f"FACTORY_SESSION_COST_USD={args.session_cost_usd}",
            "-e",
            f"AIDER_MODEL={selected_models['aider_model']}",
            "-e",
            f"CLAUDE_CODE_MODEL={selected_models['claude_code_model']}",
            "-v",
            f"{ROOT}:/app",
            "-w",
            "/app",
            args.docker_image,
            *worker_args,
        ]

    return worker_args


def main() -> int:
    parser = argparse.ArgumentParser(description="Factory Supervisor (Bikit PLAN/DO/CHECK)")
    parser.add_argument("--dry-run", action="store_true", help="print command without execution")
    parser.add_argument("--container-mode", choices=["docker", "local"], default="docker")
    parser.add_argument("--docker-network", default="docker_arbitrage-network")
    parser.add_argument("--env-file", default=".env.factory.local")
    parser.add_argument("--docker-image", default="arbitrage-factory-worker:latest")
    parser.add_argument("--max-credit-usd", type=float, default=5.0)
    parser.add_argument("--session-cost-usd", type=float, default=0.0)
    parser.add_argument("--do-command", default="")
    parser.add_argument("--skip-do", action="store_true", help="skip DO step (CHECK-only cycle)")
    args = parser.parse_args()

    try:
        ensure_credit_guard(args.session_cost_usd, args.max_credit_usd)
    except RuntimeError as exc:
        print(str(exc))
        return 2

    env_file, env_warnings, used_fallback = resolve_env_file(args.env_file)
    for message in env_warnings:
        print(f"[ENV] WARN: {message}")
    if used_fallback:
        print(f"[ENV] FAIL-FAST: required env file missing: {args.env_file}")
        print_factory_env_template()
        return 2

    env_keys = read_env_keys(env_file)
    try:
        missing_keys = ensure_secret_guard(
            env_keys,
            dry_run=args.dry_run,
            allow_missing=bool(args.do_command.strip()),
        )
    except RuntimeError as exc:
        print(str(exc))
        return 2

    args.docker_network = detect_redis_network(args.docker_network)

    run_cmd(["python3", "-m", "ops.factory.controller", "--output", "logs/autopilot/plan.json"], check=True)
    plan = load_plan()
    selected_models = resolve_model_selection(plan, env_keys)
    ticket_id = str(plan.get("ticket_id", "SAFE::UNKNOWN"))
    ticket_slug = sanitize_ticket(ticket_id)
    append_model_routing_log(env_file=env_file, ticket_id=ticket_id, selected_models=selected_models)
    append_model_usage_log(ticket_id=ticket_id, selected_models=selected_models)

    plan_doc = write_plan_doc(plan, ticket_slug)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    report_doc = REPORT_ROOT / f"{ticket_slug}_analyze.md"

    worker_cmd = build_worker_command(
        args,
        env_file=env_file,
        selected_models=selected_models,
        ticket_id=ticket_id,
        plan_doc=plan_doc,
        report_doc=report_doc,
    )

    print("[SUPERVISOR] PLAN complete")
    print(f"  - ticket_id: {ticket_id}")
    print(f"  - plan_doc: {plan_doc.relative_to(ROOT)}")
    print(f"  - report_doc: {report_doc.relative_to(ROOT)}")
    print(f"  - docker_network: {args.docker_network}")
    print(f"  - env_file: {env_file.relative_to(ROOT)}")
    print(f"  - aider_model: {selected_models['aider_model']}")
    print(f"  - claude_code_model: {selected_models['claude_code_model']}")
    print(f"  - risk_level: {selected_models['risk_level']}")
    print(f"  - model_budget: {selected_models['model_budget']}")

    if args.dry_run:
        display_cmd = ["$(pwd):/app" if token == f"{ROOT}:/app" else token for token in worker_cmd]
        rendered_cmd = shlex.join(display_cmd)
        print("[SUPERVISOR] DRY-RUN docker command")
        print(rendered_cmd)
        if missing_keys:
            print("[SUPERVISOR] INFO: set required keys in env file before factory_run")
        append_init_log(
            mode="DRY_RUN",
            env_file=env_file,
            docker_network=args.docker_network,
            command_line=rendered_cmd,
            worker_exit_code=0,
            stage_exit_codes={},
            selected_models=selected_models,
            gate_failure_summary=[],
        )
        return 0

    proc = run_cmd(worker_cmd, check=False)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="")

    if proc.returncode != 0:
        print(f"[SUPERVISOR] FAIL: worker exit_code={proc.returncode}")
        append_init_log(
            mode="RUN",
            env_file=env_file,
            docker_network=args.docker_network,
            command_line=shlex.join(worker_cmd),
            worker_exit_code=proc.returncode,
            stage_exit_codes=extract_stage_exit_codes(),
            selected_models=selected_models,
            gate_failure_summary=extract_gate_failure_summary(),
        )
        return proc.returncode

    append_init_log(
        mode="RUN",
        env_file=env_file,
        docker_network=args.docker_network,
        command_line=shlex.join(worker_cmd),
        worker_exit_code=0,
        stage_exit_codes=extract_stage_exit_codes(),
        selected_models=selected_models,
        gate_failure_summary=[],
    )
    print("[SUPERVISOR] DONE: Bikit cycle completed")
    print(f"  - result: {RESULT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
