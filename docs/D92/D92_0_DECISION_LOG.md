# D92 단계 정의 결정 로그 (Decision Log)

**작성일:** 2025-12-12 18:40 KST  
**상태:** ✅ 확정 (Fact-Locked)  
**목적:** D92 시리즈의 단계 정의 혼란 해소 및 향후 일관성 확보

---

## 🔍 문제 상황

### D_ROADMAP의 원래 정의 (2025-12-12 이전)
```
D92-1: TopN Multi-Symbol 1h LONGRUN (Top10)
D92-2: RiskGuard Zone-aware 통합
D92-3: Auto-Tuning Pipeline 설계
```

### 실제 진행된 작업
```
D92-1: TopN Longrun 인프라 구축 (dry-run, 테스트만)
D92-1-FIX: Zone Profile v2 Integration (run_d77_0에 직접 통합)
D92-2: Zone Profile Threshold Calibration + Telemetry 구현
D92-3: 60-Minute Longrun Fact-Locked Validation
```

### 충돌 지점
1. **D92-2 의미 변경**: RiskGuard 통합(계획) → Threshold Calibration(실행)
2. **D92-3 의미 변경**: Auto-Tuning 설계(계획) → 60m Longrun(실행)
3. **커밋 메시지 불일치**: `[D92-2]`, `[D92-3]` 커밋이 원래 정의와 다름
4. **문서 파일명 불일치**: `D92_2_CALIBRATION_REPORT.md`, `D92_3_LONGRUN_60M_REPORT.md`

---

## 🎯 결정 사항

### 선택: 옵션 B (D_ROADMAP을 실제 작업에 맞게 재정의)

**이유:**
1. **Git 커밋 이미 확정**: `[D92-2]`, `[D92-3]` 커밋이 이미 master에 존재
2. **파일명 이미 확정**: `D92_2_*.md`, `D92_3_*.md`로 문서 작성 완료
3. **효율성**: 문서/커밋 재번호보다 ROADMAP 업데이트가 더 실용적
4. **혼선 최소화**: 기존 산출물을 그대로 유지하고 정의만 정렬

---

## 📋 재정의된 D92 시리즈 (확정)

### D92-1: TopN Multi-Symbol Longrun Infrastructure (2025-12-12 완료)
**목적:** Zone Profile v2를 TopN LONGRUN 인프라에 통합  
**산출물:**
- `scripts/run_d92_1_topn_longrun.py`
- `scripts/prepare_d92_1_env.py`
- `tests/test_d92_1_topn_longrun.py` (13/13 PASS)
- `docs/D92/D92_1_TOPN_LONGRUN_REPORT.md`

**상태:** ⚠️ Dry-run 성공, 실제 실행 시 Zone Profile 미적용 (구조적 한계)

---

### D92-1-FIX: Zone Profile v2 Integration to PAPER Loop (2025-12-12 완료)
**목적:** Zone Profile을 D77-0 PAPER Runner에 직접 통합 (subprocess 제거)  
**산출물:**
- `scripts/run_d77_0_topn_arbitrage_paper.py` 수정 (Zone Profile Applier 통합)
- `docs/D92_1_FIX_*.md` (4개 문서, 통합 예정)

**상태:** ✅ Zone Profile 적용 성공, BTC threshold 6.0 bps 확인

---

### D92-2: Zone Profile Threshold Calibration + Telemetry (2025-12-12 완료)
**목적:** Spread 분포 텔레메트리 수집 및 Threshold 재보정  
**산출물:**
- Telemetry 구현 (p50/p90/p95/max/ge_rate)
- `scripts/calibrate_zone_profile_threshold.py`
- `logs/d92-2/<session_id>/d92_2_spread_report.json`
- `docs/D92_2_CALIBRATION_REPORT.md`
- `docs/D92_2_SCAN_SUMMARY.md`

**핵심 결과:**
- BTC p95: 10.33 bps (초기), 4.82 bps (60m 실행)
- Threshold: 20.0 bps → 6.0 bps 재보정
- GE Rate: 0.0% → 1.04%

**상태:** ✅ 완료 (Threshold 추가 하향 필요)

---

### D92-3: 60-Minute Longrun Fact-Locked Validation (2025-12-12 완료)
**목적:** Zone Profile 적용 상태에서 60분 전체 실행 및 팩트 검증  
**산출물:**
- Fact-locked timestamp logging (start/end/duration)
- `docs/D92_3_LONGRUN_60M_REPORT.md`
- `logs/d92-2/<session_id>/d92_2_spread_report.json` (60.01분)
- `logs/d77-0/<session_id>_kpi_summary.json`

**핵심 결과:**
- Duration: 60.01분 (100.0% 완료)
- Trades: 22 (11 RT)
- PnL: -$40,200 (TIME_LIMIT 청산, spread 축소)
- Telemetry: p95=4.82 bps, ge_rate=1.04%

**상태:** ✅ 완료 (AC 5개 전부 PASS)

---

## 🚀 향후 D92-4+ 정의 (확정)

### D92-4: Threshold Re-tuning + 60m Re-validation (다음 작업)
**목적:** Threshold 4.8-5.0 bps로 하향 조정 후 재검증  
**플랜:**
- Threshold 후보: 5.0 / 4.8 / 4.5 bps
- 실행: 10m smoke → 60m base
- KPI: trade count, ge_rate, RT PnL, TP/SL ratio

---

### D92-5: RiskGuard Zone-Aware Integration (원래 D92-2 계획)
**목적:** Zone별 리스크 한도 설정 및 포트폴리오 레벨 노출 제한  
**상태:** 🔜 계획 단계

---

### D92-6: Auto-Tuning Pipeline Design (원래 D92-3 계획)
**목적:** Best Profile 자동 선정 및 다목적 최적화  
**상태:** 🔜 설계 단계

---

## 📂 파일명/경로 규칙 (확정)

### 문서 위치
```
docs/D92/
  ├── D92_0_DECISION_LOG.md (이 문서)
  ├── D92_1_TOPN_LONGRUN_REPORT.md
  ├── D92_1_FIX_FINAL_REPORT.md (통합 예정, 4→1)
  ├── D92_2_CALIBRATION_REPORT.md
  ├── D92_2_SCAN_SUMMARY.md
  ├── D92_3_LONGRUN_60M_REPORT.md
  ├── D92_3_PNL_ACCOUNTING_FACTLOCK.md (신규)
  └── D92_4_NEXT_EXPERIMENT_PLAN.md (신규)
```

### 스크립트 위치
```
scripts/
  ├── run_d92_1_topn_longrun.py (D92-1 전용)
  ├── prepare_d92_1_env.py (D92-1 환경 준비)
  ├── calibrate_zone_profile_threshold.py (D92-2 전용)
  └── run_d77_0_topn_arbitrage_paper.py (D92-1-FIX 수정, 공통 사용)
```

### 로그 위치
```
logs/
  ├── d92-1/ (D92-1 dry-run)
  ├── d92-2/ (D92-2 calibration + D92-3 60m)
  └── d92-3-*.log (D92-3 fact-locked logs)
```

---

## ✅ 정합성 보장 규칙

### 1. Git 커밋 메시지
- D92-1: `[D92-1] TopN longrun infrastructure`
- D92-1-FIX: `[D92-1-FIX] Zone Profile integration complete`
- D92-2: `[D92-2] Threshold calibration + telemetry`
- D92-3: `[D92-3] 60m longrun fact-locked validation`

### 2. 문서 제목
- `# D92-X {작업명} Report` 형식
- 영문 제목 + 한국어 본문 (필요 용어만 영문 병기)

### 3. 로그 경로
- `logs/d92-{N}/` 형식
- Session ID 명확히 기재

### 4. 테스트 파일
- `tests/test_d92_{N}_{작업명}.py` 형식

---

## 🔒 이 결정의 영구성

**이 문서는 D92 시리즈의 SSOT(Single Source of Truth)입니다.**

- D_ROADMAP.md는 이 문서 기준으로 업데이트됨
- 향후 D92-4+ 작업은 이 정의를 따름
- 파일 이동/이름 변경 시 이 문서 먼저 업데이트

**변경 금지:**
- D92-1/2/3의 재정의 (이미 확정)
- 기존 커밋 메시지/파일명 (Git history 보존)

**변경 허용:**
- D92-4+ 정의 (실행 전 계획 수정 가능)
- 문서 통합/정리 (내용 유지, 경로만 변경)

---

## 📌 Summary

**문제:** D92-2/3 정의가 계획과 실제 작업 사이에 불일치  
**결정:** 옵션 B 채택 (D_ROADMAP을 실제에 맞게 재정의)  
**근거:** 커밋/파일명 이미 확정, 효율성, 혼선 최소화  
**결과:** D92-1/2/3 의미 확정, D92-4+ 명확한 정의 확보  
**보장:** 이 문서가 SSOT, 파일명/경로 규칙 확정

**작성자:** Windsurf AI  
**검토자:** (사용자 승인 대기)  
**상태:** ✅ Fact-Locked
