# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Tests - Upbit Spot Exchange

UpbitSpotExchange 테스트 (100% mock 기반).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
from arbitrage.exchanges.base import OrderSide, OrderType, TimeInForce, OrderStatus


class TestUpbitSpotExchangeInitialization:
    """UpbitSpotExchange 초기화 테스트"""
    
    def test_upbit_initialization_default(self):
        """기본 초기화"""
        exchange = UpbitSpotExchange()
        
        assert exchange.name == "upbit"
        assert exchange.base_url == "https://api.upbit.com"
        assert exchange.timeout == 10
        assert exchange.live_enabled is False
    
    def test_upbit_initialization_custom_config(self):
        """사용자 정의 설정"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "base_url": "https://custom.upbit.com",
            "timeout": 20,
            "live_enabled": False,
        }
        
        exchange = UpbitSpotExchange(config)
        
        assert exchange.api_key == "test_key"
        assert exchange.api_secret == "test_secret"
        assert exchange.base_url == "https://custom.upbit.com"
        assert exchange.timeout == 20


class TestUpbitSpotExchangeOrderbook:
    """UpbitSpotExchange 호가 테스트"""
    
    @pytest.mark.live_api
    def test_get_orderbook(self):
        """호가 조회"""
        exchange = UpbitSpotExchange()
        
        orderbook = exchange.get_orderbook("BTC-KRW")
        
        assert orderbook.symbol == "BTC-KRW"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0


class TestUpbitSpotExchangeBalance:
    """UpbitSpotExchange 잔고 테스트"""
    
    @pytest.mark.live_api
    def test_get_balance(self):
        """잔고 조회"""
        exchange = UpbitSpotExchange()
        
        balance = exchange.get_balance()
        
        assert "KRW" in balance
        assert balance["KRW"].free > 0


class TestUpbitSpotExchangeOrders:
    """UpbitSpotExchange 주문 테스트"""
    
    def test_create_order_live_disabled(self):
        """실거래 비활성화 상태에서 주문"""
        exchange = UpbitSpotExchange({"live_enabled": False})
        
        with pytest.raises(RuntimeError):
            exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=1.0,
                price=100000.0,
            )
    
    def test_create_order_live_enabled(self):
        """실거래 활성화 상태에서 주문"""
        config = {
            "api_key": "test_key",
            "api_secret": "test_secret",
            "live_enabled": True,
        }
        exchange = UpbitSpotExchange(config)
        
        # Mock requests 라이브러리
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "uuid": "upbit_order_123",
                "side": "bid",
                "ord_type": "limit",
                "price": 100000.0,
                "state": "wait",
                "market": "KRW-BTC",
                "created_at": "2025-01-01T00:00:00Z",
                "volume": 1.0,
                "remaining_volume": 1.0,
                "reserved_fee": 0.0,
                "remaining_fee": 0.0,
                "paid_fee": 0.0,
                "locked": 100000.0,
                "executed_volume": 0.0,
                "trades_count": 0,
                "user_id": 123,
                "identifier": "upbit_order_123",
            }
            mock_post.return_value = mock_response
            
            order = exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=1.0,
                price=100000.0,
            )
            
            assert order.symbol == "BTC-KRW"
            assert order.side == OrderSide.BUY
    
    def test_cancel_order_live_disabled(self):
        """실거래 비활성화 상태에서 취소"""
        exchange = UpbitSpotExchange({"live_enabled": False})
        
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
        exchange = UpbitSpotExchange(config)
        
        with patch("requests.delete") as mock_delete:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_delete.return_value = mock_response
            
            result = exchange.cancel_order("order_123")
            
            assert result is True
    
    def test_get_order_status(self):
        """주문 상태 조회"""
        exchange = UpbitSpotExchange()
        
        order = exchange.get_order_status("order_123")
        
        assert order.order_id == "order_123"
        assert order.status == OrderStatus.FILLED


class TestUpbitSpotExchangePositions:
    """UpbitSpotExchange 포지션 테스트"""
    
    def test_get_open_positions(self):
        """미결제 포지션 조회 (현물은 없음)"""
        exchange = UpbitSpotExchange()
        
        positions = exchange.get_open_positions()
        
        assert len(positions) == 0
