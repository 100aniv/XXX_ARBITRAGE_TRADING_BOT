#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — Common Type Definitions
============================================

실거래 모듈에서 사용하는 공통 타입 및 데이터 클래스.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class OrderSide(str, Enum):
    """주문 방향"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """주문 상태"""
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class ExchangeType(str, Enum):
    """거래소 타입"""
    UPBIT = "upbit"
    BINANCE = "binance"


@dataclass
class Price:
    """실시간 가격 데이터"""
    exchange: ExchangeType
    symbol: str
    bid: float
    ask: float
    timestamp: datetime
    
    @property
    def mid(self) -> float:
        """중간값"""
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        """스프레드"""
        return self.ask - self.bid


@dataclass
class Order:
    """주문 정보"""
    order_id: str
    exchange: ExchangeType
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    status: OrderStatus
    filled_quantity: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def fill_rate(self) -> float:
        """체결율"""
        if self.quantity == 0:
            return 0.0
        return self.filled_quantity / self.quantity


@dataclass
class Position:
    """포지션 정보"""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    side: OrderSide
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def pnl(self) -> float:
        """손익"""
        if self.side == OrderSide.BUY:
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity
    
    @property
    def pnl_pct(self) -> float:
        """손익률"""
        if self.entry_price == 0:
            return 0.0
        if self.side == OrderSide.BUY:
            return (self.current_price - self.entry_price) / self.entry_price
        else:
            return (self.entry_price - self.current_price) / self.entry_price


@dataclass
class Signal:
    """차익 신호"""
    symbol: str
    buy_exchange: ExchangeType
    sell_exchange: ExchangeType
    buy_price: float
    sell_price: float
    spread: float
    spread_pct: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_profitable(self) -> bool:
        """수익성 판단 (수수료 고려 전)"""
        return self.spread > 0


@dataclass
class ExecutionResult:
    """실행 결과"""
    symbol: str
    buy_order_id: str
    sell_order_id: str
    buy_price: float
    sell_price: float
    quantity: float
    gross_pnl: float
    net_pnl: float
    fees: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def pnl_pct(self) -> float:
        """수익률"""
        if self.buy_price == 0:
            return 0.0
        return self.net_pnl / (self.buy_price * self.quantity)


@dataclass
class RiskMetrics:
    """리스크 메트릭 (D15 연동)"""
    var_95: float
    var_99: float
    expected_shortfall: float
    max_drawdown: float
    sharpe_ratio: float
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PortfolioState:
    """포트폴리오 상태"""
    total_balance: float
    available_balance: float
    positions: Dict[str, Position] = field(default_factory=dict)
    orders: Dict[str, Order] = field(default_factory=dict)
    risk_metrics: Optional[RiskMetrics] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def total_position_value(self) -> float:
        """포지션 총 가치"""
        return sum(pos.quantity * pos.current_price for pos in self.positions.values())
    
    @property
    def utilization_rate(self) -> float:
        """자본 활용률"""
        if self.total_balance == 0:
            return 0.0
        return self.total_position_value / self.total_balance
