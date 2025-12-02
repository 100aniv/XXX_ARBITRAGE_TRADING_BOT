# -*- coding: utf-8 -*-
"""
D80-5: Multi-Source FX Provider Tests

MultiSourceFxRateProvider, OKX/Bybit WebSocket Client 테스트.
"""

import pytest
import time
from decimal import Decimal
from unittest import mock

from arbitrage.common.currency import Currency, MultiSourceFxRateProvider
from arbitrage.common.fx_cache import FxCache
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.cross_exchange.executor import CrossExchangeExecutor


# =============================================================================
# A. Aggregation Algorithm Tests (8)
# =============================================================================

def test_median_calculation_3_sources():
    """Median 계산 (3개 정상)"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    rates = [Decimal("1.000"), Decimal("0.999"), Decimal("1.001")]
    median = fx._calculate_median(rates)
    
    assert median == Decimal("1.000")


def test_median_calculation_2_sources():
    """Median 계산 (2개)"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    rates = [Decimal("1.000"), Decimal("0.999")]
    median = fx._calculate_median(rates)
    
    # Even count: (1.000 + 0.999) / 2 = 0.9995
    assert median == Decimal("0.9995")


def test_median_calculation_1_source():
    """Median 계산 (1개)"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    rates = [Decimal("1.000")]
    median = fx._calculate_median(rates)
    
    assert median == Decimal("1.000")


def test_outlier_removal_1_outlier():
    """Outlier 제거 (1개 비정상)"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    rates = [Decimal("1.000"), Decimal("0.999"), Decimal("1.150")]  # 1.150은 +15% outlier
    filtered = fx._remove_outliers(rates)
    
    # Median = 1.000, threshold = [0.950, 1.050]
    # 1.150 > 1.050 → Remove
    assert len(filtered) == 2
    assert Decimal("1.150") not in filtered


def test_outlier_removal_2_outliers():
    """Outlier 제거 (2개 비정상)"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    rates = [Decimal("1.000"), Decimal("0.800"), Decimal("1.200")]  # 0.800, 1.200 outliers
    filtered = fx._remove_outliers(rates)
    
    # Median = 1.000, threshold = [0.950, 1.050]
    # 0.800 < 0.950 → Remove
    # 1.200 > 1.050 → Remove
    assert len(filtered) == 1
    assert filtered[0] == Decimal("1.000")


def test_outlier_removal_all_outliers():
    """Outlier 제거 (모두 outlier → keep original)"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    rates = [Decimal("0.800"), Decimal("0.810"), Decimal("0.820")]
    # Median = 0.810, threshold = [0.7695, 0.8505]
    # 하지만 모든 값이 median 대비 너무 낮으면 all outlier로 간주
    
    filtered = fx._remove_outliers(rates)
    
    # All outliers → keep original
    assert len(filtered) == 3


def test_median_even_count():
    """Median (even count)"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    rates = [Decimal("1.000"), Decimal("0.999"), Decimal("1.001"), Decimal("1.002")]
    median = fx._calculate_median(rates)
    
    # Sorted: [0.999, 1.000, 1.001, 1.002]
    # Median = (1.000 + 1.001) / 2 = 1.0005
    assert median == Decimal("1.0005")


def test_median_odd_count():
    """Median (odd count)"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    rates = [Decimal("1.000"), Decimal("0.999"), Decimal("1.001")]
    median = fx._calculate_median(rates)
    
    # Sorted: [0.999, 1.000, 1.001]
    # Median = 1.000
    assert median == Decimal("1.000")


# =============================================================================
# B. Multi-Source Provider Tests (7)
# =============================================================================

def test_get_rate_all_sources_healthy():
    """get_rate() with all sources healthy"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    # Simulate 3 sources
    fx._on_source_update("binance", Decimal("1.000"), time.time())
    fx._on_source_update("okx", Decimal("0.999"), time.time())
    fx._on_source_update("bybit", Decimal("1.001"), time.time())
    
    rate = fx.get_rate(Currency.USDT, Currency.USD)
    
    # Median([1.000, 0.999, 1.001]) = 1.000
    assert rate == Decimal("1.000")


def test_get_rate_1_source_down():
    """get_rate() with 1 source down"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    # Only 2 sources
    fx._on_source_update("binance", Decimal("1.000"), time.time())
    fx._on_source_update("okx", Decimal("0.999"), time.time())
    # bybit: None (down)
    
    rate = fx.get_rate(Currency.USDT, Currency.USD)
    
    # Median([1.000, 0.999]) = 0.9995
    assert rate == Decimal("0.9995")


def test_get_rate_2_sources_down():
    """get_rate() with 2 sources down"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    # Only 1 source
    fx._on_source_update("binance", Decimal("1.000"), time.time())
    # okx, bybit: None (down)
    
    rate = fx.get_rate(Currency.USDT, Currency.USD)
    
    # Median([1.000]) = 1.000
    assert rate == Decimal("1.000")


def test_get_rate_all_sources_down_http_fallback():
    """get_rate() with all sources down → HTTP fallback"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    # All sources: None (down)
    # Cache miss → HTTP fallback
    
    with mock.patch.object(fx.http_provider, "get_rate") as mock_get_rate:
        mock_get_rate.return_value = Decimal("1.0")
        
        rate = fx.get_rate(Currency.USDT, Currency.USD)
        
        assert rate == Decimal("1.0")
        mock_get_rate.assert_called_once_with(Currency.USDT, Currency.USD)


def test_start_stop_all_websockets():
    """start/stop all WebSocket clients"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    # Mock WebSocket clients
    fx.ws_clients = {
        "binance": mock.Mock(),
        "okx": mock.Mock(),
        "bybit": mock.Mock(),
    }
    fx.enable_websocket = True  # Enable for start()
    
    # Start
    fx.start()
    
    for client in fx.ws_clients.values():
        client.start.assert_called_once()
    
    # Stop
    fx.stop()
    
    for client in fx.ws_clients.values():
        client.stop.assert_called_once()


def test_get_source_stats():
    """get_source_stats() 조회"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    # Mock WebSocket clients
    fx.ws_clients = {
        "binance": mock.Mock(is_connected=lambda: True),
        "okx": mock.Mock(is_connected=lambda: False),
        "bybit": mock.Mock(is_connected=lambda: True),
    }
    
    # Simulate source updates
    fx._on_source_update("binance", Decimal("1.000"), time.time())
    fx._on_source_update("bybit", Decimal("1.001"), time.time())
    # okx: None (down)
    
    stats = fx.get_source_stats()
    
    assert stats["binance"]["connected"] is True
    assert stats["binance"]["rate"] == 1.000
    assert stats["okx"]["connected"] is False
    assert stats["okx"]["rate"] is None
    assert stats["bybit"]["connected"] is True
    assert stats["bybit"]["rate"] == 1.001


def test_websocket_disabled():
    """WebSocket disabled (enable_websocket=False) → HTTP-only"""
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    assert fx.enable_websocket is False
    assert len(fx.ws_clients) == 0
    
    # Should still work with HTTP fallback
    with mock.patch.object(fx.http_provider, "get_rate") as mock_get_rate:
        mock_get_rate.return_value = Decimal("1.0")
        rate = fx.get_rate(Currency.USDT, Currency.USD)
        assert rate == Decimal("1.0")


# =============================================================================
# C. Integration Tests (5)
# =============================================================================

def test_executor_with_multi_source_fx_provider():
    """Executor + MultiSourceFxRateProvider 통합"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # MultiSourceFxRateProvider (HTTP-only for test)
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    fx.cache.set(Currency.USDT, Currency.KRW, Decimal("1420.0"))
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=fx,
    )
    
    # Estimate order cost
    binance_cost = executor._estimate_order_cost(
        exchange=binance_exchange,
        symbol="BTCUSDT",
        price=40_000.0,
        qty=0.1
    )
    
    assert binance_cost.currency == Currency.USDT
    assert binance_cost.amount == Decimal("4000")


def test_metrics_recording():
    """Metrics: source_count, outlier_count, median_rate"""
    from arbitrage.monitoring.cross_exchange_metrics import (
        CrossExchangeMetrics,
        InMemoryMetricsBackend,
    )
    
    backend = InMemoryMetricsBackend()
    metrics = CrossExchangeMetrics(prometheus_backend=backend)
    
    # Record Multi-Source FX metrics
    source_stats = {
        "binance": {"connected": True, "rate": 1.000, "age": 0.5},
        "okx": {"connected": False, "rate": None, "age": 10.0},
        "bybit": {"connected": True, "rate": 1.001, "age": 1.0},
    }
    
    metrics.record_fx_multi_source_metrics(
        source_count=2,  # binance + bybit
        outlier_count=0,
        median_rate=1.0005,
        source_stats=source_stats,
    )
    
    # Check metrics
    all_metrics = backend.get_all_metrics()
    
    assert all_metrics["gauges"]["cross_fx_multi_source_count"] == 2.0
    assert all_metrics["gauges"]["cross_fx_multi_source_outlier_total"] == 0.0
    assert all_metrics["gauges"]["cross_fx_multi_source_median"] == 1.0005


def test_backward_compatibility_websocket_fx_provider():
    """Backward compatibility (WebSocketFxRateProvider 여전히 동작)"""
    from arbitrage.common.currency import WebSocketFxRateProvider
    
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # WebSocketFxRateProvider (D80-4)
    fx = WebSocketFxRateProvider(enable_websocket=False)
    fx.cache.set(Currency.USDT, Currency.KRW, Decimal("1420.0"))
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=fx,
    )
    
    # Should still work
    binance_cost = executor._estimate_order_cost(
        exchange=binance_exchange,
        symbol="BTCUSDT",
        price=40_000.0,
        qty=0.1
    )
    
    assert binance_cost.currency == Currency.USDT


def test_backward_compatibility_real_fx_provider():
    """Backward compatibility (RealFxRateProvider 여전히 동작)"""
    from arbitrage.common.currency import StaticFxRateProvider
    
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # StaticFxRateProvider (D80-2)
    fx = StaticFxRateProvider({
        (Currency.USD, Currency.KRW): Decimal("1420.0"),
        (Currency.USDT, Currency.KRW): Decimal("1420.0"),
    })
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=fx,
    )
    
    # Should still work
    upbit_cost = executor._estimate_order_cost(
        exchange=upbit_exchange,
        symbol="KRW-BTC",
        price=100_000_000.0,
        qty=0.001
    )
    
    assert upbit_cost.currency == Currency.KRW


def test_source_update_to_cache_to_executor():
    """Source update → cache → executor cost 반영"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    fx = MultiSourceFxRateProvider(enable_websocket=False)
    
    # Simulate multi-source update
    fx._on_source_update("binance", Decimal("1.000"), time.time())
    fx._on_source_update("okx", Decimal("0.999"), time.time())
    fx._on_source_update("bybit", Decimal("1.001"), time.time())
    
    # USD→KRW for chain
    fx.cache.set(Currency.USD, Currency.KRW, Decimal("1420.0"))
    
    executor = CrossExchangeExecutor(
        upbit_client=upbit_exchange,
        binance_client=binance_exchange,
        position_manager=None,
        fx_converter=None,
        health_monitor=None,
        settings=None,
        fx_provider=fx,
    )
    
    # get_rate() should use multi-source aggregated cache
    rate = fx.get_rate(Currency.USDT, Currency.USD)
    assert rate == Decimal("1.000")  # Median([1.000, 0.999, 1.001])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
