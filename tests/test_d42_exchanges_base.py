# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Tests - Base Interface

BaseExchange 및 공통 데이터 구조 테스트.
"""

import pytest
from arbitrage.exchanges.base import (
    OrderSide,
    OrderType,
    TimeInForce,
    OrderStatus,
    OrderBookSnapshot,
    Balance,
    Position,
    PositionSide,
    OrderResult,
)


class TestOrderSide:
    """OrderSide enum 테스트"""
    
    def test_order_side_buy(self):
        """BUY 주문"""
        assert OrderSide.BUY == "BUY"
        assert OrderSide.BUY.value == "BUY"
    
    def test_order_side_sell(self):
        """SELL 주문"""
        assert OrderSide.SELL == "SELL"
        assert OrderSide.SELL.value == "SELL"


class TestOrderType:
    """OrderType enum 테스트"""
    
    def test_order_type_limit(self):
        """LIMIT 주문"""
        assert OrderType.LIMIT == "LIMIT"
    
    def test_order_type_market(self):
        """MARKET 주문"""
        assert OrderType.MARKET == "MARKET"


class TestTimeInForce:
    """TimeInForce enum 테스트"""
    
    def test_time_in_force_gtc(self):
        """GTC (Good-Till-Canceled)"""
        assert TimeInForce.GTC == "GTC"
    
    def test_time_in_force_ioc(self):
        """IOC (Immediate-Or-Cancel)"""
        assert TimeInForce.IOC == "IOC"


class TestOrderStatus:
    """OrderStatus enum 테스트"""
    
    def test_order_status_pending(self):
        """PENDING 상태"""
        assert OrderStatus.PENDING == "PENDING"
    
    def test_order_status_filled(self):
        """FILLED 상태"""
        assert OrderStatus.FILLED == "FILLED"


class TestOrderBookSnapshot:
    """OrderBookSnapshot 데이터 클래스 테스트"""
    
    def test_orderbook_snapshot_creation(self):
        """호가 스냅샷 생성"""
        snapshot = OrderBookSnapshot(
            symbol="BTC-KRW",
            timestamp=1234567890.0,
            bids=[(100000.0, 1.0), (99000.0, 2.0)],
            asks=[(101000.0, 1.0), (102000.0, 2.0)],
        )
        
        assert snapshot.symbol == "BTC-KRW"
        assert len(snapshot.bids) == 2
        assert len(snapshot.asks) == 2
    
    def test_best_bid(self):
        """최고 매수가"""
        snapshot = OrderBookSnapshot(
            symbol="BTC-KRW",
            timestamp=1234567890.0,
            bids=[(100000.0, 1.0), (99000.0, 2.0)],
            asks=[(101000.0, 1.0)],
        )
        
        assert snapshot.best_bid() == 100000.0
    
    def test_best_ask(self):
        """최저 매도가"""
        snapshot = OrderBookSnapshot(
            symbol="BTC-KRW",
            timestamp=1234567890.0,
            bids=[(100000.0, 1.0)],
            asks=[(101000.0, 1.0), (102000.0, 2.0)],
        )
        
        assert snapshot.best_ask() == 101000.0
    
    def test_empty_orderbook(self):
        """빈 호가"""
        snapshot = OrderBookSnapshot(
            symbol="BTC-KRW",
            timestamp=1234567890.0,
            bids=[],
            asks=[],
        )
        
        assert snapshot.best_bid() is None
        assert snapshot.best_ask() is None


class TestBalance:
    """Balance 데이터 클래스 테스트"""
    
    def test_balance_creation(self):
        """잔고 생성"""
        balance = Balance(asset="BTC", free=1.0, locked=0.5)
        
        assert balance.asset == "BTC"
        assert balance.free == 1.0
        assert balance.locked == 0.5
    
    def test_balance_total(self):
        """총 잔고"""
        balance = Balance(asset="BTC", free=1.0, locked=0.5)
        
        assert balance.total == 1.5


class TestPosition:
    """Position 데이터 클래스 테스트"""
    
    def test_position_creation(self):
        """포지션 생성"""
        position = Position(
            symbol="BTCUSDT",
            side=PositionSide.LONG,
            qty=1.0,
            entry_price=40000.0,
            mark_price=41000.0,
            unrealized_pnl=1000.0,
            leverage=2,
        )
        
        assert position.symbol == "BTCUSDT"
        assert position.side == PositionSide.LONG
        assert position.qty == 1.0


class TestOrderResult:
    """OrderResult 데이터 클래스 테스트"""
    
    def test_order_result_creation(self):
        """주문 결과 생성"""
        order = OrderResult(
            order_id="order_123",
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            filled_qty=0.0,
        )
        
        assert order.order_id == "order_123"
        assert order.symbol == "BTC-KRW"
        assert order.side == OrderSide.BUY
    
    def test_is_filled(self):
        """완전 체결 여부"""
        order_open = OrderResult(
            order_id="order_1",
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            filled_qty=0.0,
        )
        
        order_filled = OrderResult(
            order_id="order_2",
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            filled_qty=1.0,
        )
        
        assert not order_open.is_filled
        assert order_filled.is_filled
    
    def test_is_open(self):
        """미체결 여부"""
        order_open = OrderResult(
            order_id="order_1",
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.OPEN,
            filled_qty=0.0,
        )
        
        order_filled = OrderResult(
            order_id="order_2",
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            filled_qty=1.0,
        )
        
        assert order_open.is_open
        assert not order_filled.is_open
