# D92-1 TopN Multi-Symbol 1h LONGRUN Validation - 문서 인덱스

**최종 갱신:** 2025-12-12 19:05 KST  
**상태:** ✅ ROADMAP SSOT 원칙 적용 완료

---

## 📋 ROADMAP 정의 (SSOT)

**D_ROADMAP.md 기준:**
- **D92-1:** TopN Multi-Symbol 1h LONGRUN Validation (Zone Profile v2 적용 실전 검증)
- **D92-2:** RiskGuard Zone-aware Integration (예정)
- **D92-3:** Auto-Tuning Pipeline Design (예정)

---

## 🔄 레거시 라벨 정리

**과거 커밋 메시지:**
- `[D92-2]` Zone Profile threshold calibration + telemetry (4ab381b)
- `[D92-3]` 60m longrun fact-locked validation (20e58a8)

**정정:**
이들은 **모두 D92-1 작업의 하위 산출물**입니다.
Git 히스토리 보존을 위해 커밋 메시지는 유지하되, 문서 체계는 ROADMAP에 일치시킵니다.

---

## 📂 D92-1 문서 구조

### 1. 핵심 리포트 (실행 검증)
- **`D92_1_TOPN_LONGRUN_REPORT.md`** - D92-1 초기 인프라 구축 리포트
- **`D92_1_LONGRUN_60M_REPORT.md`** - 60분 전체 실행 검증 리포트 (구 D92-3 리포트)
- **`D92_1_CALIBRATION_REPORT.md`** - Threshold 보정 리포트 (구 D92-2 리포트)

### 2. 기술 상세 문서
- **`D92_1_FIX_ROOT_CAUSE.md`** - Zone Profile 통합 과정 근본 원인 분석
- **`D92_1_FIX_VERIFICATION_REPORT.md`** - Zone Profile 적용 검증 상세
- **`D92_1_FIX_COMPLETION_REPORT.md`** - Zone Profile 통합 완료 리포트
- **`D92_1_FIX_FINAL_STATUS.md`** - 최종 상태 정리

### 3. 정산 & 분석
- **`D92_1_PNL_ACCOUNTING_FACTLOCK.md`** - PnL 정산 팩트락 (코드 추적 기반)
- **`D92_1_SCAN_SUMMARY.md`** - 컨텍스트 스캔 요약

### 4. 다음 액션
- **`D92_1_NEXT_EXPERIMENT_PLAN.md`** - Threshold 재조정 실험 플랜

---

## 🎯 D92-1 주요 성과

### ✅ 완료 항목
1. **Zone Profile v2 Integration**
   - `zone_profiles_v2.yaml` SSOT 확립
   - 5개 심볼 (BTC/ETH/XRP/SOL/DOGE) Best Profile 적용
   - `ZoneProfileApplier` 직접 통합 (subprocess 제거)

2. **Telemetry 구현**
   - Spread 분포 수집 (p50/p90/p95/max, ge_rate)
   - `d92_2_spread_report.json` 자동 생성
   - Threshold 보정 스크립트 (`calibrate_zone_profile_threshold.py`)

3. **60분 LONGRUN 검증**
   - Duration: 60.01분 (100% 완료)
   - Trades: 22 (11 RT)
   - Telemetry: p95=4.82 bps, ge_rate=1.04%
   - Exit Reasons: 100% TIME_LIMIT

4. **PnL 정산 분석**
   - Total PnL: -$40,200
   - 계산 경로 추적 완료
   - Quantity 과대 가능성 식별 (73 BTC/RT 추정)

5. **테스트 100% PASS**
   - `test_d92_1_topn_longrun.py`: 13/13 PASS

### ⚠️ 남은 작업
1. **PnL 정산 팩트 확정**
   - Quantity 설정 코드 검증
   - 단위 테스트 3개 추가 (PASS 강제)

2. **Threshold 재조정**
   - 현재: 6.0 bps (ge_rate 1.04% 너무 낮음)
   - 목표: 5.0/4.8/4.5 bps 후보 테스트

3. **20m Smoke + 60m Base 재실행**
   - Threshold 재보정 후 검증
   - Trade 생성률 개선 확인

---

## 🔗 관련 파일

### Scripts
- `scripts/run_d92_1_topn_longrun.py` - TopN LONGRUN Runner
- `scripts/run_d77_0_topn_arbitrage_paper.py` - PAPER Runner (Zone Profile 통합)
- `scripts/calibrate_zone_profile_threshold.py` - Threshold 보정 스크립트
- `scripts/prepare_d92_1_env.py` - 환경 준비 스크립트

### Config
- `config/arbitrage/zone_profiles_v2.yaml` - Zone Profile SSOT

### Core
- `arbitrage/core/zone_profile_applier.py` - Zone Profile 적용 로직
- `arbitrage/config/zone_profiles_loader_v2.py` - Zone Profile 로더

### Tests
- `tests/test_d92_1_topn_longrun.py` - D92-1 테스트 스위트 (13/13 PASS)

### Logs
- `logs/d92-2/d82-0-top_10-20251212172430/d92_2_spread_report.json` - Telemetry
- `logs/d77-0/d82-0-top_10-20251212172430_kpi_summary.json` - KPI Summary

---

## 📊 핵심 지표

| Metric | Value | Status |
|--------|-------|--------|
| **Duration** | 60.01분 | ✅ 100% |
| **Trades** | 22 (11 RT) | ⚠️ 낮음 |
| **PnL** | -$40,200 | ⚠️ 검증 필요 |
| **GE Rate** | 1.04% | ❌ 목표 3-7% 미달 |
| **p95 Spread** | 4.82 bps | ✅ 측정 완료 |
| **Threshold** | 6.0 bps | ⚠️ 재조정 필요 |
| **Exit Reasons** | TIME_LIMIT 100% | ⚠️ TP/SL 미작동 |

---

## 🚀 Next Steps (즉시 실행 가능)

1. **PnL 코드 검증** (STEP 3)
   - `arbitrage/execution/executor.py` PnL 계산 함수 추적
   - Quantity 설정 확인 (config/paper/topn_arb_baseline.yaml)
   - 단위 테스트 3개 작성 + 100% PASS

2. **Threshold 재보정** (STEP 4)
   - `zone_profiles_v2.yaml` BTC threshold → 5.0 bps
   - 20m Smoke 실행 (trade > 0 확인)
   - 60m Base 실행 (ge_rate ≥ 3% 목표)

3. **문서 정리** (STEP 5)
   - DOCS_DEDUP_PLAN.md 실행
   - 중복/레거시 문서 제거

4. **Git 커밋 + Push** (STEP 6)
   - 대용량 파일 제외
   - 원격 동기화

---

## 📌 주의사항

**ROADMAP이 SSOT입니다.**
- 향후 D92-2는 RiskGuard 통합 (Zone-aware 리스크 한도)
- 향후 D92-3는 Auto-Tuning Pipeline (Best Profile 자동 선정)
- D92-1 작업은 이 인덱스 기준으로 문서화 완료

**레거시 커밋 라벨 해석:**
- `[D92-2]`, `[D92-3]` 커밋은 모두 D92-1의 하위 작업
- Git 히스토리는 보존 (커밋 메시지 변경 없음)
- 문서 체계만 ROADMAP에 일치

---

**작성자:** Windsurf AI  
**버전:** 1.0 (ROADMAP SSOT 원칙 적용)  
**상태:** ✅ 정합성 복구 완료
