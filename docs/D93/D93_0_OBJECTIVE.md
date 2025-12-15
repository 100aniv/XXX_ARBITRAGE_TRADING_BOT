# D93: ROADMAP 동기화 완결 + Gate 재현성 100% 달성

**Status:** 🚀 IN PROGRESS
**Date:** 2025-12-15
**Author:** Windsurf AI

---

## 목표 (Objective)

D92 POST-MOVE-HARDEN v3.2 완료 후 **"문서 흔들림 영구 차단"** 및 **"Gate 재현성 100% 보장"**을 목표로 다음을 달성:

1. **ROADMAP 동기화 자동화**
   - `D_ROADMAP.md` ↔ `TOBE_ROADMAP.md` D 번호 1:1 일치 강제
   - Fast Gate에 `check_roadmap_sync.py` 통합
   - 불일치 시 exit 2 (자동 FAIL)

2. **Gate 10m 재현성 100%**
   - 동일 조건에서 반복 실행 시 결과 일관성 보장
   - KPI JSON 필드 고정 (drift 방지)
   - 증거 파일 경로 표준화

3. **D92 문서 최종 정리**
   - 중복/임시 문서 제거
   - 최종 보고서만 유지 (v3.2 REPORT)
   - 증거 경로 문서와 실제 파일 100% 일치

---

## Acceptance Criteria (AC)

### AC-1: ROADMAP 동기화 자동화 ✅ (PHASE 2 완료)
- [x] `TOBE_ROADMAP.md` 생성 완료
- [x] `scripts/check_roadmap_sync.py` 작성
- [x] D82-D92 번호 1:1 일치 검증 PASS
- [ ] Fast Gate 5종에 `check_roadmap_sync.py` 추가 (문서화)

### AC-2: Core Regression 100% PASS ✅ (PHASE 3 완료)
- [x] `docs/D92/D92_CORE_REGRESSION_DEFINITION.md` 정의 명확화
- [x] 43개 테스트 100% PASS (44 passed 실행 확인)
- [x] Collection error 0개
- [x] SyntaxError 0개

### AC-3: Gate 10m 재현성 검증 (PHASE 3에서 일부 완료)
- [x] Gate 10m 600초+Exit0+KPI JSON 생성 확인 (이전 세션)
- [ ] Gate 10m 재실행 (재현성 확인)
- [ ] KPI JSON 필드 일관성 검증
- [ ] 증거 파일 경로 표준화 문서 작성

### AC-4: D92 문서 정리
- [ ] 중복 문서 스캔 및 제거
- [ ] 최종 보고서만 유지
- [ ] 증거 경로 검증 스크립트 작성

### AC-5: D93 Runner SSOT
- [ ] `scripts/run_d93_gate_reproducibility.py` 작성
- [ ] Gate 10m 2회 실행 자동화
- [ ] KPI 비교 자동화

---

## 산출물 (Deliverables)

1. **문서**
   - `docs/D93/D93_0_OBJECTIVE.md` (본 문서)
   - `docs/D93/D93_1_GATE_REPRODUCIBILITY_REPORT.md` (재현성 검증 보고서)
   - `docs/D93/D93_2_ROADMAP_SYNC_GUIDE.md` (ROADMAP 동기화 가이드)

2. **스크립트**
   - `scripts/run_d93_gate_reproducibility.py` (Gate 재현성 검증 Runner)
   - `scripts/verify_d93_evidence_paths.py` (증거 파일 경로 검증)

3. **증거 파일**
   - `logs/d93/gate_10m_run1/` (Gate 10m 1차 실행)
   - `logs/d93/gate_10m_run2/` (Gate 10m 2차 실행)
   - `logs/d93/kpi_comparison.json` (KPI 비교 결과)

---

## 실행 계획 (Execution Plan)

### Step 1: ROADMAP 동기화 가이드 작성
- TOBE_ROADMAP.md 작성 규칙 문서화
- check_roadmap_sync.py 사용법 정리
- Fast Gate 5종 통합 가이드

### Step 2: Gate 10m 재현성 검증
- Gate 10m 2회 실행 (동일 조건)
- KPI JSON 비교 자동화
- 차이점 분석 및 허용 범위 정의

### Step 3: D92 문서 정리
- 중복/임시 문서 목록화
- 제거 대상 확정
- 최종 보고서 경로 고정

### Step 4: D93 Runner SSOT 작성
- Gate 재현성 검증 자동화 스크립트
- 증거 파일 경로 검증 스크립트
- AC 자동 판정 로직

---

## 다음 단계 (Next Steps)

D93 완료 후:
- **D94**: Long-run PAPER 검증 (1h+)
- **D95**: Multi-Symbol TopN 확장
- **D96**: Production Readiness Checklist

---

## 참고 (References)

- D92 POST-MOVE-HARDEN v3.2: `docs/D92/D92_POST_MOVE_HARDEN_V3_2_REPORT.md`
- Core Regression 정의: `docs/D92/D92_CORE_REGRESSION_DEFINITION.md`
- Gate 10m SSOT: `scripts/run_gate_10m_ssot_v3_2.py`
