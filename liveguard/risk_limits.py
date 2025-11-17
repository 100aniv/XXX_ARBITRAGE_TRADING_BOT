#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — Risk Limits Configuration
=============================================

리스크 제한 설정 (포지션, 손실, 거래 빈도).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskLimits:
    """
    리스크 제한 설정
    
    포지션 크기, 일일 손실, 거래 빈도 등을 제어.
    """
    
    # 포지션 제한
    max_position_size: float = 1_000_000  # 최대 포지션 크기 (KRW)
    max_position_count: int = 10  # 최대 동시 포지션 수
    
    # 손실 제한
    max_daily_loss: float = 500_000  # 최대 일일 손실 (KRW)
    max_total_loss: float = 2_000_000  # 최대 누적 손실 (KRW)
    
    # 거래 빈도 제한
    max_trades_per_hour: int = 100  # 시간당 최대 거래 수
    max_trades_per_day: int = 1000  # 일일 최대 거래 수
    
    # 슬리피지 제한
    max_slippage_pct: float = 0.5  # 최대 슬리피지 (%)
    
    # 체결율 제한
    min_fill_rate: float = 0.8  # 최소 체결율 (80%)
    
    # 스프레드 제한
    min_spread_pct: float = 0.1  # 최소 수익 스프레드 (%)
    
    # 회로차단기
    circuit_breaker_threshold: float = 0.05  # 손실 임계값 (5%)
    circuit_breaker_cooldown: int = 300  # 회로차단기 쿨다운 (초)
    
    def validate(self) -> bool:
        """
        설정 유효성 검사
        
        Returns:
            유효 여부
        """
        if self.max_position_size <= 0:
            return False
        if self.max_position_count <= 0:
            return False
        if self.max_daily_loss <= 0:
            return False
        if self.max_total_loss <= 0:
            return False
        if self.max_trades_per_hour <= 0:
            return False
        if self.max_trades_per_day <= 0:
            return False
        if self.max_slippage_pct < 0:
            return False
        if not (0 <= self.min_fill_rate <= 1):
            return False
        if self.min_spread_pct < 0:
            return False
        if not (0 <= self.circuit_breaker_threshold <= 1):
            return False
        if self.circuit_breaker_cooldown < 0:
            return False
        
        return True
    
    def to_dict(self) -> dict:
        """설정을 딕셔너리로 변환"""
        return {
            "max_position_size": self.max_position_size,
            "max_position_count": self.max_position_count,
            "max_daily_loss": self.max_daily_loss,
            "max_total_loss": self.max_total_loss,
            "max_trades_per_hour": self.max_trades_per_hour,
            "max_trades_per_day": self.max_trades_per_day,
            "max_slippage_pct": self.max_slippage_pct,
            "min_fill_rate": self.min_fill_rate,
            "min_spread_pct": self.min_spread_pct,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
            "circuit_breaker_cooldown": self.circuit_breaker_cooldown,
        }
