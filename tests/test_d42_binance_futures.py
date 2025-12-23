# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Tests - Binance Futures Exchange

BinanceFuturesExchange 테스트 (100% mock 기반).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
from arbitrage.exchanges.base import OrderSide, OrderType, TimeInForce, OrderStatus


class TestBinanceFuturesExchangeInitialization:
    """BinanceFuturesExchange 초기화 테스트"""
    
    def test_binance_initialization_default(self):
        """기본 초기화"""
        exchange = BinanceFuturesExchange()
        
        assert exchange.name == "binance_futures"
        assert exchange.base_url == "https://fapi.binance.com"
        assert exchange.timeout == 10
        assert exchange.leverage == 1
        assert exchange.live_enabled is False
    
    def test_binance_initialization_custom_config(self):
        """사용자 정의 설정"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://custom.binance.com",
            "timeout": 20,
            "leverage": 2,
            "live_enabled": False,
        }
        
        exchange = BinanceFuturesExchange(config)
        
        assert exchange.api_key == "test_key"
        assert exchange.api_secret == "test_secret"
        assert exchange.base_url == "https://custom.binance.com"
        assert exchange.timeout == 20
        assert exchange.leverage == 2


class TestBinanceFuturesExchangeOrderbook:
    """BinanceFuturesExchange 호가 테스트"""
    
    def test_get_orderbook(self):
        """호가 조회"""
        exchange = BinanceFuturesExchange()
        
        orderbook = exchange.get_orderbook("BTCUSDT")
        
        assert orderbook.symbol == "BTCUSDT"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0


class TestBinanceFuturesExchangeBalance:
    """BinanceFuturesExchange 잔고 테스트"""
    
    @pytest.mark.live_api
    def test_get_balance(self):
        """잔고 조회"""
        exchange = BinanceFuturesExchange()
        
        balance = exchange.get_balance()
        
        assert "USDT" in balance
        assert balance["USDT"].free > 0


class TestBinanceFuturesExchangeOrders:
    """BinanceFuturesExchange 주문 테스트"""
    
    def test_create_order_live_disabled(self):
        """실거래 비활성화 상태에서 주문"""
        exchange = BinanceFuturesExchange({"live_enabled": False})
        
        with pytest.raises(RuntimeError):
            exchange.create_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                qty=1.0,
                price=40000.0,
            )
    
    def test_create_order_live_enabled(self):
        """실거래 활성화 상태에서 주문"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
            "leverage": 2,
        }
        exchange = BinanceFuturesExchange(config)
        
        # Mock requests 라이브러리
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "orderId": 123456789,
                "symbol": "BTCUSDT",
                "status": "NEW",
                "clientOrderId": "binance_order_123",
                "price": 40000.0,
                "avgPrice": 0.0,
                "origQty": 1.0,
                "executedQty": 0.0,
                "cumQty": 0.0,
                "cumQuote": 0.0,
                "timeInForce": "GTC",
                "type": "LIMIT",
                "reduceOnly": False,
                "closePosition": False,
                "side": "BUY",
                "positionSide": "LONG",
                "stopPrice": 0.0,
                "workingType": "CONTRACT_PRICE",
                "priceProtect": False,
                "origType": "LIMIT",
                "updateTime": 1234567890000,
            }
            mock_post.return_value = mock_response
            
            order = exchange.create_order(
                symbol="BTCUSDT",
                side=OrderSide.BUY,
                qty=1.0,
                price=40000.0,
            )
            
            assert order.symbol == "BTCUSDT"
            assert order.side == OrderSide.BUY
    
    def test_cancel_order_live_disabled(self):
        """실거래 비활성화 상태에서 취소"""
        exchange = BinanceFuturesExchange({"live_enabled": False})
        
        with pytest.raises(RuntimeError):
            exchange.cancel_order("order_123")
    
    @pytest.mark.live_api
    def test_cancel_order_live_enabled(self):
        """실거래 활성화 상태에서 취소"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        }
        exchange = BinanceFuturesExchange(config)
        
        with patch("requests.delete") as mock_delete:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_delete.return_value = mock_response
            
            result = exchange.cancel_order("order_123")
            
            assert result is True
    
    def test_get_order_status(self):
        """주문 상태 조회"""
        exchange = BinanceFuturesExchange()
        
        order = exchange.get_order_status("order_123")
        
        assert order.order_id == "order_123"
        assert order.status == OrderStatus.FILLED


class TestBinanceFuturesExchangePositions:
    """BinanceFuturesExchange 포지션 테스트"""
    
    def test_get_open_positions(self):
        """미결제 포지션 조회"""
        exchange = BinanceFuturesExchange()
        
        positions = exchange.get_open_positions()
        
        # 기본값은 빈 리스트
        assert isinstance(positions, list)
