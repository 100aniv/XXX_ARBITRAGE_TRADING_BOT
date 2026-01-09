"""
D203-1: Break-even Threshold (SSOT)

수수료 + 슬리피지 + 버퍼를 반영한 최소 진입 스프레드(bps) 공식.

D205-9-2 SSOT Alignment:
- execution_risk = slippage + latency
- execution_risk_per_leg: 편도 비용 (BUY 또는 SELL 한 쪽)
- execution_risk_round_trip: 왕복 비용 (BUY + SELL 양쪽)
- Fill Model에서 BUY에 +risk, SELL에 -risk 적용하면 왕복 영향은 ~2*risk

Reuse-First:
- FeeModel (V1: arbitrage/domain/fee_model.py) 재사용
- ThresholdConfig (V2: arbitrage/v2/core/config.py) 재사용
"""

from dataclasses import dataclass
from typing import Dict, Any

# V1 재사용
from arbitrage.domain.fee_model import FeeModel

# V2 재사용
from arbitrage.v2.core.config import ThresholdConfig


@dataclass
class BreakEvenParams:
    """
    Break-even 계산 파라미터
    
    Attributes:
        fee_model: 수수료 모델 (V1 FeeModel 재사용)
        slippage_bps: 슬리피지 (basis points)
        latency_bps: 레이턴시 비용 (basis points, D205-9-1 추가)
        buffer_bps: 안전 버퍼 (basis points)
    """
    fee_model: FeeModel
    slippage_bps: float
    latency_bps: float = 10.0  # D205-9-1: 기본값 10 bps
    buffer_bps: float = 0.0
    
    @classmethod
    def from_threshold_config(
        cls,
        fee_model: FeeModel,
        threshold_config: ThresholdConfig,
    ) -> "BreakEvenParams":
        """
        ThresholdConfig에서 생성
        
        Args:
            fee_model: FeeModel (V1)
            threshold_config: ThresholdConfig (V2)
            
        Returns:
            BreakEvenParams
        """
        return cls(
            fee_model=fee_model,
            slippage_bps=threshold_config.slippage_bps,
            buffer_bps=threshold_config.buffer_bps,
        )


def compute_execution_risk_per_leg(params: BreakEvenParams) -> float:
    """
    D205-9-2: Execution Risk per leg (편도) 계산.
    
    execution_risk_per_leg = slippage_bps + latency_bps
    
    이 값이 fill price 왜곡에 적용됨:
    - BUY: base_price * (1 + risk_per_leg / 10000)
    - SELL: base_price * (1 - risk_per_leg / 10000)
    """
    return params.slippage_bps + params.latency_bps


def compute_execution_risk_round_trip(params: BreakEvenParams) -> float:
    """
    D205-9-2: Execution Risk round-trip (왕복) 계산.
    
    Fill model에서 BUY에 +risk, SELL에 -risk 적용하면
    왕복 영향은 대략 2 * per_leg.
    
    Returns:
        execution_risk_round_trip = 2 * (slippage_bps + latency_bps)
    """
    return 2.0 * compute_execution_risk_per_leg(params)


def compute_break_even_bps(params: BreakEvenParams) -> float:
    """
    Break-even spread (bps) 계산.
    
    D205-15-5d FIX: execution_risk 재포함 (정확한 필터링 기준)
    - break_even = "이 기회가 profitable한지 판단하는 기준"
    - fill model = "실제 체결가 시뮬레이션"
    - 둘 다 execution_risk 포함해야 일치함!
    
    포함 항목:
    - entry/exit fee (round-trip)
    - execution_risk (round-trip): 실제 fill에서 발생할 비용
    - buffer (safety margin)
    
    Note:
    - 핵심: "필터 기준 = 실제 비용"
    - execution_risk는 필터와 fill 둘 다 필요 (이중 적용 아님, 일치시킴)
    """
    fee_entry_bps = params.fee_model.total_entry_fee_bps()
    fee_exit_bps = params.fee_model.total_exit_fee_bps()
    execution_risk_round_trip = compute_execution_risk_round_trip(params)
    
    # D205-15-5d FIX: execution_risk 재포함
    break_even_bps = (
        fee_entry_bps +
        fee_exit_bps +
        execution_risk_round_trip +
        params.buffer_bps
    )
    
    return break_even_bps


def compute_edge_bps(spread_bps: float, break_even_bps: float) -> float:
    """
    Edge 계산 (= spread - break_even)
    
    Args:
        spread_bps: 관측된 스프레드 (bps)
        break_even_bps: Break-even threshold (bps)
        
    Returns:
        Edge (bps)
        - 양수: 수익 가능 (spread > break_even)
        - 0: Break-even (spread == break_even)
        - 음수: 손실 예상 (spread < break_even)
        
    Example:
        >>> compute_edge_bps(spread_bps=50.0, break_even_bps=45.0)
        5.0
        >>> compute_edge_bps(spread_bps=40.0, break_even_bps=45.0)
        -5.0
    """
    return spread_bps - break_even_bps


def explain_break_even(
    params: BreakEvenParams,
    spread_bps: float,
) -> Dict[str, Any]:
    """
    Break-even 계산 과정을 설명 (디버깅/리포트용)
    
    D205-9-2 FIX: per_leg/round_trip 명시적 기록
    
    Args:
        params: BreakEvenParams
        spread_bps: 관측된 스프레드 (bps)
        
    Returns:
        Dict with breakdown (per_leg/round_trip 포함)
    """
    fee_entry_bps = params.fee_model.total_entry_fee_bps()
    fee_exit_bps = params.fee_model.total_exit_fee_bps()
    exec_risk_per_leg = compute_execution_risk_per_leg(params)
    exec_risk_round_trip = compute_execution_risk_round_trip(params)
    break_even_bps = compute_break_even_bps(params)
    edge_bps = compute_edge_bps(spread_bps, break_even_bps)
    
    return {
        "fee_entry_bps": fee_entry_bps,
        "fee_exit_bps": fee_exit_bps,
        "slippage_bps": params.slippage_bps,
        "latency_bps": params.latency_bps,
        "exec_risk_per_leg_bps": exec_risk_per_leg,      # D205-9-2: 편도
        "exec_risk_round_trip_bps": exec_risk_round_trip,  # D205-9-2: 왕복
        "buffer_bps": params.buffer_bps,
        "break_even_bps": break_even_bps,
        "spread_bps": spread_bps,
        "edge_bps": edge_bps,
        "profitable": edge_bps > 0,
    }
