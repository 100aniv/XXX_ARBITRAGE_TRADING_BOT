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
    D99-6: 테스트 환경 기본 환경변수 설정
    
    - Production config 테스트 시 필요한 환경변수 기본값 제공
    - 실제 값은 .env 파일이나 CI/CD에서 오버라이드
    """
    test_env_defaults = {
        # PostgreSQL (Docker 기본값)
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "arbitrage",
        "POSTGRES_USER": "arbitrage",
        "POSTGRES_PASSWORD": "arbitrage",
        
        # Redis (Docker 기본값)
        "REDIS_HOST": "localhost",
        "REDIS_PORT": "6380",
        "REDIS_DB": "0",
        "REDIS_PASSWORD": "",  # D99-10: Redis password (empty for local dev)
        
        # API Keys (테스트용 placeholder)
        "UPBIT_ACCESS_KEY": "test_upbit_key",
        "UPBIT_SECRET_KEY": "test_upbit_secret",
        "BINANCE_API_KEY": "test_binance_key",
        "BINANCE_SECRET_KEY": "test_binance_secret",
        
        # Telegram (테스트용)
        "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "TELEGRAM_CHAT_ID": "-1001234567890",
        
        # Environment
        "ARBITRAGE_ENV": "local_dev",
    }
    
    # 기존 값이 없을 때만 설정 (오버라이드 방지)
    for key, default_value in test_env_defaults.items():
        if key not in os.environ:
            os.environ[key] = default_value
    
    yield
    
    # cleanup은 하지 않음 (테스트 격리는 개별 fixture에서 처리)


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
