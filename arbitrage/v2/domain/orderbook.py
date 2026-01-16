"""
D206-1: OrderBookSnapshot Domain Model

V1 arbitrage_core.py 정의 기반으로 V2에서 재사용.
HFT Readiness + Commercial UI 직렬화 추가.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class OrderBookSnapshot:
    """
    호가 스냅샷 (양방향 거래소)
    
    V1 정의 (arbitrage/arbitrage_core.py Line 35-42) 기반.
    
    Fields (V1):
        timestamp: ISO 8601 형식 타임스탬프
        best_bid_a: Exchange A 최고 매수가
        best_ask_a: Exchange A 최저 매도가
        best_bid_b: Exchange B 최고 매수가
        best_ask_b: Exchange B 최저 매도가
    
    Fields (HFT Readiness - Optional):
        obi_score: Order Book Imbalance score (Aldridge model)
        depth_imbalance: 호가 깊이 불균형 (bid_depth / ask_depth)
        spread_a_bps: Exchange A spread (bps)
        spread_b_bps: Exchange B spread (bps)
    
    Invariants:
        - best_bid_a < best_ask_a (no crossed market)
        - best_bid_b < best_ask_b (no crossed market)
        - all prices > 0
        - timestamp exists
    """
    
    timestamp: str
    best_bid_a: float
    best_ask_a: float
    best_bid_b: float
    best_ask_b: float
    
    # HFT Readiness (D214 예비)
    obi_score: Optional[float] = None
    depth_imbalance: Optional[float] = None
    spread_a_bps: Optional[float] = None
    spread_b_bps: Optional[float] = None
    
    # Metadata
    symbol: Optional[str] = None
    exchange_a: Optional[str] = None
    exchange_b: Optional[str] = None
    
    def __post_init__(self):
        """불변 조건 검증"""
        # Price validation
        if self.best_bid_a <= 0 or self.best_ask_a <= 0:
            raise ValueError(f"Exchange A prices must be > 0 (bid={self.best_bid_a}, ask={self.best_ask_a})")
        if self.best_bid_b <= 0 or self.best_ask_b <= 0:
            raise ValueError(f"Exchange B prices must be > 0 (bid={self.best_bid_b}, ask={self.best_ask_b})")
        
        # No crossed market
        if self.best_bid_a >= self.best_ask_a:
            raise ValueError(f"Exchange A crossed market (bid={self.best_bid_a} >= ask={self.best_ask_a})")
        if self.best_bid_b >= self.best_ask_b:
            raise ValueError(f"Exchange B crossed market (bid={self.best_bid_b} >= ask={self.best_ask_b})")
        
        # Timestamp exists
        if not self.timestamp:
            raise ValueError("Timestamp is required")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        JSON 직렬화 (Evidence/DB/로그)
        
        Returns:
            dict with all fields
        """
        return {
            'timestamp': self.timestamp,
            'best_bid_a': self.best_bid_a,
            'best_ask_a': self.best_ask_a,
            'best_bid_b': self.best_bid_b,
            'best_ask_b': self.best_ask_b,
            'obi_score': self.obi_score,
            'depth_imbalance': self.depth_imbalance,
            'spread_a_bps': self.spread_a_bps,
            'spread_b_bps': self.spread_b_bps,
            'symbol': self.symbol,
            'exchange_a': self.exchange_a,
            'exchange_b': self.exchange_b,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderBookSnapshot':
        """
        JSON 역직렬화
        
        Args:
            data: dict with required fields
        
        Returns:
            OrderBookSnapshot instance
        """
        return cls(
            timestamp=data['timestamp'],
            best_bid_a=data['best_bid_a'],
            best_ask_a=data['best_ask_a'],
            best_bid_b=data['best_bid_b'],
            best_ask_b=data['best_ask_b'],
            obi_score=data.get('obi_score'),
            depth_imbalance=data.get('depth_imbalance'),
            spread_a_bps=data.get('spread_a_bps'),
            spread_b_bps=data.get('spread_b_bps'),
            symbol=data.get('symbol'),
            exchange_a=data.get('exchange_a'),
            exchange_b=data.get('exchange_b'),
        )
    
    def to_ui_dict(self) -> Dict[str, Any]:
        """
        Commercial UI 직렬화 (D210/D218 FastAPI + React 대응)
        
        Returns:
            UI-friendly dict (compact, human-readable)
        """
        return {
            'timestamp': self.timestamp,
            'exchanges': {
                'a': {
                    'name': self.exchange_a or 'Exchange A',
                    'bid': self.best_bid_a,
                    'ask': self.best_ask_a,
                    'spread_bps': self.spread_a_bps,
                },
                'b': {
                    'name': self.exchange_b or 'Exchange B',
                    'bid': self.best_bid_b,
                    'ask': self.best_ask_b,
                    'spread_bps': self.spread_b_bps,
                },
            },
            'symbol': self.symbol,
            'hft_signals': {
                'obi_score': self.obi_score,
                'depth_imbalance': self.depth_imbalance,
            } if (self.obi_score is not None or self.depth_imbalance is not None) else None,
        }
