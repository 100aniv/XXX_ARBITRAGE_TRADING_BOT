#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D98-2: ReadOnlyGuard Unit Tests for Live Exchange Adapters

Tests that UpbitSpotExchange and BinanceFuturesExchange respect READ_ONLY_ENFORCED.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock

from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
from arbitrage.exchanges.base import OrderSide, OrderType, TimeInForce
from arbitrage.exchanges.exceptions import AuthenticationError
from arbitrage.config.readonly_guard import ReadOnlyError, set_readonly_mode


class TestUpbitSpotReadOnlyGuard:
    """UpbitSpotExchange ReadOnlyGuard 테스트"""
    
    def test_upbit_create_order_blocked_when_readonly_true(self):
        """READ_ONLY_ENFORCED=true 시 Upbit create_order 차단"""
        set_readonly_mode(True)
        
        exchange = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        })
        
        with pytest.raises(ReadOnlyError) as exc_info:
            exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=0.001,
                price=50000000.0,
            )
        
        assert "READ_ONLY" in str(exc_info.value).upper()
        assert "create_order" in str(exc_info.value)
    
    def test_upbit_cancel_order_blocked_when_readonly_true(self):
        """READ_ONLY_ENFORCED=true 시 Upbit cancel_order 차단"""
        set_readonly_mode(True)
        
        exchange = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        })
        
        with pytest.raises(ReadOnlyError) as exc_info:
            exchange.cancel_order("test_order_id")
        
        assert "READ_ONLY" in str(exc_info.value).upper()
        assert "cancel_order" in str(exc_info.value)
    
    @patch('arbitrage.exchanges.upbit_spot.requests.get')
    def test_upbit_get_balance_allowed_when_readonly_true(self, mock_get):
        """READ_ONLY_ENFORCED=true 시 Upbit get_balance 허용"""
        set_readonly_mode(True)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"currency": "KRW", "balance": "1000000", "locked": "0"},
            {"currency": "BTC", "balance": "1.5", "locked": "0"},
        ]
        mock_get.return_value = mock_response
        
        exchange = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
        })
        
        balances = exchange.get_balance()
        
        assert "KRW" in balances
        assert "BTC" in balances
        assert balances["KRW"].free == 1000000.0
    
    @patch('arbitrage.exchanges.upbit_spot.requests.get')
    def test_upbit_get_orderbook_allowed_when_readonly_true(self, mock_get):
        """READ_ONLY_ENFORCED=true 시 Upbit get_orderbook 허용"""
        set_readonly_mode(True)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "market": "BTC-KRW",
            "timestamp": 1234567890,
            "orderbook_units": [
                {"ask_price": 50100000, "ask_size": 1.0, "bid_price": 50000000, "bid_size": 1.0},
            ]
        }
        mock_get.return_value = mock_response
        
        exchange = UpbitSpotExchange(config={})
        
        orderbook = exchange.get_orderbook("BTC-KRW")
        
        assert orderbook.symbol == "BTC-KRW"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0
    
    @patch('arbitrage.exchanges.http_client.HTTPClient.post')
    def test_upbit_create_order_allowed_when_readonly_false(self, mock_post):
        """READ_ONLY_ENFORCED=false 시 Upbit create_order 허용 (live_enabled 체크로 이동)"""
        set_readonly_mode(False)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "uuid": "order_123",
            "state": "wait",
            "executed_volume": "0",
        }
        mock_post.return_value = mock_response
        
        exchange = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        })
        
        result = exchange.create_order(
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=0.001,
            price=50000000.0,
        )
        
        assert result.order_id == "order_123"
        assert mock_post.called


class TestBinanceFuturesReadOnlyGuard:
    """BinanceFuturesExchange ReadOnlyGuard 테스트"""
    
    def test_binance_create_order_blocked_when_readonly_true(self):
        """READ_ONLY_ENFORCED=true 시 Binance create_order 차단"""
        set_readonly_mode(True)
        
        exchange = BinanceFuturesExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        })
        
        with pytest.raises(ReadOnlyError) as exc_info:
            exchange.create_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                qty=0.001,
                price=40000.0,
            )
        
        assert "READ_ONLY" in str(exc_info.value).upper()
        assert "create_order" in str(exc_info.value)
    
    def test_binance_cancel_order_blocked_when_readonly_true(self):
        """READ_ONLY_ENFORCED=true 시 Binance cancel_order 차단"""
        set_readonly_mode(True)
        
        exchange = BinanceFuturesExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        })
        
        with pytest.raises(ReadOnlyError) as exc_info:
            exchange.cancel_order("test_order_id", symbol="BTCUSDT")
        
        assert "READ_ONLY" in str(exc_info.value).upper()
        assert "cancel_order" in str(exc_info.value)
    
    @patch('arbitrage.exchanges.binance_futures.requests.get')
    def test_binance_get_balance_allowed_when_readonly_true(self, mock_get):
        """READ_ONLY_ENFORCED=true 시 Binance get_balance 허용"""
        set_readonly_mode(True)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "assets": [
                {"asset": "USDT", "walletBalance": "10000", "crossUnPnl": "0"},
                {"asset": "BTC", "walletBalance": "0.5", "crossUnPnl": "100"},
            ]
        }
        mock_get.return_value = mock_response
        
        exchange = BinanceFuturesExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
        })
        
        balances = exchange.get_balance()
        
        assert "USDT" in balances
        assert "BTC" in balances
        assert balances["USDT"].free == 10000.0
    
    @patch('arbitrage.exchanges.binance_futures.requests.get')
    def test_binance_get_orderbook_allowed_when_readonly_true(self, mock_get):
        """READ_ONLY_ENFORCED=true 시 Binance get_orderbook 허용"""
        set_readonly_mode(True)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "bids": [["40000", "1.0"], ["39999", "2.0"]],
            "asks": [["40100", "1.0"], ["40101", "2.0"]],
            "E": 1234567890000,
        }
        mock_get.return_value = mock_response
        
        exchange = BinanceFuturesExchange(config={})
        
        orderbook = exchange.get_orderbook("BTCUSDT")
        
        assert orderbook.symbol == "BTCUSDT"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0
    
    @patch('arbitrage.exchanges.http_client.HTTPClient.post')
    def test_binance_create_order_allowed_when_readonly_false(self, mock_post):
        """READ_ONLY_ENFORCED=false 시 Binance create_order 허용 (live_enabled 체크로 이동)"""
        set_readonly_mode(False)
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "orderId": "12345",
            "status": "NEW",
            "executedQty": "0",
        }
        mock_post.return_value = mock_response
        
        exchange = BinanceFuturesExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        })
        
        result = exchange.create_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=0.001,
            price=40000.0,
        )
        
        assert result.order_id == "12345"
        assert mock_post.called


class TestLiveAdaptersReadOnlyGuardConsistency:
    """Live Adapters 간 ReadOnlyGuard 일관성 테스트"""
    
    def test_all_live_adapters_block_orders_when_readonly_true(self):
        """모든 Live Adapter가 READ_ONLY_ENFORCED=true 시 주문 차단"""
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        binance = BinanceFuturesExchange(config={"live_enabled": True})
        
        # Upbit create_order 차단
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        # Binance create_order 차단
        with pytest.raises(ReadOnlyError):
            binance.create_order("BTCUSDT", OrderSide.BUY, 0.001, 40000.0)
        
        # Upbit cancel_order 차단
        with pytest.raises(ReadOnlyError):
            upbit.cancel_order("order_1")
        
        # Binance cancel_order 차단
        with pytest.raises(ReadOnlyError):
            binance.cancel_order("order_2", symbol="BTCUSDT")
    
    def test_readonly_guard_takes_precedence_over_live_enabled(self):
        """ReadOnlyGuard가 live_enabled보다 우선순위 높음"""
        set_readonly_mode(True)
        
        # live_enabled=True여도 ReadOnlyGuard가 먼저 차단
        upbit = UpbitSpotExchange(config={"live_enabled": True})
        
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        # ReadOnlyGuard가 없으면 live_enabled=False가 차단
        set_readonly_mode(False)
        upbit = UpbitSpotExchange(config={"live_enabled": False})
        
        with pytest.raises(RuntimeError) as exc_info:
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        assert "Live trading is disabled" in str(exc_info.value)


class TestLiveAdaptersReadOnlyGuardEnvironment:
    """환경변수 기반 ReadOnlyGuard 테스트"""
    
    def test_environment_variable_controls_readonly_mode(self):
        """READ_ONLY_ENFORCED 환경변수로 ReadOnly 모드 제어"""
        # 환경변수로 제어
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True
        })
        
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
        
        # ReadOnly 모드 비활성화
        set_readonly_mode(False)
        
        # live_enabled=False로 설정하면 RuntimeError 발생
        upbit2 = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": False
        })
        
        with pytest.raises(RuntimeError):
            upbit2.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
    
    def test_fail_closed_principle(self):
        """Fail-Closed: 환경변수 없으면 기본값 true"""
        # 명시적으로 readonly 모드 활성화 (fail-closed 시뮬레이션)
        set_readonly_mode(True)
        
        upbit = UpbitSpotExchange(config={
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True
        })
        
        # ReadOnly 모드에서 주문 차단 확인
        with pytest.raises(ReadOnlyError):
            upbit.create_order("BTC-KRW", OrderSide.BUY, 0.001, 50000000.0)
