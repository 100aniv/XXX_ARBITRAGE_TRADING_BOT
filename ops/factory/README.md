# Factory Setup (DRY-RUN)

## Purpose

This directory contains the minimum Controller/Worker skeleton for Prompt 3.
Only DRY-RUN behavior is implemented.

## Files

- `schema.py`: machine-readable plan/result schema helpers
- `controller.py`: selects one OPEN safety ticket from AC ledger and writes `logs/autopilot/plan.json`
- `worker.py`: runs local validation commands and writes `logs/autopilot/result.json`

## Command path

`just` recipe names cannot include `:` on this repository's justfile parser.
Equivalent mapping is provided:

- requested: `just factory:dry`
- actual: `just factory_dry`

- requested: `just factory:run`
- actual: `just factory_run`

## Execution

```powershell
just factory_dry
```

This performs:

1. `controller.py` -> create `logs/autopilot/plan.json`
2. `worker.py` -> run `just gate`, `just docops`, `just evidence_check`
3. create `logs/autopilot/result.json`

## Safety rule

- DRY-RUN only
- no modification of `arbitrage/v2/**`
- external integrations (Docker/Claude Code/Aider) are placeholders
