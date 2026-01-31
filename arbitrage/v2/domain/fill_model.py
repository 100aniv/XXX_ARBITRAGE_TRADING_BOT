"""
D205-15-6: Fill Model (Execution-Risk Simulation)

Engine-Centric 원칙에 따라 PaperRunner에서 추출.
실거래(Live) 체결 시뮬레이션에도 재사용 가능.

Purpose:
- Slippage + Latency를 반영한 체결 가격 계산
- BUY: 불리한 방향(가격 상승)
- SELL: 불리한 방향(가격 하락)

Author: arbitrage-lite V2
Date: 2026-01-10
"""

from typing import Literal, Optional
from arbitrage.v2.domain.break_even import BreakEvenParams
from dataclasses import dataclass
from decimal import Decimal
import random
import time


@dataclass
class FillModelConfig:
    """체결 모델 설정 (D206 Taxonomy)"""
    enable_slippage: bool = True
    slippage_bps_min: float = 20.0
    slippage_bps_max: float = 50.0
    enable_latency: bool = True
    latency_ms_min: int = 10
    latency_ms_max: int = 100
    enable_partial_fill: bool = True
    partial_fill_probability: float = 0.1  # 10% 부분 체결 확률
    partial_fill_ratio_min: float = 0.5
    partial_fill_ratio_max: float = 0.9


@dataclass
class FillResult:
    """체결 결과"""
    filled_qty: Decimal
    avg_price: Decimal
    is_fully_filled: bool
    slippage_bps: Optional[float] = None  # 슬리피지 (bps)
    latency_ms: Optional[int] = None  # 지연 시간 (ms)
    is_partial: bool = False  # 부분 체결 여부


def apply_execution_risk(
    base_price: float,
    side: Literal["BUY", "SELL"],
    break_even_params: BreakEvenParams
) -> float:
    """
    Execution-Risk 가격 왜곡 적용
    
    Args:
        base_price: 기준 가격 (orderbook의 bid/ask)
        side: 주문 방향 ("BUY" or "SELL")
        break_even_params: slippage_bps + latency_bps 포함
    
    Returns:
        체결 예상 가격 (execution risk 반영)
    
    Example:
        >>> params = BreakEvenParams(slippage_bps=15.0, latency_bps=10.0, ...)
        >>> apply_execution_risk(100.0, "BUY", params)
        100.25  # 100 * (1 + 25/10000)
    """
    execution_risk_bps = break_even_params.slippage_bps + break_even_params.latency_bps
    
    if side == "BUY":
        # BUY: 가격이 올라서 불리하게 체결
        return base_price * (1 + execution_risk_bps / 10000.0)
    else:  # SELL
        # SELL: 가격이 내려서 불리하게 체결
        return base_price * (1 - execution_risk_bps / 10000.0)


def calculate_fee(
    price: float,
    quantity: float,
    fee_bps: float
) -> float:
    """
    거래 수수료 계산
    
    Args:
        price: 체결 가격
        quantity: 체결 수량
        fee_bps: 수수료율 (bps, 0.05% = 5.0)
    
    Returns:
        수수료 (quote currency 기준)
    
    Example:
        >>> calculate_fee(100.0, 0.1, 5.0)
        0.05  # (100 * 0.1) * (5.0 / 10000)
    """
    notional = price * quantity
    return notional * (fee_bps / 10000.0)
