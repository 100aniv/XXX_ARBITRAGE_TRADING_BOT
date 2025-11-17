#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Order Manager (PHASE D7)
=========================

주문 실행 및 체결 추적.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class Order:
    """주문"""
    
    def __init__(
        self,
        order_id: str,
        exchange: str,
        symbol: str,
        side: str,  # BUY | SELL
        quantity: float,
        price: float,
        order_type: str = "LIMIT"
    ):
        self.order_id = order_id
        self.exchange = exchange
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.order_type = order_type
        
        self.status = OrderStatus.PENDING
        self.filled_quantity = 0.0
        self.average_fill_price = 0.0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.latency_ms = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "order_id": self.order_id,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": self.average_fill_price,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class OrderManager:
    """주문 관리자"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 설정 딕셔너리
        """
        self.config = config or {}
        self.orders: Dict[str, Order] = {}
        
        # 주문 설정
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 1)  # 초
        self.order_timeout = self.config.get("order_timeout", 60)  # 초
        
        # 슬리피지 허용 범위 (%)
        self.slippage_tolerance = self.config.get("slippage_tolerance", 0.5)
    
    def create_order(
        self,
        exchange: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        order_type: str = "LIMIT"
    ) -> Order:
        """
        주문 생성
        
        Args:
            exchange: 거래소
            symbol: 심볼
            side: BUY | SELL
            quantity: 수량
            price: 가격
            order_type: LIMIT | MARKET
        
        Returns:
            Order 객체
        """
        order_id = f"{exchange}_{symbol}_{int(time.time() * 1000)}"
        order = Order(
            order_id=order_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type
        )
        self.orders[order_id] = order
        return order
    
    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_quantity: float = 0.0,
        average_fill_price: float = 0.0,
        latency_ms: float = 0.0
    ):
        """
        주문 상태 업데이트
        
        Args:
            order_id: 주문 ID
            status: 주문 상태
            filled_quantity: 체결 수량
            average_fill_price: 평균 체결가
            latency_ms: 지연 시간 (ms)
        """
        if order_id not in self.orders:
            return
        
        order = self.orders[order_id]
        order.status = status
        order.filled_quantity = filled_quantity
        order.average_fill_price = average_fill_price
        order.latency_ms = latency_ms
        order.updated_at = datetime.now()
        
        logger.debug(
            f"[OrderManager] Order {order_id} updated: "
            f"status={status.value}, filled={filled_quantity}, latency={latency_ms:.1f}ms"
        )
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """주문 조회"""
        return self.orders.get(order_id)
    
    def get_pending_orders(self) -> List[Order]:
        """대기 중인 주문 조회"""
        return [
            order for order in self.orders.values()
            if order.status in [OrderStatus.PENDING, OrderStatus.PARTIAL]
        ]
    
    def is_order_filled(self, order_id: str) -> bool:
        """주문 체결 여부"""
        order = self.get_order(order_id)
        return order and order.status == OrderStatus.FILLED
    
    def is_order_timeout(self, order_id: str) -> bool:
        """주문 타임아웃 여부"""
        order = self.get_order(order_id)
        if not order:
            return False
        
        elapsed = (datetime.now() - order.created_at).total_seconds()
        return elapsed > self.order_timeout
    
    def calculate_slippage(self, order_id: str) -> float:
        """슬리피지 계산 (%)"""
        order = self.get_order(order_id)
        if not order or order.average_fill_price == 0:
            return 0.0
        
        slippage = abs(order.price - order.average_fill_price) / order.price * 100
        return slippage
    
    def is_slippage_acceptable(self, order_id: str) -> bool:
        """슬리피지 허용 범위 확인"""
        slippage = self.calculate_slippage(order_id)
        return slippage <= self.slippage_tolerance
