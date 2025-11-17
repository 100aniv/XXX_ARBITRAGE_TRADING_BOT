#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Live API Base Module (PHASE D4)
================================

실거래 API 통합을 위한 기본 클래스 및 인터페이스.

특징:
- REST/WebSocket 지원
- Rate limiting 내장
- Mock mode (credentials 없을 때 자동 전환)
- 에러 처리 및 재시도 로직
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OrderRequest:
    """주문 요청"""
    symbol: str
    side: str  # BUY | SELL
    order_type: str  # LIMIT | MARKET
    quantity: float
    price: Optional[float] = None  # LIMIT 주문 시 필수


@dataclass
class OrderResponse:
    """주문 응답"""
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    status: str  # PENDING | FILLED | CANCELLED | REJECTED
    timestamp: datetime


@dataclass
class TickerData:
    """시세 데이터"""
    symbol: str
    bid: float
    ask: float
    last: float
    timestamp: datetime


class LiveAPIBase(ABC):
    """Live API 기본 클래스"""
    
    def __init__(self, config: Dict[str, Any], mock_mode: bool = False):
        """
        Args:
            config: API 설정 딕셔너리
            mock_mode: Mock 모드 활성화
        """
        self.config = config
        self.mock_mode = mock_mode
        self.logger = logging.getLogger(f"arbitrage.{self.__class__.__name__}")
        
        if self.mock_mode:
            self.logger.warning(f"[{self.__class__.__name__}] Mock mode enabled")
    
    @abstractmethod
    def connect(self) -> bool:
        """API 연결
        
        Returns:
            연결 성공 여부
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """API 연결 해제"""
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Optional[TickerData]:
        """시세 조회
        
        Args:
            symbol: 심볼 (예: BTC-KRW)
        
        Returns:
            TickerData 또는 None
        """
        pass
    
    @abstractmethod
    def place_order(self, order: OrderRequest) -> Optional[OrderResponse]:
        """주문 실행
        
        Args:
            order: OrderRequest 객체
        
        Returns:
            OrderResponse 또는 None
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소
        
        Args:
            order_id: 주문 ID
        
        Returns:
            취소 성공 여부
        """
        pass
    
    @abstractmethod
    def get_balance(self) -> Optional[Dict[str, float]]:
        """잔액 조회
        
        Returns:
            {통화: 잔액} 딕셔너리 또는 None
        """
        pass
    
    @abstractmethod
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        """열린 주문 조회
        
        Args:
            symbol: 심볼 (None이면 전체)
        
        Returns:
            OrderResponse 리스트
        """
        pass


class MockLiveAPI(LiveAPIBase):
    """Mock Live API (테스트용)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config, mock_mode=True)
        self.connected = False
        self.balance = {"KRW": 1000000.0, "BTC": 0.1, "ETH": 1.0}
        self.orders: Dict[str, OrderResponse] = {}
    
    def connect(self) -> bool:
        self.connected = True
        self.logger.info("[MockLiveAPI] Connected (mock mode)")
        return True
    
    def disconnect(self) -> None:
        self.connected = False
        self.logger.info("[MockLiveAPI] Disconnected")
    
    def get_ticker(self, symbol: str) -> Optional[TickerData]:
        # Mock 시세 데이터
        return TickerData(
            symbol=symbol,
            bid=50000000.0,
            ask=50001000.0,
            last=50000500.0,
            timestamp=datetime.now()
        )
    
    def place_order(self, order: OrderRequest) -> Optional[OrderResponse]:
        order_id = f"mock_{len(self.orders)}"
        response = OrderResponse(
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=order.price or 50000000.0,
            status="FILLED",
            timestamp=datetime.now()
        )
        self.orders[order_id] = response
        self.logger.info(f"[MockLiveAPI] Order placed: {order_id}")
        return response
    
    def cancel_order(self, order_id: str) -> bool:
        if order_id in self.orders:
            self.orders[order_id].status = "CANCELLED"
            self.logger.info(f"[MockLiveAPI] Order cancelled: {order_id}")
            return True
        return False
    
    def get_balance(self) -> Optional[Dict[str, float]]:
        return self.balance.copy()
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        orders = [o for o in self.orders.values() if o.status == "PENDING"]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders


def get_live_api(config: Dict[str, Any], exchange: str = "upbit") -> LiveAPIBase:
    """Live API 인스턴스 반환
    
    Args:
        config: 설정 딕셔너리
        exchange: 거래소 (upbit | binance)
    
    Returns:
        LiveAPIBase 인스턴스
    """
    exchange_config = config.get(exchange, {})
    
    # Mock 모드 판단
    api_key = exchange_config.get("api_key", "")
    mock_mode = not api_key or config.get("mock_mode", True)
    
    if mock_mode:
        return MockLiveAPI(exchange_config)
    
    # 실제 API 구현은 D4 확장에서 추가
    if exchange == "upbit":
        from arbitrage.upbit_live import UpbitLiveAPI
        return UpbitLiveAPI(exchange_config)
    elif exchange == "binance":
        from arbitrage.binance_live import BinanceLiveAPI
        return BinanceLiveAPI(exchange_config)
    else:
        raise ValueError(f"Unknown exchange: {exchange}")
