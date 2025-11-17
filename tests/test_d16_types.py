#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Tests — Type Definitions
=============================

공통 타입 및 데이터 클래스 테스트.
"""

import pytest
from datetime import datetime
from arbitrage.types import (
    Price, Order, Position, Signal, ExecutionResult,
    OrderSide, OrderStatus, ExchangeType
)


class TestPrice:
    """Price 테스트"""
    
    def test_price_creation(self):
        """가격 객체 생성"""
        price = Price(
            exchange=ExchangeType.UPBIT,
            symbol="KRW-BTC",
            bid=50_000_000,
            ask=50_100_000,
            timestamp=datetime.utcnow()
        )
        
        assert price.exchange == ExchangeType.UPBIT
        assert price.symbol == "KRW-BTC"
        assert price.bid == 50_000_000
        assert price.ask == 50_100_000
    
    def test_price_mid(self):
        """중간값 계산"""
        price = Price(
            exchange=ExchangeType.UPBIT,
            symbol="KRW-BTC",
            bid=50_000_000,
            ask=50_100_000,
            timestamp=datetime.utcnow()
        )
        
        assert price.mid == 50_050_000
    
    def test_price_spread(self):
        """스프레드 계산"""
        price = Price(
            exchange=ExchangeType.UPBIT,
            symbol="KRW-BTC",
            bid=50_000_000,
            ask=50_100_000,
            timestamp=datetime.utcnow()
        )
        
        assert price.spread == 100_000


class TestOrder:
    """Order 테스트"""
    
    def test_order_creation(self):
        """주문 객체 생성"""
        order = Order(
            order_id="order_123",
            exchange=ExchangeType.UPBIT,
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_000_000,
            status=OrderStatus.PENDING
        )
        
        assert order.order_id == "order_123"
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.PENDING
    
    def test_order_fill_rate(self):
        """체결율 계산"""
        order = Order(
            order_id="order_123",
            exchange=ExchangeType.UPBIT,
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_000_000,
            status=OrderStatus.PARTIALLY_FILLED,
            filled_quantity=0.5
        )
        
        assert order.fill_rate == 0.5


class TestPosition:
    """Position 테스트"""
    
    def test_position_creation(self):
        """포지션 객체 생성"""
        position = Position(
            symbol="KRW-BTC",
            quantity=1.0,
            entry_price=50_000_000,
            current_price=50_500_000,
            side=OrderSide.BUY
        )
        
        assert position.symbol == "KRW-BTC"
        assert position.quantity == 1.0
    
    def test_position_pnl_buy(self):
        """매수 포지션 손익"""
        position = Position(
            symbol="KRW-BTC",
            quantity=1.0,
            entry_price=50_000_000,
            current_price=50_500_000,
            side=OrderSide.BUY
        )
        
        assert position.pnl == 500_000
        assert position.pnl_pct == pytest.approx(0.01, rel=1e-3)
    
    def test_position_pnl_sell(self):
        """매도 포지션 손익"""
        position = Position(
            symbol="KRW-BTC",
            quantity=1.0,
            entry_price=50_000_000,
            current_price=49_500_000,
            side=OrderSide.SELL
        )
        
        assert position.pnl == 500_000
        assert position.pnl_pct == pytest.approx(0.01, rel=1e-3)


class TestSignal:
    """Signal 테스트"""
    
    def test_signal_creation(self):
        """신호 객체 생성"""
        signal = Signal(
            symbol="BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=50_000_000,
            sell_price=50_500_000,
            spread=500_000,
            spread_pct=1.0
        )
        
        assert signal.symbol == "BTC"
        assert signal.is_profitable
    
    def test_signal_not_profitable(self):
        """수익성 없는 신호"""
        signal = Signal(
            symbol="BTC",
            buy_exchange=ExchangeType.UPBIT,
            sell_exchange=ExchangeType.BINANCE,
            buy_price=50_000_000,
            sell_price=49_500_000,
            spread=-500_000,
            spread_pct=-1.0
        )
        
        assert not signal.is_profitable


class TestExecutionResult:
    """ExecutionResult 테스트"""
    
    def test_execution_creation(self):
        """실행 결과 객체 생성"""
        execution = ExecutionResult(
            symbol="BTC",
            buy_order_id="buy_123",
            sell_order_id="sell_123",
            buy_price=50_000_000,
            sell_price=50_500_000,
            quantity=1.0,
            gross_pnl=500_000,
            net_pnl=499_000,
            fees=1_000
        )
        
        assert execution.symbol == "BTC"
        assert execution.net_pnl == 499_000
    
    def test_execution_pnl_pct(self):
        """수익률 계산"""
        execution = ExecutionResult(
            symbol="BTC",
            buy_order_id="buy_123",
            sell_order_id="sell_123",
            buy_price=50_000_000,
            sell_price=50_500_000,
            quantity=1.0,
            gross_pnl=500_000,
            net_pnl=499_000,
            fees=1_000
        )
        
        expected_pnl_pct = 499_000 / (50_000_000 * 1.0)
        assert execution.pnl_pct == pytest.approx(expected_pnl_pct, rel=1e-3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
