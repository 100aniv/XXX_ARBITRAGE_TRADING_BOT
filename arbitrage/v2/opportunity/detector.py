"""
D203-2: Opportunity Detector v1

두 거래소 가격을 입력받아 차익거래 기회를 탐지.

Reuse-First:
- SpreadModel 로직 참조 (V1: arbitrage/cross_exchange/spread_model.py)
- BreakEvenParams 재사용 (D203-1)
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from arbitrage.v2.domain.break_even import (
    BreakEvenParams,
    compute_break_even_bps,
    compute_edge_bps,
)


class OpportunityDirection(str, Enum):
    """기회 방향"""
    BUY_A_SELL_B = "buy_a_sell_b"  # A에서 사고 B에서 팔기 (A < B, spread > 0)
    BUY_B_SELL_A = "buy_b_sell_a"  # B에서 사고 A에서 팔기 (B < A, spread < 0)
    NONE = "none"  # 기회 없음


@dataclass
class OpportunityCandidate:
    """
    차익거래 기회 후보
    
    Attributes:
        symbol: 심볼 (예: "BTC/KRW")
        exchange_a: 거래소 A 이름
        exchange_b: 거래소 B 이름
        price_a: 거래소 A 가격 (normalized to same currency)
        price_b: 거래소 B 가격 (normalized to same currency)
        spread_bps: 스프레드 (bps) = abs((price_a - price_b) / price_b * 10000)
        break_even_bps: Break-even threshold (bps)
        edge_bps: Edge (bps) = spread_bps - break_even_bps
        direction: 거래 방향
        profitable: 수익 가능 여부 (edge_bps > 0)
    """
    symbol: str
    exchange_a: str
    exchange_b: str
    price_a: float
    price_b: float
    spread_bps: float
    break_even_bps: float
    edge_bps: float
    direction: OpportunityDirection
    profitable: bool


def detect_candidates(
    symbol: str,
    exchange_a: str,
    exchange_b: str,
    price_a: float,
    price_b: float,
    params: BreakEvenParams,
) -> Optional[OpportunityCandidate]:
    """
    단일 심볼에 대한 기회 탐지
    
    Args:
        symbol: 심볼 (예: "BTC/KRW")
        exchange_a: 거래소 A 이름 (예: "upbit")
        exchange_b: 거래소 B 이름 (예: "binance")
        price_a: 거래소 A 가격 (normalized)
        price_b: 거래소 B 가격 (normalized)
        params: BreakEvenParams
        
    Returns:
        OpportunityCandidate 또는 None (가격이 invalid한 경우)
        
    Logic:
        1. Spread 계산 (bps)
        2. Break-even 계산 (bps)
        3. Edge 계산 (bps)
        4. Direction 판단
        5. Profitable 여부 확인
    """
    # Validation
    if price_a <= 0 or price_b <= 0:
        return None
    
    # 1. Spread 계산 (V1 SpreadModel 로직 참조)
    # spread_percent = (price_a - price_b) / price_b * 100
    # spread_bps = abs(spread_percent * 100)
    spread_percent = (price_a - price_b) / price_b * 100.0
    spread_bps = abs(spread_percent * 100.0)  # Convert % to bps
    
    # 2. Break-even 계산
    break_even_bps = compute_break_even_bps(params)
    
    # 3. Edge 계산
    edge_bps = compute_edge_bps(spread_bps, break_even_bps)
    
    # 4. Direction 판단
    if price_a < price_b:
        # A가 저렴 → A에서 사고 B에서 팔기
        direction = OpportunityDirection.BUY_A_SELL_B
    elif price_a > price_b:
        # B가 저렴 → B에서 사고 A에서 팔기
        direction = OpportunityDirection.BUY_B_SELL_A
    else:
        # 가격 동일 → 기회 없음
        direction = OpportunityDirection.NONE
    
    # 5. Profitable 여부
    profitable = edge_bps > 0
    
    return OpportunityCandidate(
        symbol=symbol,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        price_a=price_a,
        price_b=price_b,
        spread_bps=spread_bps,
        break_even_bps=break_even_bps,
        edge_bps=edge_bps,
        direction=direction,
        profitable=profitable,
    )


def detect_multi_candidates(
    opportunities: List[dict],
    params: BreakEvenParams,
) -> List[OpportunityCandidate]:
    """
    여러 심볼에 대한 기회 탐지
    
    Args:
        opportunities: List of dicts with:
            - symbol: str
            - exchange_a: str
            - exchange_b: str
            - price_a: float
            - price_b: float
        params: BreakEvenParams
        
    Returns:
        List of OpportunityCandidate (profitable만)
    """
    candidates = []
    
    for opp in opportunities:
        candidate = detect_candidates(
            symbol=opp["symbol"],
            exchange_a=opp["exchange_a"],
            exchange_b=opp["exchange_b"],
            price_a=opp["price_a"],
            price_b=opp["price_b"],
            params=params,
        )
        
        if candidate and candidate.profitable:
            candidates.append(candidate)
    
    # Sort by edge_bps (descending)
    candidates.sort(key=lambda c: c.edge_bps, reverse=True)
    
    return candidates
