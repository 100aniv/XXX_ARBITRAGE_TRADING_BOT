---
description: Engine-centric purge audit report (non-SSOT)
---

# Engine-Centric Purge Audit (Non-SSOT)

Date: 2026-02-17  
Scope: `scripts/` + `arbitrage/v2/harness/`

## 1) Classification Rules

- A (Entrypoint-only OK): import + CLI handoff + no core business loop
- B (Contains business logic): metrics/decision math/loop orchestration/validation logic

## 2) Harness Inventory

| file | class | status |
|---|---|---|
| `arbitrage/v2/harness/__init__.py` | A | OK |
| `arbitrage/v2/harness/d205_10_1_wait_harness.py` | A | OK |
| `arbitrage/v2/harness/wait_harness_v2.py` | A | OK |
| `arbitrage/v2/harness/topn_stress.py` | A | thin wrapper -> `arbitrage/v2/tools/topn_stress.py` |
| `arbitrage/v2/harness/paper_runner_thin.py` | A | OK |
| `arbitrage/v2/harness/paper_runner.py` | B | backlog |
| `arbitrage/v2/harness/paper_chain.py` | B | backlog |
| `arbitrage/v2/harness/smoke_runner.py` | B | backlog |

## 3) Script Inventory (High-impact run scripts)

| file | class | status |
|---|---|---|
| `scripts/run_d205_8_topn_stress.py` | A | thin wrapper -> `arbitrage/v2/tools/topn_stress.py` |
| `scripts/run_d205_10_1_sweep.py` | A | thin wrapper -> `arbitrage/v2/tools/d205_10_1_sweep.py` |
| `scripts/run_d206_1_profit_proof_matrix.py` | A | thin wrapper -> `arbitrage/v2/tools/profit_proof_matrix.py` |
| `scripts/run_gate_with_evidence.py` | A | gate wrapper + preflight checks |

## 4) Completed Move in This Turn

Moved business logic into engine-owned tools:
- `arbitrage/v2/tools/topn_stress.py`
- `arbitrage/v2/tools/d205_10_1_sweep.py`
- `arbitrage/v2/tools/profit_proof_matrix.py`

Compatibility wrappers kept:
- `arbitrage/v2/core/topn_stress.py`
- `arbitrage/v2/core/d205_10_1_sweep.py`

Thin wrappers now:
- `arbitrage/v2/harness/topn_stress.py`
- `scripts/run_d205_8_topn_stress.py`
- `scripts/run_d205_10_1_sweep.py`
- `scripts/run_d206_1_profit_proof_matrix.py`

## 5) Enforcement Guard

Guard script:
- `scripts/check_engine_centricity.py`

Gate integration:
- `scripts/run_gate_with_evidence.py` preflight executes:
  - `python scripts/check_engine_centricity.py`

Policy now enforced:
- required wrapper files must stay thin
- changed files under `scripts/` or `arbitrage/v2/harness/` fail if non-thin and not allowlisted
- core/domain modules cannot reverse-import `arbitrage.v2.harness` or `scripts`

## 6) Next Backlog Targets

1. `arbitrage/v2/harness/paper_runner.py`
2. `arbitrage/v2/harness/paper_chain.py`
3. `arbitrage/v2/harness/smoke_runner.py`
