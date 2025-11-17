#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — Safety Module (LiveGuard)
=============================================

실거래 안전 장치:
- 포지션 크기 제한
- 일일/누적 손실 제한
- 거래 빈도 제한
- 슬리피지 검사
- 체결율 관리
- 회로차단기
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import numpy as np

from arbitrage.types import Order, Position, OrderStatus
from .risk_limits import RiskLimits

logger = logging.getLogger(__name__)


@dataclass
class SafetyState:
    """안전 상태 추적"""
    daily_loss: float = 0.0
    total_loss: float = 0.0
    trades_this_hour: int = 0
    trades_today: int = 0
    last_hour_reset: datetime = field(default_factory=datetime.utcnow)
    last_day_reset: datetime = field(default_factory=datetime.utcnow)
    circuit_breaker_active: bool = False
    circuit_breaker_activated_at: Optional[datetime] = None


class SafetyModule:
    """
    실거래 안전 장치
    
    D15 리스크 메트릭과 연동하여 실거래 시 손실을 제한.
    """
    
    def __init__(self, limits: Optional[RiskLimits] = None):
        """
        Args:
            limits: 리스크 제한 설정 (기본값 사용 시 None)
        """
        self.limits = limits or RiskLimits()
        
        if not self.limits.validate():
            raise ValueError("Invalid risk limits")
        
        self.state = SafetyState()
        self._order_history: List[Order] = []
        self._position_history: List[Position] = []
    
    def check_position_size(self, position_value: float) -> tuple[bool, Optional[str]]:
        """
        포지션 크기 검사
        
        Args:
            position_value: 포지션 가치
        
        Returns:
            (허용 여부, 거부 사유)
        """
        if position_value > self.limits.max_position_size:
            return False, f"Position size {position_value} exceeds limit {self.limits.max_position_size}"
        
        return True, None
    
    def check_position_count(self, current_positions: int) -> tuple[bool, Optional[str]]:
        """
        동시 포지션 수 검사
        
        Args:
            current_positions: 현재 포지션 수
        
        Returns:
            (허용 여부, 거부 사유)
        """
        if current_positions >= self.limits.max_position_count:
            return False, f"Position count {current_positions} exceeds limit {self.limits.max_position_count}"
        
        return True, None
    
    def check_daily_loss(self, current_loss: float) -> tuple[bool, Optional[str]]:
        """
        일일 손실 검사
        
        Args:
            current_loss: 현재 손실
        
        Returns:
            (허용 여부, 거부 사유)
        """
        # 일일 리셋 확인
        now = datetime.utcnow()
        if (now - self.state.last_day_reset).days >= 1:
            self.state.daily_loss = 0.0
            self.state.trades_today = 0
            self.state.last_day_reset = now
        
        total_daily_loss = self.state.daily_loss + current_loss
        
        if total_daily_loss > self.limits.max_daily_loss:
            return False, f"Daily loss {total_daily_loss} exceeds limit {self.limits.max_daily_loss}"
        
        return True, None
    
    def check_total_loss(self, current_loss: float) -> tuple[bool, Optional[str]]:
        """
        누적 손실 검사
        
        Args:
            current_loss: 현재 손실
        
        Returns:
            (허용 여부, 거부 사유)
        """
        total_loss = self.state.total_loss + current_loss
        
        if total_loss > self.limits.max_total_loss:
            return False, f"Total loss {total_loss} exceeds limit {self.limits.max_total_loss}"
        
        return True, None
    
    def check_trade_frequency(self) -> tuple[bool, Optional[str]]:
        """
        거래 빈도 검사
        
        Args:
        
        Returns:
            (허용 여부, 거부 사유)
        """
        now = datetime.utcnow()
        
        # 시간별 리셋
        if (now - self.state.last_hour_reset).seconds >= 3600:
            self.state.trades_this_hour = 0
            self.state.last_hour_reset = now
        
        # 시간당 거래 수 검사
        if self.state.trades_this_hour >= self.limits.max_trades_per_hour:
            return False, f"Trades this hour {self.state.trades_this_hour} exceeds limit {self.limits.max_trades_per_hour}"
        
        # 일일 거래 수 검사
        if self.state.trades_today >= self.limits.max_trades_per_day:
            return False, f"Trades today {self.state.trades_today} exceeds limit {self.limits.max_trades_per_day}"
        
        return True, None
    
    def check_slippage(self, expected_price: float, actual_price: float) -> tuple[bool, Optional[str]]:
        """
        슬리피지 검사
        
        Args:
            expected_price: 예상 가격
            actual_price: 실제 가격
        
        Returns:
            (허용 여부, 거부 사유)
        """
        if expected_price == 0:
            return False, "Expected price is zero"
        
        slippage_pct = abs(actual_price - expected_price) / expected_price * 100
        
        if slippage_pct > self.limits.max_slippage_pct:
            return False, f"Slippage {slippage_pct:.2f}% exceeds limit {self.limits.max_slippage_pct}%"
        
        return True, None
    
    def check_fill_rate(self, order: Order) -> tuple[bool, Optional[str]]:
        """
        체결율 검사
        
        Args:
            order: 주문 정보
        
        Returns:
            (허용 여부, 거부 사유)
        """
        if order.fill_rate < self.limits.min_fill_rate:
            return False, f"Fill rate {order.fill_rate:.2%} below minimum {self.limits.min_fill_rate:.2%}"
        
        return True, None
    
    def check_spread(self, spread_pct: float) -> tuple[bool, Optional[str]]:
        """
        스프레드 검사
        
        Args:
            spread_pct: 스프레드 비율 (%)
        
        Returns:
            (허용 여부, 거부 사유)
        """
        if spread_pct < self.limits.min_spread_pct:
            return False, f"Spread {spread_pct:.2f}% below minimum {self.limits.min_spread_pct}%"
        
        return True, None
    
    def check_circuit_breaker(self, current_loss: float, total_balance: float) -> tuple[bool, Optional[str]]:
        """
        회로차단기 검사
        
        Args:
            current_loss: 현재 손실
            total_balance: 총 잔액
        
        Returns:
            (허용 여부, 거부 사유)
        """
        now = datetime.utcnow()
        
        # 회로차단기 쿨다운 확인
        if self.state.circuit_breaker_active:
            if self.state.circuit_breaker_activated_at:
                elapsed = (now - self.state.circuit_breaker_activated_at).seconds
                if elapsed >= self.limits.circuit_breaker_cooldown:
                    self.state.circuit_breaker_active = False
                    logger.info("Circuit breaker cooldown expired")
                else:
                    return False, f"Circuit breaker active (cooldown: {self.limits.circuit_breaker_cooldown - elapsed}s)"
        
        # 손실 임계값 확인
        if total_balance > 0:
            loss_ratio = current_loss / total_balance
            if loss_ratio > self.limits.circuit_breaker_threshold:
                self.state.circuit_breaker_active = True
                self.state.circuit_breaker_activated_at = now
                logger.warning(f"Circuit breaker activated: loss ratio {loss_ratio:.2%}")
                return False, f"Circuit breaker triggered: loss ratio {loss_ratio:.2%} exceeds {self.limits.circuit_breaker_threshold:.2%}"
        
        return True, None
    
    def can_execute_order(
        self,
        position_value: float,
        current_positions: int,
        current_loss: float,
        total_balance: float
    ) -> tuple[bool, Optional[str]]:
        """
        주문 실행 가능 여부 종합 검사
        
        Args:
            position_value: 포지션 가치
            current_positions: 현재 포지션 수
            current_loss: 현재 손실
            total_balance: 총 잔액
        
        Returns:
            (실행 가능 여부, 거부 사유)
        """
        checks = [
            ("position_size", self.check_position_size(position_value)),
            ("position_count", self.check_position_count(current_positions)),
            ("daily_loss", self.check_daily_loss(current_loss)),
            ("total_loss", self.check_total_loss(current_loss)),
            ("trade_frequency", self.check_trade_frequency()),
            ("circuit_breaker", self.check_circuit_breaker(current_loss, total_balance)),
        ]
        
        for check_name, (allowed, reason) in checks:
            if not allowed:
                logger.warning(f"Order rejected: {check_name} - {reason}")
                return False, reason
        
        return True, None
    
    def record_trade(self, loss: float) -> None:
        """
        거래 기록
        
        Args:
            loss: 손실액
        """
        now = datetime.utcnow()
        
        # 일일 리셋
        if (now - self.state.last_day_reset).days >= 1:
            self.state.daily_loss = 0.0
            self.state.trades_today = 0
            self.state.last_day_reset = now
        
        # 시간별 리셋
        if (now - self.state.last_hour_reset).seconds >= 3600:
            self.state.trades_this_hour = 0
            self.state.last_hour_reset = now
        
        # 손실 기록
        self.state.daily_loss += loss
        self.state.total_loss += loss
        self.state.trades_this_hour += 1
        self.state.trades_today += 1
        
        logger.info(
            f"Trade recorded: daily_loss={self.state.daily_loss}, "
            f"total_loss={self.state.total_loss}, "
            f"trades_today={self.state.trades_today}"
        )
    
    def get_state(self) -> Dict:
        """현재 안전 상태 조회"""
        return {
            "daily_loss": self.state.daily_loss,
            "total_loss": self.state.total_loss,
            "trades_this_hour": self.state.trades_this_hour,
            "trades_today": self.state.trades_today,
            "circuit_breaker_active": self.state.circuit_breaker_active,
            "limits": self.limits.to_dict(),
        }
    
    def reset_daily(self) -> None:
        """일일 통계 리셋"""
        self.state.daily_loss = 0.0
        self.state.trades_today = 0
        self.state.last_day_reset = datetime.utcnow()
        logger.info("Daily statistics reset")
    
    def reset_all(self) -> None:
        """모든 통계 리셋"""
        self.state = SafetyState()
        self._order_history.clear()
        self._position_history.clear()
        logger.info("All safety statistics reset")
