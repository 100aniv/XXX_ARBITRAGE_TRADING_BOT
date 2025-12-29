---
trigger: always_on
---
(A) Arbitrage-lite V2 Workspace Rules 예시(복붙용)

SSOT 단일화

D_ROADMAP.md가 유일 마스터(SSOT). 다른 문서는 결과물/부록.

Docs 분리

docs/v1: 과거 보관(읽기 전용)

docs/v2: 신규 설계/결과(작성 대상)

scan-first → reuse-first 강제

신규 파일/모듈 생성 전, 기존 모듈 재사용 후보를 먼저 찾아서 근거로 남길 것.

“새로 만들기”는 대체 불가 근거 없으면 금지.

스크립트 실험 폐기 / 엔진 중심

스크립트 중심 실험/러너는 금지.

Engine → OrderIntent → ExchangeAdapter 단일 플로우 기반 Harness만 허용.

V2 핵심 결함 재발 금지

LIMIT로 시장가 흉내 금지.

Upbit MARKET 미지원 상태로 LIVE/PAPER “완료 처리” 금지.

Gate 통과 전 상태 선언 금지

fast/regression/full 중 해당 단계 요구 Gate 100% PASS 전엔 DONE/GO 선언 금지.

0번 부트스트랩 필수

매 작업 턴은 /0_bootstrap 없으면 시작 불가.
---
trigger: manual
---

