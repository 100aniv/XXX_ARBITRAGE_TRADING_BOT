---
description: Welding audit report (non-SSOT)
---

# Welding Audit (Non-SSOT)

Date: 2026-02-17  
Scope: PnL/Friction/Quality calculation path audit for V2 engine

## 1) Single Truth Module

Canonical module:
- `arbitrage/v2/domain/pnl_calculator.py`

Canonical APIs:
- `calculate_execution_friction_from_results(...)`
- `calculate_net_pnl_full_welded(...)`

## 2) Duplicate Implementation Findings and Action

1. Inline friction helpers in orchestrator
   - File: `arbitrage/v2/core/orchestrator.py`
   - Previous issue: local helper implementations for slippage/latency/partial/reject
   - Action: removed local math and routed to canonical API

2. Test-local copied formulas
   - File: `tests/test_d_alpha_1u_fix_2_latency_cost_decomposition.py`
   - Previous issue: copied slippage/latency helper formulas
   - Action: test now calls canonical API directly

## 3) Current Call Path

- Runtime:
  - `PaperOrchestrator.run()`
    -> `calculate_execution_friction_from_results(...)`
    -> `calculate_net_pnl_full_welded(...)`
- Regression tests:
  - `tests/test_d_alpha_1u_fix_2_latency_cost_decomposition.py`
  - `tests/test_d_alpha_3_pnl_welded.py`

## 4) Enforcement Guard

Guard script:
- `scripts/check_no_duplicate_pnl.py`

Gate integration:
- `scripts/run_gate_with_evidence.py` preflight executes:
  - `python scripts/check_no_duplicate_pnl.py`

Fail condition:
- local helper redefinition of friction math outside `pnl_calculator.py`

## 5) Audit Result

Status: PASS  
Result: one welding truth path is active in runtime and tests.
