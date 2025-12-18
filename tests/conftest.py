#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pytest configuration and fixtures

Path bootstrap: ensures imports work from any CWD

Core Regression SSOT:
- Core tests: always 100% PASS (no environment dependencies)
- Optional tests: ML/Live (environment-dependent, collected separately)

D98-1: ReadOnly Guard 테스트 격리
- 기본: READ_ONLY_ENFORCED=false (기존 테스트 호환)
- D98 테스트: 명시적 true 설정 (set_readonly_mode)
"""

import os
import sys
import pytest
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True, scope="function")
def disable_readonly_guard_for_tests():
    """
    D98-1: 테스트 환경에서 ReadOnlyGuard 비활성화 (기본값)
    
    - 기존 테스트 호환성 보장
    - D98 테스트는 set_readonly_mode(True)로 명시적 재설정
    """
    original_value = os.environ.get("READ_ONLY_ENFORCED")
    
    # 테스트 시작 시 READ_ONLY_ENFORCED=false 설정
    os.environ["READ_ONLY_ENFORCED"] = "false"
    
    yield
    
    # 테스트 종료 후 원래 값 복원
    if original_value is not None:
        os.environ["READ_ONLY_ENFORCED"] = original_value
    else:
        os.environ.pop("READ_ONLY_ENFORCED", None)


# Core Regression SSOT: Exclude environment-dependent tests from collection
# These tests have import-time dependencies (torch, LiveTrader with ML)
# Run separately: python -m pytest tests/test_d15_volatility.py tests/test_d19_live_mode.py tests/test_d20_live_arm.py
collect_ignore = [
    "test_d15_volatility.py",  # ML/torch dependency
    "test_d19_live_mode.py",   # LiveTrader/ML dependency  
    "test_d20_live_arm.py",    # LiveTrader/ML dependency
]
