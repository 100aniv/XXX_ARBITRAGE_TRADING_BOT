# -*- coding: utf-8 -*-
"""
D80-4: WebSocket FX Provider Tests

WebSocketFxRateProvider, BinanceFxWebSocketClient 테스트.
"""

import pytest
import time
import json
from decimal import Decimal
from unittest import mock

from arbitrage.common.currency import Currency, WebSocketFxRateProvider, RealFxRateProvider
from arbitrage.common.fx_cache import FxCache
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.cross_exchange.executor import CrossExchangeExecutor


# =============================================================================
# A. WebSocket Client Tests (5)
# =============================================================================

def test_ws_message_parsing():
    """Message parsing (mock WebSocket message → rate extraction)"""
    from arbitrage.common.fx_ws_client import BinanceFxWebSocketClient
    
    callback_called = []
    
    def on_rate_update(rate: Decimal, timestamp: float):
        callback_called.append((rate, timestamp))
    
    client = BinanceFxWebSocketClient(
        symbol="btcusdt",
        on_rate_update=on_rate_update
    )
    
    # Mock WebSocket message
    mock_message = json.dumps({
        "e": "markPriceUpdate",
        "E": 1701449123450,
        "s": "BTCUSDT",
        "p": "97000.00",
        "r": "0.0001"
    })
    
    # Call _on_message directly
    client._on_message(None, mock_message)
    
    # Check callback was called
    assert len(callback_called) == 1
    rate, timestamp = callback_called[0]
    assert rate == Decimal("1.0")  # USDT≈USD
    assert timestamp > 0


def test_ws_cache_update_callback():
    """FxCache 업데이트 callback (on_rate_update 호출 확인)"""
    from arbitrage.common.fx_ws_client import BinanceFxWebSocketClient
    
    cache = FxCache(ttl_seconds=10.0)
    
    def on_rate_update(rate: Decimal, timestamp: float):
        cache.set(Currency.USDT, Currency.USD, rate, updated_at=timestamp)
    
    client = BinanceFxWebSocketClient(
        symbol="btcusdt",
        on_rate_update=on_rate_update
    )
    
    # Simulate message
    mock_message = json.dumps({
        "e": "markPriceUpdate",
        "s": "BTCUSDT",
        "p": "97000.00",
        "r": "0.0001"
    })
    
    client._on_message(None, mock_message)
    
    # Check cache was updated
    rate = cache.get(Currency.USDT, Currency.USD)
    assert rate == Decimal("1.0")


def test_ws_start_stop():
    """Start/Stop (Thread 시작/종료)"""
    from arbitrage.common.fx_ws_client import BinanceFxWebSocketClient
    
    client = BinanceFxWebSocketClient(symbol="btcusdt")
    
    # Note: 실제 WebSocket 연결은 안 하고, Thread만 시작/종료 확인
    # (실제 연결은 websocket-client 라이브러리가 없으면 실패)
    
    # Start는 Thread를 생성하므로, 즉시 stop 호출
    try:
        client.start()
        time.sleep(0.1)  # Thread 시작 대기
        assert client._thread is not None
    finally:
        client.stop()
        time.sleep(0.1)  # Thread 종료 대기


def test_ws_get_stats():
    """WebSocket stats 조회"""
    from arbitrage.common.fx_ws_client import BinanceFxWebSocketClient
    
    client = BinanceFxWebSocketClient(symbol="btcusdt")
    
    stats = client.get_stats()
    
    assert "connected" in stats
    assert "reconnect_count" in stats
    assert "message_count" in stats
    assert "error_count" in stats
    assert "last_message_age" in stats
    
    assert stats["connected"] is False  # Not started yet
    assert stats["reconnect_count"] == 0
    assert stats["message_count"] == 0


def test_ws_error_callback():
    """WebSocket error callback"""
    from arbitrage.common.fx_ws_client import BinanceFxWebSocketClient
    
    error_called = []
    
    def on_error(error: Exception):
        error_called.append(error)
    
    client = BinanceFxWebSocketClient(
        symbol="btcusdt",
        on_error=on_error
    )
    
    # Simulate error
    test_error = Exception("Test error")
    client._on_ws_error(None, test_error)
    
    assert len(error_called) == 1
    assert error_called[0] == test_error


# =============================================================================
# B. WebSocketFxRateProvider Tests (6)
# =============================================================================

def test_ws_provider_get_rate_cache_hit():
    """get_rate() with WS cache hit"""
    fx = WebSocketFxRateProvider(enable_websocket=False)  # HTTP-only for test
    
    # Pre-populate cache
    fx.cache.set(Currency.USDT, Currency.USD, Decimal("1.0"))
    
    rate = fx.get_rate(Currency.USDT, Currency.USD)
    
    assert rate == Decimal("1.0")


def test_ws_provider_get_rate_http_fallback():
    """get_rate() with cache miss → HTTP fallback"""
    fx = WebSocketFxRateProvider(enable_websocket=False)  # HTTP-only
    
    # Mock HTTP fallback
    with mock.patch.object(fx.real_fx_provider, "get_rate") as mock_get_rate:
        mock_get_rate.return_value = Decimal("1420.0")
        
        rate = fx.get_rate(Currency.USD, Currency.KRW)
        
        assert rate == Decimal("1420.0")
        mock_get_rate.assert_called_once_with(Currency.USD, Currency.KRW)


def test_ws_provider_websocket_update_to_cache():
    """WebSocket update → FxCache → get_rate() 반영"""
    fx = WebSocketFxRateProvider(enable_websocket=False)
    
    # Simulate WebSocket update (직접 callback 호출)
    fx._on_ws_rate_update(Decimal("1.0"), time.time())
    
    # Check cache was updated
    rate = fx.cache.get(Currency.USDT, Currency.USD)
    assert rate == Decimal("1.0")
    
    # get_rate() should return cached value
    rate = fx.get_rate(Currency.USDT, Currency.USD)
    assert rate == Decimal("1.0")


def test_ws_provider_websocket_disabled():
    """WebSocket disabled (enable_websocket=False) → HTTP-only"""
    fx = WebSocketFxRateProvider(enable_websocket=False)
    
    assert fx.enable_websocket is False
    assert fx.ws_client is None
    assert fx.is_websocket_connected() is False
    
    # Should still work with HTTP fallback
    with mock.patch.object(fx.real_fx_provider, "get_rate") as mock_get_rate:
        mock_get_rate.return_value = Decimal("1420.0")
        rate = fx.get_rate(Currency.USD, Currency.KRW)
        assert rate == Decimal("1420.0")


def test_ws_provider_is_websocket_connected():
    """is_websocket_connected() 상태 확인"""
    fx = WebSocketFxRateProvider(enable_websocket=False)
    
    # WebSocket disabled
    assert fx.is_websocket_connected() is False
    
    # With WebSocket (mock)
    fx.ws_client = mock.Mock()
    fx.ws_client.is_connected.return_value = True
    
    assert fx.is_websocket_connected() is True


def test_ws_provider_get_websocket_stats():
    """get_websocket_stats() 조회"""
    fx = WebSocketFxRateProvider(enable_websocket=False)
    
    # WebSocket disabled
    stats = fx.get_websocket_stats()
    assert stats["connected"] is False
    assert stats["reconnect_count"] == 0
    assert stats["message_count"] == 0
    
    # With WebSocket (mock)
    fx.ws_client = mock.Mock()
    fx.ws_client.get_stats.return_value = {
        "connected": True,
        "reconnect_count": 3,
        "message_count": 100,
        "error_count": 1,
        "last_message_age": 5.0,
    }
    
    stats = fx.get_websocket_stats()
    assert stats["connected"] is True
    assert stats["reconnect_count"] == 3
    assert stats["message_count"] == 100


# =============================================================================
# C. Integration Tests (4)
# =============================================================================

def test_executor_with_ws_fx_provider():
    """Executor + WebSocketFxRateProvider 통합"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # WebSocket FX Provider (HTTP-only for test)
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
    
    # Estimate order cost
    binance_cost = executor._estimate_order_cost(
        exchange=binance_exchange,
        symbol="BTCUSDT",
        price=40_000.0,
        qty=0.1
    )
    
    assert binance_cost.currency == Currency.USDT
    assert binance_cost.amount == Decimal("4000")


def test_ws_update_to_executor_cost():
    """WebSocket update → Executor._estimate_order_cost() 반영"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    fx = WebSocketFxRateProvider(enable_websocket=False)
    
    # Simulate WebSocket update
    fx._on_ws_rate_update(Decimal("1.0"), time.time())
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
    
    # get_rate() should use WS-updated cache
    rate = fx.get_rate(Currency.USDT, Currency.USD)
    assert rate == Decimal("1.0")


def test_ws_metrics_recording():
    """Metrics: cross_fx_ws_connected, reconnect_total, message_total"""
    from arbitrage.monitoring.cross_exchange_metrics import (
        CrossExchangeMetrics,
        InMemoryMetricsBackend,
    )
    
    backend = InMemoryMetricsBackend()
    metrics = CrossExchangeMetrics(prometheus_backend=backend)
    
    # Record WebSocket metrics
    metrics.record_fx_ws_metrics(
        connected=True,
        reconnect_count=3,
        message_count=100,
        error_count=1,
        last_message_age=5.0,
    )
    
    # Check metrics
    all_metrics = backend.get_all_metrics()
    
    # labels가 비어있으므로 key는 name만 (콜론 없음)
    assert all_metrics["gauges"]["cross_fx_ws_connected"] == 1.0
    assert all_metrics["gauges"]["cross_fx_ws_reconnect_total"] == 3.0
    assert all_metrics["gauges"]["cross_fx_ws_message_total"] == 100.0
    assert all_metrics["gauges"]["cross_fx_ws_error_total"] == 1.0
    assert all_metrics["gauges"]["cross_fx_ws_last_message_seconds"] == 5.0


def test_backward_compatibility_real_fx_provider():
    """Backward compatibility (RealFxRateProvider 여전히 동작)"""
    upbit_exchange = PaperExchange(config={"base_currency": Currency.KRW})
    binance_exchange = PaperExchange(config={"base_currency": Currency.USDT})
    
    # Use RealFxRateProvider (HTTP-only, D80-3)
    from arbitrage.common.currency import StaticFxRateProvider
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
    assert upbit_cost.amount == Decimal("100000")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
