# D82-9A: Real PAPER KPI Deepdive Analysis

**Generated:** 2025-12-05T20:52:14.231232

---

## D82-9 Real PAPER: 5-Candidate KPI Summary

| Entry (bps) | TP (bps) | Duration | RT | Wins | Losses | WR (%) | Total PnL (USD) | Avg PnL/RT | Exit: TP | Exit: Timeout |
|-------------|----------|----------|-----|------|--------|--------|-----------------|------------|----------|---------------|
| 10.0 | 13.0 | 10.0m | 2 | 0 | 2 | 0.0 | $-925.91 | $-462.95 | 0 | 2 |
| 10.0 | 14.0 | 10.0m | 2 | 0 | 2 | 0.0 | $-823.59 | $-411.79 | 0 | 2 |
| 10.0 | 15.0 | 10.0m | 2 | 0 | 2 | 0.0 | $-1036.68 | $-518.34 | 0 | 2 |
| 12.0 | 13.0 | 10.0m | 2 | 0 | 2 | 0.0 | $-850.11 | $-425.05 | 0 | 2 |
| 12.0 | 14.0 | 10.0m | 3 | 0 | 3 | 0.0 | $-2720.05 | $-906.68 | 0 | 3 |

### Fill Quality

| Entry (bps) | TP (bps) | Avg Buy Fill | Avg Sell Fill | Partial Fills | Failed Fills |
|-------------|----------|--------------|---------------|---------------|---------------|
| 10.0 | 13.0 | 26.15% | 100.00% | 3 | 0 |
| 10.0 | 14.0 | 26.15% | 100.00% | 2 | 0 |
| 10.0 | 15.0 | 26.15% | 100.00% | 3 | 0 |
| 12.0 | 13.0 | 26.15% | 100.00% | 3 | 0 |
| 12.0 | 14.0 | 26.15% | 100.00% | 4 | 0 |

### Slippage

| Entry (bps) | TP (bps) | Avg Buy Slip (bps) | Avg Sell Slip (bps) | Avg Slip (bps) |
|-------------|----------|--------------------|---------------------|----------------|
| 10.0 | 13.0 | 2.14 | 2.14 | 2.14 |
| 10.0 | 14.0 | 2.14 | 2.14 | 2.14 |
| 10.0 | 15.0 | 2.14 | 2.14 | 2.14 |
| 12.0 | 13.0 | 2.14 | 2.14 | 2.14 |
| 12.0 | 14.0 | 2.14 | 2.14 | 2.14 |

### Infrastructure

| Entry (bps) | TP (bps) | Latency Avg (ms) | Latency P99 (ms) | CPU (%) | Memory (MB) |
|-------------|----------|------------------|------------------|---------|-------------|
| 10.0 | 13.0 | 16.50 | 31.83 | 35.0 | 150.0 |
| 10.0 | 14.0 | 14.29 | 25.29 | 35.0 | 150.0 |
| 10.0 | 15.0 | 15.19 | 28.61 | 35.0 | 150.0 |
| 12.0 | 13.0 | 14.71 | 25.75 | 35.0 | 150.0 |
| 12.0 | 14.0 | 14.48 | 26.13 | 35.0 | 150.0 |

---

## Common Patterns & Root Causes

### Overall Statistics (n=5)

- **Average Round Trips:** 2.2
- **Average Win Rate:** 0.0%
- **Average PnL:** $-1271.27
- **Total TP Exits:** 0 / 11 (0.0%)
- **Total Timeout Exits:** 11 / 11 (100.0%)
- **Average Buy Fill Ratio:** 26.15%
- **Average Sell Fill Ratio:** 100.00%

### Key Findings

❌ **CRITICAL: 100% Loss Rate**
- All round trips resulted in losses
- 11/11 exits were due to time_limit (100.0%)
- **Root Cause:** TP thresholds (13-15 bps) are unreachable within 10-minute duration

❌ **CRITICAL: Low Buy Fill Ratio (26.15%)**
- Only ~26% of buy orders are filled
- **Root Cause:** Mock Fill Model with aggressive partial fill simulation
- **Impact:** Positions are undersized, limiting profit potential

❌ **CRITICAL: Negative PnL ($-1271.27 average)**
- All runs resulted in net losses
- **Root Cause:** Combination of:
  - TP unreachable → forced timeout exits at worse spreads
  - Slippage accumulation (~2.14 bps per side)
  - Partial fills reducing position sizes

⚠️ **WARNING: Low Round Trips (2.2 average)**
- Insufficient sample size for statistical significance
- **Root Cause:** 10-minute duration is too short
- **Recommendation:** Increase duration to 20+ minutes for at least 10 RT

---

## D77-4 / D82-8 / D82-9 Historical Comparison

### Execution Parameters

| Metric | D77-4 (Baseline) | D82-8 (Intermediate) | D82-9 (Fine-tuned) |
|--------|------------------|----------------------|--------------------|
| **Universe** | Top50 | Top20 | Top20 |
| **Duration** | 60 minutes | 20 minutes | 10 minutes |
| **Entry Threshold** | Default (~5-10 bps) | 10-14 bps | 10-12 bps |
| **TP Threshold** | Default (~5-10 bps) | 15-20 bps | 13-15 bps |
| **Data Source** | Real Market | Real Market | Real Market |
| **Validation Profile** | topn_research | topn_research | topn_research |
| **Fill Model** | Mock (D80-4) | Mock (D80-4) | Mock (D80-4) |

### Results Comparison

| Metric | D77-4 (Baseline) | D82-8 (Intermediate) | D82-9 (Fine-tuned) | D82-9 vs D77-4 |
|--------|------------------|----------------------|--------------------|----------------|
| **Total Entries** | ~1,656 entries | avg 6.7 entries | avg 3.0 entries | -99.8% |
| **Round Trips** | 1,656 RT | avg 6.0 RT | avg 2.2 RT | -99.9% |
| **Win Rate** | 100% | 0% | 0% | -100% |
| **Total PnL** | Positive | avg -$3,500 | avg -$1,271 | N/A |
| **Timeout Exits** | 0% | 100% | 100% | +100% |
| **TP Exits** | 100% | 0% | 0% | -100% |
| **Latency Avg** | ~15-20ms | 13-14ms | 14-16ms | Similar |
| **CPU Usage** | ~35% | 35% | 35% | Same |
| **Memory Usage** | ~150MB | 150MB | 150MB | Same |
| **Crash Count** | 0 | 0 | 0 | Same |

### Root Cause Analysis: Why D82-9 Failed vs D77-4 Success?

#### 1. **Threshold Configuration Mismatch**

**D77-4 (Success):**
- Entry: ~5-10 bps (default, permissive)
- TP: ~5-10 bps (default, achievable)
- **Result:** 100% TP exits, 1,656 RT, positive PnL

**D82-9 (Failure):**
- Entry: 10-12 bps (more conservative)
- TP: 13-15 bps (too aggressive)
- **Result:** 0% TP exits, 100% timeout, negative PnL

**Diagnosis:**
- D82-9's TP threshold (13-15 bps) is **2-3x higher** than D77-4's default (~5-10 bps)
- Current market volatility cannot reach 13-15 bps within 10-minute duration
- **Conclusion:** D82-9 threshold tuning **overcorrected** from D82-7/D82-8 failures

#### 2. **Mock Fill Model Impact**

**Buy Fill Ratio: 26.15%**
- Only 1/4 of buy orders are filled in D82-9
- This severely limits position sizes and profit potential
- **Comparison:** D77-4 likely had higher fill ratios (data not available)

**Slippage: 2.14 bps per side**
- Consistent across all D82-9 runs
- Total slippage: ~4.28 bps per round trip
- **Impact:** Slippage alone consumes 33-38% of TP target (13-15 bps)

**Root Cause:**
- Mock Fill Model (D80-4) may be **overly pessimistic**
- Real L2 Orderbook data needed for accurate fill/slippage estimation
- **Recommendation:** D83-x WebSocket L2 Orderbook integration is **critical**

#### 3. **Duration Insufficiency**

**D77-4:** 60 minutes → 1,656 RT (27.6 RT/min)
**D82-8:** 20 minutes → 6.0 RT (0.3 RT/min)
**D82-9:** 10 minutes → 2.2 RT (0.22 RT/min)

**Diagnosis:**
- D82-9 RT rate is **125x slower** than D77-4 (0.22 vs 27.6 RT/min)
- This indicates **threshold configuration problem**, not duration problem
- Even 60-minute duration would yield only ~13 RT at current rate

#### 4. **Exit Reason Pattern**

| Exit Reason | D77-4 | D82-8 | D82-9 |
|-------------|-------|-------|-------|
| Take Profit | 100% | 0% | 0% |
| Timeout | 0% | 100% | 100% |
| Stop Loss | 0% | 0% | 0% |
| Spread Reversal | 0% | 0% | 0% |

**Diagnosis:**
- D82-8 and D82-9 show **identical exit pattern** (100% timeout)
- TP threshold lowering (15-20 → 13-15 bps) had **zero impact**
- **Conclusion:** Current TP range (13-20 bps) is fundamentally unreachable

### Structural Issues Identified

#### Issue 1: Entry/Exit Logic Verification Needed

**Questions to investigate:**
1. Are entry spreads being calculated correctly?
   - Upbit bid vs Binance ask (or vice versa)
   - Currency conversion (KRW → USD)
2. Are TP spreads being checked correctly?
   - Spread direction (must reverse for profit)
   - Fee/slippage already deducted?
3. Are fees being double-counted?
   - Entry fee + Exit fee = ~0.2% (~20 bps)
   - This alone exceeds some TP targets

**Recommendation:**
- Audit `arbitrage/engine/topn_arbitrage_engine.py` entry/exit logic
- Add trade-level logging (TradeLogger activation)
- Verify 1-2 sample round trips manually

#### Issue 2: Mock Fill Model Pessimism

**Evidence:**
- Buy fill ratio: 26.15% (extremely low)
- Slippage: 2.14 bps (consistent, possibly overestimated)
- Comparison: D77-4 with same model likely had different parameters

**Recommendation:**
- Review `arbitrage/models/realistic_fill_model.py` configuration
- Compare D77-4 vs D82-9 fill model parameters
- Consider L2 Orderbook integration (D83-x) as **priority**

#### Issue 3: Threshold Range Calibration

**D82-7 Edge Analysis:**
- Minimum viable TP: 19 bps (for Edge > 0)
- D82-9 actual TP: 13-15 bps (below minimum)

**Contradiction:**
- D82-9 candidates were selected with Effective Edge > 0
- But Edge calculation may not account for:
  - Actual market dynamics
  - Mock Fill Model pessimism
  - Timeout opportunity cost

**Recommendation:**
- Re-calibrate Edge formula with real execution data
- Test with D77-4 default thresholds (~5-10 bps) first
- **Then** tune upward for better Edge, not downward

### Verdict: D82-9 vs D77-4

| Aspect | D77-4 | D82-9 | Status |
|--------|-------|-------|--------|
| **Infrastructure** | ✅ Stable | ✅ Stable | **PASS** |
| **Trade Activity** | ✅ 1,656 RT | ❌ 2.2 RT | **FAIL** |
| **Win Rate** | ✅ 100% | ❌ 0% | **FAIL** |
| **PnL** | ✅ Positive | ❌ Negative | **FAIL** |
| **Acceptance Criteria** | ✅ PASS | ❌ NO-GO | **FAIL** |

**Final Diagnosis:**

D82-9 failed not due to infrastructure issues, but due to **threshold configuration mismatch**:
1. Entry/TP thresholds are 2-3x higher than D77-4 baseline
2. Mock Fill Model may be overly pessimistic
3. TP targets (13-15 bps) are unreachable in current market regime
4. Duration (10min) is insufficient, but not the root cause

**Recommended Next Steps:**
1. **Immediate:** Re-run with D77-4 default thresholds (Entry ~5-10, TP ~5-10 bps)
2. **Short-term:** Integrate L2 Orderbook (D83-x) for realistic fill/slippage
3. **Medium-term:** Audit entry/exit logic for calculation errors
4. **Long-term:** Implement adaptive thresholds based on real-time market volatility

