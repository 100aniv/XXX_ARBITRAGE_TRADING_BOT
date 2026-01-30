"""
D_ALPHA-1: Fill Probability Model

Maker 주문 체결 확률 추정:
- 호가창 깊이
- Queue Position
- 시장 변동성
- 주문 크기

HFT 레벨 지능 주입의 핵심 모듈.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from dataclasses import dataclass


@dataclass
class FillProbabilityParams:
    """
    Fill Probability 추정 파라미터
    
    보수적 기본값:
    - base_fill_probability: 0.7 (70% 체결 확률)
    - queue_position_penalty: 0.1 (queue 위치당 -10%)
    - volatility_penalty: 0.05 (변동성 증가 시 -5%)
    - wait_time_seconds: 5.0 (미체결 대기 시간)
    - slippage_per_second_bps: 0.2 (초당 슬리피지)
    """
    base_fill_probability: float = 0.7
    queue_position_penalty: float = 0.1
    volatility_penalty: float = 0.05
    min_fill_probability: float = 0.3
    max_fill_probability: float = 0.95
    wait_time_seconds: float = 5.0
    slippage_per_second_bps: float = 0.2


def estimate_fill_probability(
    orderbook_depth: Optional[float] = None,
    order_size: Optional[float] = None,
    queue_position: Optional[int] = None,
    volatility_bps: Optional[float] = None,
    params: Optional[FillProbabilityParams] = None
) -> Decimal:
    """
    Maker 주문 체결 확률 추정 (보수적)
    
    Args:
        orderbook_depth: 호가창 깊이 (USD)
        order_size: 주문 크기 (USD)
        queue_position: Queue 위치 (1=최상단)
        volatility_bps: 시장 변동성 (bps, 최근 1분)
        params: Fill Probability 파라미터
    
    Returns:
        체결 확률 (0.0 ~ 1.0, Decimal)
    
    Note:
        데이터 부족 시 보수적 기본값(0.7) 사용.
        실전 배포 전 백테스트로 파라미터 튜닝 필요.
    
    Example:
        >>> estimate_fill_probability(orderbook_depth=10000, order_size=500, queue_position=1)
        Decimal('0.70')
    """
    if params is None:
        params = FillProbabilityParams()
    
    # Base: 보수적 70% 시작
    fill_prob = params.base_fill_probability
    
    # Queue Position Penalty: 대기 순서가 뒤쪽일수록 체결 확률 감소
    if queue_position is not None and queue_position > 1:
        penalty = min((queue_position - 1) * params.queue_position_penalty, 0.4)
        fill_prob -= penalty
    
    # Orderbook Depth Penalty: 주문 크기가 호가창 깊이의 20% 초과 시 체결 확률 감소
    if orderbook_depth is not None and order_size is not None and orderbook_depth > 0:
        size_ratio = order_size / orderbook_depth
        if size_ratio > 0.2:
            penalty = min((size_ratio - 0.2) * 0.5, 0.3)
            fill_prob -= penalty
    
    # Volatility Penalty: 변동성 증가 시 체결 확률 감소 (Maker 주문이 가격을 놓칠 위험)
    if volatility_bps is not None and volatility_bps > 10.0:
        penalty = min((volatility_bps - 10.0) / 100.0 * params.volatility_penalty, 0.2)
        fill_prob -= penalty
    
    # Clamp
    fill_prob = max(params.min_fill_probability, min(fill_prob, params.max_fill_probability))
    
    # Decimal 변환 (4자리 정밀도)
    return Decimal(str(fill_prob)).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def calculate_opportunity_cost_bps(
    fill_probability: Decimal,
    spread_bps: float,
    wait_time_seconds: float = 5.0,
    slippage_per_second_bps: float = 0.2
) -> Decimal:
    """
    Maker 주문 미체결 시 기회비용 계산
    
    Args:
        fill_probability: 체결 확률 (0.0 ~ 1.0)
        spread_bps: 현재 스프레드 (bps)
        wait_time_seconds: 대기 시간 (초, default=5초)
        slippage_per_second_bps: 초당 슬리피지 (bps, default=0.2)
    
    Returns:
        기회비용 (bps, Decimal)
    
    Note:
        미체결 확률 × (대기 시간 × 초당 슬리피지)
        = (1 - fill_prob) × (wait_time × slippage_per_sec)
    
    Example:
        >>> calculate_opportunity_cost_bps(Decimal('0.7'), 50.0, 5.0, 0.2)
        Decimal('0.3000')  # (1 - 0.7) * (5 * 0.2) = 0.3 bps
    """
    unfilled_prob = Decimal('1.0') - fill_probability
    wait_cost = Decimal(str(wait_time_seconds)) * Decimal(str(slippage_per_second_bps))
    opportunity_cost = unfilled_prob * wait_cost
    
    return opportunity_cost.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def estimate_maker_net_edge_bps(
    spread_bps: float,
    maker_fee_bps: Decimal,
    slippage_bps: float,
    latency_bps: float,
    fill_probability: Decimal,
    wait_time_seconds: float = 5.0,
    slippage_per_second_bps: float = 0.2
) -> Decimal:
    """
    Maker 주문 기반 순 edge 계산 (D_ALPHA-1 핵심)
    
    Args:
        spread_bps: 스프레드 (bps)
        maker_fee_bps: Maker 수수료 (bps, rebate는 음수)
        slippage_bps: 슬리피지 (bps)
        latency_bps: 지연 비용 (bps)
        fill_probability: 체결 확률 (0.0 ~ 1.0)
        wait_time_seconds: 대기 시간 (초)
        slippage_per_second_bps: 초당 슬리피지 (bps)
    
    Returns:
        순 edge (bps, Decimal)
    
    Formula:
        net_edge = spread - maker_fee - slippage - latency - opportunity_cost
        where opportunity_cost = (1 - fill_prob) × (wait_time × slippage_per_sec)
    
    Example (Upbit Maker Rebate):
        >>> estimate_maker_net_edge_bps(
        ...     spread_bps=50.0,
        ...     maker_fee_bps=Decimal('-5.0'),  # Rebate
        ...     slippage_bps=5.0,
        ...     latency_bps=2.0,
        ...     fill_probability=Decimal('0.7'),
        ...     wait_time_seconds=5.0
        ... )
        Decimal('47.7000')  # 50 - (-5) - 5 - 2 - 0.3 = 47.7 bps
    """
    spread = Decimal(str(spread_bps))
    slippage = Decimal(str(slippage_bps))
    latency = Decimal(str(latency_bps))
    
    opportunity_cost = calculate_opportunity_cost_bps(
        fill_probability, spread_bps, wait_time_seconds, slippage_per_second_bps
    )
    
    net_edge = spread - maker_fee_bps - slippage - latency - opportunity_cost
    return net_edge.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
