# SSOT: Dev Workflow Gate 3단 + doctor (사전진단)
# 근거: D92_CORE_REGRESSION_DEFINITION.md (44-test SSOT)
# Python 러너: python -m pytest (Windows, abt_bot_env 우선)
# Watchdog: watchexec 기반 (또는 scripts/watchdog.ps1 래퍼)

# Core Regression SSOT (D92 정의)
# - 타깃: 43-44개 테스트 (test_d27, test_d82_*, test_d92_*)
# - 기준: 100% PASS만 SSOT 인정
# - 명령: python -m pytest tests/test_d27_monitoring.py tests/test_d82_*.py tests/test_d92_*.py --import-mode=importlib -v --tb=short

# Fast/Regression = Core Regression SSOT (동일)
# Full = DEBT/OPTIONAL (필요 시 실행, SSOT 아님)

# 참고: just가 설치되지 않으면 아래 명령을 직접 PowerShell에서 실행하세요:
#   python -m pytest tests/test_d27_monitoring.py tests/test_d82_*.py tests/test_d92_*.py --import-mode=importlib -v --tb=short
