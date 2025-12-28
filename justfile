# Arbitrage-Lite SSOT Workflow (D106-3)
# Python: 3.13.11, venv: abt_bot_env

# Default: show available commands
default:
    @just --list

# [GATE 1] Doctor: Syntax/import checks only (fast, no test execution)
doctor:
    @echo "[GATE 1/3] Doctor: Syntax + Import checks"
    .\abt_bot_env\Scripts\python.exe -m pytest tests/ --collect-only -q

# [GATE 2] Fast: Core critical tests (~5-10s, no ML/Live/API)
fast:
    @echo "[GATE 2/3] Fast: Core tests (no ML/Live/API dependencies)"
    .\abt_bot_env\Scripts\python.exe -m pytest -m "not optional_ml and not optional_live and not live_api and not fx_api" -x --tb=short -v

# [GATE 3] Regression: Full test suite (excluding live API calls)
regression:
    @echo "[GATE 3/3] Regression: Full suite (no live API)"
    .\abt_bot_env\Scripts\python.exe -m pytest -m "not live_api and not fx_api" --tb=short -v

# Clean: Remove cache and temporary files
clean:
    @echo "Cleaning cache and temporary files"
    -Remove-Item -Recurse -Force .pytest_cache, __pycache__, *.pyc, .coverage
    @echo "Clean complete"

# Preflight: D106 Live environment check (7/7 PASS target)
preflight:
    @echo "[D106] Live Preflight Check"
    .\abt_bot_env\Scripts\python.exe scripts\d106_0_live_preflight.py

# Install: Install dependencies from requirements.txt
install:
    @echo "Installing dependencies"
    .\abt_bot_env\Scripts\pip.exe install -r requirements.txt
    @echo "Install complete"
