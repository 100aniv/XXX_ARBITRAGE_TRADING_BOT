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


@pytest.fixture(autouse=True, scope="session")
def setup_test_environment_variables():
    """
    D99-16 P15: 테스트 환경 기본 환경변수 설정 (최소화)
    
    - production secrets 검증 충돌 방지를 위해 DB/API keys 제외
    - 필요한 테스트는 개별적으로 monkeypatch 사용
    - 환경 기본값만 설정 (ARBITRAGE_ENV=local_dev)
    """
    test_env_defaults = {
        # Environment (기본값만)
        "ARBITRAGE_ENV": "local_dev",
    }
    
    # 기존 값이 없을 때만 설정
    for key, default_value in test_env_defaults.items():
        if key not in os.environ:
            os.environ[key] = default_value
    
    yield
    
    # cleanup은 하지 않음 (테스트 격리는 개별 fixture에서 처리)


@pytest.fixture(autouse=True, scope="function")
def disable_readonly_guard_for_tests(request):
    """
    D98-1/D99-15 P14: 테스트 환경에서 ReadOnlyGuard 비활성화 (기본값)
    
    - 기존 테스트 호환성 보장
    - D98 테스트는 SKIP (자체적으로 set_readonly_mode 호출)
    - D99-15 P14: Singleton reset 추가 (캐시된 상태 무효화)
    """
    # D99-15 P14: Skip for D98 readonly tests (they control their own state)
    if "test_d98" in request.node.nodeid or "readonly" in request.node.nodeid.lower():
        # D98 tests manage their own READ_ONLY state
        yield
        return
    
    from arbitrage.config.readonly_guard import set_readonly_mode
    
    original_value = os.environ.get("READ_ONLY_ENFORCED")
    
    # 테스트 시작 시 READ_ONLY_ENFORCED=false 설정 + singleton reset
    set_readonly_mode(False)
    
    yield
    
    # 테스트 종료 후 원래 값 복원
    if original_value is not None:
        os.environ["READ_ONLY_ENFORCED"] = original_value
    else:
        os.environ.pop("READ_ONLY_ENFORCED", None)
    
    # Singleton 재초기화
    from arbitrage.config import readonly_guard
    readonly_guard._guard_instance = None


# Core Regression SSOT: Exclude environment-dependent tests from collection
# These tests have import-time dependencies (torch, LiveTrader with ML)
# Run separately: python -m pytest tests/test_d15_volatility.py tests/test_d19_live_mode.py tests/test_d20_live_arm.py
collect_ignore = [
    "test_d15_volatility.py",  # ML/torch dependency
    "test_d19_live_mode.py",   # LiveTrader/ML dependency  
    "test_d20_live_arm.py",    # LiveTrader/ML dependency
]
