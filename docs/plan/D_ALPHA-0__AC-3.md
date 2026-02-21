# PLAN: D_ALPHA-0::AC-3

## Bikit Workflow
- PLAN: 본 문서 + 시스템 프롬프트를 기준으로 설계한다.
- DO: Aider로 구현 후 커밋한다.
- CHECK: make gate + SSOT 검증으로 완료 판정한다.

## Ticket
- ac_id: D_ALPHA-0::AC-3
- title: symbols_top=100인데 10개만 들어가는 경로 제거/수정
- done_criteria: Gate 3단 PASS + DocOps ExitCode=0 + Evidence 생성

## System Prompt
- ops/prompts/worker_instruction.md

## Scope/Allowlist
### modify
- (none)

### readonly
- docs/v2/design/AC_LEDGER.md
- docs/v2/design/AGENTIC_FACTORY_WORKFLOW.md

### forbidden
- D_ROADMAP.md
- docs/v2/SSOT_RULES.md
