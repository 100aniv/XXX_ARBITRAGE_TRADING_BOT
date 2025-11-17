# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Tests - Paper Exchange

PaperExchange (모의 거래) 테스트.
"""

import pytest
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.base import (
    OrderSide,
    OrderType,
    TimeInForce,
    OrderStatus,
    OrderBookSnapshot,
)
from arbitrage.exchanges.exceptions import (
    InsufficientBalanceError,
    OrderNotFoundError,
    InvalidOrderError,
)


class TestPaperExchangeInitialization:
    """PaperExchange 초기화 테스트"""
    
    def test_paper_exchange_default_balance(self):
        """기본 잔고"""
        exchange = PaperExchange()
        balance = exchange.get_balance()
        
        assert "KRW" in balance
        assert balance["KRW"].free == 1000000.0
    
    def test_paper_exchange_custom_balance(self):
        """사용자 정의 잔고"""
        exchange = PaperExchange(
            initial_balance={"KRW": 500000.0, "BTC": 0.5}
        )
        balance = exchange.get_balance()
        
        assert balance["KRW"].free == 500000.0
        assert balance["BTC"].free == 0.5


class TestPaperExchangeOrderbook:
    """PaperExchange 호가 테스트"""
    
    def test_get_orderbook_default(self):
        """기본 호가"""
        exchange = PaperExchange()
        orderbook = exchange.get_orderbook("BTC-KRW")
        
        assert orderbook.symbol == "BTC-KRW"
        assert len(orderbook.bids) > 0
        assert len(orderbook.asks) > 0
    
    def test_set_orderbook(self):
        """호가 설정"""
        exchange = PaperExchange()
        snapshot = OrderBookSnapshot(
            symbol="BTC-KRW",
            timestamp=1234567890.0,
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0)],
        )
        
        exchange.set_orderbook("BTC-KRW", snapshot)
        orderbook = exchange.get_orderbook("BTC-KRW")
        
        assert orderbook.best_bid() == 100000.0
        assert orderbook.best_ask() == 101000.0


class TestPaperExchangeOrders:
    """PaperExchange 주문 테스트"""
    
    def test_create_buy_order(self):
        """매수 주문"""
        exchange = PaperExchange(initial_balance={"KRW": 1000000.0})
        
        order = exchange.create_order(
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
            order_type=OrderType.LIMIT,
        )
        
        assert order.symbol == "BTC-KRW"
        assert order.side == OrderSide.BUY
        assert order.qty == 1.0
        assert order.status == OrderStatus.FILLED
    
    def test_create_sell_order(self):
        """매도 주문"""
        exchange = PaperExchange(initial_balance={"KRW": 0.0, "BTC": 1.0})
        
        order = exchange.create_order(
            symbol="BTC-KRW",
            side=OrderSide.SELL,
            qty=1.0,
            price=100000.0,
            order_type=OrderType.LIMIT,
        )
        
        assert order.side == OrderSide.SELL
        assert order.status == OrderStatus.FILLED
    
    def test_insufficient_balance(self):
        """잔고 부족"""
        exchange = PaperExchange(initial_balance={"KRW": 50000.0})
        
        with pytest.raises(InsufficientBalanceError):
            exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=1.0,
                price=100000.0,
            )
    
    def test_invalid_quantity(self):
        """유효하지 않은 수량"""
        exchange = PaperExchange()
        
        with pytest.raises(InvalidOrderError):
            exchange.create_order(
                symbol="BTC-KRW",
                side=OrderSide.BUY,
                qty=-1.0,
                price=100000.0,
            )
    
    def test_cancel_order(self):
        """주문 취소"""
        exchange = PaperExchange()
        
        order = exchange.create_order(
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
        )
        
        # Paper 모드에서는 즉시 체결되므로 취소 불가
        result = exchange.cancel_order(order.order_id)
        assert result is False
    
    def test_get_order_status(self):
        """주문 상태 조회"""
        exchange = PaperExchange()
        
        order = exchange.create_order(
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
        )
        
        status = exchange.get_order_status(order.order_id)
        assert status.order_id == order.order_id
        assert status.status == OrderStatus.FILLED
    
    def test_order_not_found(self):
        """주문을 찾을 수 없음"""
        exchange = PaperExchange()
        
        with pytest.raises(OrderNotFoundError):
            exchange.get_order_status("nonexistent_order")


class TestPaperExchangeBalance:
    """PaperExchange 잔고 변화 테스트"""
    
    def test_balance_after_buy(self):
        """매수 후 잔고"""
        exchange = PaperExchange(initial_balance={"KRW": 1000000.0})
        
        exchange.create_order(
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
        )
        
        balance = exchange.get_balance()
        assert balance["KRW"].free == 900000.0  # 1,000,000 - 100,000
        assert balance["BTC"].free == 1.0
    
    def test_balance_after_sell(self):
        """매도 후 잔고"""
        exchange = PaperExchange(initial_balance={"KRW": 0.0, "BTC": 1.0})
        
        exchange.create_order(
            symbol="BTC-KRW",
            side=OrderSide.SELL,
            qty=1.0,
            price=100000.0,
        )
        
        balance = exchange.get_balance()
        assert balance["KRW"].free == 100000.0
        assert balance["BTC"].free == 0.0


class TestPaperExchangePositions:
    """PaperExchange 포지션 테스트"""
    
    def test_get_open_positions(self):
        """미결제 포지션 조회"""
        exchange = PaperExchange()
        positions = exchange.get_open_positions()
        
        # Paper 모드에서는 현물 거래이므로 포지션 없음
        assert len(positions) == 0
