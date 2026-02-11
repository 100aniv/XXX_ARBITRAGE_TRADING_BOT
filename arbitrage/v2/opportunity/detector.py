"""
D203-2: Opportunity Detector v1

두 거래소 가격을 입력받아 차익거래 기회를 탐지.

Reuse-First:
- SpreadModel 로직 참조 (V1: arbitrage/cross_exchange/spread_model.py)
- BreakEvenParams 재사용 (D203-1)

D205-8: Quote Normalization 통합
- KRW/USDT 단위 정규화 후 spread/edge 계산
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import logging

from arbitrage.v2.domain.break_even import (
    BreakEvenParams,
    compute_break_even_bps,
    compute_edge_bps,
)
from arbitrage.v2.domain.fill_probability import FillProbabilityParams
from arbitrage.v2.execution_quality.model_v1 import SimpleExecutionQualityModel
from arbitrage.v2.execution_quality.schemas import ExecutionCostBreakdown

logger = logging.getLogger(__name__)


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
        exchange_a_bid: 거래소 A bid (정규화 통화)
        exchange_a_ask: 거래소 A ask (정규화 통화)
        exchange_b_bid: 거래소 B bid (정규화 통화)
        exchange_b_ask: 거래소 B ask (정규화 통화)
        fx_rate: FX rate (예: KRW/USDT)
        fx_rate_source: FX source label
        fx_rate_age_sec: FX age seconds
        fx_rate_timestamp: FX timestamp (ISO)
        fx_rate_degraded: FX degraded flag
        deterministic_drift_bps: Deterministic drift penalty (bps)
        net_edge_bps: Edge after deterministic drift (bps)
        maker_mode: Maker mode flag
        fill_probability: Fill probability (optional)
        maker_net_edge_bps: Maker net edge (optional)
        allow_unprofitable: Allow unprofitable flag
        exec_cost_bps: Execution cost (bps) (optional)
        net_edge_after_exec_bps: Net edge after execution (bps) (optional)
        exec_model_version: Execution model version (optional)
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
    exchange_a_bid: Optional[float] = None
    exchange_a_ask: Optional[float] = None
    exchange_b_bid: Optional[float] = None
    exchange_b_ask: Optional[float] = None
    fx_rate: Optional[float] = None
    fx_rate_source: Optional[str] = None
    fx_rate_age_sec: Optional[float] = None
    fx_rate_timestamp: Optional[str] = None
    fx_rate_degraded: Optional[bool] = None
    deterministic_drift_bps: float = 0.0
    net_edge_bps: float = 0.0
    maker_mode: bool = False
    fill_probability: Optional[float] = None
    maker_net_edge_bps: Optional[float] = None
    allow_unprofitable: bool = False
    exec_cost_bps: Optional[float] = None
    net_edge_after_exec_bps: Optional[float] = None
    exec_model_version: Optional[str] = None


def detect_candidates(
    symbol: str,
    exchange_a: str,
    exchange_b: str,
    price_a: float,
    price_b: float,
    params: BreakEvenParams,
    deterministic_drift_bps: float = 0.0,
    maker_mode: bool = False,
    fill_probability_params: Optional[FillProbabilityParams] = None,
    notional: Optional[float] = None,
    upbit_bid_size: Optional[float] = None,
    upbit_ask_size: Optional[float] = None,
    binance_bid_size: Optional[float] = None,
    binance_ask_size: Optional[float] = None,
) -> Optional[OpportunityCandidate]:
    """
    단일 심볼에 대한 기회 탐지
    
    Args:
        symbol: 심볼 (예: "BTC/KRW")
        exchange_a: 거래소 A 이름 (예: "upbit")
        exchange_b: 거래소 B 이름 (예: "binance")
        price_a: 거래소 A 가격 (D205-8: 반드시 KRW로 정규화된 값)
        price_b: 거래소 B 가격 (D205-8: 반드시 KRW로 정규화된 값)
        params: BreakEvenParams
        
    Returns:
        OpportunityCandidate 또는 None (가격이 invalid한 경우)
        
    Logic:
        1. Spread 계산 (bps)
        2. Break-even 계산 (bps)
        3. Edge 계산 (bps)
        4. Direction 판단
        5. Profitable 여부 확인
    
    Note (D205-8):
        price_a, price_b는 호출 전에 반드시 동일 통화(KRW)로 정규화되어야 함.
        정규화는 replay_runner 또는 engine에서 quote_normalizer 사용.
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
    net_edge_bps = edge_bps - deterministic_drift_bps
    
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
    
    # 5. Profitable 여부 (deterministic drift 반영)
    profitable = net_edge_bps > 0
    
    # D_ALPHA-1: Maker mode 처리
    fill_prob = None
    maker_net_edge = None
    if maker_mode:
        from arbitrage.v2.domain.fill_probability import (
            estimate_fill_probability,
            estimate_maker_net_edge_bps,
        )
        from decimal import Decimal
        
        # Fill probability 추정 (보수적 기본값)
        fill_params = fill_probability_params or FillProbabilityParams()
        fill_prob_decimal = estimate_fill_probability(params=fill_params)
        fill_prob = float(fill_prob_decimal)
        
        # Maker fee 추출 (FeeModel에서)
        maker_fee_bps = Decimal(str(params.fee_model.fee_a.maker_fee_bps))
        
        # Maker net edge 계산
        maker_net_edge = float(estimate_maker_net_edge_bps(
            spread_bps=spread_bps,
            maker_fee_bps=maker_fee_bps,
            slippage_bps=params.slippage_bps,
            latency_bps=params.latency_bps,
            fill_probability=fill_prob_decimal,
            wait_time_seconds=fill_params.wait_time_seconds,
            slippage_per_second_bps=fill_params.slippage_per_second_bps,
        ))
        
        # Maker mode에서는 maker_net_edge로 profitable 판정
        profitable = maker_net_edge > 0
    
    exec_cost_breakdown: Optional[ExecutionCostBreakdown] = None
    if (not maker_mode) and (notional is not None) and float(notional) > 0:
        exec_quality_model = SimpleExecutionQualityModel()
        exec_cost_breakdown = exec_quality_model.compute_execution_cost(
            edge_bps=net_edge_bps,
            notional=float(notional),
            upbit_bid_size=upbit_bid_size,
            upbit_ask_size=upbit_ask_size,
            binance_bid_size=binance_bid_size,
            binance_ask_size=binance_ask_size,
        )
        profitable = exec_cost_breakdown.net_edge_after_exec_bps > 0
    
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
        deterministic_drift_bps=deterministic_drift_bps,
        net_edge_bps=net_edge_bps,
        maker_mode=maker_mode,
        fill_probability=fill_prob,
        maker_net_edge_bps=maker_net_edge,
        exec_cost_bps=(
            exec_cost_breakdown.total_exec_cost_bps if exec_cost_breakdown is not None else None
        ),
        net_edge_after_exec_bps=(
            exec_cost_breakdown.net_edge_after_exec_bps if exec_cost_breakdown is not None else None
        ),
        exec_model_version=(
            exec_cost_breakdown.exec_model_version if exec_cost_breakdown is not None else None
        ),
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
