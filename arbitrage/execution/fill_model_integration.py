# -*- coding: utf-8 -*-
"""
D87-0: Fill Model Integration Interface

Multi-Exchange Execution 레이어와 CalibratedFillModel 통합을 위한 인터페이스 정의.

D87-1+ 단계에서 구현 예정:
- FillModelAdvice: Fill Model이 Route/Executor/RiskGuard에게 제공하는 조언
- FillModelIntegration: Fill Model 통합 컨테이너
- 메트릭, Alert, 동적 한도 조정 등

Author: arbitrage-lite project
Date: 2025-12-07
"""

import logging
from dataclasses import dataclass
from typing import Optional, Literal

logger = logging.getLogger(__name__)


@dataclass
class FillModelAdvice:
    """
    D87-0: Fill Model Advice Interface
    
    Fill Model이 Multi-Exchange Execution 레이어에게 제공하는 조언.
    
    D87-1에서 구현 예정:
    - RouteHealthScore 보정 (ArbRoute.evaluate)
    - 주문 파라미터 조정 (CrossExchangeExecutor._prepare_order_params)
    - 동적 한도 조정 (CrossExchangeRiskGuard.evaluate)
    
    Attributes:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        zone_id: 매칭된 Zone (예: "Z1", "Z2", "Z3", "Z4")
        expected_fill_probability: 예상 체결 확률 (0.0 ~ 1.0)
        expected_slippage_bps: 예상 슬리피지 (bps)
        confidence_level: 통계적 신뢰도 (0.0 ~ 1.0, 샘플 수 기반)
    """
    entry_bps: float
    tp_bps: float
    zone_id: str
    expected_fill_probability: float
    expected_slippage_bps: float
    confidence_level: float


@dataclass
class FillModelConfig:
    """
    D87-0: Fill Model Config Interface
    
    Fill Model 설정을 담는 구조체.
    
    D87-1에서 ArbitrageConfig로 통합 예정.
    
    Attributes:
        enabled: Fill Model 활성화 여부
        mode: "none" (비활성화), "advisory" (메트릭만), "strict" (실제 사용)
        calibration_path: Calibration JSON 경로
        min_confidence_level: 최소 신뢰도 (샘플 수 기반)
        staleness_threshold_seconds: Calibration 유효기간 (기본 24시간)
    """
    enabled: bool = False
    mode: Literal["none", "advisory", "strict"] = "none"
    calibration_path: Optional[str] = None
    min_confidence_level: float = 0.5
    staleness_threshold_seconds: float = 86400.0  # 24시간


class FillModelIntegration:
    """
    D87-0: Fill Model Integration Container
    
    CalibratedFillModel과 Multi-Exchange Execution 레이어를 연결하는 통합 컨테이너.
    
    D87-1+ 단계에서 구현 예정:
    - compute_advice(): Entry/TP → FillModelAdvice 생성
    - adjust_route_score(): RouteHealthScore 보정
    - adjust_order_params(): 주문 파라미터 조정
    - adjust_risk_limits(): 동적 한도 조정
    - check_health(): Fill Model 상태 검증
    
    Usage:
        # D87-1 example (NOT implemented yet)
        integration = FillModelIntegration(config, calibration_table)
        advice = integration.compute_advice(entry_bps=10.0, tp_bps=15.0)
        adjusted_score = integration.adjust_route_score(base_score, advice)
    """
    
    def __init__(self, config: FillModelConfig):
        """
        초기화
        
        Args:
            config: Fill Model Config
        """
        self.config = config
        logger.info(
            f"[D87-0_FILL_MODEL_INTEGRATION] 초기화: "
            f"enabled={config.enabled}, mode={config.mode}"
        )
    
    def compute_advice(
        self,
        entry_bps: float,
        tp_bps: float
    ) -> Optional[FillModelAdvice]:
        """
        D87-1: FillModelAdvice 생성 (NOT IMPLEMENTED)
        
        Args:
            entry_bps: Entry threshold (bps)
            tp_bps: TP threshold (bps)
        
        Returns:
            FillModelAdvice 또는 None (Fill Model 비활성화 시)
        
        Raises:
            NotImplementedError: D87-1에서 구현 예정
        """
        raise NotImplementedError("D87-1에서 구현 예정")
    
    def adjust_route_score(
        self,
        base_score: float,
        advice: FillModelAdvice
    ) -> float:
        """
        D87-1: RouteHealthScore 보정 (NOT IMPLEMENTED)
        
        Args:
            base_score: 기본 RouteHealthScore (0~100)
            advice: Fill Model Advice
        
        Returns:
            보정된 RouteHealthScore (0~100)
        
        Raises:
            NotImplementedError: D87-1에서 구현 예정
        """
        raise NotImplementedError("D87-1에서 구현 예정")
    
    def adjust_order_params(
        self,
        base_quantity: float,
        base_price_offset: float,
        advice: FillModelAdvice
    ) -> tuple[float, float]:
        """
        D87-2: 주문 파라미터 조정 (NOT IMPLEMENTED)
        
        Args:
            base_quantity: 기본 주문 수량
            base_price_offset: 기본 가격 오프셋
            advice: Fill Model Advice
        
        Returns:
            (조정된 수량, 조정된 가격 오프셋)
        
        Raises:
            NotImplementedError: D87-2에서 구현 예정
        """
        raise NotImplementedError("D87-2에서 구현 예정")
    
    def adjust_risk_limits(
        self,
        base_position_limit: float,
        base_pnl_threshold: float,
        advice: FillModelAdvice
    ) -> tuple[float, float]:
        """
        D87-3: RiskGuard 동적 한도 조정 (NOT IMPLEMENTED)
        
        Args:
            base_position_limit: 기본 Position limit
            base_pnl_threshold: 기본 PnL threshold
            advice: Fill Model Advice
        
        Returns:
            (조정된 Position limit, 조정된 PnL threshold)
        
        Raises:
            NotImplementedError: D87-3에서 구현 예정
        """
        raise NotImplementedError("D87-3에서 구현 예정")
    
    def check_health(self) -> dict:
        """
        D87-3: Fill Model 상태 검증 (NOT IMPLEMENTED)
        
        Returns:
            {
                "healthy": bool,
                "calibration_age_seconds": float,
                "confidence_level": float,
                "warnings": list[str]
            }
        
        Raises:
            NotImplementedError: D87-3에서 구현 예정
        """
        raise NotImplementedError("D87-3에서 구현 예정")
