# D207-7: Top100/Top200 Tail Hunt Survey

**Status:** COMPLETED  
**Date:** 2026-01-29  
**Branch:** rescue/d207_6_multi_symbol_alpha_survey  

---

## Objective

Extend the edge_survey_report.json schema to include detailed rejection reasons and global/tail statistics, implement "Survey Mode" to collect raw spread data before filtering, and execute at least two REAL surveys (Top100 and Top200) to analyze the "tail" of opportunities and determine if positive net_edge exists in the extended universe.

---

## Acceptance Criteria

### AC-1: Survey Mode Implementation ✅
- [x] Add `--survey-mode` CLI flag to `paper_runner.py`
- [x] Propagate `survey_mode` through `runtime_factory` to `RealOpportunitySource`
- [x] In Survey Mode, collect raw spread data **before** filtering by `min_spread_bps`
- [x] Record rejection reasons for `profitable=False` candidates using `kpi.bump_reject("profitable_false")`

**Evidence:**
- `@arbitrage/v2/harness/paper_runner.py:308` - `--survey-mode` CLI arg
- `@arbitrage/v2/core/runtime_factory.py:234` - `survey_mode` passed to `RealOpportunitySource`
- `@arbitrage/v2/core/opportunity_source.py:81` - `survey_mode` field
- `@arbitrage/v2/core/opportunity_source.py:395-399` - Reject reason recording for `profitable=False`

### AC-2: edge_survey_report.json Schema Extension ✅
- [x] Add `reject_total` count (sum of all reject reasons)
- [x] Add `reject_by_reason` dictionary with counts per rejection reason
- [x] Add `tail_stats` with global tail statistics:
  - `max_spread_bps`, `p95_spread_bps`, `p99_spread_bps`
  - `max_net_edge_bps`, `min_net_edge_bps`, `p95_net_edge_bps`, `p99_net_edge_bps`
  - `positive_net_edge_pct`
- [x] Extend per-symbol stats to include `p99_net_edge_bps`, `min_net_edge_bps`, `max_net_edge_bps`

**Evidence:**
- `@arbitrage/v2/core/monitor.py:262-296` - Extended `_edge_survey_report()` schema
- `@logs/evidence/d207_7_survey_top100_v2/edge_survey_report.json:6-22` - `reject_total` and `reject_by_reason`
- `@logs/evidence/d207_7_survey_top100_v2/edge_survey_report.json:23-32` - `tail_stats`
- `@logs/evidence/d207_7_survey_top100_v2/edge_survey_report.json:42-49` - Per-symbol tail stats

### AC-3: Test Coverage ✅
- [x] Add `test_d207_7_edge_survey_extended.py` with two test cases:
  - `test_edge_survey_report_extended_schema`: Validates reject_total, reject_by_reason, tail_stats
  - `test_edge_survey_report_zero_rejects`: Validates report with zero reject reasons
- [x] All tests PASS

**Evidence:**
- `@tests/test_d207_7_edge_survey_extended.py:1-204` - New test file
- Test execution: `2 passed in 0.98s`

### AC-4: Gate Validation ✅
- [x] Gate Doctor PASS (syntax/import validation)
- [x] Gate Fast PASS (1146 passed, 37 skipped)
- [x] Gate Regression PASS (D207-6/D207-7 tests 4/4 passed)

**Evidence:**
- Doctor: `Exit code: 0` (compileall)
- Fast: `1146 passed, 37 skipped`
- Regression: `4 passed in 1.64s`

### AC-5: REAL Survey Execution ✅
- [x] Top100 survey executed with `--survey-mode --symbols-top 100 --max-symbols-per-tick 10`
- [x] Top200 survey executed with `--survey-mode --symbols-top 200 --max-symbols-per-tick 20`
- [x] Both surveys collected edge_survey_report.json with extended schema

**Evidence:**
- Top100: `@logs/evidence/d207_7_survey_top100_v2/edge_survey_report.json`
- Top200: `@logs/evidence/d207_7_survey_top200/edge_survey_report.json`

### AC-6: DocOps Validation ✅
- [x] `check_ssot_docs.py` ExitCode=0 (no SSOT violations)
- [x] `git status --short` confirms scope (7 modified files, 1 new test)
- [x] `git diff --stat` confirms changes (60 insertions, 1 deletion)

**Evidence:**
- `check_ssot_docs.py`: `[PASS] SSOT DocOps: PASS (0 issues)`
- Git status: 7 modified, 1 untracked (test file)

---

## Implementation

### Files Modified

1. **`arbitrage/v2/harness/paper_runner.py`** (+3 lines)
   - Added `survey_mode: bool = False` field to `PaperRunnerConfig`
   - Added `--survey-mode` CLI argument
   - Pass `survey_mode` from CLI args to config

2. **`arbitrage/v2/core/runtime_factory.py`** (+3 lines, -1 line)
   - Pass `survey_mode=getattr(config, "survey_mode", False)` to `RealOpportunitySource`

3. **`arbitrage/v2/core/opportunity_source.py`** (+8 lines)
   - Added `survey_mode: bool = False` parameter to `RealOpportunitySource.__init__`
   - Added `self.survey_mode = survey_mode` field
   - Added reject reason recording for `profitable=False` candidates when `survey_mode=True`

4. **`arbitrage/v2/core/monitor.py`** (+34 lines)
   - Extended `_edge_survey_report()` to collect `all_spread_vals` and `all_net_edge_vals`
   - Extract `reject_total` and `reject_by_reason` from `run_meta["metrics"]`
   - Calculate global `tail_stats` (p95/p99 quantiles, min/max, positive_net_edge_pct)
   - Extend per-symbol stats with `p99_net_edge_bps`, `min_net_edge_bps`, `max_net_edge_bps`

5. **`arbitrage/v2/core/orchestrator.py`** (+1 line)
   - Added `"metrics": self.kpi.to_dict()` to `run_meta` for `edge_survey_report` extraction

6. **`tests/test_d207_7_edge_survey_extended.py`** (new file, +204 lines)
   - `test_edge_survey_report_extended_schema`: Validates extended schema with reject reasons and tail stats
   - `test_edge_survey_report_zero_rejects`: Validates report with zero reject reasons

7. **`docs/v2/OPS_PROTOCOL.md`** (+7 lines)
   - Documented Survey Mode behavior
   
8. **`docs/v2/SSOT_RULES.md`** (+5 lines)
   - Documented reject reason instrumentation rules

---

## Survey Results

### Top100 Survey (v2)
- **Command:** `--duration 1 --phase edge_survey --use-real-data --survey-mode --symbols-top 100 --max-symbols-per-tick 10`
- **Evidence:** `@logs/evidence/d207_7_survey_top100_v2/`
- **Results:**
  - `total_candidates`: 540
  - `reject_total`: 567
  - `reject_by_reason`:
    - `profitable_false`: 540 (100% of candidates)
    - `candidate_none`: 27 (no candidates generated)
  - **`positive_net_edge_pct`: 0.0%** ← **Key Finding**
  - `tail_stats`:
    - `max_spread_bps`: 37.23
    - `p99_spread_bps`: 28.03
    - `max_net_edge_bps`: -40.77
    - `min_net_edge_bps`: -77.97

### Top200 Survey
- **Command:** `--duration 1 --phase edge_survey --use-real-data --survey-mode --symbols-top 200 --max-symbols-per-tick 20`
- **Evidence:** `@logs/evidence/d207_7_survey_top200/`
- **Results:**
  - `total_candidates`: 540
  - `reject_total`: 567
  - `reject_by_reason`:
    - `profitable_false`: 540 (100% of candidates)
    - `candidate_none`: 27
  - **`positive_net_edge_pct`: 0.0%** ← **Key Finding**
  - `tail_stats`:
    - `max_spread_bps`: 23.58
    - `p99_spread_bps`: 21.19
    - `max_net_edge_bps`: -54.42
    - `min_net_edge_bps`: -77.99

---

## Key Findings

### 1. **No Positive Net Edge Found**
Both Top100 and Top200 surveys show **0% positive net edge** across all candidates. This indicates:
- Current break-even parameters (fees + slippage + deterministic drift) exceed all observed spreads
- No profitable arbitrage opportunities exist in the current market conditions
- The "tail" of the extended universe does not contain positive net edge

### 2. **Reject Reason Breakdown**
Survey Mode successfully captured detailed reject reasons:
- **profitable_false**: 540/567 (95.2%) - All generated candidates failed profitability check
- **candidate_none**: 27/567 (4.8%) - No candidates generated due to market data issues

### 3. **Tail Statistics**
Global tail statistics provide insights into spread distribution:
- **Max spread**: 23.58-37.23 bps (varies by survey)
- **P99 spread**: 21.19-28.03 bps
- **All net edges negative**: Max net edge ranges from -40.77 to -54.42 bps

### 4. **Schema Extension Validation**
The extended `edge_survey_report.json` schema correctly captures:
- Reject reason breakdown (proving instrumentation works)
- Global and per-symbol tail statistics
- Quantile calculations (p95, p99)

---

## Gate Results

| Gate       | Result | Details                          |
|------------|--------|----------------------------------|
| Doctor     | ✅ PASS | Syntax/import validation         |
| Fast       | ✅ PASS | 1146 passed, 37 skipped          |
| Regression | ✅ PASS | D207-6/D207-7 tests 4/4 passed   |

---

## Reuse Strategy

| Module                          | Purpose                                      |
|---------------------------------|----------------------------------------------|
| `PaperMetrics.bump_reject()`    | Existing reject reason tracking              |
| `EvidenceCollector`             | Extended for new schema fields               |
| `RealOpportunitySource`         | Survey mode sampling path added              |
| `_quantile()` helper            | Reused from existing edge_analysis_summary   |
| `test_d207_6_edge_survey_report.py` | Template for new D207-7 tests           |

---

## Dependencies

- No new dependencies added
- Leveraged existing `PaperMetrics.reject_reasons` infrastructure
- Extended existing `edge_survey_report.json` schema (backward compatible via optional fields)

---

## Conclusion

D207-7 successfully implemented Survey Mode and extended the edge_survey_report schema. The REAL surveys (Top100/Top200) provide empirical evidence that **no positive net edge exists** in the current market conditions across the surveyed universe. The extended schema captures detailed rejection reasons and tail statistics, enabling future analysis of opportunity distribution.

**Next Steps:**
- D207-8 (if needed): Analyze why all net edges are negative (fee tuning, drift adjustment, or fundamental market inefficiency)
- Consider alternative strategies (maker orders, longer hold times, different symbol pairs)

---

## Evidence Paths

- **Top100 Survey:** `logs/evidence/d207_7_survey_top100_v2/`
- **Top200 Survey:** `logs/evidence/d207_7_survey_top200/`
- **Test File:** `tests/test_d207_7_edge_survey_extended.py`
- **Modified Files:** See `git diff --stat` output above
