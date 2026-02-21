from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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

DEFAULT_MODELS = {
    "openai": {
        "low": "gpt-4.1-mini",
        "mid": "gpt-4.1",
        "high": "o3",
    },
    "anthropic": {
        "low": "claude-sonnet-4-20250514",
        "mid": "claude-sonnet-4-20250514",
        "high": "claude-opus-4-20250514",
    },
}

AGENT_DEFAULT_PROVIDER = {
    "aider": "openai",
    "claude_code": "anthropic",
}

REQUIRED_AGENT_KEYS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
]

PROVIDER_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


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
    print("AIDER_PROVIDER=openai")
    print("CLAUDE_CODE_PROVIDER=anthropic")
    print("AIDER_MODEL_MAX_TIER=high")
    print("CLAUDE_CODE_MODEL_MAX_TIER=high")
    print("ROUTER_ESCALATE_ON_GATE_FAIL=1")
    print("ROUTER_ESCALATE_MAX_STEP=1")


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
    if any(token in value for token in ["mini", "haiku", "small", "nano"]):
        return "low"
    if any(token in value for token in ["apex", "opus", "o3", "o1", "ultra", "max"]):
        return "high"
    if any(token in value for token in ["sonnet", "4o", "4.1", "gpt-4"]):
        return "mid"
    return "mid"


def resolve_agent_provider(agent: str, env_keys: Dict[str, str]) -> str:
    """Agent Provider 결정. env override > default."""
    key = f"{agent.upper()}_PROVIDER"
    val = env_keys.get(key, "").strip().lower()
    if val in ("openai", "anthropic"):
        return val
    return AGENT_DEFAULT_PROVIDER.get(agent, "openai")


def ensure_secret_guard_smart(
    env_keys: Dict[str, str],
    agent_preference: str,
    dry_run: bool,
    allow_missing: bool,
) -> List[str]:
    """실제 사용 provider만 키 요구 (운영 친화).

    - agent=aider & provider=openai -> OPENAI_API_KEY 필수
    - agent=claude_code & provider=anthropic -> ANTHROPIC_API_KEY 필수
    """
    provider = resolve_agent_provider(agent_preference, env_keys)
    required_key = PROVIDER_KEY_MAP.get(provider)
    if not required_key:
        return []

    if env_keys.get(required_key):
        return []

    print(f"[SECRET_GUARD] agent={agent_preference}, provider={provider}")
    print(f"[SECRET_GUARD] missing required key: {required_key}")
    if not dry_run and not allow_missing:
        raise RuntimeError(
            f"[SECRET_GUARD] FAIL-FAST: {required_key} required for {agent_preference}/{provider}"
        )
    if not dry_run and allow_missing:
        print(f"[SECRET_GUARD] WARN: {required_key} missing, DO step may fail")
    return [required_key]


def _resolve_agent_model(
    agent: str,
    policy_tier: str,
    risk_tier: str,
    plan: Dict[str, str],
    env_keys: Dict[str, str],
) -> Dict[str, str]:
    """Single agent 모델 결정.

    Priority: plan override > env per-tier > env general > policy default.
    """
    agent_upper = agent.upper()
    provider = resolve_agent_provider(agent, env_keys)
    max_tier = normalize_tier(env_keys.get(f"{agent_upper}_MODEL_MAX_TIER", "high"))
    effective_tier = clamp_tier(policy_tier, max_tier)
    high_allowed = risk_tier == "high"
    if effective_tier == "high" and not high_allowed:
        effective_tier = "mid"

    overrides = plan.get("model_overrides", {}) if isinstance(plan.get("model_overrides"), dict) else {}

    plan_model = str(overrides.get(agent, "")).strip()
    if plan_model:
        inferred = infer_model_tier(plan_model)
        if tier_index(inferred) <= tier_index(max_tier) and (inferred != "high" or high_allowed):
            return {"model": plan_model, "provider": provider, "tier": effective_tier}

    per_tier_key = f"{agent_upper}_MODEL_{effective_tier.upper()}"
    per_tier_val = env_keys.get(per_tier_key, "").strip()
    if per_tier_val:
        return {"model": per_tier_val, "provider": provider, "tier": effective_tier}

    general_key = f"{agent_upper}_MODEL"
    general_val = env_keys.get(general_key, "").strip()
    if general_val:
        inferred = infer_model_tier(general_val)
        if tier_index(inferred) <= tier_index(max_tier) and (inferred != "high" or high_allowed):
            return {"model": general_val, "provider": provider, "tier": effective_tier}

    return {"model": DEFAULT_MODELS[provider][effective_tier], "provider": provider, "tier": effective_tier}


def resolve_model_selection(
    plan: Dict[str, str],
    env_keys: Dict[str, str],
    override_tier: str = "",
) -> Dict[str, str]:
    """Dual-Provider 모델 선택 (Aider=OpenAI, Claude Code=Anthropic).

    override_tier: Escalation 시 강제 티어 지정에 사용.
    """
    risk_level = normalize_tier(str(plan.get("risk_level", "mid")).strip().lower() or "mid")
    model_budget = normalize_tier(str(plan.get("model_budget", risk_level)).strip().lower() or risk_level)
    policy_tier = normalize_tier(override_tier or model_budget)

    aider = _resolve_agent_model("aider", policy_tier, risk_level, plan, env_keys)
    claude = _resolve_agent_model("claude_code", policy_tier, risk_level, plan, env_keys)

    return {
        "agent_preference": plan.get("agent_preference", "aider"),
        "intent": plan.get("intent", ""),
        "risk_level": risk_level,
        "model_budget": model_budget,
        "aider_model": aider["model"],
        "aider_provider": aider["provider"],
        "aider_tier": aider["tier"],
        "aider_max_tier": normalize_tier(env_keys.get("AIDER_MODEL_MAX_TIER", "high")),
        "claude_code_model": claude["model"],
        "claude_code_provider": claude["provider"],
        "claude_code_tier": claude["tier"],
        "claude_max_tier": normalize_tier(env_keys.get("CLAUDE_CODE_MODEL_MAX_TIER", "high")),
    }


def escalate_tier(current_tier: str) -> str:
    """Tier 를 1단계 올림. high면 그대로."""
    idx = tier_index(current_tier)
    if idx < len(MODEL_TIERS) - 1:
        return MODEL_TIERS[idx + 1]
    return current_tier


def can_escalate_check(
    current_tier: str,
    max_tier: str,
    escalation_count: int,
    env_keys: Dict[str, str],
) -> bool:
    """Escalation 가능 여부 판단 (결정론적)."""
    if env_keys.get("ROUTER_ESCALATE_ON_GATE_FAIL", "0") != "1":
        return False
    max_step = int(env_keys.get("ROUTER_ESCALATE_MAX_STEP", "1"))
    if escalation_count >= max_step:
        return False
    next_tier = escalate_tier(current_tier)
    if tier_index(next_tier) > tier_index(max_tier):
        return False
    return next_tier != current_tier


def write_escalation_context(plan_doc: Path, failure_summary: List[str]) -> None:
    """Escalation Context Handover: 실패 로그를 고성능 모델에 주입."""
    if not failure_summary:
        return
    context = "\n\n## Escalation Context (Previous Failure)\n\n"
    context += "The previous attempt with a lower-tier model failed.\n"
    context += "Focus on fixing these specific issues:\n\n```\n"
    context += "\n".join(failure_summary[-15:])
    context += "\n```\n"
    with plan_doc.open("a", encoding="utf-8") as f:
        f.write(context)


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


# ---------------------------------------------------------------------------
# DocOps Self-Heal (결정론적, LLM 없음)
# ---------------------------------------------------------------------------

# 허용된 Self-Heal 타입
_HEAL_TYPE_CONCEPT = "missing_concept"
_HEAL_TYPE_FILENAME = "report_filename"

# conflict_resolution 삽입 템플릿 (D_ROADMAP.md 전용)
_CONFLICT_RESOLUTION_BLOCK = """
## conflict_resolution (SSOT 충돌 해결 원칙)

**판정 우선순위 (변경 금지):**
1. `docs/v2/SSOT_RULES.md` — 헌법, 최상위. 모든 충돌 시 SSOT_RULES 채택.
2. `D_ROADMAP.md` — Process SSOT. D번호 의미/상태/AC/증거 경로 정의.
3. `docs/v2/design/SSOT_MAP.md` — 도메인별 SSOT 위치 명시.
4. `docs/v2/V2_ARCHITECTURE.md` — 아키텍처 계약.
5. runtime(config/artifacts) — 실행 증거 + Gate 결과.

**충돌 해결 규칙:**
- 같은 레벨 문서 간 conflict 발생 시: 최신 증거(evidence) + Gate 결과 우선.
- 하위 문서가 상위 SSOT와 다른 정의를 사용하면 하위 문서를 상위에 맞춤.
- 운영 중 긴급 변경은 D_ROADMAP/AC_LEDGER에 반영 후 증거 첨부 필수.
- conflict 발견 시 조치: SSOT_RULES 확인 → D_ROADMAP 동기화 → check_ssot_docs.py ExitCode=0 확인.
"""

# Report 파일명 패턴 (check_ssot_docs.py와 동일)
_REPORT_NAME_RE = re.compile(
    r"^(?:D\d{3}(?:-\d+){0,3}|DALPHA(?:-[0-9A-Z]+){0,3})_REPORT\.md$"
)

# /app/ prefix 제거 후 repo 상대경로로 normalize
_APP_PREFIX_RE = re.compile(r"^/app/")


def _normalize_path(raw: str, root: Path) -> Optional[Path]:
    """DocOps 출력의 절대경로 또는 /app/ prefix 경로를 repo 상대 Path로 변환."""
    cleaned = _APP_PREFIX_RE.sub("", raw.strip())
    candidate = Path(cleaned)
    if candidate.is_absolute():
        try:
            return candidate.relative_to(root)
        except ValueError:
            return None
    return candidate


def parse_docops_failures(output: str) -> List[Dict[str, str]]:
    """DocOps stdout/stderr에서 FAIL 항목을 파싱해 구조화된 리스트로 반환.

    반환 형식:
      [{"type": _HEAL_TYPE_*, "path": "<repo-relative>", "concept": "...", "raw": "..."}]
    """
    failures: List[Dict[str, str]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("- [FAIL]"):
            continue

        # 패턴 A: missing concept: conflict_resolution (라벨 포함 케이스 대응)
        m_concept = re.search(
            r"- \[FAIL\]\s+(.+?)\s+-\s+.*missing.*concept:\s+(\S+)",
            line,
        )
        if m_concept:
            failures.append({
                "type": _HEAL_TYPE_CONCEPT,
                "path": m_concept.group(1).strip(),
                "concept": m_concept.group(2).strip(),
                "raw": line,
            })
            continue

        # 패턴 B: Report filename violates pattern
        m_fname = re.search(
            r"- \[FAIL\]\s+(.+?)\s+-\s+Report filename violates pattern",
            line,
        )
        if m_fname:
            failures.append({
                "type": _HEAL_TYPE_FILENAME,
                "path": m_fname.group(1).strip(),
                "concept": "",
                "raw": line,
            })
            continue

    return failures


def _heal_concept_conflict_resolution(doc_path: Path) -> bool:
    """D_ROADMAP.md에 conflict_resolution 블록이 없으면 삽입. 이미 있으면 False 반환."""
    if not doc_path.exists():
        return False
    text = doc_path.read_text(encoding="utf-8")
    if re.search(r"conflict.?resolution", text, re.IGNORECASE):
        return False  # 이미 존재
    # SSOT 불변 규칙 섹션 뒤에 삽입
    marker = "## D번호 의미 (Immutable Semantics)"
    if marker in text:
        text = text.replace(marker, _CONFLICT_RESOLUTION_BLOCK.strip() + "\n\n---\n\n" + marker)
    else:
        text = text + "\n" + _CONFLICT_RESOLUTION_BLOCK.strip() + "\n"
    doc_path.write_text(text, encoding="utf-8")
    return True


def _compute_rename_target(src: Path, reports_root: Path) -> Optional[Path]:
    """패턴 위반 파일명에 대해 유효한 rename 대상을 결정론적으로 계산.

    전략:
    - 파일명에서 D번호 힌트 추출 (예: D205_REBASE_REPORT -> D205)
    - 해당 D 폴더 내 최대 서브스텝 번호 + 1 로 새 파일명 결정
    - 힌트 없으면 D000 폴더에 D000-99_REPORT.md 사용
    """
    stem = src.stem  # e.g. "D205_REBASE_REPORT"
    m = re.match(r"(D(\d{3}))", stem, re.IGNORECASE)
    if not m:
        fallback = reports_root / "D000" / "D000-99_REPORT.md"
        return fallback if not fallback.exists() else None

    d_prefix = m.group(1).upper()  # e.g. "D205"
    d_num = m.group(2)             # e.g. "205"
    d_folder = reports_root / d_prefix
    d_folder.mkdir(parents=True, exist_ok=True)

    # 기존 서브스텝 번호 수집
    existing_nums: List[int] = []
    for f in d_folder.glob(f"{d_prefix}-*_REPORT.md"):
        sub_m = re.match(rf"{d_prefix}-(\d+)_REPORT\.md", f.name, re.IGNORECASE)
        if sub_m:
            existing_nums.append(int(sub_m.group(1)))
    next_num = (max(existing_nums) + 1) if existing_nums else 18
    new_name = f"{d_prefix}-{next_num}_REPORT.md"
    return d_folder / new_name


def _update_references(old_rel: str, new_rel: str, root: Path) -> List[str]:
    """repo 전체 .md 파일에서 old_rel 참조를 new_rel로 교체. 수정된 파일 목록 반환."""
    updated: List[str] = []
    old_name = Path(old_rel).name
    new_name = Path(new_rel).name
    for md in root.rglob("*.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if old_name in text or old_rel in text:
            new_text = text.replace(old_rel, new_rel).replace(old_name, new_name)
            if new_text != text:
                md.write_text(new_text, encoding="utf-8")
                updated.append(str(md.relative_to(root)))
    return updated


def _heal_report_filename(raw_path: str, root: Path) -> Tuple[bool, str, str]:
    """패턴 위반 report 파일을 rename + 참조 업데이트.

    Returns: (success, old_rel, new_rel)
    """
    rel = _normalize_path(raw_path, root)
    if rel is None:
        return False, raw_path, ""
    src = root / rel
    if not src.exists():
        return False, str(rel), ""
    if _REPORT_NAME_RE.match(src.name):
        return False, str(rel), ""  # 이미 유효

    reports_root = root / "docs" / "v2" / "reports"
    target = _compute_rename_target(src, reports_root)
    if target is None or target.exists():
        return False, str(rel), ""

    target.parent.mkdir(parents=True, exist_ok=True)
    src.rename(target)
    new_rel = str(target.relative_to(root))
    old_rel = str(rel)
    _update_references(old_rel, new_rel, root)
    return True, old_rel, new_rel


def _patch_result_json_status(
    result_path: Path,
    new_status: str,
    heal_actions: List[str],
) -> None:
    """result.json의 status 필드를 new_status로 업데이트하고 self-heal 노트를 추가.

    T3: 컨트롤러가 다음 티켓으로 포인터를 이동시킬 수 있도록 즉시 동기화.
    T4: factory_budget 비용 로그에 self_heal_applied 플래그 반영.
    """
    if not result_path.exists():
        return
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return

    payload["status"] = new_status
    payload["self_heal_applied"] = True
    payload["self_heal_actions"] = heal_actions

    # factory_budget 반영: notes에 self-heal 비용 마커 추가
    notes = payload.get("notes", [])
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    notes.append(f"[SELF_HEAL] DocOps auto-fix applied at {stamp}: {len(heal_actions)} action(s)")
    payload["notes"] = notes

    try:
        result_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[DOCOPS_HEAL] result.json status → {new_status} (동기화 완료)")
    except Exception as e:
        print(f"[DOCOPS_HEAL] result.json 업데이트 실패: {e}")


def run_docops_check(root: Path) -> Tuple[int, str]:
    """check_ssot_docs.py 실행 후 (exit_code, combined_output) 반환."""
    result = subprocess.run(
        ["python3", "scripts/check_ssot_docs.py"],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    return result.returncode, combined


def apply_docops_self_heal(
    failures: List[Dict[str, str]],
    root: Path,
) -> List[str]:
    """허용된 타입(A/B)만 자동 수정. 수정 내역 문자열 리스트 반환."""
    actions: List[str] = []
    for f in failures:
        ftype = f.get("type", "")
        fpath = f.get("path", "")
        concept = f.get("concept", "")

        if ftype == _HEAL_TYPE_CONCEPT and concept == "conflict_resolution":
            # 액션 A: D_ROADMAP.md에 conflict_resolution 삽입
            doc_path = root / _normalize_path(fpath, root) if _normalize_path(fpath, root) else None
            if doc_path is None:
                doc_path = root / "D_ROADMAP.md"
            changed = _heal_concept_conflict_resolution(doc_path)
            if changed:
                actions.append(f"[SELF_HEAL_A] conflict_resolution 삽입: {doc_path.relative_to(root)}")
            else:
                actions.append(f"[SELF_HEAL_A] conflict_resolution 이미 존재 (skip): {fpath}")

        elif ftype == _HEAL_TYPE_FILENAME:
            # 액션 B: report 파일명 rename
            ok, old_rel, new_rel = _heal_report_filename(fpath, root)
            if ok:
                actions.append(f"[SELF_HEAL_B] rename: {old_rel} -> {new_rel}")
            else:
                actions.append(f"[SELF_HEAL_B] rename 불가 (skip): {fpath}")

        else:
            # 허용되지 않은 타입 → 수정 안 함
            actions.append(f"[SELF_HEAL_SKIP] 허용되지 않은 타입={ftype}: {fpath}")

    return actions


def git_commit_self_heal(actions: List[str]) -> bool:
    """Self-Heal 수정 후 자동 git commit. 성공 여부 반환."""
    try:
        subprocess.run(
            [sys.executable, "scripts/git_safe_stage.py"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
        )
        msg = "docops: self-heal auto-fix\n\n" + "\n".join(actions)
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def run_docops_with_self_heal(
    root: Path,
    report_doc: Optional[Path] = None,
) -> Tuple[int, str, List[str]]:
    """DocOps 실행 → FAIL 시 Self-Heal 1회 → 재실행 → 결과 반환.

    Returns: (final_exit_code, final_output, heal_actions)
    """
    exit_code, output = run_docops_check(root)
    if exit_code == 0:
        return 0, output, []

    failures = parse_docops_failures(output)
    healable = [f for f in failures if f["type"] in (_HEAL_TYPE_CONCEPT, _HEAL_TYPE_FILENAME)]
    unhealable = [f for f in failures if f["type"] not in (_HEAL_TYPE_CONCEPT, _HEAL_TYPE_FILENAME)]

    if not healable:
        print("[DOCOPS_HEAL] 자동 수정 불가 항목만 존재. FAIL 유지.")
        return exit_code, output, []

    print(f"[DOCOPS_HEAL] {len(healable)}개 자동 수정 가능 / {len(unhealable)}개 수동 필요")
    actions = apply_docops_self_heal(healable, root)
    for a in actions:
        print(f"  {a}")

    committed = git_commit_self_heal(actions)
    if committed:
        print("[DOCOPS_HEAL] git commit 완료 (self-heal)")
    else:
        print("[DOCOPS_HEAL] git commit 실패 (변경사항 없거나 오류)")

    # 재실행 (1회만)
    retry_code, retry_output = run_docops_check(root)
    print(f"[DOCOPS_HEAL] 재시도 결과: {'PASS' if retry_code == 0 else 'FAIL'}")
    print(retry_output.strip())

    if report_doc is not None and report_doc.exists():
        _append_self_heal_to_report(report_doc, actions, retry_code, retry_output)

    return retry_code, retry_output, actions


def _append_self_heal_to_report(
    report_doc: Path,
    actions: List[str],
    retry_code: int,
    retry_output: str,
) -> None:
    """티켓 analyze.md에 Self-Heal 결과 섹션 추가."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    result_str = "PASS" if retry_code == 0 else "FAIL"
    lines = [
        "",
        "## DocOps Self-Heal 기록",
        f"",
        f"**시각:** {stamp}",
        f"**재시도 결과:** {result_str}",
        "",
        "### 적용 항목",
    ]
    lines.extend([f"- {a}" for a in actions])
    lines += [
        "",
        "### 재시도 출력",
        "```",
        retry_output.strip(),
        "```",
        "",
    ]
    with report_doc.open("a", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")


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


def _append_history_jsonl(result_path: Path) -> None:
    """result.json 내용을 logs/autopilot/history.jsonl에 1줄 append.

    factory_status.py의 최근 5회 히스토리 표시에 사용됨.
    """
    if not result_path.exists():
        return
    history_path = result_path.parent / "history.jsonl"
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with history_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[HISTORY] history.jsonl append 실패: {e}")


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
    parser.add_argument("--max-cycles", type=int, default=1, help="max AC cycles per run")
    parser.add_argument("--skip-plan-gen", action="store_true", help="Skip controller plan generation (use existing plan.json)")
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

    if not args.skip_plan_gen:
        run_cmd(["python3", "-m", "ops.factory.controller", "--output", "logs/autopilot/plan.json"], check=True)
    plan = load_plan()
    selected_models = resolve_model_selection(plan, env_keys)

    agent_pref_from_plan = plan.get("agent_preference", "aider")
    try:
        missing_keys = ensure_secret_guard_smart(
            env_keys,
            agent_preference=agent_pref_from_plan,
            dry_run=args.dry_run,
            allow_missing=bool(args.do_command.strip()),
        )
    except RuntimeError as exc:
        print(str(exc))
        return 2
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

    agent_pref = selected_models.get("agent_preference", "aider")
    active_agent = agent_pref
    active_model_key = f"{active_agent}_model"
    active_tier_key = f"{active_agent}_tier" if active_agent == "aider" else "claude_code_tier"

    print("[SUPERVISOR] PLAN complete")
    print(f"  - ticket_id: {ticket_id}")
    print(f"  - plan_doc: {plan_doc.relative_to(ROOT)}")
    print(f"  - report_doc: {report_doc.relative_to(ROOT)}")
    print(f"  - docker_network: {args.docker_network}")
    print(f"  - env_file: {env_file.relative_to(ROOT)}")
    print(f"  - agent_preference: {agent_pref}")
    print(f"  - intent: {selected_models.get('intent', '')}")
    print(f"  - aider_model: {selected_models['aider_model']} (provider={selected_models.get('aider_provider', '')})")
    print(f"  - claude_code_model: {selected_models['claude_code_model']} (provider={selected_models.get('claude_code_provider', '')})")
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

    # -----------------------------------------------------------------------
    # Gate/DO FAIL 여부 판단 (DocOps와 분리)
    # result.json에서 각 스텝 exit_code를 읽어 판단
    # -----------------------------------------------------------------------
    stage_codes = extract_stage_exit_codes()
    gate_failed = stage_codes.get("gate", proc.returncode) != 0
    # DO 실패 판단: do_* 스텝 중 _retry 제외 primary 스텝 또는 retry 성공 여부
    do_exit = stage_codes.get("do_aider", stage_codes.get("do_claude_code",
              stage_codes.get("do_custom", proc.returncode)))
    do_retry_exit = stage_codes.get("do_aider_retry", stage_codes.get("do_claude_code_retry", None))
    # retry 성공 시 do_exit=0으로 간주
    if do_retry_exit is not None and do_retry_exit == 0:
        do_exit = 0
    do_failed_in_worker = do_exit != 0

    # -----------------------------------------------------------------------
    # DocOps Self-Heal: Gate PASS + DO PASS + DocOps FAIL 인 경우에만 1회 시도
    # DO 실패면 절대 PASS 오버라이드 금지 (거짓 PASS 차단)
    # -----------------------------------------------------------------------
    docops_exit, _docops_out, _heal_actions = run_docops_with_self_heal(
        ROOT, report_doc=report_doc
    )
    self_heal_applied = len(_heal_actions) > 0

    if not gate_failed and not do_failed_in_worker and docops_exit == 0 and proc.returncode != 0:
        # Gate PASS + DO PASS + DocOps Self-Heal 성공 → 사이클 PASS로 오버라이드
        print("[DOCOPS_HEAL] Gate PASS + DO PASS + DocOps Self-Heal PASS → 사이클 PASS 처리.")
        proc = subprocess.CompletedProcess(
            args=proc.args, returncode=0,
            stdout=proc.stdout, stderr=proc.stderr
        )
        _patch_result_json_status(RESULT_PATH, "PASS", _heal_actions)
    elif do_failed_in_worker and proc.returncode == 0:
        # DO 실패인데 worker가 PASS로 리턴한 경우 → 거짓 PASS 차단
        print(f"[SUPERVISOR] DO FAIL (exit={do_exit}) 감지 → 사이클 FAIL 강제 (거짓 PASS 차단)")
        proc = subprocess.CompletedProcess(
            args=proc.args, returncode=1,
            stdout=proc.stdout, stderr=proc.stderr
        )
    elif not gate_failed and not do_failed_in_worker and docops_exit != 0 and proc.returncode == 0:
        # Gate PASS + DO PASS였지만 DocOps Self-Heal 후에도 FAIL → worker 실패로 처리
        print("[DOCOPS_HEAL] Self-Heal 후에도 DocOps FAIL. 사이클 FAIL 처리.")
        proc = subprocess.CompletedProcess(
            args=proc.args, returncode=1,
            stdout=proc.stdout, stderr=proc.stderr
        )

    # -----------------------------------------------------------------------
    # Escalation: Gate FAIL에만 발동 (DocOps FAIL은 위에서 처리 완료)
    # -----------------------------------------------------------------------
    escalation_count = 0
    escalated = False
    escalation_reason = ""

    if gate_failed and proc.returncode != 0:
        current_tier = selected_models.get(active_tier_key, "mid")
        agent_max_tier = selected_models.get(
            "aider_max_tier" if active_agent == "aider" else "claude_max_tier", "high"
        )
        if can_escalate_check(current_tier, agent_max_tier, escalation_count, env_keys):
            next_tier = escalate_tier(current_tier)
            print(f"[ESCALATION] Gate 실패. {current_tier} -> {next_tier} 으로 1회 상향 재시도")

            failure_summary = extract_gate_failure_summary()
            write_escalation_context(plan_doc, failure_summary)

            selected_models = resolve_model_selection(plan, env_keys, override_tier=next_tier)
            worker_cmd = build_worker_command(
                args,
                env_file=env_file,
                selected_models=selected_models,
                ticket_id=ticket_id,
                plan_doc=plan_doc,
                report_doc=report_doc,
            )
            append_model_routing_log(env_file=env_file, ticket_id=ticket_id, selected_models=selected_models)

            print(f"[ESCALATION] Re-run: aider={selected_models['aider_model']}, claude={selected_models['claude_code_model']}")
            proc = run_cmd(worker_cmd, check=False)
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="")

            escalation_count += 1
            escalated = True
            escalation_reason = f"gate_fail_tier_{current_tier}_to_{next_tier}"

    if proc.returncode != 0:
        print(f"[SUPERVISOR] FAIL: worker exit_code={proc.returncode}")
        if escalated:
            print(f"[SUPERVISOR] Escalation was attempted: {escalation_reason}")
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
        _append_history_jsonl(RESULT_PATH)
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
    _append_history_jsonl(RESULT_PATH)
    status_msg = "(escalated)" if escalated else ""
    print(f"[SUPERVISOR] DONE: Bikit cycle completed {status_msg}")
    print(f"  - result: {RESULT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
