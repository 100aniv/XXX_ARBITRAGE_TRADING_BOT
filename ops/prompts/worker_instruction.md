# Factory Worker Instruction (Bikit PDCA)

## 역할 분담
- Claude Code: PLAN/CHECK 담당
  - PLAN 문서(`docs/plan/{ticket}.md`)를 읽고 변경 범위를 확정한다.
  - CHECK 단계에서 gate/docops 결과를 검증하고 보고서(`docs/report/{ticket}_analyze.md`)를 남긴다.
- Aider: DO 담당
  - PLAN 문서와 scope를 기준으로 실제 코드 구현 및 커밋을 수행한다.

## Bikit 사이클
1. PLAN
   - SSOT 우선순위: `docs/v2/SSOT_RULES.md` > `D_ROADMAP.md` > runtime(config/artifacts)
   - 변경 허용 범위(`scope.modify`)와 금지 범위(`scope.forbidden`)를 확인한다.
2. DO
   - Aider를 통해 변경 수행 후 `git add -A && git commit`을 실행한다.
   - 코어(`arbitrage/v2/**`) 대량 변경 금지.
3. CHECK
   - `make gate`(fallback: `just gate`) 실행
   - `python3 scripts/check_ssot_docs.py` 실행
   - 결과를 `docs/report/{ticket}_analyze.md`에 기록

## 안전 규칙
- Secret Guard: API 키 누락 시 값 노출 없이 템플릿만 출력하고 FAIL-FAST.
- Credit Guard: 세션 비용이 cap(기본 $5) 초과 시 즉시 종료.
- Friction-Truth: PnL 마찰 모델은 `_trade_to_result` 단일 용접 지점 유지.
