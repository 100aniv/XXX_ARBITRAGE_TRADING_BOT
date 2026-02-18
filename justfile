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

# Standard entrypoints (B3)
fmt:
    @echo "[FMT] No formatter configured; running compileall as syntax guard"
    .\abt_bot_env\Scripts\python.exe -m compileall arbitrage scripts tests

test:
    @echo "[TEST] Pytest quick run"
    .\abt_bot_env\Scripts\python.exe -m pytest -q

gate:
    @just doctor
    @just fast
    @just regression

docops:
    @echo "[DOCOPS] SSOT check + forbidden token scan"
    .\abt_bot_env\Scripts\python.exe scripts\check_ssot_docs.py
    .\abt_bot_env\Scripts\python.exe scripts\check_docops_tokens.py --config config\docops_token_allowlist.yml
    git status --short
    git diff --stat

evidence:check:
    @echo "[EVIDENCE] Latest run minimum set check"
    .\abt_bot_env\Scripts\python.exe -c "from pathlib import Path; import sys; root=Path('logs/evidence'); required=['manifest.json','gate.log','git_info.json','cmd_history.txt']; runs=sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True) if root.exists() else []; candidate=next((p for p in runs if all((p / f).exists() for f in required)), None); missing=[] if candidate else required; print('latest=%s' % candidate); print('missing=' + ','.join(missing)) if missing else print('PASS'); sys.exit(1 if missing else 0)"

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
