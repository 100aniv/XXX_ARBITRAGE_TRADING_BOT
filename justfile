set shell := ["powershell.exe", "-NoProfile", "-Command"]

# SSOT: Core Regression (44 tests) - D92 정의
# 근거: docs/D92/D92_CORE_REGRESSION_DEFINITION.md
# Python: .venv\Scripts\python.exe (abt_bot_env)

doctor:
    @echo "=== doctor: Pre-flight checks ==="
    @python --version
    @python -c "import sys; print('Python:', sys.executable)"
    @python -c "import pytest; print('pytest: OK')"
    @git status --short
    @echo "=== doctor: PASS ==="

fast:
    @echo "=== fast: Core Regression SSOT (44 tests) ==="
    python -m pytest tests/test_d27_monitoring.py tests/test_d82_0_runner_executor_integration.py tests/test_d82_2_hybrid_mode.py tests/test_d92_1_fix_zone_profile_integration.py tests/test_d92_7_3_zone_profile_ssot.py --import-mode=importlib -v --tb=short

regression:
    @echo "=== regression: Core Regression SSOT (44 tests) ==="
    python -m pytest tests/test_d27_monitoring.py tests/test_d82_0_runner_executor_integration.py tests/test_d82_2_hybrid_mode.py tests/test_d92_1_fix_zone_profile_integration.py tests/test_d92_7_3_zone_profile_ssot.py --import-mode=importlib -v --tb=short

full:
    @echo "=== full: DEBT/OPTIONAL (not SSOT) ==="
    @echo "Use: python -m pytest -q"

help:
    @echo "SSOT Gate Runner (D92 Core Regression 44 tests)"
    @echo ""
    @echo "Recipes:"
    @echo "  just doctor      - Pre-flight checks (python, pytest, git)"
    @echo "  just fast        - Core Regression SSOT (44 tests)"
    @echo "  just regression  - Core Regression SSOT (44 tests, same as fast)"
    @echo "  just full        - DEBT/OPTIONAL (not SSOT)"
    @echo ""
    @echo "Watchdog (file change auto-rerun):"
    @echo "  .\scripts\watchdog.ps1 fast"
    @echo "  .\scripts\watchdog.ps1 regression"
