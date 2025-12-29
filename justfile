# Arbitrage-Lite SSOT Workflow (D106-3)
# Python: 3.13.11, venv: abt_bot_env
# Evidence: logs/evidence/<run_id>/ (자동 생성)

# Default: show available commands
default:
    @just --list

# [GATE 1] Doctor: Syntax/import checks only (fast, no test execution)
doctor:
    @echo "[GATE 1/3] Doctor: Syntax + Import checks"
    @echo "[Evidence] Starting doctor gate..."
    .\abt_bot_env\Scripts\python.exe -c "from tools.evidence_pack import EvidencePacker; packer = EvidencePacker('d200-3', 'doctor gate'); packer.start(); packer.add_command('doctor', 'pytest --collect-only', 'IN_PROGRESS')" 2>nul || true
    .\abt_bot_env\Scripts\python.exe -m pytest tests/ --collect-only -q
    @echo "[Evidence] doctor gate completed"

# [GATE 2] Fast: Core critical tests (~5-10s, no ML/Live/API)
fast:
    @echo "[GATE 2/3] Fast: Core tests (no ML/Live/API dependencies)"
    @echo "[Evidence] Starting fast gate..."
    .\abt_bot_env\Scripts\python.exe -c "from tools.evidence_pack import EvidencePacker; packer = EvidencePacker('d200-3', 'fast gate'); packer.start(); packer.add_command('fast', 'pytest -m not optional_ml...', 'IN_PROGRESS')" 2>nul || true
    .\abt_bot_env\Scripts\python.exe -m pytest -m "not optional_ml and not optional_live and not live_api and not fx_api" -x --tb=short -v
    @echo "[Evidence] fast gate completed"

# [GATE 3] Regression: Full test suite (excluding live API calls)
regression:
    @echo "[GATE 3/3] Regression: Full suite (no live API)"
    @echo "[Evidence] Starting regression gate..."
    .\abt_bot_env\Scripts\python.exe -c "from tools.evidence_pack import EvidencePacker; packer = EvidencePacker('d200-3', 'regression gate'); packer.start(); packer.add_command('regression', 'pytest -m not live_api...', 'IN_PROGRESS')" 2>nul || true
    .\abt_bot_env\Scripts\python.exe -m pytest -m "not live_api and not fx_api" --tb=short -v
    @echo "[Evidence] regression gate completed"

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
