# SSOT: Dev Workflow Gate 3단 + doctor (사전진단)
# 근거: pytest.ini (Core Regression), D_ROADMAP.md (M1~M2 SSOT)
# Python 러너: python -m pytest (Windows)
# 주의: just/watchexec이 PATH에 없으면 scripts/run_gate.py 또는 PowerShell 직접 실행 사용

# 이 justfile은 "의도 선언" 역할
# 실제 실행은:
#   - PowerShell: python -m pytest -m "not optional_ml and not optional_live" -q
#   - Python: python scripts/run_gate.py doctor|fast|regression|full
#   - Watchdog: .\scripts\watchdog.ps1 fast|regression|full

# 참고: just가 설치되지 않으면 아래 명령을 직접 PowerShell에서 실행하세요:
#   python -m pytest -m "not optional_ml and not optional_live" -q  # fast/regression
#   python -m pytest -q                                              # full
