# DocOps Token Policy (Policy A)

## 목적
- DocOps 토큰 스캔의 PASS/FAIL 기준을 고정한다.
- 히스토리/리포트 문서는 보존하면서, 핵심 SSOT 문서만 0건을 강제한다.

## 정책 요약 (Policy A)
- **Strict (0건 강제):** 핵심 SSOT 문서만 적용
- **Allowlist (카운트만):** 히스토리/리포트 문서
- **기타 문서:** 카운트만 기록 (FAIL 아님)

## 스캔 토큰
- cci
- migrate, migration, \uC774\uAD00
- TODO, TBD, PLACEHOLDER

## Strict 대상 (0건 강제)
- `docs/v2/SSOT_RULES.md`
- `docs/v2/design/SSOT_MAP.md`
- `docs/v2/V2_ARCHITECTURE.md`

## Allowlist 대상 (카운트만)
- `D_ROADMAP.md`
- `docs/v2/reports/**`

## PASS/FAIL 기준
- **FAIL:** Strict 대상 문서에서 토큰 1건이라도 발견
- **PASS:** Strict 대상 문서에서 토큰 0건
- Allowlist/기타 문서의 토큰은 리포트만 하며 FAIL로 취급하지 않는다.

## 구현
- 설정 파일: `config/docops_token_allowlist.yml`
- 실행 엔트리포인트: `just docops`
- 출력 형식: 전체 카운트 + Strict 위반 상세

## 변경 통제
- 정책 변경은 반드시 D_ROADMAP에 기록한다.
- Strict 대상 추가/삭제는 allowlist 설정과 동시에 갱신한다.
