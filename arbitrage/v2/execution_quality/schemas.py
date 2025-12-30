"""
D205-6: ExecutionQuality 스키마

ExecutionCostBreakdown: 실제 체결 비용 분해
"""

from dataclasses import dataclass


@dataclass
class ExecutionCostBreakdown:
    """
    실제 체결 비용 분해
    
    Attributes:
        spread_cost_bps: 스프레드 비용 (양쪽 taker fee 가정)
        slippage_cost_bps: 슬리피지 비용 (notional/size 비율 기반)
        partial_fill_risk_bps: 부분체결 리스크 페널티
        total_exec_cost_bps: 총 실행 비용 (spread + slippage + partial_fill)
        net_edge_after_exec_bps: 순 엣지 (edge - total_exec_cost)
        exec_model_version: 실행 모델 버전 ("v1")
    """
    spread_cost_bps: float
    slippage_cost_bps: float
    partial_fill_risk_bps: float
    total_exec_cost_bps: float
    net_edge_after_exec_bps: float
    exec_model_version: str = "v1"
