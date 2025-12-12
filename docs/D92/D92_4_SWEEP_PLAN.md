# D92-4 Parameter Sweep Plan

**Execution Date:** 2025-12-12 20:35 KST  
**Estimated Duration:** 3.5 hours (210 minutes)  
**Session Mode:** Non-interactive (원샷)

---

## 🎯 Objective

**Goal:** Determine optimal entry threshold for BTC/KRW advisory mode through controlled parameter sweep.

**Candidates:** 3 threshold values (5.0, 4.8, 4.5 bps)

**Methodology:** Zone 2 boundary adjustment to achieve target thresholds via midpoint calculation.

---

## 📋 Sweep Configuration

### Candidate 1: Threshold = 5.0 bps
```yaml
zone_boundaries:
- [2.0, 4.0]   # Z1
- [4.0, 6.0]   # Z2 → midpoint = 5.0 bps
- [6.0, 10.0]  # Z3
- [10.0, 20.0] # Z4
```

### Candidate 2: Threshold = 4.8 bps
```yaml
zone_boundaries:
- [2.0, 4.0]   # Z1
- [4.0, 5.6]   # Z2 → midpoint = 4.8 bps
- [5.6, 10.0]  # Z3
- [10.0, 20.0] # Z4
```

### Candidate 3: Threshold = 4.5 bps
```yaml
zone_boundaries:
- [2.0, 4.0]   # Z1
- [4.0, 5.0]   # Z2 → midpoint = 4.5 bps
- [5.0, 10.0]  # Z3
- [10.0, 20.0] # Z4
```

---

## 🔬 Execution Protocol

### Each Candidate: 70 minutes total

1. **YAML Update:** Modify `config/arbitrage/zone_profiles_v2.yaml` BTC zone_boundaries
2. **Verification:** Re-read file + python import check
3. **Unit Tests:** `pytest tests/test_d92_4_pnl_currency.py tests/test_d92_1_pnl_validation.py` (must be 14/14 PASS)
4. **10m Smoke Test:**
   - Command: `python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 10 --mode advisory`
   - Monitor: ZONE_THRESHOLD log confirmation, Entry count ≥ 1
5. **60m Base Run:**
   - Command: `python scripts/run_d92_1_topn_longrun.py --top-n 10 --duration-minutes 60 --mode advisory`
   - Monitor: 5-min status updates (RT/Entry/Exit/PnL)

---

## ✅ Acceptance Criteria (per candidate)

### AC-1: Threshold Confirmation
- `[ZONE_THRESHOLD] BTC/KRW (BTC): X.XX bps (Zone Profile)` matches target
- Logged within first 30 seconds of run

### AC-2: Smoke Test Success
- Duration: 10 minutes ± 5 seconds
- Entry trades: ≥ 1
- No crashes or exceptions
- Log file saved with unique run_id

### AC-3: Base Run Completion
- Duration: 60 minutes ± 10 seconds
- Round trips: ≥ 0 (may be zero in low-volatility)
- Final metrics JSON saved
- PnL reported in both USD and KRW

### AC-4: Data Isolation
- Each run has unique `run_id` timestamp
- Logs saved to separate directories
- No file overwrites between candidates

---

## 📊 KPI Collection

**Per Candidate:**
- Total runtime (seconds)
- Entry count
- Exit count
- Round trips completed
- Win rate (%)
- Total PnL (USD with FX=1300)
- Total PnL (KRW raw)
- Exit reason distribution (take_profit, stop_loss, time_limit, spread_reversal)
- ge_rate: % of spread checks ≥ threshold
- Avg spread (bps)
- P50/P90 spread (bps)

**Sources:**
- `logs/d92-1/{run_id}/d92_1_summary.json`
- `logs/d77-0/{session_id}_kpi_summary.json`
- `logs/d92-2/{session_id}/d92_2_spread_report.json`

---

## 🕐 Timeline

| Start | End | Duration | Activity |
|-------|-----|----------|----------|
| T+0m | T+5m | 5m | STEP 2: Plan documentation |
| T+5m | T+15m | 10m | Candidate 1: 10m smoke |
| T+15m | T+75m | 60m | Candidate 1: 60m base |
| T+75m | T+85m | 10m | Candidate 2: 10m smoke |
| T+85m | T+145m | 60m | Candidate 2: 60m base |
| T+145m | T+155m | 10m | Candidate 3: 10m smoke |
| T+155m | T+215m | 60m | Candidate 3: 60m base |
| T+215m | T+230m | 15m | STEP 4: Analysis + commit |

**Total:** 230 minutes (3h 50m with buffer)

---

## 🚨 Failure Handling

**Smoke Test Failure (Entry = 0):**
- Log as "Threshold too aggressive for current market"
- Continue to base run but flag result as "inconclusive"

**Base Run Crash:**
- Capture exception log
- Mark candidate as "failed"
- Continue to next candidate

**File Overwrite:**
- **Prevention:** Use timestamp-based run_id
- **Detection:** Check log directory before each run

---

## 📝 Output Deliverables

1. **Comparison Report:** `docs/D92/D92_4_SWEEP_RESULTS.md`
   - 3-column table: Threshold | RT | Entry | PnL (USD/KRW) | ge_rate
   - Winner selection criteria
   - Next steps recommendation

2. **ROADMAP Update:** `D_ROADMAP.md`
   - D92-4 status: COMPLETED
   - Selected threshold documented
   - D92-5 next action defined

3. **Git Commit:**
   - Message: `[D92-4] Parameter Sweep 완료 (T=5.0/4.8/4.5 bps) + 최적 threshold 선정`
   - Modified: `config/arbitrage/zone_profiles_v2.yaml`, `D_ROADMAP.md`, docs
   - Added: `docs/D92/D92_4_SWEEP_RESULTS.md`

---

**Start Time:** 2025-12-12 20:35 KST  
**Expected End:** 2025-12-13 00:25 KST  
**Status:** READY TO EXECUTE
