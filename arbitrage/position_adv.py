#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Position Management (PHASE D14)
========================================

변동성 기반 포지션 사이징, 시장 레짐 감지, 동적 노출도 조정.

특징:
- 변동성 기반 포지션 사이징 (D13 확장)
- 시장 레짐 감지 (Trending / Ranging)
- Slippage 비용 기반 포지션 감쇠
- Exposure 카운터 기반 max_exposure 동적 조정
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """시장 레짐"""
    RANGING = "ranging"        # 박스권
    TRENDING = "trending"      # 추세


class AdvancedPositionManager:
    """고급 포지션 관리자"""
    
    def __init__(
        self,
        base_position_size_krw: float = 100000.0,
        max_exposure_krw: float = 500000.0,
        slippage_cost_threshold_pct: float = 0.2
    ):
        """
        Args:
            base_position_size_krw: 기본 포지션 사이즈
            max_exposure_krw: 최대 노출도
            slippage_cost_threshold_pct: 슬리피지 비용 임계치
        """
        self.base_position_size_krw = base_position_size_krw
        self.max_exposure_krw = max_exposure_krw
        self.slippage_cost_threshold_pct = slippage_cost_threshold_pct
        
        # 상태
        self.market_regime = MarketRegime.RANGING
        self.price_history: list = []
        self.max_price_history = 50
        self.cumulative_slippage_cost = 0.0
        self.exposure_counter = 0
    
    def update_market_data(self, price: float, bid_ask_spread_pct: float = 0.0) -> None:
        """
        시장 데이터 업데이트
        
        Args:
            price: 현재 가격
            bid_ask_spread_pct: Bid-Ask 스프레드 (%)
        """
        self.price_history.append(price)
        if len(self.price_history) > self.max_price_history:
            self.price_history.pop(0)
        
        # 슬리피지 누적
        self.cumulative_slippage_cost += bid_ask_spread_pct
        
        # 레짐 감지
        self._detect_regime()
    
    def _detect_regime(self) -> None:
        """시장 레짐 감지 (Trending vs Ranging)"""
        if len(self.price_history) < 10:
            self.market_regime = MarketRegime.RANGING
            return
        
        # 최근 10개 가격의 표준편차 계산
        recent_prices = self.price_history[-10:]
        mean_price = sum(recent_prices) / len(recent_prices)
        variance = sum((p - mean_price) ** 2 for p in recent_prices) / len(recent_prices)
        stddev = variance ** 0.5
        
        # 변동성 계수 (Coefficient of Variation)
        if mean_price == 0:
            cv = 0.0
        else:
            cv = stddev / mean_price
        
        # CV > 2% → Trending, 아니면 Ranging
        self.market_regime = MarketRegime.TRENDING if cv > 0.02 else MarketRegime.RANGING
    
    def get_dynamic_position_size(
        self,
        volatility_estimate: float,
        risk_mode: str = "normal"
    ) -> float:
        """
        동적 포지션 사이즈 계산
        
        Args:
            volatility_estimate: 변동성 추정치 (0.0~1.0)
            risk_mode: 리스크 모드 (normal/cautious/extreme)
        
        Returns:
            포지션 사이즈 (KRW)
        """
        # 기본 배수 (리스크 모드)
        risk_multiplier = {
            'normal': 1.0,
            'cautious': 0.6,
            'extreme': 0.3
        }.get(risk_mode, 1.0)
        
        # 레짐 배수 (Trending에서 더 공격적)
        regime_multiplier = 1.2 if self.market_regime == MarketRegime.TRENDING else 0.8
        
        # 슬리피지 감쇠 (누적 슬리피지가 높으면 포지션 감소)
        slippage_decay = max(0.5, 1.0 - (self.cumulative_slippage_cost / 100.0))
        
        # 최종 포지션 사이즈
        position_size = (
            self.base_position_size_krw *
            risk_multiplier *
            regime_multiplier *
            slippage_decay
        )
        
        return position_size
    
    def get_adjusted_exposure_limit(
        self,
        current_exposure_krw: float,
        exposure_increase_rate: float = 0.0
    ) -> float:
        """
        동적 노출도 한계 조정
        
        Args:
            current_exposure_krw: 현재 노출도
            exposure_increase_rate: 노출도 증가 속도 (d/dt)
        
        Returns:
            조정된 max_exposure
        """
        # 노출도 증가 속도가 높으면 한계 감소
        if exposure_increase_rate > 0.1:  # 10% 이상 증가
            # 한계를 현재 노출도 + 10%로 제한
            adjusted_limit = current_exposure_krw * 1.1
        elif exposure_increase_rate > 0.05:  # 5% 이상 증가
            # 한계를 현재 노출도 + 20%로 제한
            adjusted_limit = current_exposure_krw * 1.2
        else:
            # 정상: 기본 한계 사용
            adjusted_limit = self.max_exposure_krw
        
        return min(adjusted_limit, self.max_exposure_krw)
    
    def record_trade(self, trade_size_krw: float) -> None:
        """거래 기록 (노출도 카운터 업데이트)"""
        self.exposure_counter += 1
        
        # 누적 슬리피지 리셋 (거래 후)
        if self.exposure_counter % 10 == 0:
            self.cumulative_slippage_cost = 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        return {
            'market_regime': self.market_regime.value,
            'cumulative_slippage_cost': self.cumulative_slippage_cost,
            'exposure_counter': self.exposure_counter,
            'price_history_length': len(self.price_history)
        }
