# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Layer - Base Interface

공통 거래소 인터페이스 정의.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Union

from arbitrage.common.currency import Currency, Money

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """주문 방향"""
    BUY = "BUY"
    SELL = "SELL"


class PositionSide(str, Enum):
    """포지션 방향 (선물용)"""
    LONG = "LONG"
    SHORT = "SHORT"


class OrderType(str, Enum):
    """주문 유형"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class TimeInForce(str, Enum):
    """주문 유효 기간"""
    GTC = "GTC"  # Good-Till-Canceled
    IOC = "IOC"  # Immediate-Or-Cancel
    FOK = "FOK"  # Fill-Or-Kill


class OrderStatus(str, Enum):
    """주문 상태"""
    PENDING = "PENDING"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"


@dataclass
class OrderBookSnapshot:
    """호가 스냅샷"""
    symbol: str
    timestamp: float
    bids: List[tuple]  # [(price, qty), ...]
    asks: List[tuple]  # [(price, qty), ...]
    
    def best_bid(self) -> Optional[float]:
        """최고 매수가"""
        return self.bids[0][0] if self.bids else None
    
    def best_ask(self) -> Optional[float]:
        """최저 매도가"""
        return self.asks[0][0] if self.asks else None


@dataclass
class Balance:
    """자산 잔고"""
    asset: str
    free: float
    locked: float
    
    @property
    def total(self) -> float:
        """총 잔고"""
        return self.free + self.locked


@dataclass
class Position:
    """포지션 (선물용)"""
    symbol: str
    side: PositionSide
    qty: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int = 1


@dataclass
class OrderResult:
    """주문 결과"""
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    price: Optional[float]
    order_type: OrderType
    status: OrderStatus
    filled_qty: float = 0.0
    timestamp: float = field(default_factory=lambda: __import__('time').time())
    
    @property
    def is_filled(self) -> bool:
        """완전 체결 여부"""
        return self.status == OrderStatus.FILLED
    
    @property
    def is_open(self) -> bool:
        """미체결 여부"""
        return self.status in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]
    
    def to_dict(self) -> Dict[str, Any]:
        """D70: JSON 직렬화를 위한 dict 변환"""
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side.value if hasattr(self.side, 'value') else str(self.side),
            'qty': self.qty,
            'price': self.price,
            'order_type': self.order_type.value if hasattr(self.order_type, 'value') else str(self.order_type),
            'status': self.status.value if hasattr(self.status, 'value') else str(self.status),
            'filled_qty': self.filled_qty,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderResult':
        """D70: dict에서 OrderResult 객체 복원"""
        return cls(
            order_id=data['order_id'],
            symbol=data['symbol'],
            side=OrderSide(data['side']) if isinstance(data['side'], str) else data['side'],
            qty=data['qty'],
            price=data.get('price'),
            order_type=OrderType(data['order_type']) if isinstance(data['order_type'], str) else data['order_type'],
            status=OrderStatus(data['status']) if isinstance(data['status'], str) else data['status'],
            filled_qty=data.get('filled_qty', 0.0),
            timestamp=data.get('timestamp', __import__('time').time())
        )


class BaseExchange(ABC):
    """
    거래소 어댑터 기본 인터페이스.
    
    모든 거래소 어댑터는 이 클래스를 상속받아 구현해야 한다.
    
    D80-2: base_currency 속성 및 make_money() 헬퍼 추가
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            name: 거래소 이름 (upbit, binance, paper 등)
            config: 설정 dict (API 키, 엔드포인트 등)
        """
        self.name = name
        self.config = config or {}
        self.base_currency: Currency = self._infer_base_currency()  # D80-2
        logger.info(f"[D42_EXCHANGE] {name} initialized (base_currency={self.base_currency.value})")
    
    def _infer_base_currency(self) -> Currency:
        """
        D80-2: 거래소별 기본 통화 추론
        
        Returns:
            Currency (기본값: KRW)
        
        Note:
            하위 클래스에서 override하여 거래소별 통화 설정
        """
        return self.config.get("base_currency", Currency.KRW)
    
    def make_money(
        self,
        amount: Union[Decimal, float, int],
        currency: Optional[Currency] = None
    ) -> Money:
        """
        D80-2: Money 객체 생성 헬퍼
        
        Args:
            amount: 금액 (Decimal, float, int)
            currency: 통화 (기본값: self.base_currency)
        
        Returns:
            Money 객체
        
        Example:
            >>> exchange.make_money(10000)  # Money(Decimal("10000"), Currency.KRW)
            >>> exchange.make_money(100, Currency.USDT)  # Money(Decimal("100"), Currency.USDT)
        """
        if currency is None:
            currency = self.base_currency
        return Money(Decimal(str(amount)), currency)
    
    @abstractmethod
    def get_orderbook(self, symbol: str) -> OrderBookSnapshot:
        """
        호가 정보 조회.
        
        Args:
            symbol: 거래 쌍 (예: "BTC-KRW", "BTCUSDT")
        
        Returns:
            OrderBookSnapshot
        """
        pass
    
    @abstractmethod
    def get_balance(self) -> Dict[str, Balance]:
        """
        자산 잔고 조회.
        
        Returns:
            {asset: Balance, ...}
        """
        pass
    
    @abstractmethod
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> OrderResult:
        """
        주문 생성.
        
        Args:
            symbol: 거래 쌍
            side: 주문 방향 (BUY/SELL)
            qty: 주문 수량
            price: 주문 가격 (MARKET 주문 시 None)
            order_type: 주문 유형 (LIMIT/MARKET)
            time_in_force: 주문 유효 기간
        
        Returns:
            OrderResult
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        주문 취소.
        
        Args:
            order_id: 주문 ID
        
        Returns:
            성공 여부
        """
        pass
    
    @abstractmethod
    def get_open_positions(self) -> List[Position]:
        """
        미결제 포지션 조회 (선물용).
        
        Returns:
            포지션 리스트
        """
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderResult:
        """
        주문 상태 조회.
        
        Args:
            order_id: 주문 ID
        
        Returns:
            OrderResult
        """
        pass
