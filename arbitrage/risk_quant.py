#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-Performance Advanced Quantitative Risk Management (PHASE D15)
==================================================================

VaR, Expected Shortfall, 스트레스 테스트 (고성능 버전).

특징:
- NumPy 벡터화 Historical VaR (95%, 99%)
- NumPy 벡터화 Expected Shortfall
- 벡터화 스트레스 테스트
- 유동성 조정 리스크 페널티
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RiskMetrics:
    """리스크 메트릭"""
    var_95: float           # 95% VaR
    var_99: float           # 99% VaR
    expected_shortfall: float  # Expected Shortfall
    max_drawdown: float     # 최대 낙폭
    sharpe_ratio: float     # 샤프 지수


class QuantitativeRiskManager:
    """
    고성능 정량적 리스크 관리자
    
    NumPy 벡터화 연산을 활용한 VaR, ES, 스트레스 테스트.
    """
    
    def __init__(self, window_size: int = 100):
        """
        Args:
            window_size: 히스토리 윈도우 크기
        """
        self.window_size = window_size
        
        # NumPy 배열로 히스토리 관리 (벡터화)
        self.returns_history = np.array([], dtype=np.float32)
        self.pnl_history = np.array([], dtype=np.float32)
        self.volatility_history = np.array([], dtype=np.float32)
    
    def record_return(self, return_pct: float) -> None:
        """수익률 기록 (벡터화)"""
        self.returns_history = np.append(self.returns_history, return_pct)
        if len(self.returns_history) > self.window_size:
            self.returns_history = self.returns_history[-self.window_size:]
    
    def record_returns_batch(self, returns: np.ndarray) -> None:
        """배치 수익률 기록 (벡터화)"""
        returns = np.asarray(returns, dtype=np.float32)
        self.returns_history = np.append(self.returns_history, returns)
        if len(self.returns_history) > self.window_size:
            self.returns_history = self.returns_history[-self.window_size:]
    
    def record_pnl(self, pnl: float) -> None:
        """손익 기록 (벡터화)"""
        self.pnl_history = np.append(self.pnl_history, pnl)
        if len(self.pnl_history) > self.window_size:
            self.pnl_history = self.pnl_history[-self.window_size:]
    
    def record_pnl_batch(self, pnl: np.ndarray) -> None:
        """배치 손익 기록 (벡터화)"""
        pnl = np.asarray(pnl, dtype=np.float32)
        self.pnl_history = np.append(self.pnl_history, pnl)
        if len(self.pnl_history) > self.window_size:
            self.pnl_history = self.pnl_history[-self.window_size:]
    
    def record_volatility(self, volatility: float) -> None:
        """변동성 기록 (벡터화)"""
        self.volatility_history = np.append(self.volatility_history, volatility)
        if len(self.volatility_history) > self.window_size:
            self.volatility_history = self.volatility_history[-self.window_size:]
    
    def record_volatilities_batch(self, volatilities: np.ndarray) -> None:
        """배치 변동성 기록 (벡터화)"""
        volatilities = np.asarray(volatilities, dtype=np.float32)
        self.volatility_history = np.append(self.volatility_history, volatilities)
        if len(self.volatility_history) > self.window_size:
            self.volatility_history = self.volatility_history[-self.window_size:]
    
    def calculate_var(self, confidence_level: float = 0.95) -> float:
        """
        Historical VaR 계산 (벡터화)
        
        Args:
            confidence_level: 신뢰도 (0.95 또는 0.99)
        
        Returns:
            VaR 값 (음수)
        """
        if len(self.returns_history) < 10:
            return 0.0
        
        # NumPy 벡터화 quantile 계산
        var = float(np.quantile(self.returns_history, 1 - confidence_level))
        return var
    
    def calculate_expected_shortfall(self, confidence_level: float = 0.95) -> float:
        """
        Expected Shortfall (CVaR) 계산 (벡터화)
        
        VaR보다 극단적인 손실의 평균
        
        Args:
            confidence_level: 신뢰도
        
        Returns:
            Expected Shortfall 값 (음수)
        """
        if len(self.returns_history) < 10:
            return 0.0
        
        # VaR 계산
        var = self.calculate_var(confidence_level)
        
        # 벡터화 필터링
        tail_returns = self.returns_history[self.returns_history <= var]
        
        if len(tail_returns) == 0:
            return var
        
        # 벡터화 평균
        return float(np.mean(tail_returns))
    
    def calculate_max_drawdown(self) -> float:
        """
        최대 낙폭 계산 (벡터화)
        
        Returns:
            최대 낙폭 (음수)
        """
        if len(self.pnl_history) < 2:
            return 0.0
        
        # 벡터화 누적합
        cumulative_pnl = np.cumsum(self.pnl_history)
        
        # 벡터화 누적 최대값
        running_max = np.maximum.accumulate(cumulative_pnl)
        
        # 벡터화 낙폭 계산
        drawdown = cumulative_pnl - running_max
        
        return float(np.min(drawdown))
    
    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """
        샤프 지수 계산 (벡터화)
        
        Args:
            risk_free_rate: 무위험 수익률 (연율)
        
        Returns:
            샤프 지수
        """
        if len(self.returns_history) < 2:
            return 0.0
        
        # 벡터화 평균, 표준편차
        mean_return = np.mean(self.returns_history)
        std_return = np.std(self.returns_history)
        
        if std_return == 0:
            return 0.0
        
        # 일일 무위험 수익률
        daily_rf = risk_free_rate / 252
        
        # 샤프 지수 계산
        sharpe = (mean_return - daily_rf) / std_return * np.sqrt(252)
        
        return float(sharpe)
    
    def get_risk_metrics(self) -> RiskMetrics:
        """전체 리스크 메트릭 계산 (벡터화)"""
        return RiskMetrics(
            var_95=self.calculate_var(0.95),
            var_99=self.calculate_var(0.99),
            expected_shortfall=self.calculate_expected_shortfall(0.95),
            max_drawdown=self.calculate_max_drawdown(),
            sharpe_ratio=self.calculate_sharpe_ratio()
        )
    
    def stress_test_volatility_spike(
        self,
        current_position_krw: float,
        volatility_multiplier: float = 2.0
    ) -> float:
        """
        스트레스 테스트: 변동성 급증 (벡터화)
        
        Args:
            current_position_krw: 현재 포지션 (KRW)
            volatility_multiplier: 변동성 배수
        
        Returns:
            예상 손실 (KRW)
        """
        if len(self.volatility_history) == 0:
            return 0.0
        
        # 벡터화 평균
        avg_volatility = np.mean(self.volatility_history)
        stressed_volatility = avg_volatility * volatility_multiplier
        
        # 변동성 증가 → 손실 증가
        loss_pct = stressed_volatility * 10
        loss_krw = current_position_krw * loss_pct / 100
        
        return float(loss_krw)
    
    def stress_test_spread_widening(
        self,
        current_position_krw: float,
        spread_multiplier: float = 3.0
    ) -> float:
        """
        스트레스 테스트: 스프레드 확대 (벡터화)
        
        Args:
            current_position_krw: 현재 포지션
            spread_multiplier: 스프레드 배수
        
        Returns:
            예상 손실 (KRW)
        """
        base_spread_pct = 0.1
        stressed_spread = base_spread_pct * spread_multiplier
        loss_krw = current_position_krw * stressed_spread / 100
        
        return float(loss_krw)
    
    def stress_test_exchange_outage(
        self,
        current_position_krw: float,
        outage_duration_hours: float = 1.0
    ) -> float:
        """
        스트레스 테스트: 거래소 장애 (벡터화)
        
        Args:
            current_position_krw: 현재 포지션
            outage_duration_hours: 장애 지속 시간
        
        Returns:
            예상 손실 (KRW)
        """
        loss_pct = outage_duration_hours * 0.1
        loss_krw = current_position_krw * loss_pct / 100
        
        return float(loss_krw)
    
    def stress_test_batch(
        self,
        position_krw: float,
        scenarios: Dict[str, float]
    ) -> Dict[str, float]:
        """
        배치 스트레스 테스트 (벡터화)
        
        Args:
            position_krw: 포지션 크기
            scenarios: {시나리오명: 파라미터} 딕셔너리
        
        Returns:
            {시나리오명: 손실} 딕셔너리
        """
        results = {}
        
        if 'vol_spike' in scenarios:
            results['vol_spike'] = self.stress_test_volatility_spike(
                position_krw, scenarios['vol_spike']
            )
        
        if 'spread_widening' in scenarios:
            results['spread_widening'] = self.stress_test_spread_widening(
                position_krw, scenarios['spread_widening']
            )
        
        if 'exchange_outage' in scenarios:
            results['exchange_outage'] = self.stress_test_exchange_outage(
                position_krw, scenarios['exchange_outage']
            )
        
        return results
    
    def get_liquidity_adjusted_risk(
        self,
        position_krw: float,
        daily_volume_krw: float
    ) -> float:
        """
        유동성 조정 리스크 페널티 (벡터화)
        
        포지션이 일일 거래량에 비해 크면 페널티 증가
        
        Args:
            position_krw: 포지션 크기
            daily_volume_krw: 일일 거래량
        
        Returns:
            리스크 페널티 (%)
        """
        if daily_volume_krw == 0:
            return 100.0
        
        position_ratio = position_krw / daily_volume_krw
        
        # 벡터화 페널티 계산 (NumPy clip 사용)
        penalty = np.clip(
            np.where(position_ratio < 0.01, 0.0,
            np.where(position_ratio < 0.05, 0.5,
            np.where(position_ratio < 0.1, 1.0,
            np.where(position_ratio < 0.2, 2.0, 5.0)))),
            0.0, 100.0
        )
        
        return float(penalty)
    
    def get_stats(self) -> Dict[str, any]:
        """통계 반환 (벡터화)"""
        metrics = self.get_risk_metrics()
        
        return {
            'var_95': metrics.var_95,
            'var_99': metrics.var_99,
            'expected_shortfall': metrics.expected_shortfall,
            'max_drawdown': metrics.max_drawdown,
            'sharpe_ratio': metrics.sharpe_ratio,
            'num_returns': len(self.returns_history),
            'num_pnl': len(self.pnl_history),
            'num_volatility': len(self.volatility_history)
        }
