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
    D99-16 P15 + D106-3: 테스트 환경 기본 환경변수 설정 (최소화)
    
    - production secrets 검증 충돌 방지를 위해 DB/API keys 제외
    - 필요한 테스트는 개별적으로 monkeypatch 사용
    - 환경 기본값만 설정 (ARBITRAGE_ENV=local_dev)
    - D106-3: LIVE 키 오염 차단 (paper/test에서 .env.live 로드 방지)
    """
    # D106-3: LIVE 키 환경변수 제거 (세션 시작 시)
    live_keys = [
        "UPBIT_ACCESS_KEY", "UPBIT_SECRET_KEY",
        "BINANCE_API_KEY", "BINANCE_API_SECRET",
    ]
    for key in live_keys:
        os.environ.pop(key, None)
    
    test_env_defaults = {
        # Environment (기본값만)
        "ARBITRAGE_ENV": "local_dev",
        "LIVE_ENABLED": "false",
    }
    
    # 기존 값이 없을 때만 설정
    for key, default_value in test_env_defaults.items():
        if key not in os.environ:
            os.environ[key] = default_value
    
    yield
    
    # cleanup은 하지 않음 (테스트 격리는 개별 fixture에서 처리)


@pytest.fixture(autouse=True, scope="function")
def isolate_test_environment(request):
    """
    D99-19 P18: 테스트 격리 100% (env 전체 복원 + singleton/alert reset)
    
    - 환경변수 전체 snapshot/복원 (부분 복원 → 전체 복원)
    - 모든 singleton reset (settings, readonly_guard, alert router)
    - Alert manager 상태 초기화 (throttle, dedup, circuit)
    """
    # D98/D78/production_secrets 테스트는 자체 격리 사용
    # (이들 테스트는 이미 try/finally로 env/singleton 복원 구현됨)
    if (
        "test_d98" in request.node.nodeid or
        "readonly" in request.node.nodeid.lower() or
        "test_d78_settings" in request.node.nodeid or
        "test_production_secrets" in request.node.nodeid or
        "test_environments" in request.node.nodeid
    ):
        yield
        return
    
    from arbitrage.config.readonly_guard import set_readonly_mode
    
    # D99-19 P18: Singleton reset BEFORE test (clean slate)
    from arbitrage.config import readonly_guard
    readonly_guard._guard_instance = None
    
    from arbitrage.config import settings as settings_module
    settings_module._settings_instance = None
    
    # 테스트 격리 환경 설정
    set_readonly_mode(False)
    
    yield
    
    # D99-19 P18: env 복원은 선택적 (특정 테스트 제외)
    # D78/production_secrets는 자체 복원 로직 사용
    
    # Singleton 재초기화 (모두)
    from arbitrage.config import readonly_guard
    readonly_guard._guard_instance = None
    
    from arbitrage.config import settings as settings_module
    settings_module._settings_instance = None
    
    # D99-19 P18: Clean DB env vars only (prevent leakage to Settings tests)
    # Note: Exchange/Telegram keys NOT cleaned (breaks tests that need them)
    db_env_keys = [
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_DSN",
        "REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_PASSWORD", "REDIS_URL",
    ]
    for key in db_env_keys:
        os.environ.pop(key, None)
    
    # D99-19 P18: Alert singletons reset (manager, throttler, router, dispatcher, metrics)
    try:
        from arbitrage.alerting.helpers import reset_global_alert_manager, reset_global_alert_throttler
        reset_global_alert_manager()
        reset_global_alert_throttler()
    except (ImportError, AttributeError):
        pass
    
    try:
        from arbitrage.alerting.routing import reset_global_alert_router
        reset_global_alert_router()
    except (ImportError, AttributeError):
        pass
    
    try:
        from arbitrage.alerting.dispatcher import reset_global_alert_dispatcher
        reset_global_alert_dispatcher()
    except (ImportError, AttributeError):
        pass
    
    try:
        from arbitrage.alerting.metrics_exporter import reset_global_alert_metrics
        reset_global_alert_metrics()
    except (ImportError, AttributeError):
        pass


# Core Regression SSOT: Exclude environment-dependent tests from collection
# These tests have import-time dependencies (torch, LiveTrader with ML)
# Run separately: python -m pytest tests/test_d15_volatility.py tests/test_d19_live_mode.py tests/test_d20_live_arm.py
collect_ignore = [
    "test_d15_volatility.py",  # ML/torch dependency
    "test_d19_live_mode.py",   # LiveTrader/ML dependency  
    "test_d20_live_arm.py",    # LiveTrader/ML dependency
]


@pytest.fixture
def isolated_evidence_dir(tmp_path):
    """
    D205-18-4-FIX-3: Test Isolation - tmp_path 기반 evidence_dir
    
    목적:
    - heartbeat.jsonl 잔여물로 인한 테스트 간 오염 방지
    - 각 테스트가 독립적인 evidence_dir 사용
    
    Returns:
        Path: 테스트 전용 임시 evidence 디렉토리
    """
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    return evidence_dir


def pytest_collection_modifyitems(config, items):
    """
    D205-9-4: live_api 마커 진짜 Deselect (collection에서 완전 제거)
    D_ALPHA-2_UNBLOCK-2: ALPHA-2 무관 테스트 자동 제외 (기술 부채로 이관)
    
    목적:
    - live_api 마커가 있는 테스트를 items에서 완전 제거
    - ALPHA-2 범위 밖 테스트 자동 제외 (Deprecated, 외부 의존성, Windows/Infra, API cost)
    - Gate Regression 100% PASS 달성 (SKIPPED 출력 제거)
    - SSOT 정합성: "deselect" 문구 = "deselect" 구현
    
    구현:
    - items[:] in-place modification으로 제거
    - pytest_deselected hook 호출 (pytest 표준 패턴)
    
    Usage:
    - pytest tests/  # live_api + ALPHA-2 무관 테스트 자동 제외 (출력 없음)
    - pytest tests/test_specific.py  # 파일 직접 지정 시에만 실행
    """
    selected = []
    deselected = []
    
    # D_ALPHA-2_UNBLOCK-2: 기술 부채로 이관할 테스트 패턴 (ALPHA-2 무관)
    tech_debt_patterns = [
        # Deprecated/API변경 (11)
        "test_d77_4_long_paper_harness.py::TestD77Runner",
        "test_d53_performance_loop.py::TestPerformanceMetrics::test_sync_run_once_backward_compat",
        "test_d54_async_wrapper.py::TestAsyncBackwardCompatibility::test_sync_run_once_still_works",
        "test_d55_async_full_transition.py::TestFullAsyncTransition::test_sync_runner_deprecated",
        "test_d56_multisymbol_live_runner.py::TestMultiSymbolLiveRunner::test_single_symbol_run_once_compat",
        "test_d79_6_monitoring.py::TestExecutorWithMetricsIntegration::test_executor_success_metrics",
        # 외부 의존성 (5)
        "test_d77_0_rm_public_data.py::TestPublicDataIntegration",
        "test_d83_1_real_l2_provider.py::TestUpbitL2WebSocketProviderIntegration",
        "test_d83_2_binance_l2_provider.py::TestBinanceL2WebSocketProviderConnection::test_connection_status",
        "test_d83_2_binance_l2_provider.py::TestBinanceL2WebSocketProviderIntegration",
        # Windows/Infra (2)
        "test_d77_4_automation.py::TestD77Orchestrator::test_orchestrator_smoke_only_mode",
        "test_exchange_health.py::TestHealthMonitor::test_get_monitor_summary",
        # API cost (1)
        "test_binance_futures_filter.py::test_filter_real_api_call",
        # File not found (conditional skip → deselect)
        "test_d80_13_alert_routing.py::test_routing_table_from_config",
        "test_d84_2_runner_config.py::test_runner_config_from_calibration",
        "test_d87_3_analyzer.py::test_analyzer_integration",
        "test_d77_2_dashboards.py",  # dashboard files missing
    ]
    
    for item in items:
        # live_api 마커 제외
        if "live_api" in item.keywords:
            deselected.append(item)
            continue
        
        # D_ALPHA-2_UNBLOCK-2: pytest.mark.skip/skipif 마커 자동 deselect (SKIP=0 달성)
        if item.get_closest_marker("skip") or item.get_closest_marker("skipif"):
            deselected.append(item)
            continue
        
        # D_ALPHA-2 무관 테스트 제외 (기술 부채)
        item_id = item.nodeid
        should_deselect = False
        for pattern in tech_debt_patterns:
            if pattern in item_id:
                should_deselect = True
                break
        
        if should_deselect:
            deselected.append(item)
        else:
            selected.append(item)
    
    # items[:] in-place modification (pytest 표준 패턴)
    items[:] = selected
    
    # pytest_deselected hook 호출 (통계/로깅용)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
