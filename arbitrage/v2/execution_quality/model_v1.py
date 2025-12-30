"""
D205-6: ExecutionQuality Model v1

단순 선형 모델:
- spread_cost: half-spread (taker fee 가정)
- slippage_cost: notional / top_size 비율 기반 선형 증가
- partial_fill_risk: size 부족 시 페널티

재사용:
- SimpleFillModel 로직 참조 (arbitrage/execution/fill_model.py)
"""

import logging
from typing import Optional

from arbitrage.v2.execution_quality.schemas import ExecutionCostBreakdown

logger = logging.getLogger(__name__)


class SimpleExecutionQualityModel:
    """
    Simple ExecutionQuality Model (v1)
    
    비용 모델:
    - spread_cost_bps: 양쪽 taker fee 가정 (기본 25 bps)
    - slippage_cost_bps: (notional / top_size) * alpha (선형)
    - partial_fill_risk_bps: size 부족 시 추가 페널티
    
    Args:
        default_spread_cost_bps: 기본 스프레드 비용 (default: 25 bps)
        slippage_alpha: 슬리피지 계수 (default: 10.0 bps per unit impact)
        partial_fill_penalty_bps: 부분체결 페널티 (default: 20 bps)
        max_safe_ratio: 최대 안전 size ratio (notional/top_size > 이 값이면 페널티) (default: 0.3)
    """
    
    def __init__(
        self,
        default_spread_cost_bps: float = 25.0,
        slippage_alpha: float = 10.0,
        partial_fill_penalty_bps: float = 20.0,
        max_safe_ratio: float = 0.3,
    ):
        self.default_spread_cost_bps = default_spread_cost_bps
        self.slippage_alpha = slippage_alpha
        self.partial_fill_penalty_bps = partial_fill_penalty_bps
        self.max_safe_ratio = max_safe_ratio
        
        logger.info(
            f"[D205-6_EXEC_QUALITY] Initialized v1: "
            f"spread={default_spread_cost_bps}bps, "
            f"alpha={slippage_alpha}, "
            f"partial_penalty={partial_fill_penalty_bps}bps, "
            f"max_safe_ratio={max_safe_ratio}"
        )
    
    def compute_execution_cost(
        self,
        edge_bps: float,
        notional: float,
        upbit_bid_size: Optional[float] = None,
        upbit_ask_size: Optional[float] = None,
        binance_bid_size: Optional[float] = None,
        binance_ask_size: Optional[float] = None,
    ) -> ExecutionCostBreakdown:
        """
        실제 체결 비용 계산
        
        Args:
            edge_bps: 이론상 엣지 (spread - break_even)
            notional: 주문 금액 (quote currency)
            upbit_bid_size: Upbit 매수 호가 잔량 (optional)
            upbit_ask_size: Upbit 매도 호가 잔량 (optional)
            binance_bid_size: Binance 매수 호가 잔량 (optional)
            binance_ask_size: Binance 매도 호가 잔량 (optional)
        
        Returns:
            ExecutionCostBreakdown
        """
        # 1. Spread cost (양쪽 taker fee 가정)
        spread_cost_bps = self.default_spread_cost_bps
        
        # 2. Slippage cost (notional / size 비율 기반)
        slippage_cost_bps = self._compute_slippage_cost(
            notional=notional,
            upbit_bid_size=upbit_bid_size,
            upbit_ask_size=upbit_ask_size,
            binance_bid_size=binance_bid_size,
            binance_ask_size=binance_ask_size,
        )
        
        # 3. Partial fill risk (size 부족 시 페널티)
        partial_fill_risk_bps = self._compute_partial_fill_risk(
            notional=notional,
            upbit_bid_size=upbit_bid_size,
            upbit_ask_size=upbit_ask_size,
            binance_bid_size=binance_bid_size,
            binance_ask_size=binance_ask_size,
        )
        
        # 4. Total execution cost
        total_exec_cost_bps = spread_cost_bps + slippage_cost_bps + partial_fill_risk_bps
        
        # 5. Net edge after execution
        net_edge_after_exec_bps = edge_bps - total_exec_cost_bps
        
        return ExecutionCostBreakdown(
            spread_cost_bps=spread_cost_bps,
            slippage_cost_bps=slippage_cost_bps,
            partial_fill_risk_bps=partial_fill_risk_bps,
            total_exec_cost_bps=total_exec_cost_bps,
            net_edge_after_exec_bps=net_edge_after_exec_bps,
            exec_model_version="v1",
        )
    
    def _compute_slippage_cost(
        self,
        notional: float,
        upbit_bid_size: Optional[float],
        upbit_ask_size: Optional[float],
        binance_bid_size: Optional[float],
        binance_ask_size: Optional[float],
    ) -> float:
        """
        슬리피지 비용 계산 (선형 모델)
        
        Logic:
        - 양쪽 top-of-book size 평균 사용
        - size 없으면 보수적 페널티 (20 bps)
        - impact_ratio = notional / avg_size
        - slippage_cost = alpha * impact_ratio (단조 증가)
        
        Returns:
            slippage_cost_bps
        """
        # Size 수집
        sizes = []
        if upbit_bid_size is not None and upbit_bid_size > 0:
            sizes.append(upbit_bid_size)
        if upbit_ask_size is not None and upbit_ask_size > 0:
            sizes.append(upbit_ask_size)
        if binance_bid_size is not None and binance_bid_size > 0:
            sizes.append(binance_bid_size)
        if binance_ask_size is not None and binance_ask_size > 0:
            sizes.append(binance_ask_size)
        
        # Size 없으면 보수적 페널티
        if not sizes:
            logger.debug("[D205-6_EXEC_QUALITY] No size info, using conservative penalty (20 bps)")
            return 20.0
        
        # 평균 size
        avg_size = sum(sizes) / len(sizes)
        
        if avg_size <= 0:
            return 20.0
        
        # Impact ratio
        impact_ratio = notional / avg_size
        
        # Slippage cost (선형)
        slippage_cost_bps = self.slippage_alpha * impact_ratio
        
        # Cap at 100 bps (비현실적 큰 값 방지)
        slippage_cost_bps = min(slippage_cost_bps, 100.0)
        
        return slippage_cost_bps
    
    def _compute_partial_fill_risk(
        self,
        notional: float,
        upbit_bid_size: Optional[float],
        upbit_ask_size: Optional[float],
        binance_bid_size: Optional[float],
        binance_ask_size: Optional[float],
    ) -> float:
        """
        부분체결 리스크 페널티
        
        Logic:
        - notional / avg_size < min_size_ratio이면 partial_fill_penalty_bps 적용
        - 그렇지 않으면 0
        
        Returns:
            partial_fill_risk_bps
        """
        # Size 수집
        sizes = []
        if upbit_bid_size is not None and upbit_bid_size > 0:
            sizes.append(upbit_bid_size)
        if upbit_ask_size is not None and upbit_ask_size > 0:
            sizes.append(upbit_ask_size)
        if binance_bid_size is not None and binance_bid_size > 0:
            sizes.append(binance_bid_size)
        if binance_ask_size is not None and binance_ask_size > 0:
            sizes.append(binance_ask_size)
        
        # Size 없으면 페널티 적용
        if not sizes:
            logger.debug("[D205-6_EXEC_QUALITY] No size info, applying partial fill penalty")
            return self.partial_fill_penalty_bps
        
        # 평균 size
        avg_size = sum(sizes) / len(sizes)
        
        if avg_size <= 0:
            return self.partial_fill_penalty_bps
        
        # Size ratio (주문 크기 / 시장 유동성)
        size_ratio = notional / avg_size
        
        # max_safe_ratio보다 작으면 안전 (페널티 없음)
        if size_ratio <= self.max_safe_ratio:
            return 0.0
        
        # 크면 페널티 (주문이 시장 대비 너무 큼 → 부분체결 리스크)
        return self.partial_fill_penalty_bps
