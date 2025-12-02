#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D17 Tests — Simulated Exchange
===============================

SimulatedExchange 단위 테스트.
"""

import pytest
import asyncio
from arbitrage.exchanges.simulated_exchange import SimulatedExchange
from arbitrage.types import OrderSide, OrderStatus, ExchangeType


class TestSimulatedExchange:
    """SimulatedExchange 테스트"""
    
    @pytest.fixture
    def exchange(self):
        """거래소 픽스처"""
        ex = SimulatedExchange(
            exchange_type=ExchangeType.UPBIT,
            initial_balance={"KRW": 10_000_000, "BTC": 0},
            slippage_bps=5.0,
            fee_bps=2.5
        )
        return ex
    
    def test_initialization(self):
        """초기화"""
        ex = SimulatedExchange()
        assert ex.exchange_type == ExchangeType.UPBIT
        assert ex.balance["KRW"] == 10_000_000
        assert ex.slippage_bps == 5.0
    
    @pytest.mark.asyncio
    async def test_get_balance(self, exchange):
        """잔액 조회"""
        await exchange.connect()
        balance = await exchange.get_balance()
        await exchange.disconnect()
        assert balance["KRW"] == 10_000_000
    
    @pytest.mark.asyncio
    async def test_set_price(self, exchange):
        """가격 설정"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        price = await exchange.get_ticker("KRW-BTC")
        await exchange.disconnect()
        
        assert price is not None
        assert price.bid == 50_000_000
        assert price.ask == 50_100_000
    
    @pytest.mark.asyncio
    async def test_market_buy_order(self, exchange):
        """시장가 매수 주문"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        
        order = await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_100_000
        )
        await exchange.disconnect()
        
        assert order is not None
        assert order.status == OrderStatus.FILLED
        assert order.filled_quantity == 1.0
    
    @pytest.mark.asyncio
    async def test_market_sell_order(self, exchange):
        """시장가 매도 주문"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        buy_order = await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_100_000
        )
        
        sell_order = await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.SELL,
            quantity=1.0,
            price=50_000_000
        )
        await exchange.disconnect()
        
        assert sell_order is not None
        assert sell_order.status == OrderStatus.FILLED
    
    @pytest.mark.asyncio
    async def test_partial_fill(self, exchange):
        """부분 체결"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        exchange._order_books["KRW-BTC"].ask_volume = 0.5
        
        order = await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_100_000
        )
        await exchange.disconnect()
        
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert order.filled_quantity < order.quantity
    
    @pytest.mark.asyncio
    async def test_slippage(self, exchange):
        """슬리피지 적용"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        initial_balance = exchange.balance["KRW"]
        
        order = await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_100_000
        )
        await exchange.disconnect()
        
        cost = initial_balance - exchange.balance["KRW"]
        assert cost > 50_100_000
    
    @pytest.mark.asyncio
    async def test_fee_calculation(self, exchange):
        """수수료 계산"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        
        initial_fees = exchange.total_fees
        
        await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_100_000
        )
        await exchange.disconnect()
        
        assert exchange.total_fees > initial_fees
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, exchange):
        """주문 취소"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        
        order = await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_100_000
        )
        
        result = await exchange.cancel_order(order.order_id)
        await exchange.disconnect()
        
        assert not result
    
    @pytest.mark.asyncio
    async def test_get_order_status(self, exchange):
        """주문 상태 조회"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        
        order = await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_100_000
        )
        
        retrieved = await exchange.get_order_status(order.order_id)
        await exchange.disconnect()
        
        assert retrieved is not None
        assert retrieved.order_id == order.order_id
        assert retrieved.status == OrderStatus.FILLED
    
    @pytest.mark.asyncio
    async def test_get_stats(self, exchange):
        """통계 조회"""
        await exchange.connect()
        exchange.set_price("KRW-BTC", 50_000_000, 50_100_000)
        
        await exchange.place_order(
            symbol="KRW-BTC",
            side=OrderSide.BUY,
            quantity=1.0,
            price=50_100_000
        )
        await exchange.disconnect()
        
        stats = exchange.get_stats()
        assert stats["total_trades"] == 1
        assert stats["total_fees"] > 0
        assert stats["orders_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
