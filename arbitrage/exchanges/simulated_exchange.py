#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D17 Paper/Shadow Mode Simulated Exchange
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
    """Simple orderbook model"""
    
    def __init__(self, symbol: str, bid: float, ask: float):
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.bid_volume = 1000.0
        self.ask_volume = 1000.0


class SimulatedExchange:
    """
    Simulated Exchange for Paper/Shadow mode
    """
    
    def __init__(
        self,
        exchange_type: ExchangeType = ExchangeType.UPBIT,
        initial_balance: Dict[str, float] = None,
        slippage_bps: float = 5.0,
        fee_bps: float = 2.5,
        latency_ms: float = 100.0
    ):
        self.exchange_type = exchange_type
        self.slippage_bps = slippage_bps
        self.fee_bps = fee_bps
        self.latency_ms = latency_ms
        
        self.balance = initial_balance or {"KRW": 10_000_000, "USDT": 1000}
        self._order_books: Dict[str, OrderBook] = {}
        self._orders: Dict[str, Order] = {}
        self.total_trades = 0
        self.total_fees = 0.0
        
        logger.info(
            f"SimulatedExchange initialized: {exchange_type.value}, "
            f"balance={self.balance}"
        )
    
    def update_orderbook(self, symbol: str, bid: float, ask: float) -> None:
        """Update orderbook prices"""
        self._order_books[symbol] = OrderBook(symbol, bid, ask)
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: Optional[float] = None
    ) -> Order:
        """Place order (simulated)"""
        order_id = str(uuid.uuid4())
        
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price or 0.0,
            status=OrderStatus.PENDING,
            filled_quantity=0.0,
            timestamp=datetime.now(timezone.utc)
        )
        
        await self._simulate_execution(order)
        
        self._orders[order_id] = order
        self.total_trades += 1
        
        logger.info(
            f"Order placed: {order_id} {side.value} {quantity} @ {price} "
            f"(filled: {order.filled_quantity})"
        )
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        if order_id not in self._orders:
            return False
        
        order = self._orders[order_id]
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return False
        
        order.status = OrderStatus.CANCELLED
        logger.info(f"Order cancelled: {order_id}")
        
        return True
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get order status"""
        return self._orders.get(order_id)
    
    async def subscribe_prices(
        self,
        symbols: List[str],
        callback: callable
    ) -> None:
        """Subscribe to price updates (no-op for simulated)"""
        logger.info(f"Subscribed to {len(symbols)} symbols (simulated)")
    
    async def _simulate_execution(self, order: Order) -> None:
        """Simulate order execution"""
        if order.symbol not in self._order_books:
            order.status = OrderStatus.PENDING
            return
        
        ob = self._order_books[order.symbol]
        
        slippage_ratio = self.slippage_bps / 10000
        
        if order.side == OrderSide.BUY:
            execution_price = ob.ask * (1 + slippage_ratio)
            
            if order.quantity <= ob.ask_volume:
                order.filled_quantity = order.quantity
                order.status = OrderStatus.FILLED
            else:
                order.filled_quantity = ob.ask_volume * 0.8
                order.status = OrderStatus.PARTIALLY_FILLED
        
        else:  # SELL
            execution_price = ob.bid * (1 - slippage_ratio)
            
            if order.quantity <= ob.bid_volume:
                order.filled_quantity = order.quantity
                order.status = OrderStatus.FILLED
            else:
                order.filled_quantity = ob.bid_volume * 0.8
                order.status = OrderStatus.PARTIALLY_FILLED
        
        fee_ratio = self.fee_bps / 10000
        fee = order.filled_quantity * execution_price * fee_ratio
        self.total_fees += fee
        
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
        """Get exchange stats"""
        return {
            "total_trades": self.total_trades,
            "total_fees": self.total_fees,
            "balance": self.balance.copy(),
            "orders_count": len(self._orders),
        }
