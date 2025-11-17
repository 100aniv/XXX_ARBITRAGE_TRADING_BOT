#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Tests — Safety Module (LiveGuard)
======================================

안전 장치 테스트.
"""

import pytest
from liveguard.safety import SafetyModule
from liveguard.risk_limits import RiskLimits


class TestRiskLimits:
    """RiskLimits 테스트"""
    
    def test_default_limits(self):
        """기본 제한 설정"""
        limits = RiskLimits()
        
        assert limits.max_position_size == 1_000_000
        assert limits.max_daily_loss == 500_000
        assert limits.max_trades_per_hour == 100
    
    def test_limits_validation(self):
        """제한 설정 유효성 검사"""
        limits = RiskLimits()
        assert limits.validate()
    
    def test_invalid_limits(self):
        """유효하지 않은 제한 설정"""
        limits = RiskLimits(max_position_size=-1)
        assert not limits.validate()
    
    def test_limits_to_dict(self):
        """제한 설정을 딕셔너리로 변환"""
        limits = RiskLimits()
        limits_dict = limits.to_dict()
        
        assert "max_position_size" in limits_dict
        assert "max_daily_loss" in limits_dict


class TestSafetyModule:
    """SafetyModule 테스트"""
    
    def test_safety_initialization(self):
        """안전 모듈 초기화"""
        safety = SafetyModule()
        assert safety.limits is not None
        assert safety.state is not None
    
    def test_check_position_size_valid(self):
        """유효한 포지션 크기"""
        safety = SafetyModule()
        allowed, reason = safety.check_position_size(500_000)
        
        assert allowed
        assert reason is None
    
    def test_check_position_size_invalid(self):
        """유효하지 않은 포지션 크기"""
        safety = SafetyModule()
        allowed, reason = safety.check_position_size(2_000_000)
        
        assert not allowed
        assert reason is not None
    
    def test_check_position_count_valid(self):
        """유효한 포지션 수"""
        safety = SafetyModule()
        allowed, reason = safety.check_position_count(5)
        
        assert allowed
        assert reason is None
    
    def test_check_position_count_invalid(self):
        """유효하지 않은 포지션 수"""
        safety = SafetyModule()
        allowed, reason = safety.check_position_count(15)
        
        assert not allowed
        assert reason is not None
    
    def test_check_daily_loss_valid(self):
        """유효한 일일 손실"""
        safety = SafetyModule()
        allowed, reason = safety.check_daily_loss(100_000)
        
        assert allowed
        assert reason is None
    
    def test_check_daily_loss_invalid(self):
        """유효하지 않은 일일 손실"""
        safety = SafetyModule()
        allowed, reason = safety.check_daily_loss(600_000)
        
        assert not allowed
        assert reason is not None
    
    def test_check_slippage_valid(self):
        """유효한 슬리피지"""
        safety = SafetyModule()
        allowed, reason = safety.check_slippage(100, 100.3)
        
        assert allowed
        assert reason is None
    
    def test_check_slippage_invalid(self):
        """유효하지 않은 슬리피지"""
        safety = SafetyModule()
        allowed, reason = safety.check_slippage(100, 101)
        
        assert not allowed
        assert reason is not None
    
    def test_check_spread_valid(self):
        """유효한 스프레드"""
        safety = SafetyModule()
        allowed, reason = safety.check_spread(1.0)
        
        assert allowed
        assert reason is None
    
    def test_check_spread_invalid(self):
        """유효하지 않은 스프레드"""
        safety = SafetyModule()
        allowed, reason = safety.check_spread(0.05)
        
        assert not allowed
        assert reason is not None
    
    def test_can_execute_order_valid(self):
        """주문 실행 가능"""
        safety = SafetyModule()
        allowed, reason = safety.can_execute_order(
            position_value=500_000,
            current_positions=5,
            current_loss=100_000,
            total_balance=10_000_000
        )
        
        assert allowed
        assert reason is None
    
    def test_can_execute_order_position_size_exceeded(self):
        """포지션 크기 초과"""
        safety = SafetyModule()
        allowed, reason = safety.can_execute_order(
            position_value=2_000_000,
            current_positions=5,
            current_loss=100_000,
            total_balance=10_000_000
        )
        
        assert not allowed
        assert "Position size" in reason or "position_size" in reason
    
    def test_record_trade(self):
        """거래 기록"""
        safety = SafetyModule()
        
        initial_loss = safety.state.daily_loss
        safety.record_trade(50_000)
        
        assert safety.state.daily_loss == initial_loss + 50_000
        assert safety.state.trades_today == 1
    
    def test_get_state(self):
        """안전 상태 조회"""
        safety = SafetyModule()
        state = safety.get_state()
        
        assert "daily_loss" in state
        assert "total_loss" in state
        assert "trades_today" in state
        assert "circuit_breaker_active" in state
    
    def test_reset_daily(self):
        """일일 통계 리셋"""
        safety = SafetyModule()
        safety.record_trade(50_000)
        
        assert safety.state.daily_loss > 0
        
        safety.reset_daily()
        
        assert safety.state.daily_loss == 0
        assert safety.state.trades_today == 0
    
    def test_reset_all(self):
        """모든 통계 리셋"""
        safety = SafetyModule()
        safety.record_trade(50_000)
        
        safety.reset_all()
        
        assert safety.state.daily_loss == 0
        assert safety.state.total_loss == 0
        assert safety.state.trades_today == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
