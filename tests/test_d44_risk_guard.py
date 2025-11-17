# -*- coding: utf-8 -*-
"""
D44 RiskGuard 테스트

RiskGuard의 리스크 체크 로직을 검증합니다.
"""

import pytest
from datetime import datetime

from arbitrage.arbitrage_core import ArbitrageTrade
from arbitrage.live_runner import RiskGuard, RiskLimits, RiskGuardDecision


class TestRiskGuardInitialization:
    """RiskGuard 초기화 테스트"""
    
    def test_riskguard_init_with_defaults(self):
        """기본값으로 RiskGuard 초기화"""
        limits = RiskLimits()
        guard = RiskGuard(limits)
        
        assert guard.risk_limits.max_notional_per_trade == 10000.0
        assert guard.risk_limits.max_daily_loss == 1000.0
        assert guard.risk_limits.max_open_trades == 1
        assert guard.daily_loss_usd == 0.0
    
    def test_riskguard_init_with_custom_limits(self):
        """커스텀 리스크 제한으로 RiskGuard 초기화"""
        limits = RiskLimits(
            max_notional_per_trade=5000.0,
            max_daily_loss=500.0,
            max_open_trades=2,
        )
        guard = RiskGuard(limits)
        
        assert guard.risk_limits.max_notional_per_trade == 5000.0
        assert guard.risk_limits.max_daily_loss == 500.0
        assert guard.risk_limits.max_open_trades == 2


class TestRiskGuardTradeAllowed:
    """거래 허용 여부 판정 테스트"""
    
    def test_trade_allowed_ok(self):
        """정상 거래 허용"""
        limits = RiskLimits(
            max_notional_per_trade=5000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        trade = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True,
        )
        
        decision = guard.check_trade_allowed(trade, num_active_orders=0)
        assert decision == RiskGuardDecision.OK
    
    def test_trade_rejected_notional_exceeded(self):
        """거래당 최대 명목가 초과로 거절"""
        limits = RiskLimits(max_notional_per_trade=1000.0)
        guard = RiskGuard(limits)
        
        trade = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=2000.0,  # 제한 초과
            is_open=True,
        )
        
        decision = guard.check_trade_allowed(trade, num_active_orders=0)
        assert decision == RiskGuardDecision.TRADE_REJECTED
    
    def test_trade_rejected_max_open_trades_exceeded(self):
        """최대 동시 거래 수 초과로 거절"""
        limits = RiskLimits(
            max_notional_per_trade=5000.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        trade = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True,
        )
        
        # 이미 1개 거래가 활성화됨
        decision = guard.check_trade_allowed(trade, num_active_orders=1)
        assert decision == RiskGuardDecision.TRADE_REJECTED
    
    def test_session_stop_daily_loss_exceeded(self):
        """일일 최대 손실 초과로 세션 종료"""
        limits = RiskLimits(
            max_notional_per_trade=5000.0,
            max_daily_loss=100.0,
        )
        guard = RiskGuard(limits)
        
        # 손실 누적
        guard.daily_loss_usd = 100.0
        
        trade = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True,
        )
        
        decision = guard.check_trade_allowed(trade, num_active_orders=0)
        assert decision == RiskGuardDecision.SESSION_STOP


class TestRiskGuardDailyLossUpdate:
    """일일 손실 업데이트 테스트"""
    
    def test_update_daily_loss_negative_pnl(self):
        """손실 (음수 PnL) 업데이트"""
        limits = RiskLimits()
        guard = RiskGuard(limits)
        
        guard.update_daily_loss(-100.0)
        assert guard.daily_loss_usd == 100.0
    
    def test_update_daily_loss_positive_pnl(self):
        """수익 (양수 PnL)은 손실 업데이트 안 함"""
        limits = RiskLimits()
        guard = RiskGuard(limits)
        
        guard.update_daily_loss(100.0)
        assert guard.daily_loss_usd == 0.0
    
    def test_update_daily_loss_cumulative(self):
        """손실 누적"""
        limits = RiskLimits()
        guard = RiskGuard(limits)
        
        guard.update_daily_loss(-50.0)
        guard.update_daily_loss(-30.0)
        guard.update_daily_loss(100.0)  # 수익은 무시
        guard.update_daily_loss(-20.0)
        
        assert guard.daily_loss_usd == 100.0  # 50 + 30 + 20


class TestRiskGuardScenarios:
    """통합 시나리오 테스트"""
    
    def test_scenario_multiple_trades_with_loss(self):
        """여러 거래 시도 및 손실 누적"""
        limits = RiskLimits(
            max_notional_per_trade=1000.0,
            max_daily_loss=200.0,
            max_open_trades=1,
        )
        guard = RiskGuard(limits)
        
        # 첫 번째 거래: OK
        trade1 = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=500.0,
            is_open=True,
        )
        decision1 = guard.check_trade_allowed(trade1, num_active_orders=0)
        assert decision1 == RiskGuardDecision.OK
        
        # 손실 누적
        guard.update_daily_loss(-100.0)
        
        # 두 번째 거래: OK
        trade2 = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            side="LONG_B_SHORT_A",
            entry_spread_bps=50.0,
            notional_usd=500.0,
            is_open=True,
        )
        decision2 = guard.check_trade_allowed(trade2, num_active_orders=0)
        assert decision2 == RiskGuardDecision.OK
        
        # 더 많은 손실 누적
        guard.update_daily_loss(-100.0)
        
        # 세 번째 거래: SESSION_STOP (손실 한계 도달)
        trade3 = ArbitrageTrade(
            open_timestamp=datetime.utcnow().isoformat(),
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=500.0,
            is_open=True,
        )
        decision3 = guard.check_trade_allowed(trade3, num_active_orders=0)
        assert decision3 == RiskGuardDecision.SESSION_STOP
