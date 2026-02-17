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
| `arbitrage/v2/harness/topn_stress.py` | A | moved to core wrapper |
| `arbitrage/v2/harness/paper_runner_thin.py` | A | OK |
| `arbitrage/v2/harness/paper_runner.py` | B | backlog |
| `arbitrage/v2/harness/paper_chain.py` | B | backlog |
| `arbitrage/v2/harness/smoke_runner.py` | B | backlog |

## 3) Script Inventory (High-impact run scripts)

| file | class | status |
|---|---|---|
| `scripts/run_d205_8_topn_stress.py` | A | moved to core wrapper |
| `scripts/run_d206_1_profit_proof_matrix.py` | B | backlog |
| `scripts/run_gate_with_evidence.py` | A | gate wrapper + preflight checks |

## 4) Completed Move in This Turn

Moved business logic into core:
- `arbitrage/v2/core/topn_stress.py` (new)

Thin wrappers now:
- `arbitrage/v2/harness/topn_stress.py`
- `scripts/run_d205_8_topn_stress.py`

## 5) Enforcement Guard

Guard script:
- `scripts/check_engine_centricity.py`

Gate integration:
- `scripts/run_gate_with_evidence.py` preflight executes:
  - `python scripts/check_engine_centricity.py`

Policy now enforced:
- required wrapper files must stay thin
- changed files under `scripts/` or `arbitrage/v2/harness/` fail if non-thin and not allowlisted

## 6) Next Backlog Targets

1. `arbitrage/v2/harness/paper_runner.py`
2. `arbitrage/v2/harness/paper_chain.py`
3. `arbitrage/v2/harness/smoke_runner.py`
4. `scripts/run_d206_1_profit_proof_matrix.py`
