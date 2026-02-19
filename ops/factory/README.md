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

## Dynamic Model Routing

- 티켓 난이도(`risk_level`/`model_budget`) 기준으로 기본 모델 자동 선택
- 우선순위: plan override > env override(AIDER_MODEL/CLAUDE_CODE_MODEL) > policy default
- 안전 상한: `AIDER_MODEL_MAX_TIER`, `CLAUDE_CODE_MODEL_MAX_TIER` (low|mid|high)
