# -*- coding: utf-8 -*-
"""
D87-1: Fill Model Integration – Advisory Mode

Multi-Exchange Execution 레이어와 CalibratedFillModel 통합.

D87-1 구현 완료:
- FillModelAdvice: Fill Model이 Route/Executor/RiskGuard에게 제공하는 조언
- FillModelIntegration: Fill Model 통합 컨테이너 (Advisory Mode)
- Calibration 로드, Zone 선택, Score/Size/Limit 보정

Author: arbitrage-lite project
Date: 2025-12-07
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
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
    D87-1/D87-2/D87-4: Fill Model Config
    
    Fill Model 설정을 담는 구조체.
    
    Attributes:
        enabled: Fill Model 활성화 여부
        mode: "none" (비활성화), "advisory" (soft bias), "strict" (강한 개입, D87-2)
        calibration_path: Calibration JSON 경로
        min_confidence_level: 최소 신뢰도 (샘플 수 기반)
        staleness_threshold_seconds: Calibration 유효기간 (기본 24시간)
        
        # Advisory Mode 파라미터 (D87-1, ±10% 이내) - Deprecated in favor of zone_preference (D87-4)
        advisory_score_bias_z2: Z2(고 fill_ratio) Route Score 보정값 (기본 +5.0)
        advisory_score_bias_other: Z1/Z3/Z4 Route Score 보정값 (기본 -2.0)
        advisory_size_multiplier_z2: Z2 주문 수량 배율 (기본 1.1)
        advisory_size_multiplier_other: 기타 Zone 주문 수량 배율 (기본 1.0)
        advisory_risk_multiplier_z2: Z2 Risk Limit 완화 배율 (기본 1.1)
        advisory_risk_multiplier_other: 기타 Zone Risk Limit 배율 (기본 1.0)
        
        # Strict Mode 파라미터 (D87-2, ±20% 이내) - Deprecated in favor of zone_preference (D87-4)
        strict_score_bias_z2: Z2 Route Score 보정값 (기본 +10.0)
        strict_score_bias_other: Z1/Z3/Z4 Route Score 보정값 (기본 -5.0)
        strict_size_multiplier_z2: Z2 주문 수량 배율 (기본 1.2)
        strict_size_multiplier_other: 기타 Zone 주문 수량 배율 (기본 1.0)
        strict_risk_multiplier_z2: Z2 Risk Limit 완화 배율 (기본 1.2)
        strict_risk_multiplier_other: 기타 Zone Risk Limit 배율 (기본 1.0)
        
        # D87-4: Zone Preference Weights (Multiplicative)
        zone_preference: Mode별 Zone 선호도 가중치 (Dict[mode, Dict[zone_id, weight]])
            none: 모든 Zone 1.0 (neutral)
            advisory: Z2=1.05, Z1/Z4=0.90, Z3=0.95
            strict: Z2=1.15, Z1/Z4=0.80, Z3=0.85
    """
    enabled: bool = False
    mode: Literal["none", "advisory", "strict"] = "none"
    calibration_path: Optional[str] = None
    min_confidence_level: float = 0.5
    staleness_threshold_seconds: float = 86400.0  # 24시간
    
    # Advisory Mode 파라미터 (D87-1, ±10% 이내)
    advisory_score_bias_z2: float = 5.0  # Z2 Score +5.0
    advisory_score_bias_other: float = -2.0  # Z1/Z3/Z4 Score -2.0
    advisory_size_multiplier_z2: float = 1.1  # Z2 수량 10% 증가
    advisory_size_multiplier_other: float = 1.0  # 기타 Zone 변화 없음
    advisory_risk_multiplier_z2: float = 1.1  # Z2 Risk Limit 10% 완화
    advisory_risk_multiplier_other: float = 1.0  # 기타 Zone 변화 없음
    
    # Strict Mode 파라미터 (D87-2, ±20% 이내)
    strict_score_bias_z2: float = 10.0  # Z2 Score +10.0
    strict_score_bias_other: float = -5.0  # Z1/Z3/Z4 Score -5.0
    strict_size_multiplier_z2: float = 1.2  # Z2 수량 20% 증가
    strict_size_multiplier_other: float = 1.0  # 기타 Zone 변화 없음
    strict_risk_multiplier_z2: float = 1.2  # Z2 Risk Limit 20% 완화
    strict_risk_multiplier_other: float = 1.0  # 기타 Zone 변화 없음
    
    # D87-4: Zone Preference Weights (Multiplicative)
    zone_preference: Optional[dict] = None
    
    def __post_init__(self):
        """
        D87-4: Zone Preference Weights 초기화
        
        zone_preference가 None이면 기본값으로 설정.
        """
        if self.zone_preference is None:
            self.zone_preference = {
                "none": {
                    "Z1": 1.0,
                    "Z2": 1.0,
                    "Z3": 1.0,
                    "Z4": 1.0,
                    "DEFAULT": 1.0,
                },
                "advisory": {
                    "Z1": 0.80,
                    "Z2": 3.00,  # D89-0: 1.05 → 3.00 (강화)
                    "Z3": 0.85,
                    "Z4": 0.80,
                    "DEFAULT": 0.85,
                },
                "strict": {
                    "Z1": 0.80,
                    "Z2": 1.15,
                    "Z3": 0.85,
                    "Z4": 0.80,
                    "DEFAULT": 0.85,
                },
            }


class FillModelIntegration:
    """
    D87-1: Fill Model Integration Container – Advisory Mode
    
    CalibratedFillModel과 Multi-Exchange Execution 레이어를 연결하는 통합 컨테이너.
    
    D87-1 구현 완료:
    - from_config(): Config로부터 인스턴스 생성 (Calibration 로드 포함)
    - compute_advice(): Entry/TP → FillModelAdvice 생성
    - adjust_route_score(): RouteHealthScore 보정 (Advisory Mode)
    - adjust_order_size(): 주문 수량 조정 (Advisory Mode)
    - adjust_risk_limit(): Risk Limit 조정 (Advisory Mode)
    - check_health(): Fill Model 상태 검증
    
    Usage:
        # D87-1 Advisory Mode
        integration = FillModelIntegration.from_config(config)
        advice = integration.compute_advice(entry_bps=10.0, tp_bps=15.0)
        if advice:
            adjusted_score = integration.adjust_route_score(base_score=60.0, advice=advice)
            adjusted_size = integration.adjust_order_size(base_size=0.01, advice=advice)
    """
    
    def __init__(self, config: FillModelConfig, calibration_data: Optional[dict] = None):
        """
        초기화 (내부용, from_config() 사용 권장)
        
        Args:
            config: Fill Model Config
            calibration_data: Calibration JSON 데이터 (dict)
        """
        self.config = config
        self.calibration_data = calibration_data
        self.calibration_loaded_at = time.time() if calibration_data else None
        
        logger.info(
            f"[D87-1_FILL_MODEL_INTEGRATION] 초기화: "
            f"enabled={config.enabled}, mode={config.mode}, "
            f"calibration_loaded={calibration_data is not None}"
        )
    
    @classmethod
    def from_config(cls, config: FillModelConfig) -> "FillModelIntegration":
        """
        Config로부터 FillModelIntegration 인스턴스 생성.
        
        Calibration JSON 파일을 로드하고, 유효성을 검증한다.
        
        Args:
            config: FillModelConfig
        
        Returns:
            FillModelIntegration 인스턴스
        
        Raises:
            FileNotFoundError: Calibration 파일이 없을 경우
            ValueError: Calibration 포맷이 잘못되었을 경우
        """
        calibration_data = None
        
        if config.enabled and config.calibration_path:
            calibration_path = Path(config.calibration_path)
            
            if not calibration_path.exists():
                logger.error(f"[FILL_MODEL_INTEGRATION] Calibration 파일 없음: {calibration_path}")
                raise FileNotFoundError(f"Calibration file not found: {calibration_path}")
            
            with open(calibration_path, "r", encoding="utf-8") as f:
                calibration_data = json.load(f)
            
            # 기본 필드 검증
            required_fields = ["version", "zones", "default_buy_fill_ratio", "default_sell_fill_ratio"]
            for field in required_fields:
                if field not in calibration_data:
                    raise ValueError(f"Calibration missing required field: {field}")
            
            logger.info(
                f"[FILL_MODEL_INTEGRATION] Calibration 로드 완료: "
                f"version={calibration_data['version']}, zones={len(calibration_data['zones'])}"
            )
        
        return cls(config=config, calibration_data=calibration_data)
    
    def compute_advice(
        self,
        entry_bps: float,
        tp_bps: float
    ) -> Optional[FillModelAdvice]:
        """
        D87-1: FillModelAdvice 생성
        
        Entry/TP Threshold로부터 Zone을 선택하고, Fill Model Advice를 생성한다.
        
        Args:
            entry_bps: Entry threshold (bps)
            tp_bps: TP threshold (bps)
        
        Returns:
            FillModelAdvice 또는 None (Fill Model 비활성화 또는 Zone 미매칭 시)
        """
        # Mode가 none이거나 비활성화된 경우
        if not self.config.enabled or self.config.mode == "none":
            return None
        
        # Calibration 데이터가 없는 경우
        if not self.calibration_data:
            logger.warning("[FILL_MODEL_INTEGRATION] Calibration 데이터 없음, advice 생성 불가")
            return None
        
        # Zone 선택
        matched_zone = None
        for zone in self.calibration_data["zones"]:
            if (zone["entry_min"] <= entry_bps <= zone["entry_max"] and
                zone["tp_min"] <= tp_bps <= zone["tp_max"]):
                matched_zone = zone
                break
        
        if not matched_zone:
            # Zone 미매칭 시 기본값 사용
            logger.debug(
                f"[FILL_MODEL_INTEGRATION] Zone 미매칭: entry={entry_bps:.2f}, tp={tp_bps:.2f}"
            )
            return FillModelAdvice(
                entry_bps=entry_bps,
                tp_bps=tp_bps,
                zone_id="DEFAULT",
                expected_fill_probability=self.calibration_data["default_buy_fill_ratio"],
                expected_slippage_bps=0.0,  # Slippage는 현재 미구현
                confidence_level=0.0,
            )
        
        # Confidence level 계산 (샘플 수 기반)
        samples = matched_zone.get("samples", 0)
        confidence_level = min(1.0, samples / 30.0)  # 30 samples = 100% confidence
        
        # FillModelAdvice 생성
        advice = FillModelAdvice(
            entry_bps=entry_bps,
            tp_bps=tp_bps,
            zone_id=matched_zone["zone_id"],
            expected_fill_probability=matched_zone["buy_fill_ratio"],  # BUY 기준
            expected_slippage_bps=0.0,  # Slippage는 D87-2+ 구현 예정
            confidence_level=confidence_level,
        )
        
        logger.debug(
            f"[FILL_MODEL_INTEGRATION] Advice 생성: zone={advice.zone_id}, "
            f"fill_prob={advice.expected_fill_probability:.4f}, "
            f"confidence={advice.confidence_level:.2f}"
        )
        
        return advice
    
    def adjust_route_score(
        self,
        base_score: float,
        advice: FillModelAdvice
    ) -> float:
        """
        D87-4: RouteHealthScore 보정 (Multiplicative Zone Preference)
        
        Zone별로 Route Score를 보정한다:
        - AS-IS (D87-1/2): adjusted_score = base_score + bias (Additive)
        - TO-BE (D87-4): adjusted_score = base_score * zone_pref (Multiplicative)
        
        Mode별 Zone Preference:
        - none: 모든 Zone 1.0 (neutral)
        - advisory: Z2=1.05, Z1/Z4=0.90, Z3=0.95
        - strict: Z2=1.15, Z1/Z4=0.80, Z3=0.85
        
        효과:
        - Strict mode, base_score=60.0 기준:
          - Z2: 60.0 * 1.15 = 69.0 (+15%)
          - Z1: 60.0 * 0.80 = 48.0 (-20%)
          - Z2 vs Z1 차이: 21점 (35% 상대 차이)
        
        Args:
            base_score: 기본 RouteHealthScore (0~100)
            advice: Fill Model Advice
        
        Returns:
            보정된 RouteHealthScore (0~100, clipped)
        """
        # Mode가 none이면 보정 없음
        if self.config.mode == "none":
            return base_score
        
        # Zone preference weight 가져오기
        zone_id = advice.zone_id
        zone_pref = self.config.zone_preference.get(self.config.mode, {}).get(
            zone_id,
            self.config.zone_preference[self.config.mode].get("DEFAULT", 1.0)
        )
        
        # Multiplicative adjustment
        adjusted_score = base_score * zone_pref
        
        # 0~100 범위로 clipping
        adjusted_score = max(0.0, min(100.0, adjusted_score))
        
        # 변화율 계산
        change_pct = ((adjusted_score / base_score) - 1.0) * 100 if base_score > 0 else 0.0
        
        logger.debug(
            f"[FILL_MODEL_INTEGRATION] Score 보정 (D87-4 Multiplicative): "
            f"mode={self.config.mode}, base={base_score:.1f}, zone={zone_id}, "
            f"zone_pref={zone_pref:.2f}, adjusted={adjusted_score:.1f} "
            f"({change_pct:+.1f}%)"
        )
        
        return adjusted_score
    
    def adjust_order_size(
        self,
        base_size: float,
        advice: FillModelAdvice
    ) -> float:
        """
        D87-1/D87-2: 주문 수량 조정 (Advisory/Strict Mode)
        
        Zone별로 주문 수량을 조정한다:
        - Advisory Mode:
          - Z2 (고 fill_ratio): base_size * advisory_size_multiplier_z2 (기본 1.1)
          - 기타 Zone: base_size * advisory_size_multiplier_other (기본 1.0)
        - Strict Mode:
          - Z2: base_size * strict_size_multiplier_z2 (기본 1.2)
          - 기타 Zone: base_size * strict_size_multiplier_other (기본 1.0)
        
        Args:
            base_size: 기본 주문 수량
            advice: Fill Model Advice
        
        Returns:
            조정된 주문 수량
        """
        # Mode가 none이면 조정 없음
        if self.config.mode == "none":
            return base_size
        
        # Mode별 multiplier 선택
        if self.config.mode == "advisory":
            if advice.zone_id == "Z2":
                multiplier = self.config.advisory_size_multiplier_z2
            else:
                multiplier = self.config.advisory_size_multiplier_other
        elif self.config.mode == "strict":
            if advice.zone_id == "Z2":
                multiplier = self.config.strict_size_multiplier_z2
            else:
                multiplier = self.config.strict_size_multiplier_other
        else:
            multiplier = 1.0
        
        adjusted_size = base_size * multiplier
        
        logger.debug(
            f"[FILL_MODEL_INTEGRATION] Size 조정: "
            f"mode={self.config.mode}, base={base_size:.6f}, zone={advice.zone_id}, "
            f"multiplier={multiplier:.2f}, adjusted={adjusted_size:.6f}"
        )
        
        return adjusted_size
    
    def adjust_risk_limit(
        self,
        base_limit: float,
        advice: FillModelAdvice
    ) -> float:
        """
        D87-1/D87-2: RiskGuard 한도 조정 (Advisory/Strict Mode)
        
        Zone별로 Risk Limit을 조정한다:
        - Advisory Mode:
          - Z2 (고 fill_ratio): base_limit * advisory_risk_multiplier_z2 (기본 1.1)
          - 기타 Zone: base_limit * advisory_risk_multiplier_other (기본 1.0)
        - Strict Mode:
          - Z2: base_limit * strict_risk_multiplier_z2 (기본 1.2)
          - 기타 Zone: base_limit * strict_risk_multiplier_other (기본 1.0)
        
        Args:
            base_limit: 기본 Risk Limit (예: max_notional, max_position)
            advice: Fill Model Advice
        
        Returns:
            조정된 Risk Limit
        """
        # Mode가 none이면 조정 없음
        if self.config.mode == "none":
            return base_limit
        
        # Mode별 multiplier 선택
        if self.config.mode == "advisory":
            if advice.zone_id == "Z2":
                multiplier = self.config.advisory_risk_multiplier_z2
            else:
                multiplier = self.config.advisory_risk_multiplier_other
        elif self.config.mode == "strict":
            if advice.zone_id == "Z2":
                multiplier = self.config.strict_risk_multiplier_z2
            else:
                multiplier = self.config.strict_risk_multiplier_other
        else:
            multiplier = 1.0
        
        adjusted_limit = base_limit * multiplier
        
        logger.debug(
            f"[FILL_MODEL_INTEGRATION] Risk Limit 조정: "
            f"mode={self.config.mode}, base={base_limit:.2f}, zone={advice.zone_id}, "
            f"multiplier={multiplier:.2f}, adjusted={adjusted_limit:.2f}"
        )
        
        return adjusted_limit
    
    def check_health(self) -> dict:
        """
        D87-1: Fill Model 상태 검증
        
        Calibration staleness, confidence level 등을 확인하고,
        경고가 있는 경우 warnings 리스트를 반환한다.
        
        Returns:
            {
                "healthy": bool,
                "calibration_age_seconds": float,
                "confidence_level": float,
                "warnings": list[str]
            }
        """
        warnings = []
        
        # Calibration 로드 여부
        if not self.calibration_data:
            warnings.append("Calibration 데이터 없음")
            return {
                "healthy": False,
                "calibration_age_seconds": -1.0,
                "confidence_level": 0.0,
                "warnings": warnings,
            }
        
        # Calibration staleness 확인
        calibration_age_seconds = 0.0
        if self.calibration_loaded_at:
            calibration_age_seconds = time.time() - self.calibration_loaded_at
            
            if calibration_age_seconds > self.config.staleness_threshold_seconds:
                warnings.append(
                    f"Calibration 오래됨: {calibration_age_seconds:.0f}s > "
                    f"{self.config.staleness_threshold_seconds:.0f}s"
                )
        
        # Zone별 샘플 수 확인 (confidence level)
        total_samples = sum(zone.get("samples", 0) for zone in self.calibration_data["zones"])
        avg_confidence = min(1.0, total_samples / (30.0 * len(self.calibration_data["zones"])))
        
        if avg_confidence < self.config.min_confidence_level:
            warnings.append(
                f"Confidence 낮음: {avg_confidence:.2f} < {self.config.min_confidence_level:.2f}"
            )
        
        healthy = len(warnings) == 0
        
        return {
            "healthy": healthy,
            "calibration_age_seconds": calibration_age_seconds,
            "confidence_level": avg_confidence,
            "warnings": warnings,
        }
