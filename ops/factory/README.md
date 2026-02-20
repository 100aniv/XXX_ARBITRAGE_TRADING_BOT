# Factory Setup (Phase D)

## Purpose

이 디렉터리는 Bikit(PDCA) 기반 Agentic Factory 실행 경로를 포함한다.
Supervisor가 PLAN/DO/CHECK를 orchestrate하고, Worker는 Docker 컨테이너에서 실행된다.

## Files

- `schema.py`: machine-readable plan/result schema helpers
- `controller.py`: AC ledger에서 OPEN ticket을 선택해 `logs/autopilot/plan.json` 생성
- `worker.py`: Bikit DO/CHECK 실행 후 `logs/autopilot/result.json` 및 분석 리포트 생성
- `../factory_supervisor.py`: PLAN 문서 생성, Docker Worker 실행, credit/secret guard 강제
- `Dockerfile.worker`: Node 20 + Python 3.11 + Aider + Claude Code 실설치 워커 이미지
- `../prompts/worker_instruction.md`: Worker 시스템 프롬프트

## Command path

`just` recipe names cannot include `:` on this repository's justfile parser.
Equivalent mapping is provided:

- requested: `just factory:dry`
- actual: `just factory_dry`

- requested: `just factory:run`
- actual: `just factory_run`

## Execution

```bash
just factory_dry
```

This performs:

1. `controller.py` -> create `logs/autopilot/plan.json`
2. `factory_supervisor.py` -> PLAN 문서(`docs/plan/{ticket}.md`) 생성
3. Docker Worker 실행 -> DO(Aider) + CHECK(`make gate`, `make docops`, `make evidence_check`)
4. `worker.py` -> `logs/autopilot/result.json`, `docs/report/{ticket}_analyze.md` 생성

## Safety rule

- 코어(`arbitrage/v2/**`) 대량 변경 금지
- `_trade_to_result` 마찰 반영 단일 용접 지점 유지
- Secret Guard: 키 누락 시 템플릿만 출력, 값 노출 금지
- 실행 모드(`factory_run`)에서는 LLM 키 누락 시 FAIL-FAST

## Operational Policy (Phase D)

- Master 1인 운영
  - Claude Code: PLAN/CHECK
  - Aider: DO(구현/커밋)
- 세션 크레딧 상한: 기본 `$5`
  - `factory_supervisor.py --max-credit-usd 5.0`
  - cap 초과 시 `CREDIT_GUARD`로 즉시 종료
- 기본 컨테이너 실행 파라미터
  - `--network docker_arbitrage-network`
  - `--env-file .env.factory.local` (없으면 `.env.paper` 등 fallback)
  - `-v $(pwd):/app`
- Dry-run 검증
  - `python3 ops/factory_supervisor.py --dry-run --container-mode docker --docker-network docker_arbitrage-network --env-file .env.factory.local --docker-image arbitrage-factory-worker:latest`
- 키 주입 준비
  - `cp .env.factory.local.example .env.factory.local`
  - `chmod 600 .env.factory.local`
  - `.env.factory.local`은 gitignore 대상이며, 키 값은 로컬에서만 입력

## Smart Agent Router (Deterministic, LLM-free)

### Agent 선택 규칙

Worker가 DO 단계에서 사용할 Agent를 결정론적으로 선택:

1. **File-Scope Heuristic:** 수정 대상 파일 5개 이상 -> `claude_code` 강제
2. **Intent 키워드 분류:**
   - `claude_code`: design, architecture, ssot, docops, roadmap, refactor, audit, migrate
   - `aider`: implement, fix, test, bug, add, patch, hotfix, small change
3. **Default:** `aider`

결과는 `plan.json`의 `agent_preference` 필드에 기록.

### Dual-Provider Model Policy

| Agent | Default Provider | Low | Mid | High |
|---|---|---|---|---|
| Aider | OpenAI | gpt-4.1-mini | gpt-4.1 | o3 |
| Claude Code | Anthropic | claude-sonnet-4-20250514 | claude-sonnet-4-20250514 | claude-opus-4-20250514 |

**모델 선택 우선순위:**
1. `plan.json` model_overrides (최우선)
2. `.env` per-tier (`AIDER_MODEL_HIGH` 등)
3. `.env` general (`AIDER_MODEL` 등)
4. Policy default (위 테이블)

**Provider Override:** `.env`에서 `AIDER_PROVIDER=anthropic`으로 설정하면
Aider도 Anthropic 모델 사용 가능 (사용자 설정 > 정책).

### Tier Cap

- `AIDER_MODEL_MAX_TIER=high` (기본값)
- `CLAUDE_CODE_MODEL_MAX_TIER=high` (기본값)
- `mid`로 설정하면 high 모델 사용 차단 (비용 절감)

### Reflective Escalation (실패 시 1회 상향)

조건:
- Gate 실패 (exit != 0)
- `ROUTER_ESCALATE_ON_GATE_FAIL=1`
- 상향 횟수 < `ROUTER_ESCALATE_MAX_STEP` (기본 1)
- Budget Guard 미위반

동작:
1. 1차 시도 실패 시 model tier를 1단계 상향 (예: mid -> high)
2. 실패 로그(gate stderr)를 고성능 모델에 Context Handover
3. 같은 티켓으로 DO+CHECK 1회 재시도
4. 결과에 `escalated=true`, `escalation_reason` 기록

### ENV 설정 가이드

```bash
cp .env.factory.local.example .env.factory.local
chmod 600 .env.factory.local
# API 키 입력 후:
just factory_dry   # DRY-RUN으로 agent/model 선택 확인
just factory_next  # 1개 AC 실행
```
