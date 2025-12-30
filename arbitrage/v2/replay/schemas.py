"""
D205-5: Record/Replay 스키마

MarketTick: 시장 데이터 기록
DecisionRecord: 의사결정 결과 기록
"""

from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime


@dataclass
class MarketTick:
    """
    시장 데이터 Tick (최소 스키마)
    
    Attributes:
        timestamp: ISO 8601 형식 타임스탬프
        symbol: "BTC/KRW" 형식
        upbit_bid: Upbit 매수 호가
        upbit_ask: Upbit 매도 호가
        binance_bid: Binance 매수 호가 (USDT)
        binance_ask: Binance 매도 호가 (USDT)
    """
    timestamp: str
    symbol: str
    upbit_bid: float
    upbit_ask: float
    binance_bid: float
    binance_ask: float
    
    def to_dict(self):
        """딕셔너리 변환"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        """딕셔너리에서 생성"""
        return cls(**data)


@dataclass
class DecisionRecord:
    """
    의사결정 결과 기록
    
    Attributes:
        timestamp: ISO 8601 형식 타임스탬프
        symbol: "BTC/KRW" 형식
        spread_bps: 스프레드 (bps)
        break_even_bps: 손익분기 (bps)
        edge_bps: 엣지 (bps)
        profitable: 수익성 여부
        gate_reasons: 차단된 게이트 리스트 (빈 리스트 = 통과)
        latency_ms: tick → decision 레이턴시 (ms)
    """
    timestamp: str
    symbol: str
    spread_bps: float
    break_even_bps: float
    edge_bps: float
    profitable: bool
    gate_reasons: list
    latency_ms: float
    
    def to_dict(self):
        """딕셔너리 변환"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        """딕셔너리에서 생성"""
        return cls(**data)
