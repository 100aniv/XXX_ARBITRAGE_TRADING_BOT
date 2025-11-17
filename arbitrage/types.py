#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — Common Type Definitions
============================================

실거래 모듈에서 사용하는 공통 타입 및 데이터 클래스.

D57: Multi-Symbol Portfolio Integration
- PortfolioState에 symbol-aware 필드 추가
- Per-symbol position tracking 지원
- 단일 심볼 모드 100% 호환성 유지
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
    # D57: Multi-Symbol 확장 필드
    symbol_context: Optional[str] = None  # 심볼이 속한 컨텍스트 (예: "KRW-BTC", "BTCUSDT")
    
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
    # D57: Multi-Symbol 확장 필드
    symbol: Optional[str] = None  # 단일 심볼 모드일 때 심볼 지정
    per_symbol_positions: Dict[str, Dict[str, Position]] = field(default_factory=dict)  # {symbol: {pos_id: Position}}
    per_symbol_orders: Dict[str, Dict[str, Order]] = field(default_factory=dict)  # {symbol: {order_id: Order}}
    
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
    
    def get_symbol_positions(self, symbol: str) -> Dict[str, Position]:
        """
        D57: 특정 심볼의 포지션 조회
        
        Args:
            symbol: 심볼
        
        Returns:
            심볼별 포지션 딕셔너리
        """
        return self.per_symbol_positions.get(symbol, {})
    
    def get_symbol_orders(self, symbol: str) -> Dict[str, Order]:
        """
        D57: 특정 심볼의 주문 조회
        
        Args:
            symbol: 심볼
        
        Returns:
            심볼별 주문 딕셔너리
        """
        return self.per_symbol_orders.get(symbol, {})
    
    def add_symbol_position(self, symbol: str, position_id: str, position: Position) -> None:
        """
        D57: 심볼별 포지션 추가
        
        Args:
            symbol: 심볼
            position_id: 포지션 ID
            position: Position 객체
        """
        if symbol not in self.per_symbol_positions:
            self.per_symbol_positions[symbol] = {}
        self.per_symbol_positions[symbol][position_id] = position
    
    def add_symbol_order(self, symbol: str, order_id: str, order: Order) -> None:
        """
        D57: 심볼별 주문 추가
        
        Args:
            symbol: 심볼
            order_id: 주문 ID
            order: Order 객체
        """
        if symbol not in self.per_symbol_orders:
            self.per_symbol_orders[symbol] = {}
        self.per_symbol_orders[symbol][order_id] = order
    
    def get_total_symbol_position_value(self, symbol: str) -> float:
        """
        D57: 특정 심볼의 총 포지션 가치
        
        Args:
            symbol: 심볼
        
        Returns:
            포지션 총 가치
        """
        positions = self.get_symbol_positions(symbol)
        return sum(pos.quantity * pos.current_price for pos in positions.values())
