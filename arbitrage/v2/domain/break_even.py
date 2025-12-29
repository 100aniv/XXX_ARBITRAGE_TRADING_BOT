"""
D203-1: Break-even Threshold (SSOT)

수수료 + 슬리피지 + 버퍼를 반영한 최소 진입 스프레드(bps) 공식.

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
        buffer_bps: 안전 버퍼 (basis points)
    """
    fee_model: FeeModel
    slippage_bps: float
    buffer_bps: float
    
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


def compute_break_even_bps(params: BreakEvenParams) -> float:
    """
    Break-even 스프레드 계산 (bps)
    
    공식 (SSOT):
        break_even_bps = fee_entry_bps + fee_exit_bps + slippage_bps + buffer_bps
    
    Args:
        params: BreakEvenParams
        
    Returns:
        Break-even threshold (bps)
        
    Example:
        >>> from arbitrage.domain.fee_model import create_fee_model_upbit_binance
        >>> fee_model = create_fee_model_upbit_binance()
        >>> params = BreakEvenParams(fee_model=fee_model, slippage_bps=10.0, buffer_bps=5.0)
        >>> break_even = compute_break_even_bps(params)
        >>> # fee_entry = 5 (Upbit) + 10 (Binance) = 15
        >>> # fee_exit = 15 (왕복)
        >>> # slippage = 10
        >>> # buffer = 5
        >>> # → break_even = 15 + 15 + 10 + 5 = 45 bps
        >>> break_even
        45.0
    """
    fee_entry_bps = params.fee_model.total_entry_fee_bps()
    fee_exit_bps = params.fee_model.total_exit_fee_bps()
    
    break_even_bps = (
        fee_entry_bps +
        fee_exit_bps +
        params.slippage_bps +
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
    
    Args:
        params: BreakEvenParams
        spread_bps: 관측된 스프레드 (bps)
        
    Returns:
        Dict with breakdown:
        - fee_entry_bps
        - fee_exit_bps
        - slippage_bps
        - buffer_bps
        - break_even_bps
        - spread_bps
        - edge_bps
        - profitable (bool)
    """
    fee_entry_bps = params.fee_model.total_entry_fee_bps()
    fee_exit_bps = params.fee_model.total_exit_fee_bps()
    break_even_bps = compute_break_even_bps(params)
    edge_bps = compute_edge_bps(spread_bps, break_even_bps)
    
    return {
        "fee_entry_bps": fee_entry_bps,
        "fee_exit_bps": fee_exit_bps,
        "slippage_bps": params.slippage_bps,
        "buffer_bps": params.buffer_bps,
        "break_even_bps": break_even_bps,
        "spread_bps": spread_bps,
        "edge_bps": edge_bps,
        "profitable": edge_bps > 0,
    }
