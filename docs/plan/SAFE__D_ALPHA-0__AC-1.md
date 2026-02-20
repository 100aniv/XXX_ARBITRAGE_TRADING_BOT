# PLAN: SAFE::D_ALPHA-0::AC-1

## Bikit Workflow
- PLAN: 본 문서 + 시스템 프롬프트를 기준으로 설계한다.
- DO: Aider로 구현 후 커밋한다.
- CHECK: make gate + SSOT 검증으로 완료 판정한다.

## Ticket
- ac_id: D_ALPHA-0::AC-1
- title: universe(top=100) 로딩 시 universe_size=100 아티팩트 기록
- done_criteria: Bikit PLAN/DO/CHECK 완료 + make gate 성공 + check_ssot_docs.py exit_code==0 + machine-readable result.json/report 생성

## System Prompt
- ops/prompts/worker_instruction.md

## Scope/Allowlist
### modify
- tests/test_d_alpha_0_universe_truth.py

### readonly
- docs/v2/design/AC_LEDGER.md
- docs/v2/design/AGENTIC_FACTORY_WORKFLOW.md

### forbidden
- arbitrage/v2/**
- D_ROADMAP.md
- docs/v2/SSOT_RULES.md
