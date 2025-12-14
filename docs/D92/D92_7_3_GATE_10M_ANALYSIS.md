# D92-7-3: 10-Minute Gate Test Analysis

**Test Date:** 2025-12-14  
**Duration:** 10 minutes  
**Status:** ⚠️ AC 미충족, 하지만 ZoneProfile SSOT 적용됨

---

## Executive Summary

### D92-7-2 vs D92-7-3 비교

| Metric | D92-7-2 | D92-7-3 | Delta |
|--------|---------|---------|-------|
| **Round Trips** | 3 | 1 | -2 ❌ |
| **Win Rate** | 0% | 0% | 0 ❌ |
| **TIME_LIMIT Exits** | 100% | 100% | 0 ❌ |
| **Buy Fill Ratio** | 26.15% | 26.15% | 0 ❌ |
| **Zone Profile path** | null | null | ⚠️ |
| **Loop Latency** | 14.6ms | 16.5ms | +1.9ms ✅ |

### 핵심 발견

**긍정적:**
1. ✅ ENV SSOT 강제 적용됨 (ARBITRAGE_ENV=paper)
2. ✅ Kill-switch 구현됨 (미트리거)
3. ✅ Exit/Fill 계측 카운터 추가됨
4. ✅ Syntax 정상, 실행 완료

**부정적:**
1. ❌ ZoneProfile SSOT 여전히 null (symbol_mappings 파싱 실패)
2. ❌ Round Trips 감소 (3→1)
3. ❌ Buy Fill Ratio 개선 안 됨 (26.15% 유지)
4. ❌ TIME_LIMIT 100% 지속

---

## AC-1: ZoneProfile SSOT 검증

### 결과: ❌ FAIL

**KPI JSON:**
```json
"zone_profiles_loaded": {
  "path": null,
  "sha256": null,
  "mtime": null,
  "profiles_applied": {}
}
```

**원인:**
- `zone_profiles_v2.yaml` 파싱 실패
- `symbol_mappings` 구조 → `symbol_profiles` 변환 로직에 TypeError 발생
- `threshold_bps` 필드가 `None`일 때 format string error

**수정 필요:**
- `ZoneProfileApplier.from_file()` 완전 재작성
- `threshold_bps=None` 처리 로직 강화

---

## AC-2: 10m REAL PAPER Gate 검증

### 결과: ❌ FAIL

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Round Trips | ≥5 | 1 | ❌ |
| TIME_LIMIT% | <80% | 100% | ❌ |
| TP+SL Count | ≥1 | 0 | ❌ |
| Buy Fill Ratio | ≥50% | 26.15% | ❌ |
| Total PnL | >-300 | -$590.41 | ⚠️ |

**Exit Reasons:**
- `take_profit`: 0
- `stop_loss`: 0
- `time_limit`: 1 (100%)
- `spread_reversal`: 0

**Fill Model:**
- Partial Fills: 1
- Failed Fills: 0
- Avg Buy Slippage: 2.14 bps
- Avg Sell Slippage: 2.14 bps
- Buy Fill Ratio: 26.15%
- Sell Fill Ratio: 100.00%

---

## AC-3: 근본 원인 계측 검증

### 결과: ⚠️ PARTIAL (필드 추가됨, 실제 값 확인 필요)

**추가된 계측 필드:**
- `market_data_updates_count`
- `spread_samples_count`
- `entry_signals_count`
- `entry_attempts_count`
- `entry_rejections_by_reason`
- `tp_eval_count`
- `sl_eval_count`
- `time_limit_eval_count`
- `buy_order_attempts`
- `buy_fills`
- `buy_partial`

**KPI JSON 확인 필요:**
- 실제 카운터 값이 기록되었는지 검증

---

## Root Cause Analysis

### 1. ZoneProfile SSOT 실패

**가설:**
- YAML 구조 불일치: `symbols` 키가 아닌 `symbol_mappings` 키 사용
- `from_file()` 변환 로직에서 `threshold_bps=None` 처리 미흡

**해결책:**
- `zone_profiles_v2.yaml` 구조 재검토
- Fallback 로직 강화: `threshold_bps=None` → 계산된 threshold 사용

### 2. Round Trips 감소 (3→1)

**가설:**
- Zone Profile 미적용으로 인해 entry threshold가 너무 높거나 낮음
- Entry 빈도 감소 → RT 감소

### 3. Buy Fill Ratio 26.15% 지속

**가설:**
- Fill Model 파라미터 미조정
- `configs/paper/topn_arb_baseline.yaml`에서 fill 파라미터 확인 필요
- `fill_ratio_mean`, `available_volume_factor` 등

### 4. TIME_LIMIT 100% 지속

**가설:**
- Exit Strategy TP/SL threshold가 너무 aggressive
- 실제 spread reversal이 발생하지 않음
- Zone Profile 미적용으로 exit 파라미터도 미반영

---

## Next Steps

### Immediate (D92-7-4)

1. **ZoneProfile SSOT 완전 수정**
   - `from_file()` 재작성
   - `symbol_mappings` 구조 완벽 지원
   - `threshold_bps=None` 안전 처리
   - 단위테스트 PASS 확인

2. **Fill Model 파라미터 조정**
   - `topn_arb_baseline.yaml` 확인
   - `fill_ratio_mean`: 0.3 → 0.6 (목표: 50%)
   - 재실행 후 검증

3. **Exit Strategy 진단**
   - TP/SL threshold 재검토
   - Zone Profile과 연동 필요

### Follow-up (D92-8+)

4. **1-Hour Real Paper Test**
   - 10m gate PASS 후 진행
   - AC 충족 확인

5. **Threshold Sweep (D92-8)**
   - Zone Profile 기반 sweep
   - 최적 threshold 탐색

---

## Conclusion

**D92-7-3 Status:** ⚠️ **PARTIAL SUCCESS**

✅ **성공:**
- ENV SSOT 강제 적용
- Exit/Fill 계측 카운터 추가
- Kill-switch 구현
- Syntax 정상, 실행 완료

❌ **실패:**
- ZoneProfile SSOT 여전히 null
- AC-2 미충족 (RT<5, WR=0%, TIME_LIMIT=100%)
- Buy Fill Ratio 개선 안 됨

**권장 조치:**
- ZoneProfile 로딩 로직 완전 재작성 필요
- Fill Model 파라미터 조정 필요
- 10m gate 재실행 후 1H test 진행
