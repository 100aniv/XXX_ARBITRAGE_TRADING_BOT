"""
D206-1: ArbitrageOpportunity Domain Model

V1 arbitrage_core.py 정의 기반으로 V2에서 재사용.
HFT Readiness + Commercial UI 직렬화 추가.
"""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


Side = Literal["LONG_A_SHORT_B", "LONG_B_SHORT_A"]


@dataclass
class ArbitrageOpportunity:
    """
    차익거래 기회
    
    V1 정의 (arbitrage/arbitrage_core.py Line 46-54) 기반.
    
    Fields (V1):
        timestamp: ISO 8601 타임스탬프
        side: LONG_A_SHORT_B 또는 LONG_B_SHORT_A
        spread_bps: 총 스프레드 (bps)
        gross_edge_bps: 수수료 차감 전 엣지 (bps)
        net_edge_bps: 수수료 + 슬리피지 차감 후 엣지 (bps)
        notional_usd: 거래 규모 (USD)
    
    Fields (HFT Readiness - Optional):
        inventory_score: Avellaneda-Stoikov 재고 스코어
        alpha_signal: 알파 시그널 (OBI/momentum 기반)
        execution_confidence: 실행 신뢰도 (0.0~1.0)
    
    Invariants:
        - net_edge_bps <= gross_edge_bps
        - notional_usd > 0
        - timestamp exists
        - side in ["LONG_A_SHORT_B", "LONG_B_SHORT_A"]
    """
    
    timestamp: str
    side: Side
    spread_bps: float
    gross_edge_bps: float
    net_edge_bps: float
    notional_usd: float
    
    # HFT Readiness (D214 예비)
    inventory_score: Optional[float] = None
    alpha_signal: Optional[float] = None
    execution_confidence: Optional[float] = None
    
    # Metadata
    symbol: Optional[str] = None
    exchange_a: Optional[str] = None
    exchange_b: Optional[str] = None
    
    def __post_init__(self):
        """불변 조건 검증"""
        # Edge consistency
        if self.net_edge_bps > self.gross_edge_bps:
            raise ValueError(f"net_edge ({self.net_edge_bps}) cannot exceed gross_edge ({self.gross_edge_bps})")
        
        # Notional validation
        if self.notional_usd <= 0:
            raise ValueError(f"notional_usd must be > 0 (got {self.notional_usd})")
        
        # Timestamp exists
        if not self.timestamp:
            raise ValueError("Timestamp is required")
        
        # Side validation
        if self.side not in ["LONG_A_SHORT_B", "LONG_B_SHORT_A"]:
            raise ValueError(f"Invalid side: {self.side}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        JSON 직렬화 (Evidence/DB/로그)
        
        Returns:
            dict with all fields
        """
        return {
            'timestamp': self.timestamp,
            'side': self.side,
            'spread_bps': self.spread_bps,
            'gross_edge_bps': self.gross_edge_bps,
            'net_edge_bps': self.net_edge_bps,
            'notional_usd': self.notional_usd,
            'inventory_score': self.inventory_score,
            'alpha_signal': self.alpha_signal,
            'execution_confidence': self.execution_confidence,
            'symbol': self.symbol,
            'exchange_a': self.exchange_a,
            'exchange_b': self.exchange_b,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArbitrageOpportunity':
        """
        JSON 역직렬화
        
        Args:
            data: dict with required fields
        
        Returns:
            ArbitrageOpportunity instance
        """
        return cls(
            timestamp=data['timestamp'],
            side=data['side'],
            spread_bps=data['spread_bps'],
            gross_edge_bps=data['gross_edge_bps'],
            net_edge_bps=data['net_edge_bps'],
            notional_usd=data['notional_usd'],
            inventory_score=data.get('inventory_score'),
            alpha_signal=data.get('alpha_signal'),
            execution_confidence=data.get('execution_confidence'),
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
            'direction': 'A→B' if self.side == 'LONG_A_SHORT_B' else 'B→A',
            'spread': {
                'total_bps': self.spread_bps,
                'gross_edge_bps': self.gross_edge_bps,
                'net_edge_bps': self.net_edge_bps,
            },
            'size_usd': self.notional_usd,
            'symbol': self.symbol,
            'route': {
                'from': self.exchange_b if self.side == 'LONG_A_SHORT_B' else self.exchange_a,
                'to': self.exchange_a if self.side == 'LONG_A_SHORT_B' else self.exchange_b,
            } if (self.exchange_a and self.exchange_b) else None,
            'hft_signals': {
                'inventory_score': self.inventory_score,
                'alpha_signal': self.alpha_signal,
                'execution_confidence': self.execution_confidence,
            } if any([self.inventory_score, self.alpha_signal, self.execution_confidence]) else None,
        }
    
    def is_profitable(self) -> bool:
        """
        수익성 판정
        
        Returns:
            True if net_edge_bps > 0
        """
        return self.net_edge_bps > 0
