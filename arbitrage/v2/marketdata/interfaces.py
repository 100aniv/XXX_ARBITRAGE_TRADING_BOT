"""
D202-1: MarketData Provider Interfaces (REST/WS)

V2 계약:
- RestProvider: ticker/orderbook/trades 동기 조회
- WsProvider: L2 orderbook 실시간 스트림
- 모든 구현체는 reconnect/health check 지원
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Ticker:
    """Ticker 데이터 (거래소 공통 포맷)"""
    exchange: str
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume: float
    bid_size: Optional[float] = None  # D205-14-5: top-of-book bid size
    ask_size: Optional[float] = None  # D205-14-5: top-of-book ask size


@dataclass
class OrderbookLevel:
    """Orderbook 레벨 (price, quantity)"""
    price: float
    quantity: float


@dataclass
class Orderbook:
    """Orderbook 데이터 (L2)"""
    exchange: str
    symbol: str
    timestamp: datetime
    bids: List[OrderbookLevel]  # 매수 호가 (내림차순)
    asks: List[OrderbookLevel]  # 매도 호가 (오름차순)


@dataclass
class Trade:
    """Trade 데이터 (체결)"""
    exchange: str
    symbol: str
    timestamp: datetime
    price: float
    quantity: float
    side: str  # "buy" or "sell"


class RestProvider(ABC):
    """
    REST API Provider 인터페이스
    
    책임:
    - ticker/orderbook/trades 조회 (동기)
    - Rate limit 준수
    - 에러 핸들링
    """
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """Ticker 조회"""
        pass
    
    @abstractmethod
    def get_orderbook(self, symbol: str, depth: int = 20) -> Optional[Orderbook]:
        """Orderbook 조회 (L2)"""
        pass
    
    @abstractmethod
    def get_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """최근 체결 조회"""
        pass


class WsProvider(ABC):
    """
    WebSocket Provider 인터페이스
    
    책임:
    - L2 orderbook 실시간 스트림
    - 자동 재연결 (exponential backoff)
    - Health check
    """
    
    @abstractmethod
    async def connect(self) -> None:
        """WebSocket 연결"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """WebSocket 연결 종료"""
        pass
    
    @abstractmethod
    async def subscribe(self, symbols: List[str]) -> None:
        """심볼 구독"""
        pass
    
    @abstractmethod
    def get_latest_orderbook(self, symbol: str) -> Optional[Orderbook]:
        """최신 orderbook 스냅샷 (메모리 버퍼)"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """연결 상태 확인"""
        pass
