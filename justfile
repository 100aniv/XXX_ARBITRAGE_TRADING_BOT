# Arbitrage-Lite SSOT Workflow (D106-3)
# Python: 3.13.11, venv: abt_bot_env
# Evidence SSOT: docs/v2/design/EVIDENCE_FORMAT.md
# Evidence Path: logs/evidence/<run_id>/ (자동 생성)

# Default: show available commands
default:
    @just --list

# [GATE 1] Doctor: Syntax/import checks only (fast, no test execution)
# Evidence: logs/evidence/gate_doctor_<timestamp>_<hash>/
doctor:
    @echo "[GATE 1/3] Doctor: Syntax + Import checks"
    .\abt_bot_env\Scripts\python.exe scripts\run_gate_with_evidence.py doctor

# [GATE 2] Fast: Core critical tests (~5-10s, no ML/Live/API)
# Evidence: logs/evidence/gate_fast_<timestamp>_<hash>/
fast:
    @echo "[GATE 2/3] Fast: Core tests (no ML/Live/API dependencies)"
    .\abt_bot_env\Scripts\python.exe scripts\run_gate_with_evidence.py fast

# [GATE 3] Regression: Full test suite (excluding live API calls)
# Evidence: logs/evidence/gate_regression_<timestamp>_<hash>/
regression:
    @echo "[GATE 3/3] Regression: Full suite (no live API)"
    .\abt_bot_env\Scripts\python.exe scripts\run_gate_with_evidence.py regression

# Clean: Remove cache and temporary files
clean:
    @echo "Cleaning cache and temporary files"
    -Remove-Item -Recurse -Force .pytest_cache, __pycache__, *.pyc, .coverage
    @echo "Clean complete"

# Preflight: D106 Live environment check (7/7 PASS target)
preflight:
    @echo "[D106] Live Preflight Check"
    .\abt_bot_env\Scripts\python.exe scripts\d106_0_live_preflight.py

# Live Smoke: D107 1h LIVE Smoke Test (low-notional)
live-smoke:
    @echo "[D107] 1h LIVE Smoke Test (소액, 저위험)"
    .\abt_bot_env\Scripts\python.exe scripts\run_d107_live_smoke.py

# Install: Install dependencies from requirements.txt
install:
    @echo "Installing dependencies"
    .\abt_bot_env\Scripts\pip.exe install -r requirements.txt
    @echo "Install complete"
