# -*- coding: utf-8 -*-
"""
D60: Multi-Symbol Capital & Position Limits (Phase 2) - Tests

SymbolRiskLimits, PortfolioState, RiskGuard의 심볼별 한도 관리 검증.
"""

import pytest
from arbitrage.types import SymbolRiskLimits, PortfolioState
from arbitrage.live_runner import RiskGuard, RiskLimits


class TestSymbolRiskLimits:
    """SymbolRiskLimits 타입 테스트"""
    
    def test_symbol_risk_limits_creation(self):
        """SymbolRiskLimits 생성"""
        limits = SymbolRiskLimits(
            symbol="KRW-BTC",
            capital_limit_notional=5000.0,
            max_positions=2,
            max_concurrent_trades=1,
            max_daily_loss=500.0,
        )
        
        assert limits.symbol == "KRW-BTC"
        assert limits.capital_limit_notional == 5000.0
        assert limits.max_positions == 2
        assert limits.max_concurrent_trades == 1
        assert limits.max_daily_loss == 500.0
    
    def test_symbol_risk_limits_validation(self):
        """SymbolRiskLimits 유효성 검사"""
        # 음수 자본 한도는 실패
        with pytest.raises(ValueError):
            SymbolRiskLimits(
                symbol="KRW-BTC",
                capital_limit_notional=-5000.0,
                max_positions=2,
                max_concurrent_trades=1,
                max_daily_loss=500.0,
            )
        
        # 음수 포지션 한도는 실패
        with pytest.raises(ValueError):
            SymbolRiskLimits(
                symbol="KRW-BTC",
                capital_limit_notional=5000.0,
                max_positions=-2,
                max_concurrent_trades=1,
                max_daily_loss=500.0,
            )


class TestPortfolioStateSymbolLimits:
    """PortfolioState 심볼별 한도 필드 테스트"""
    
    def test_portfolio_state_symbol_limit_fields(self):
        """PortfolioState 심볼별 한도 필드 확인"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        
        # D60 필드 확인
        assert hasattr(portfolio, 'per_symbol_capital_used')
        assert hasattr(portfolio, 'per_symbol_position_count')
        assert hasattr(portfolio, 'per_symbol_daily_loss')
        assert portfolio.per_symbol_capital_used == {}
        assert portfolio.per_symbol_position_count == {}
        assert portfolio.per_symbol_daily_loss == {}
    
    def test_update_symbol_capital_used(self):
        """심볼별 사용된 자본 업데이트"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        
        portfolio.update_symbol_capital_used("KRW-BTC", 3000.0)
        portfolio.update_symbol_capital_used("BTCUSDT", 2000.0)
        
        assert portfolio.get_symbol_capital_used("KRW-BTC") == 3000.0
        assert portfolio.get_symbol_capital_used("BTCUSDT") == 2000.0
    
    def test_update_symbol_position_count(self):
        """심볼별 포지션 수 업데이트"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        
        portfolio.update_symbol_position_count("KRW-BTC", 2)
        portfolio.update_symbol_position_count("BTCUSDT", 1)
        
        assert portfolio.get_symbol_position_count("KRW-BTC") == 2
        assert portfolio.get_symbol_position_count("BTCUSDT") == 1
    
    def test_update_symbol_daily_loss(self):
        """심볼별 일일 손실 업데이트"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        
        portfolio.update_symbol_daily_loss("KRW-BTC", 100.0)
        portfolio.update_symbol_daily_loss("BTCUSDT", 50.0)
        
        assert portfolio.get_symbol_daily_loss("KRW-BTC") == 100.0
        assert portfolio.get_symbol_daily_loss("BTCUSDT") == 50.0


class TestRiskGuardSymbolLimits:
    """RiskGuard 심볼별 한도 메서드 테스트"""
    
    def test_set_symbol_limits(self):
        """심볼별 한도 설정"""
        guard = RiskGuard(RiskLimits())
        
        limits_btc = SymbolRiskLimits(
            symbol="KRW-BTC",
            capital_limit_notional=5000.0,
            max_positions=2,
            max_concurrent_trades=1,
            max_daily_loss=500.0,
        )
        
        limits_eth = SymbolRiskLimits(
            symbol="KRW-ETH",
            capital_limit_notional=3000.0,
            max_positions=1,
            max_concurrent_trades=1,
            max_daily_loss=300.0,
        )
        
        guard.set_symbol_limits(limits_btc)
        guard.set_symbol_limits(limits_eth)
        
        assert "KRW-BTC" in guard.per_symbol_limits
        assert "KRW-ETH" in guard.per_symbol_limits
        assert guard.per_symbol_limits["KRW-BTC"] == limits_btc
        assert guard.per_symbol_limits["KRW-ETH"] == limits_eth
    
    def test_check_symbol_capital_limit_ok(self):
        """심볼별 자본 한도 체크 - OK"""
        guard = RiskGuard(RiskLimits())
        
        limits = SymbolRiskLimits(
            symbol="KRW-BTC",
            capital_limit_notional=5000.0,
            max_positions=2,
            max_concurrent_trades=1,
            max_daily_loss=500.0,
        )
        
        guard.set_symbol_limits(limits)
        guard.update_symbol_capital_used("KRW-BTC", 2000.0)
        
        # 2000 + 2000 = 4000 < 5000 (OK)
        assert guard.check_symbol_capital_limit("KRW-BTC", 2000.0) is True
    
    def test_check_symbol_capital_limit_exceeded(self):
        """심볼별 자본 한도 체크 - 초과"""
        guard = RiskGuard(RiskLimits())
        
        limits = SymbolRiskLimits(
            symbol="KRW-BTC",
            capital_limit_notional=5000.0,
            max_positions=2,
            max_concurrent_trades=1,
            max_daily_loss=500.0,
        )
        
        guard.set_symbol_limits(limits)
        guard.update_symbol_capital_used("KRW-BTC", 4000.0)
        
        # 4000 + 2000 = 6000 > 5000 (EXCEEDED)
        assert guard.check_symbol_capital_limit("KRW-BTC", 2000.0) is False
    
    def test_check_symbol_position_limit_ok(self):
        """심볼별 포지션 한도 체크 - OK"""
        guard = RiskGuard(RiskLimits())
        
        limits = SymbolRiskLimits(
            symbol="KRW-BTC",
            capital_limit_notional=5000.0,
            max_positions=2,
            max_concurrent_trades=1,
            max_daily_loss=500.0,
        )
        
        guard.set_symbol_limits(limits)
        guard.update_symbol_position_count("KRW-BTC", 1)
        
        # 1 < 2 (OK)
        assert guard.check_symbol_position_limit("KRW-BTC") is True
    
    def test_check_symbol_position_limit_exceeded(self):
        """심볼별 포지션 한도 체크 - 초과"""
        guard = RiskGuard(RiskLimits())
        
        limits = SymbolRiskLimits(
            symbol="KRW-BTC",
            capital_limit_notional=5000.0,
            max_positions=2,
            max_concurrent_trades=1,
            max_daily_loss=500.0,
        )
        
        guard.set_symbol_limits(limits)
        guard.update_symbol_position_count("KRW-BTC", 2)
        
        # 2 >= 2 (EXCEEDED)
        assert guard.check_symbol_position_limit("KRW-BTC") is False
    
    def test_check_symbol_limits_no_limits_set(self):
        """심볼별 한도 체크 - 한도 미설정"""
        guard = RiskGuard(RiskLimits())
        
        # 한도가 설정되지 않으면 통과
        assert guard.check_symbol_capital_limit("KRW-BTC", 10000.0) is True
        assert guard.check_symbol_position_limit("KRW-BTC") is True
    
    def test_update_symbol_capital_and_position(self):
        """심볼별 자본 및 포지션 업데이트"""
        guard = RiskGuard(RiskLimits())
        
        guard.update_symbol_capital_used("KRW-BTC", 3000.0)
        guard.update_symbol_position_count("KRW-BTC", 2)
        
        assert guard.per_symbol_capital_used["KRW-BTC"] == 3000.0
        assert guard.per_symbol_position_count["KRW-BTC"] == 2


class TestMultipleSymbolsIndependentLimits:
    """여러 심볼의 독립적인 한도 관리"""
    
    def test_multiple_symbols_independent_limits(self):
        """여러 심볼의 독립적인 한도"""
        guard = RiskGuard(RiskLimits())
        
        # 각 심볼별 한도 설정
        limits_btc = SymbolRiskLimits(
            symbol="KRW-BTC",
            capital_limit_notional=5000.0,
            max_positions=2,
            max_concurrent_trades=1,
            max_daily_loss=500.0,
        )
        
        limits_eth = SymbolRiskLimits(
            symbol="KRW-ETH",
            capital_limit_notional=3000.0,
            max_positions=1,
            max_concurrent_trades=1,
            max_daily_loss=300.0,
        )
        
        guard.set_symbol_limits(limits_btc)
        guard.set_symbol_limits(limits_eth)
        
        # 각 심볼별 자본 및 포지션 업데이트
        guard.update_symbol_capital_used("KRW-BTC", 4000.0)
        guard.update_symbol_capital_used("KRW-ETH", 2000.0)
        
        guard.update_symbol_position_count("KRW-BTC", 2)
        guard.update_symbol_position_count("KRW-ETH", 1)
        
        # KRW-BTC: 4000 + 1000 = 5000 (OK), 2 >= 2 (EXCEEDED)
        assert guard.check_symbol_capital_limit("KRW-BTC", 1000.0) is True
        assert guard.check_symbol_position_limit("KRW-BTC") is False
        
        # KRW-ETH: 2000 + 500 = 2500 (OK), 1 >= 1 (EXCEEDED)
        assert guard.check_symbol_capital_limit("KRW-ETH", 500.0) is True
        assert guard.check_symbol_position_limit("KRW-ETH") is False


class TestBackwardCompatibilityD60:
    """D60 추가 후 기존 기능 호환성"""
    
    def test_riskguard_backward_compatible(self):
        """기존 RiskGuard 기능 유지"""
        guard = RiskGuard(RiskLimits())
        
        # 기존 메서드 호출 (변경 없음)
        guard.update_daily_loss(-100.0)
        
        # 확인
        assert guard.daily_loss_usd == 100.0
    
    def test_portfolio_state_backward_compatible(self):
        """기존 PortfolioState 기능 유지"""
        portfolio = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
        )
        
        # 기존 필드 접근 (변경 없음)
        assert portfolio.total_balance == 10000.0
        assert portfolio.available_balance == 10000.0
        assert portfolio.total_position_value == 0.0
