#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Risk Model (PHASE D13)
===============================

변동성 기반 포지션 사이징, 동적 슬리피지, 거래 차단 조건 등
고급 리스크 관리 모델.

특징:
- ATR/표준편차 기반 변동성 계산
- 변동성 기반 포지션 사이징
- 동적 슬리피지 허용도
- 시장 불안정성 감지
- WS 지연 스파이크 감지
- 스프레드 역전 패턴 감지
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class RiskMode(Enum):
    """리스크 모드"""
    NORMAL = "normal"          # 정상
    CAUTIOUS = "cautious"      # 주의
    EXTREME = "extreme"        # 극단적


@dataclass
class RiskDecision:
    """리스크 결정"""
    allow_trade: bool                   # 거래 허용 여부
    risk_mode: RiskMode                 # 리스크 모드
    position_size_multiplier: float     # 포지션 사이즈 배수 (1.0 = 기본값)
    slippage_tolerance_pct: float       # 슬리피지 허용도 (%)
    block_reason: Optional[str] = None  # 차단 사유
    volatility_estimate: float = 0.0    # 변동성 추정치


class VolatilityCalculator:
    """변동성 계산기"""
    
    def __init__(self, window_size: int = 20):
        """
        Args:
            window_size: 계산 윈도우 크기
        """
        self.window_size = window_size
        self.price_history: List[float] = []
    
    def add_price(self, price: float) -> None:
        """가격 추가"""
        self.price_history.append(price)
        if len(self.price_history) > self.window_size:
            self.price_history.pop(0)
    
    def calculate_atr(self, high: float, low: float, close: float) -> float:
        """
        ATR (Average True Range) 계산
        
        Args:
            high: 고가
            low: 저가
            close: 종가
        
        Returns:
            ATR 값
        """
        if len(self.price_history) < 2:
            return 0.0
        
        prev_close = self.price_history[-2] if len(self.price_history) >= 2 else close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        return tr
    
    def calculate_stddev(self) -> float:
        """
        표준편차 계산
        
        Returns:
            표준편차
        """
        if len(self.price_history) < 2:
            return 0.0
        
        mean = sum(self.price_history) / len(self.price_history)
        variance = sum((x - mean) ** 2 for x in self.price_history) / len(self.price_history)
        return variance ** 0.5
    
    def get_volatility_estimate(self) -> float:
        """변동성 추정치 (0.0 ~ 1.0)"""
        if not self.price_history:
            return 0.5  # 기본값
        
        stddev = self.calculate_stddev()
        mean = sum(self.price_history) / len(self.price_history)
        
        if mean == 0:
            return 0.5
        
        # 변동성 비율 (표준편차 / 평균)
        volatility_ratio = stddev / mean
        
        # 0.0 ~ 1.0 범위로 정규화 (0.05 = 5% 변동성)
        return min(volatility_ratio / 0.05, 1.0)


class RiskModel:
    """고급 리스크 모델"""
    
    def __init__(
        self,
        base_position_size_krw: float = 100000.0,
        max_position_size_krw: float = 300000.0,
        base_slippage_tolerance_pct: float = 0.5
    ):
        """
        Args:
            base_position_size_krw: 기본 포지션 사이즈 (KRW)
            max_position_size_krw: 최대 포지션 사이즈 (KRW)
            base_slippage_tolerance_pct: 기본 슬리피지 허용도 (%)
        """
        self.base_position_size_krw = base_position_size_krw
        self.max_position_size_krw = max_position_size_krw
        self.base_slippage_tolerance_pct = base_slippage_tolerance_pct
        
        # 변동성 계산기
        self.volatility_calc = VolatilityCalculator()
        
        # 상태
        self.last_ws_lag_ms = 0.0
        self.ws_lag_spike_count = 0
        self.last_spread_pct = 0.0
        self.spread_inversion_count = 0
    
    def update_market_data(
        self,
        price: float,
        high: float = None,
        low: float = None,
        ws_lag_ms: float = 0.0,
        spread_pct: float = 0.0
    ) -> None:
        """
        시장 데이터 업데이트
        
        Args:
            price: 현재 가격
            high: 고가
            low: 저가
            ws_lag_ms: WebSocket 지연 (ms)
            spread_pct: 스프레드 (%)
        """
        # 변동성 계산
        self.volatility_calc.add_price(price)
        
        # WS 지연 스파이크 감지
        if ws_lag_ms > 1000.0 and self.last_ws_lag_ms < 500.0:
            self.ws_lag_spike_count += 1
        self.last_ws_lag_ms = ws_lag_ms
        
        # 스프레드 역전 감지
        if spread_pct < 0 and self.last_spread_pct >= 0:
            self.spread_inversion_count += 1
        self.last_spread_pct = spread_pct
    
    def evaluate_risk(self, metrics: Dict[str, Any]) -> RiskDecision:
        """
        리스크 평가
        
        Args:
            metrics: 메트릭 딕셔너리
        
        Returns:
            RiskDecision
        """
        volatility = self.volatility_calc.get_volatility_estimate()
        
        # 리스크 모드 결정
        if volatility > 0.8 or self.ws_lag_spike_count > 5:
            risk_mode = RiskMode.EXTREME
        elif volatility > 0.5 or self.ws_lag_spike_count > 2:
            risk_mode = RiskMode.CAUTIOUS
        else:
            risk_mode = RiskMode.NORMAL
        
        # 거래 차단 조건 확인
        allow_trade = True
        block_reason = None
        
        # 1. 극단적 변동성
        if volatility > 0.9:
            allow_trade = False
            block_reason = f"Extreme volatility: {volatility:.2f}"
        
        # 2. WS 지연 스파이크 과다
        elif self.ws_lag_spike_count > 10:
            allow_trade = False
            block_reason = f"WS lag spikes: {self.ws_lag_spike_count}"
        
        # 3. 스프레드 역전 과다
        elif self.spread_inversion_count > 5:
            allow_trade = False
            block_reason = f"Spread inversions: {self.spread_inversion_count}"
        
        # 4. Redis 문제
        elif metrics.get("redis_heartbeat_age_ms", 0) > 30000:
            allow_trade = False
            block_reason = "Redis heartbeat stale"
        
        # 5. 루프 지연 과다
        elif metrics.get("loop_latency_ms", 0) > 5000:
            allow_trade = False
            block_reason = "Loop latency critical"
        
        # 포지션 사이즈 배수 계산
        position_size_multiplier = self._calculate_position_multiplier(volatility, risk_mode)
        
        # 슬리피지 허용도 계산
        slippage_tolerance_pct = self._calculate_slippage_tolerance(volatility, risk_mode)
        
        return RiskDecision(
            allow_trade=allow_trade,
            risk_mode=risk_mode,
            position_size_multiplier=position_size_multiplier,
            slippage_tolerance_pct=slippage_tolerance_pct,
            block_reason=block_reason,
            volatility_estimate=volatility
        )
    
    def _calculate_position_multiplier(self, volatility: float, risk_mode: RiskMode) -> float:
        """
        포지션 사이즈 배수 계산
        
        변동성이 높을수록 포지션 사이즈 감소
        """
        if risk_mode == RiskMode.EXTREME:
            return 0.3  # 30% 포지션
        elif risk_mode == RiskMode.CAUTIOUS:
            return 0.6  # 60% 포지션
        else:
            return 1.0  # 100% 포지션
    
    def _calculate_slippage_tolerance(self, volatility: float, risk_mode: RiskMode) -> float:
        """
        슬리피지 허용도 계산
        
        변동성이 높을수록 슬리피지 허용도 증가 (거래 성공률 향상)
        """
        if risk_mode == RiskMode.EXTREME:
            return 1.5  # 1.5% (기본값 0.5%에서 3배)
        elif risk_mode == RiskMode.CAUTIOUS:
            return 0.8  # 0.8% (기본값 0.5%에서 1.6배)
        else:
            return 0.5  # 0.5% (기본값)
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        return {
            'volatility_estimate': self.volatility_calc.get_volatility_estimate(),
            'ws_lag_spike_count': self.ws_lag_spike_count,
            'spread_inversion_count': self.spread_inversion_count,
            'last_ws_lag_ms': self.last_ws_lag_ms,
            'last_spread_pct': self.last_spread_pct
        }
