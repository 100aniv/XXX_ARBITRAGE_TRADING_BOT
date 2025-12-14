# D92-7-2: 10-Minute Gate Test Analysis

**Test Date:** 2025-12-14  
**Duration:** 10 minutes (600 seconds)  
**Status:** ✅ Zero Trades 문제 해결, ⚠️ 새로운 문제 발견

---

## Executive Summary

### Zero Trades 문제 해결 ✅
- **D92-7 (이전):** 0 trades → Zero Trades 문제
- **D92-7-2 (현재):** 7 entry trades, 3 exits → **문제 해결됨**

### 발견된 새로운 문제 ⚠️
1. **0% WinRate:** 3개 round trips 모두 손실
2. **100% TIME_LIMIT 종료:** TP/SL 없음, 시간 초과로만 종료
3. **Partial Fills 문제:** Avg Buy Fill Ratio=26.15% (매우 낮음)
4. **큰 손실:** Total PnL (KRW): -2,111,888원

---

## Trade Activity

| Metric | Value | Status |
|--------|-------|--------|
| **Entry Trades** | 7 | ✅ |
| **Exit Trades** | 3 | ⚠️ (4개 미청산) |
| **Round Trips Completed** | 3 | ❌ (< 5 target) |
| **Wins** | 0 | ❌ |
| **Losses** | 3 | ❌ |
| **Win Rate** | 0.0% | ❌ (< 50% target) |

### Exit Reasons Breakdown
```
take_profit:      0 (0%)
stop_loss:        0 (0%)
time_limit:       3 (100%)  ⚠️ 모두 시간 초과
spread_reversal:  0 (0%)
```

**분석:**
- TP/SL 로직이 전혀 작동하지 않음
- 모든 포지션이 180초 time_limit에 도달하여 강제 종료
- 시장 조건이 좋지 않거나 exit threshold 설정 문제 가능성

---

## PnL Analysis

| Currency | Value | Status |
|----------|-------|--------|
| **Total PnL (USD)** | -$1,624.53 | ❌ |
| **Total PnL (KRW)** | -₩2,111,888 | ❌ |
| **FX Rate** | 1300.0 | - |

**분석:**
- 평균 loss per round trip: $541.51
- 매우 큰 손실 → Fill Model, Slippage, 또는 Spread 계산 문제 가능성

---

## Fill Model Performance (D82-0)

| Metric | Value | Status |
|--------|-------|--------|
| **Partial Fills Count** | 4 | ⚠️ |
| **Failed Fills Count** | 0 | ✅ |
| **Avg Buy Slippage** | 2.14 bps | ✅ |
| **Avg Sell Slippage** | 2.14 bps | ✅ |
| **Avg Buy Fill Ratio** | 26.15% | ❌ (매우 낮음) |
| **Avg Sell Fill Ratio** | 100.00% | ✅ |

**Critical Issue: Buy Fill Ratio 26.15%**
- 매수 주문의 73.85%가 체결 실패
- 실제 entry size가 의도보다 훨씬 작음
- Position 크기 불균형 → PnL 왜곡 가능성

**원인 가능성:**
1. Fill Model 파라미터 (fill_ratio_mean) 너무 낮게 설정
2. Orderbook depth가 실제로 얕음
3. Mock Fill Model과 실제 시장 괴리

---

## Performance Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Loop Latency (avg)** | 14.6ms | < 80ms | ✅ |
| **Loop Latency (p99)** | 21.2ms | < 100ms | ✅ |
| **Memory Usage** | 150.0MB | < 200MB | ✅ |
| **CPU Usage** | 35.0% | < 80% | ✅ |
| **Iterations** | 392 | - | ✅ |

**분석:**
- 성능 지표는 모두 우수
- Loop latency 목표 달성
- 시스템 안정성 확인

---

## Zero-Trades RootCause Telemetry (D92-7-2)

### 계측 필드 확인 필요
다음 필드가 KPI JSON에 포함되어 있는지 확인:
- `market_data_updates_count`
- `spread_samples_count`
- `entry_signals_count`
- `entry_attempts_count`
- `entry_rejections_by_reason`
- `exceptions_count`
- `last_exception_summary`

**[KPI JSON 분석 대기 중...]**

---

## Zone Profiles Application (D92-5)

### Zone Profile 로드 증거
```json
"zone_profiles_loaded": {
  "path": "arbitrage/config/zone_profiles_v2.yaml",
  "sha256": "[SHA-256 hash]",
  "mtime": [timestamp],
  "profiles_applied": {
    "BTC": "profile_name",
    "ETH": "profile_name",
    ...
  }
}
```

**[KPI JSON에서 확인 필요]**

---

## Acceptance Criteria (topn_research Profile)

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| **Round Trips** | ≥ 5 | 3 | ❌ FAIL |
| **Win Rate** | ≥ 50% | 0.0% | ❌ FAIL |
| **Loop Latency** | < 80ms | 14.6ms | ✅ PASS |

**Result:** ❌ **SOME ACCEPTANCE CRITERIA FAILED**

---

## Root Cause Analysis

### Zero Trades 문제 (해결됨) ✅
**이전 상태 (D92-7):**
- 0 trades, 0 entry, 0 exit

**현재 상태 (D92-7-2):**
- 7 entry trades, 3 exits
- **원인 해결:** Zone Profile 또는 ENV 설정 문제였을 가능성

### 새로운 문제: 0% WinRate & 100% TIME_LIMIT

**가설 1: Fill Ratio 불균형**
- Buy Fill Ratio=26.15% → 의도보다 작은 position
- 실제 손실 크기가 왜곡되었을 가능성
- Fill Model 파라미터 재조정 필요

**가설 2: Exit Threshold 설정 문제**
- TP/SL threshold가 너무 aggressive
- 실제 spread reversal이 발생하지 않음
- Time limit (180s)만 트리거됨

**가설 3: Entry Threshold 문제**
- Zone Profile threshold가 너무 낮음
- 부실한 기회에 진입
- Entry quality 검증 필요

**가설 4: Spread Calculation 오류**
- Entry/Exit spread 계산 로직 버그 가능성
- TopNProvider spread 데이터 품질 문제

---

## Next Steps

### Immediate Actions
1. ✅ **ZeroTrades 계측 필드 확인**
   - KPI JSON에서 telemetry 데이터 추출
   - entry_rejections_by_reason 분석

2. **Fill Model 진단**
   - Fill Ratio 파라미터 검토 (`configs/paper/topn_arb_baseline.yaml`)
   - Buy Fill Ratio 26.15% 원인 규명

3. **Exit Strategy 진단**
   - TP/SL threshold 설정 확인
   - Exit 로직 로그 분석 (trade_log.jsonl)

4. **Trade Log 분석**
   - `logs/d77-0/d77-0-top10-20251214_122830/trades/...` 확인
   - Entry/Exit spread, PnL 상세 분석

### Follow-up Actions
5. **1-Hour Real Paper Test (STEP 6)**
   - 10m gate test 실패로 인해 1H test 보류 권장
   - Fill Model/Exit Strategy 수정 후 재시도

6. **Documentation Update (STEP 6)**
   - D92-7-2 Implementation Summary 업데이트
   - Zero Trades 해결 방법 문서화
   - 새로운 문제 (Fill Ratio, WinRate) 문서화

7. **Git Commit (STEP 7)**
   - Code changes (settings.py, run_d77_0)
   - Documentation (CONTEXT_SCAN, IMPLEMENTATION_SUMMARY, GATE_10M_ANALYSIS)
   - Exclude logs, KPI JSON

---

## Conclusion

**D92-7-2 Mission Accomplished (Partial):**
✅ **Zero Trades 문제 해결** - 이전 0 trades → 현재 7 entry, 3 exits

**New Challenges Discovered:**
❌ **0% WinRate** - 모든 round trips 손실  
❌ **100% TIME_LIMIT exits** - TP/SL 미작동  
❌ **26.15% Buy Fill Ratio** - Partial fills 문제

**Recommendation:**
- 1-Hour test 보류
- Fill Model + Exit Strategy 재조정 필요
- 수정 후 10m gate test 재실행 권장
