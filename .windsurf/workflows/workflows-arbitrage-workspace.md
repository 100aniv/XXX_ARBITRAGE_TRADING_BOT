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