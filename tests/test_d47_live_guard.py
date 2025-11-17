"""
D47: LiveSafetyGuard 테스트

실거래 모드 전용 보안 가드 검증
"""

import pytest
from arbitrage.live_guard import LiveSafetyGuard, LiveGuardDecision


class TestD47LiveSafetyGuard:
    """D47 LiveSafetyGuard 테스트"""

    def test_guard_initialization(self):
        """Guard 초기화"""
        config = {
            "live_trading": {
                "enabled": False,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC", "BTCUSDT"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        assert guard.enabled is False
        assert guard.dry_run_scale == 0.01
        assert guard.allowed_symbols == ["KRW-BTC", "BTCUSDT"]
        assert guard.min_account_balance == 50.0

    def test_guard_enabled_false_blocks_order(self):
        """enabled=False일 때 모든 주문 차단"""
        config = {
            "live_trading": {
                "enabled": False,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        decision = guard.check_before_send_order(
            symbol="KRW-BTC",
            notional_usd=10.0,
            current_balance=100.0,
            current_daily_loss=0.0,
        )
        
        assert decision.allowed is False
        assert "enabled=False" in decision.reason
        assert guard.total_orders_blocked == 1

    def test_guard_enabled_true_allows_valid_order(self):
        """enabled=True이고 모든 조건 충족 시 주문 허용"""
        config = {
            "live_trading": {
                "enabled": True,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        decision = guard.check_before_send_order(
            symbol="KRW-BTC",
            notional_usd=10.0,
            current_balance=100.0,
            current_daily_loss=0.0,
        )
        
        assert decision.allowed is True
        assert guard.total_orders_allowed == 1

    def test_guard_blocks_disallowed_symbol(self):
        """allowed_symbols에 없는 심볼 차단"""
        config = {
            "live_trading": {
                "enabled": True,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        decision = guard.check_before_send_order(
            symbol="BTCUSDT",  # 허용되지 않은 심볼
            notional_usd=10.0,
            current_balance=100.0,
            current_daily_loss=0.0,
        )
        
        assert decision.allowed is False
        assert "not in allowed_symbols" in decision.reason

    def test_guard_blocks_insufficient_balance(self):
        """잔고 부족 시 차단"""
        config = {
            "live_trading": {
                "enabled": True,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        decision = guard.check_before_send_order(
            symbol="KRW-BTC",
            notional_usd=10.0,
            current_balance=30.0,  # 최소값(50.0) 미만
            current_daily_loss=0.0,
        )
        
        assert decision.allowed is False
        assert "account balance" in decision.reason

    def test_guard_blocks_excessive_daily_loss(self):
        """일일 손실 초과 시 차단 + session_stop"""
        config = {
            "live_trading": {
                "enabled": True,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        decision = guard.check_before_send_order(
            symbol="KRW-BTC",
            notional_usd=10.0,
            current_balance=100.0,
            current_daily_loss=-25.0,  # -20.0 초과
        )
        
        assert decision.allowed is False
        assert "daily loss" in decision.reason
        assert decision.session_stop is True  # 세션 종료 신호

    def test_guard_blocks_excessive_notional(self):
        """명목가 초과 시 차단"""
        config = {
            "live_trading": {
                "enabled": True,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        decision = guard.check_before_send_order(
            symbol="KRW-BTC",
            notional_usd=100.0,  # 최대값(50.0) 초과
            current_balance=200.0,
            current_daily_loss=0.0,
        )
        
        assert decision.allowed is False
        assert "notional" in decision.reason

    def test_dry_run_scale_application(self):
        """dry_run_scale 적용"""
        config = {
            "live_trading": {
                "enabled": True,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        original_qty = 1.0
        scaled_qty = guard.apply_dry_run_scale(original_qty)
        
        assert scaled_qty == 0.01  # 1% 축소
        assert scaled_qty == original_qty * 0.01

    def test_dry_run_scale_full_scale(self):
        """dry_run_scale=1.0 (축소 없음)"""
        config = {
            "live_trading": {
                "enabled": True,
                "dry_run_scale": 1.0,  # 축소 없음
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        original_qty = 1.0
        scaled_qty = guard.apply_dry_run_scale(original_qty)
        
        assert scaled_qty == 1.0  # 축소 없음

    def test_guard_summary(self):
        """Guard 통계 요약"""
        config = {
            "live_trading": {
                "enabled": False,
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        # 여러 주문 시도
        for _ in range(3):
            guard.check_before_send_order(
                symbol="KRW-BTC",
                notional_usd=10.0,
                current_balance=100.0,
                current_daily_loss=0.0,
            )
        
        summary = guard.get_summary()
        
        assert summary["total_orders_attempted"] == 3
        assert summary["total_orders_blocked"] == 3
        assert summary["total_orders_allowed"] == 0

    def test_guard_multiple_conditions_failure(self):
        """여러 조건 동시 실패 시 첫 번째 실패 조건으로 차단"""
        config = {
            "live_trading": {
                "enabled": False,  # 이미 실패
                "dry_run_scale": 0.01,
                "allowed_symbols": ["KRW-BTC"],
                "min_account_balance": 50.0,
                "max_daily_loss": 20.0,
                "max_notional_per_trade": 50.0,
            }
        }
        
        guard = LiveSafetyGuard(config)
        
        decision = guard.check_before_send_order(
            symbol="BTCUSDT",  # 잘못된 심볼
            notional_usd=100.0,  # 초과
            current_balance=30.0,  # 부족
            current_daily_loss=-25.0,  # 초과
        )
        
        # enabled=False가 먼저 체크되므로 이것으로 차단
        assert decision.allowed is False
        assert "enabled=False" in decision.reason
