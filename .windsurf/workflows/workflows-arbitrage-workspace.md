(A) Arbitrage-lite V2 Workspace Workflows (추천 7개)
/0_bootstrap_v2

repo 스캔(구조/모듈/중복) + reuse 후보 리스트업

D_ROADMAP.md에서 현재 목표/Acceptance Criteria 확인

이번 턴 스코프 선언(파일 고정)

도커/DB/Redis 클린업 규칙 적용

LIVE 중단 상태 확인(있다면)

/1_gate_fast_v2

fast gate(SSOT) 실행

D202-2 같은 테스트 실패는 여기서 잡고 끝내야 함

FAIL 시 자동 디버깅 루프 템플릿 포함

/2_gate_regression_v2

regression(SSOT 타깃) 실행

watch(dog)로 중간 멈춤 방지 포함

PASS 시에만 다음 진행

/3_fix_loop_v2

“단일 원인 → 단일 수정 → fast 재실행 → regression 재실행”
이 루프를 강제하는 템플릿

/4_reuse_audit_v2

V1 대비 재사용률 점검:

새 파일 생성 목록

대체 가능 기존 모듈 링크

“왜 못 썼는지” 근거 1줄

중복 모듈 정리 TODO를 ROADMAP에 반영

/5_engine_flow_harness_v2

Engine→OrderIntent→Adapter 단일 플로우 Smoke Harness 실행 템플릿

(필요하면) PAPER 모드 20분 스모크 → 1h 베이스라인 → 3h+ 계단식 기준 포함

/6_doc_commit_push_v2

D_ROADMAP.md ✅/TODO 업데이트(근거: evidence 경로)

REPORT 갱신

git commit + push

---

## (B) SSOT DocOps Workflows (신규 추가)

/7_docops_gate_v2

DocOps Always-On 절차 (커밋 전 필수):
- Gate (A) SSOT 자동 검사: python scripts/check_ssot_docs.py (Exit code 0 필수)
- Gate (B) ripgrep 위반 탐지: cci, 이관/migrate/migration, TODO/TBD/PLACEHOLDER
- Gate (C) Pre-commit sanity: git status, git diff --stat

Evidence 저장: 각 D 리포트에 명령 + exit code + 핵심 결과 기록

/8_ac_transfer_protocol_v2

AC 이관 프로토콜 (강제):
- AC는 절대 삭제하지 않음
- 원본 AC: ~~내용~~ [MOVED_TO: <목적지 D> / <날짜> / <커밋> / <사유>]
- 목적지 AC: [ ] AC-3: 내용 [FROM: <원본 D> AC-<번호>]
- Umbrella 섹션에 "AC 이관 매핑" 서브섹션 추가

/9_wallclock_verification_v2

장기 실행 테스트(≥1h) 필수 증거:
- watch_summary.json (SSOT)
- 필수 필드: planned_total_hours, started_at_utc, ended_at_utc, monotonic_elapsed_sec, completeness_ratio, stop_reason
- stop_reason enum: TIME_REACHED | TRIGGER_HIT | EARLY_INFEASIBLE | ERROR | INTERRUPTED
- PASS 기준: completeness_ratio ≥ 0.95 또는 (< 0.95 but stop_reason = EARLY_INFEASIBLE)
- 시간 기반 완료 선언 금지 (watch_summary.json에서 자동 추출만)

/10_smoke_type_selector_v2

Smoke 유형 선택 규칙:
- Micro-Smoke (1분): 경미한 변경(설정/문서만), 기본 런타임 검증
- Full Smoke (20분): 트레이딩 루프 변경(Engine/Adapter/Detector), 실제 거래 생성 검증
- PASS 기준: 주문 ≥ 1, 포지션 정상, 0 trades → FAIL + DecisionTrace

/11_design_docs_reading_tax_v2

Design Docs 참조 규칙 (디폴트):
- 모든 D-step은 docs/v2/design/ 반드시 열어 읽기
- 이번 D에 관련된 문서 최소 2개 요약 필수
- READING_CHECKLIST.md: 읽은 문서 목록 + 1줄 요약
- "이번 작업에서 무엇을 재사용하고 무엇을 가져올지" 10줄 이내 요약

/12_d000_meta_governance_v2

D000 META/Governance 번호 체계 (강제):
- D000 제목에 [META] 태그 강제: D000-1: [META] SSOT Rules Unify
- D_ROADMAP에서 META RAIL 섹션 격리
- 브랜치명: rescue/d000_1_meta_ssot_rules
- AC 요구사항: check_ssot_docs.py ExitCode=0 필수
- D000-x Report: "왜 META 작업이 필요했는지" 명시 필수

/13_api_naming_convention_v2

API 및 버전 명칭 규칙 (강제):
- 시즌 표기 (V1/V2): 프로젝트 세대 전용 (arbitrage/v2/, docs/v2/, config/v2/)
- 외부 API 버전: 의미 기반 명명 (MarketType.SPOT | MarketType.FUTURES)
- ✅ 허용: BINANCE_SPOT_BASE_URL, BINANCE_FUTURES_BASE_URL
- ❌ 금지: "v1 API", "v3 API", API_V1, API_V3, R1, R3
- 검증: rg "v1 API|v3 API|API_V1|API_V3|R1|R3" --type py --type md --type yaml
- 폴더 리네임: D206 이후 Pure Infra Refactor 전용 D-step에서만 허용