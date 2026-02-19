# Arbitrage-Lite SSOT Workflow (D106-3)
# Python: 3.x (system or venv)
# Evidence SSOT: docs/v2/design/EVIDENCE_FORMAT.md
# Evidence Path: logs/evidence/<run_id>/ (자동 생성)

# Default: show available commands
default:
    @just --list

# [GATE 1] Doctor: Syntax/import checks only (fast, no test execution)
# Evidence: logs/evidence/gate_doctor_<timestamp>_<hash>/
doctor:
    @echo "[GATE 1/3] Doctor: Syntax + Import checks"
    python3 scripts/run_gate_with_evidence.py doctor

# [GATE 2] Fast: Core critical tests (~5-10s, no ML/Live/API)
# Evidence: logs/evidence/gate_fast_<timestamp>_<hash>/
fast:
    @echo "[GATE 2/3] Fast: Core tests (no ML/Live/API dependencies)"
    python3 scripts/run_gate_with_evidence.py fast

# [GATE 3] Regression: Full test suite (excluding live API calls)
# Evidence: logs/evidence/gate_regression_<timestamp>_<hash>/
regression:
    @echo "[GATE 3/3] Regression: Full suite (no live API)"
    python3 scripts/run_gate_with_evidence.py regression

# Standard entrypoints (B3)
fmt:
    @echo "[FMT] No formatter configured; running compileall as syntax guard"
    python3 -m compileall arbitrage scripts tests

test:
    @echo "[TEST] Pytest quick run"
    python3 -m pytest -q

gate:
    @just doctor
    @just fast
    @just regression

docops:
    @echo "[DOCOPS] SSOT check + forbidden token scan"
    python3 scripts/check_ssot_docs.py
    python3 scripts/check_docops_tokens.py --config config/docops_token_allowlist.yml
    git status --short
    git diff --stat

evidence_check:
    @echo "[EVIDENCE] Latest run minimum set check"
    python3 -c "from pathlib import Path; import sys; root=Path('logs/evidence'); required=['manifest.json','gate.log','git_info.json','cmd_history.txt']; runs=sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []; candidate=next((p for p in runs if all((p / f).exists() for f in required)), None); missing=[] if candidate else required; print('latest=%s' % candidate); print('missing=' + ','.join(missing)) if missing else print('PASS'); sys.exit(1 if missing else 0)"

# Factory DRY-RUN (Controller -> Worker)
factory_dry container_mode="docker" network="docker_arbitrage-network" env_file=".env.factory.local" image="arbitrage-factory-worker:latest":
    @echo "[FACTORY] DRY-RUN supervisor (PLAN/DO/CHECK preview)"
    python3 ops/factory_supervisor.py --dry-run --container-mode {{container_mode}} --docker-network {{network}} --env-file {{env_file}} --docker-image {{image}}

# Factory Run (Bikit PLAN -> DO -> CHECK)
factory_run container_mode="docker" network="docker_arbitrage-network" env_file=".env.factory.local" image="arbitrage-factory-worker:latest":
    @echo "[FACTORY] RUN supervisor"
    python3 ops/factory_supervisor.py --container-mode {{container_mode}} --docker-network {{network}} --env-file {{env_file}} --docker-image {{image}}

# Clean: Remove cache and temporary files
clean:
    @echo "Cleaning cache and temporary files"
    rm -rf .pytest_cache __pycache__ .coverage
    find . -name "*.pyc" -delete
    @echo "Clean complete"

# Smart storage cleanup: logs retention + cache purge + large evidence summary
clean_all:
    @echo "[CLEANUP] Smart storage cleanup"
    python3 scripts/cleanup_storage.py

# Preflight: D106 Live environment check (7/7 PASS target)
preflight:
    @echo "[D106] Live Preflight Check"
    python3 scripts/d106_0_live_preflight.py

# Live Smoke: D107 1h LIVE Smoke Test (low-notional)
live-smoke:
    @echo "[D107] 1h LIVE Smoke Test (소액, 저위험)"
    python3 scripts/run_d107_live_smoke.py

# Install: Install dependencies from requirements.txt
install:
    @echo "Installing dependencies"
    python3 -m pip install -r requirements.txt
    @echo "Install complete"
