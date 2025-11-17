# PROJECT STRUCTURE AUDIT – D39/D40

## Repo Tree

```text
PROJECT TREE (D39/D40 CHECKPOINT)
.
├── README.md
├── requirements.txt
├── arbitrage/
│   ├── __init__.py
│   ├── arbitrage_backtest.py
│   ├── arbitrage_core.py
│   ├── arbitrage_tuning.py
│   ├── tuning_session.py
│   ├── tuning_aggregate.py
│   ├── tuning_session_runner.py
│   ├── k8s_alerts.py
│   ├── k8s_apply.py
│   ├── k8s_events.py
│   ├── k8s_executor.py
│   ├── k8s_health.py
│   ├── k8s_history.py
│   ├── k8s_monitor.py
│   ├── k8s_orchestrator.py
│   ├── k8s_pipeline.py
│   └── ... (other historical engine & infra modules)
├── scripts/
│   ├── run_arbitrage_backtest.py
│   ├── run_arbitrage_tuning.py
│   ├── plan_tuning_session.py
│   ├── aggregate_tuning_results.py
│   ├── run_tuning_session_local.py
│   ├── run_k8s_tuning_pipeline.py
│   ├── gen_d29_k8s_jobs.py
│   └── ... (additional operational scripts)
├── docs/
│   ├── D37_ARBITRAGE_MVP.md
│   ├── D37_FINAL_REPORT.md
│   ├── D38_ARBITRAGE_TUNING_JOB.md
│   ├── D38_FINAL_REPORT.md
│   ├── D39_TUNING_SESSION_PLANNER.md
│   ├── D39_TUNING_AGGREGATION.md
│   ├── D39_FINAL_REPORT.md
│   ├── D40_TUNING_SESSION_LOCAL_RUNNER.md
│   ├── D40_FINAL_REPORT.md
│   └── ... (earlier phase docs)
├── tests/
│   ├── test_d37_arbitrage_mvp.py
│   ├── test_d38_arbitrage_tuning.py
│   ├── test_d39_tuning_session.py
│   ├── test_d40_tuning_session_runner.py
│   └── ... (legacy regression tests)
└── configs/
    ├── d17_scenarios/
    │   ├── basic_spread_win.yaml
    │   ├── choppy_market.yaml
    │   └── stop_loss_trigger.yaml
    ├── d23_tuning/
    │   └── advanced_baseline.yaml
    ├── d28_orchestrator/
    │   └── demo_baseline.yaml
    └── d29_k8s/
        └── orchestrator_k8s_baseline.yaml
```

## Packages & Responsibilities

### `arbitrage/`
- `arbitrage_core.py` – Core arbitrage engine: order book snapshot ingestion, opportunity detection, trade simulation.
- `arbitrage_backtest.py` – Offline backtest runner and result aggregation for strategy validation.
- `arbitrage_tuning.py` – Single tuning job runner producing metrics JSON (D38).
- `tuning_session.py` – Session planner producing cartesian job plans (D39).
- `tuning_aggregate.py` – Result loader/aggregator summarising tuning outputs (D39).
- `tuning_session_runner.py` – Local executor orchestrating multiple tuning jobs (D40).
- `k8s_*.py` – Read-only Kubernetes orchestration, monitoring, alerting, and history modules (D29–D36).
- Other historical modules (execution, monitoring, risk, etc.) remain from earlier milestones but are orthogonal to D37–D40.

### `scripts/`
- `run_arbitrage_backtest.py` – CLI wrapper around core backtesting (D37).
- `run_arbitrage_tuning.py` – Executes a single tuning job via CLI (D38).
- `plan_tuning_session.py` – Generates JSONL job plans from session specs (D39).
- `aggregate_tuning_results.py` – Aggregates tuning metrics into ranked summaries (D39).
- `run_tuning_session_local.py` – Runs a session plan on the local machine (D40).
- `run_k8s_tuning_pipeline.py`, `gen_d29_k8s_jobs.py`, `validate_k8s_jobs.py`, etc. – K8s orchestration tooling (D29–D36).
- Remaining scripts surface historical functionality (live trading, monitoring, diagnostics) without embedding business logic.

### `docs/`
- `D37_ARBITRAGE_MVP.md`, `D37_FINAL_REPORT.md` – Documentation for core MVP.
- `D38_ARBITRAGE_TUNING_JOB.md`, `D38_FINAL_REPORT.md` – Single tuning job runner reference.
- `D39_TUNING_SESSION_PLANNER.md`, `D39_TUNING_AGGREGATION.md`, `D39_FINAL_REPORT.md` – Session planning & aggregation docs.
- `D40_TUNING_SESSION_LOCAL_RUNNER.md`, `D40_FINAL_REPORT.md` – Local tuning session executor documentation.
- Extensive legacy docs remain for earlier phases.

### `tests/`
- `test_d37_arbitrage_mvp.py` – Covers core engine & backtest (D37).
- `test_d38_arbitrage_tuning.py` – Validates single tuning job runner (D38).
- `test_d39_tuning_session.py` – Exercises planner and aggregator plus safety checks (D39).
- `test_d40_tuning_session_runner.py` – Validates local session runner & CLI (D40).
- Additional regression suites for prior domains (D8–D36).

### `configs/`
- Scenario YAMLs for backtests (D17) and tuning baselines (D23, D28, D29) used by planners and orchestrators.

## D16–D40 Feature Map

| D-step | Feature | Main modules | Main scripts | Main tests |
|--------|---------|--------------|--------------|------------|
| D29 | K8s Orchestrator | `arbitrage/k8s_orchestrator.py` | `scripts/run_k8s_tuning_pipeline.py`, `scripts/gen_d29_k8s_jobs.py` | `tests/test_d29_k8s_orchestrator.py` |
| D30 | K8s Executor | `arbitrage/k8s_executor.py` | `scripts/run_k8s_tuning_pipeline.py` | `tests/test_d30_k8s_executor.py` |
| D31 | K8s Apply Layer | `arbitrage/k8s_apply.py` | `scripts/apply_k8s_jobs.py` | `tests/test_d31_k8s_apply.py` |
| D32 | K8s Monitor | `arbitrage/k8s_monitor.py` | `scripts/watch_k8s_jobs.py`, `scripts/show_k8s_health_history.py` | `tests/test_d32_k8s_monitor.py` |
| D33 | K8s Health | `arbitrage/k8s_health.py` | `scripts/check_k8s_health.py`, `scripts/record_k8s_health.py` | `tests/test_d33_k8s_health.py` |
| D34 | K8s Events & History | `arbitrage/k8s_events.py`, `arbitrage/k8s_history.py` | `scripts/show_k8s_health_history.py` | `tests/test_d34_k8s_history.py` |
| D35 | K8s Alerts | `arbitrage/k8s_alerts.py` | `scripts/send_k8s_alerts.py` | `tests/test_d35_k8s_alerts.py` |
| D36 | K8s Tuning Pipeline | `arbitrage/k8s_pipeline.py` | `scripts/run_k8s_tuning_pipeline.py` | `tests/test_d36_k8s_pipeline.py` |
| D37 | Arbitrage MVP | `arbitrage/arbitrage_core.py`, `arbitrage/arbitrage_backtest.py` | `scripts/run_arbitrage_backtest.py` | `tests/test_d37_arbitrage_mvp.py` |
| D38 | Tuning Job Runner | `arbitrage/arbitrage_tuning.py` | `scripts/run_arbitrage_tuning.py` | `tests/test_d38_arbitrage_tuning.py` |
| D39 | Session Planner & Aggregator | `arbitrage/tuning_session.py`, `arbitrage/tuning_aggregate.py` | `scripts/plan_tuning_session.py`, `scripts/aggregate_tuning_results.py` | `tests/test_d39_tuning_session.py` |
| D40 | Local Session Runner | `arbitrage/tuning_session_runner.py` | `scripts/run_tuning_session_local.py` | `tests/test_d40_tuning_session_runner.py` |

## Dependency & Safety Checks

- **Import direction:** Reviewed `arbitrage/` modules for `scripts` imports; none found. Scripts depend on `arbitrage`, maintaining a one-way boundary.
- **Banned/sensitive imports:** Project-wide search located `requests` usage only in legacy live modules (`arbitrage/collectors.py`, `arbitrage/binance_live.py`, etc.) outside D37–D40 scope. No banned imports appear in D37–D40 modules.
- **K8s boundary:** Only `k8s_*.py` modules and associated scripts reference Kubernetes or `kubectl`. Core/tuning modules (`arbitrage_core.py`, `arbitrage_tuning.py`, `tuning_session*.py`, `tuning_aggregate.py`) remain free of K8s logic.
- **Offline guarantee (D37–D39):** Confirmed that `arbitrage/arbitrage_core.py`, `arbitrage/arbitrage_backtest.py`, `arbitrage/arbitrage_tuning.py`, `arbitrage/tuning_session.py`, and `arbitrage/tuning_aggregate.py` rely solely on the standard library and local project modules—no network clients or external services.

## Test Suite Snapshot

- **Command:** `python -m pytest tests/test_d16_safety.py tests/test_d16_state_manager.py tests/test_d16_types.py tests/test_d17_paper_engine.py tests/test_d17_simulated_exchange.py tests/test_d19_live_mode.py tests/test_d20_live_arm.py tests/test_d21_state_manager_redis.py tests/test_d23_advanced_tuning.py tests/test_d24_tuning_session.py tests/test_d25_tuning_integration.py tests/test_d26_parallel_and_distributed.py tests/test_d27_monitoring.py tests/test_d28_orchestrator.py tests/test_d29_k8s_orchestrator.py tests/test_d30_k8s_executor.py tests/test_d31_k8s_apply.py tests/test_d32_k8s_monitor.py tests/test_d33_k8s_health.py tests/test_d34_k8s_history.py tests/test_d35_k8s_alerts.py tests/test_d36_k8s_pipeline.py tests/test_d37_arbitrage_mvp.py tests/test_d38_arbitrage_tuning.py tests/test_d39_tuning_session.py tests/test_d40_tuning_session_runner.py --tb=line -q`
- **Result:** 494 tests passed (31 D40 tests included). No flaky behavior observed; warnings limited to known `datetime.utcnow` deprecation notices.
