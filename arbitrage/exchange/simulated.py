#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D17 Paper/Shadow Mode — Simulated Exchange
===========================================

Upbit/Binance와 동일한 인터페이스를 가진 시뮬레이션 거래소.
주문 체결, 슬리피지, 수수료, 부분 체결, 취소, 지연 시뮬레이션.
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
import numpy as np

from arbitrage.types import (
    Price, Order, OrderSide, OrderStatus, ExchangeType, Position
)

logger = logging.getLogger(__name__)


class OrderBook:
    """주문장"""
    
    def __init__(self, symbol: str, bid: float, ask: float):
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.bid_volume = 1000.0  # 기본 유동성
        self.ask_volume = 1000.0


class SimulatedExchange:
    """
    시뮬레이션 거래소
    
    Paper/Shadow 모드에서 사용.
    실제 거래소 API 호출 없이 시뮬레이션된 주문 체결.
    """
    
    def __init__(
        self,
        exchange_type: ExchangeType = ExchangeType.UPBIT,
        initial_balance: Dict[str, float] = None,
        slippage_bps: float = 5.0,  # 슬리피지 (기본 5bp)
        fee_bps: float = 2.5,  # 수수료 (기본 2.5bp)
        latency_ms: float = 100.0  # 지연 (기본 100ms)
    ):
        """
        Args:
            exchange_type: 거래소 타입
            initial_balance: 초기 잔액 {asset: amount}
            slippage_bps: 슬리피지 (basis points)
            fee_bps: 수수료 (basis points)
            latency_ms: 네트워크 지연 (밀리초)
        """
        self.exchange_type = exchange_type
        self.slippage_bps = slippage_bps
        self.fee_bps = fee_bps
        self.latency_ms = latency_ms
        
        # 잔액
        self.balance = initial_balance or {"KRW": 10_000_000, "USDT": 1000}
        
        # 주문 기록
        self._orders: Dict[str, Order] = {}
        self._order_books: Dict[str, OrderBook] = {}
        self._positions: Dict[str, Position] = {}
        
        # 통계
        self.total_fees = 0.0
        self.total_trades = 0
    
    async def connect(self) -> None:
        """연결 (no-op)"""
        logger.info(f"Simulated {self.exchange_type.value} exchange connected")
    
    async def disconnect(self) -> None:
        """연결 해제 (no-op)"""
        logger.info(f"Simulated {self.exchange_type.value} exchange disconnected")
    
    async def get_balance(self) -> Dict[str, float]:
        """잔액 조회"""
        return self.balance.copy()
    
    async def get_ticker(self, symbol: str) -> Optional[Price]:
        """현재 가격 조회"""
        if symbol not in self._order_books:
            return None
        
        ob = self._order_books[symbol]
        return Price(
            exchange=self.exchange_type,
            symbol=symbol,
            bid=ob.bid,
            ask=ob.ask,
            timestamp=datetime.now(timezone.utc)
        )
    
    def set_price(self, symbol: str, bid: float, ask: float) -> None:
        """
        가격 설정 (시나리오용)
        
        Args:
            symbol: 심볼
            bid: 매수호가
            ask: 매도호가
        """
        self._order_books[symbol] = OrderBook(symbol, bid, ask)
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float
    ) -> Optional[Order]:
        """
        주문 생성
        
        Args:
            symbol: 심볼
            side: 주문 방향
            quantity: 수량
            price: 가격
        
        Returns:
            Order 객체 또는 None
        """
        order_id = str(uuid.uuid4())[:8]
        
        # 주문 생성
        order = Order(
            order_id=order_id,
            exchange=self.exchange_type,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        
        # 즉시 체결 시뮬레이션
        await self._simulate_execution(order)
        
        self._orders[order_id] = order
        self.total_trades += 1
        
        logger.info(
            f"Order placed: {order_id} {side.value} {quantity} @ {price} "
            f"(filled: {order.filled_quantity})"
        )
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        if order_id not in self._orders:
            return False
        
        order = self._orders[order_id]
        
        # 미체결 부분만 취소 가능
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return False
        
        order.status = OrderStatus.CANCELLED
        logger.info(f"Order cancelled: {order_id}")
        
        return True
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """주문 상태 조회"""
        return self._orders.get(order_id)
    
    async def subscribe_prices(
        self,
        symbols: List[str],
        callback: callable
    ) -> None:
        """
        가격 구독 (no-op, 시나리오용)
        
        Args:
            symbols: 심볼 목록
            callback: 콜백 (사용하지 않음)
        """
        logger.info(f"Subscribed to {len(symbols)} symbols (simulated)")
    
    async def _simulate_execution(self, order: Order) -> None:
        """
        주문 체결 시뮬레이션
        
        Args:
            order: 주문
        """
        if order.symbol not in self._order_books:
            # 주문장 없으면 미체결
            order.status = OrderStatus.PENDING
            return
        
        ob = self._order_books[order.symbol]
        
        # 슬리피지 적용
        slippage_ratio = self.slippage_bps / 10000
        
        if order.side == OrderSide.BUY:
            # 매수: ask 가격에 슬리피지 추가
            execution_price = ob.ask * (1 + slippage_ratio)
            
            # 유동성 확인
            if order.quantity <= ob.ask_volume:
                # 전부 체결
                order.filled_quantity = order.quantity
                order.status = OrderStatus.FILLED
            else:
                # 부분 체결
                order.filled_quantity = ob.ask_volume * 0.8  # 80% 체결
                order.status = OrderStatus.PARTIALLY_FILLED
        
        else:  # SELL
            # 매도: bid 가격에 슬리피지 차감
            execution_price = ob.bid * (1 - slippage_ratio)
            
            # 유동성 확인
            if order.quantity <= ob.bid_volume:
                # 전부 체결
                order.filled_quantity = order.quantity
                order.status = OrderStatus.FILLED
            else:
                # 부분 체결
                order.filled_quantity = ob.bid_volume * 0.8
                order.status = OrderStatus.PARTIALLY_FILLED
        
        # 수수료 계산
        fee_ratio = self.fee_bps / 10000
        fee = order.filled_quantity * execution_price * fee_ratio
        self.total_fees += fee
        
        # 잔액 업데이트
        if order.side == OrderSide.BUY:
            cost = order.filled_quantity * execution_price + fee
            base_asset = "KRW" if self.exchange_type == ExchangeType.UPBIT else "USDT"
            self.balance[base_asset] -= cost
            
            quote_asset = order.symbol.split("-")[-1] if "-" in order.symbol else order.symbol.replace("USDT", "")
            self.balance[quote_asset] = self.balance.get(quote_asset, 0) + order.filled_quantity
        
        else:  # SELL
            revenue = order.filled_quantity * execution_price - fee
            base_asset = "KRW" if self.exchange_type == ExchangeType.UPBIT else "USDT"
            self.balance[base_asset] += revenue
            
            quote_asset = order.symbol.split("-")[-1] if "-" in order.symbol else order.symbol.replace("USDT", "")
            self.balance[quote_asset] = self.balance.get(quote_asset, 0) - order.filled_quantity
        
        logger.debug(
            f"Execution simulated: {order.order_id} "
            f"filled={order.filled_quantity} @ {execution_price:.0f} "
            f"fee={fee:.0f}"
        )
    
    def get_stats(self) -> Dict:
        """통계 조회"""
        return {
            "total_trades": self.total_trades,
            "total_fees": self.total_fees,
            "balance": self.balance.copy(),
            "orders_count": len(self._orders),
        }
