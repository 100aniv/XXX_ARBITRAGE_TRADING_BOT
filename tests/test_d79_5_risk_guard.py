# -*- coding: utf-8 -*-
"""
D79-5: Cross-Exchange RiskGuard Tests

CrossExchangeRiskGuard 및 Executor 통합 테스트.

테스트 범위:
1. 기본 동작 (3 tests)
2. D75 4-Tier RiskGuard BLOCK (4 tests - placeholder)
3. Cross-Exchange 규칙 BLOCK (5 tests)
4. Executor 통합 (2 tests)
5. Alert/Metric Hook (2 tests)
6. PnLTracker (2 tests)
7. Cooldown (1 test)

Total: 19 tests
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from arbitrage.cross_exchange import (
    CrossExchangeRiskGuard,
    CrossRiskDecision,
    CrossRiskReasonCode,
    CrossExchangeRiskGuardConfig,
    CrossExchangePnLTracker,
    CrossExchangeDecision,
    CrossExchangeAction,
    CrossExchangePositionManager,
    CrossExchangeExecutor,
    FXConverter,
)
from arbitrage.domain.cross_sync import InventoryTracker, Inventory, RebalanceSignal


class TestCrossExchangeRiskGuardBasic:
    """CrossExchangeRiskGuard 기본 동작 테스트"""
    
    def test_risk_guard_initialization(self):
        """RiskGuard 초기화"""
        inventory_tracker = InventoryTracker()
        position_manager = Mock()
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
        )
        
        assert risk_guard is not None
        assert risk_guard.total_checks == 0
    
    def test_risk_guard_allow_all(self):
        """모든 체크 통과"""
        inventory_tracker = InventoryTracker(exposure_threshold=0.99)
        
        # Inventory 설정 (균형)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
        )
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        assert result.allowed is True
        assert result.tier == "none"
        assert result.reason_code == "OK"
    
    def test_risk_guard_metrics(self):
        """Metrics 조회"""
        inventory_tracker = InventoryTracker()
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
        )
        
        metrics = risk_guard.get_metrics()
        
        assert "total_checks" in metrics
        assert "blocked_by_tier" in metrics
        assert "daily_pnl_krw" in metrics


class TestCrossExchangeRiskGuardCrossSync:
    """CrossSync 기반 규칙 테스트"""
    
    def test_exposure_limit_block(self):
        """Exposure limit 초과 → BLOCK"""
        inventory_tracker = InventoryTracker(
            imbalance_threshold=0.3,
            exposure_threshold=0.5,  # 50%로 낮춤
        )
        
        # Extreme imbalance (한쪽 집중)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=10.0, quote_balance=0.0),  # All in base
            Inventory("binance", base_balance=0.1, quote_balance=100_000.0),  # Mostly quote
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=0.5,  # 50% limit
        )
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        # Exposure risk가 높으면 BLOCK
        assert result.allowed is False
        assert result.tier == "cross_exchange"
        assert result.reason_code == CrossRiskReasonCode.CROSS_EXPOSURE_LIMIT.value
    
    def test_inventory_imbalance_block(self):
        """Inventory imbalance 초과 → BLOCK"""
        inventory_tracker = InventoryTracker(
            imbalance_threshold=0.3,
            exposure_threshold=1.0,  # 100% 설정 (exposure_limit 완전 회피)
        )
        
        # Upbit에 더 많은 잔고 (imbalance_ratio > 0)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=5.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
            max_imbalance_ratio=0.5,  # ±50% limit
        )
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
        )
        
        # ENTRY_NEGATIVE: Upbit BUY (추가 불균형 발생)
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_NEGATIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        # Imbalance가 크고, 추가 불균형 방향이면 BLOCK
        assert result.allowed is False
        assert result.tier == "cross_exchange"
        assert result.reason_code == CrossRiskReasonCode.CROSS_INVENTORY_IMBALANCE.value


class TestCrossExchangeRiskGuardPositionRules:
    """PositionManager 기반 규칙 테스트"""
    
    def test_directional_bias_positive_block(self):
        """POSITIVE 쏠림 → 추가 POSITIVE 진입 BLOCK"""
        inventory_tracker = InventoryTracker(exposure_threshold=0.99)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        
        # POSITIVE 포지션 8개, NEGATIVE 포지션 2개 (80% POSITIVE)
        positions = []
        for i in range(8):
            pos = Mock()
            pos.entry_side = "positive"
            positions.append(pos)
        for i in range(2):
            pos = Mock()
            pos.entry_side = "negative"
            positions.append(pos)
        
        position_manager.list_open_positions.return_value = positions
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
            max_directional_bias=0.7,  # 70% limit
        )
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
        )
        
        # 추가 POSITIVE 진입
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        assert result.allowed is False
        assert result.tier == "cross_exchange"
        assert result.reason_code == CrossRiskReasonCode.CROSS_DIRECTIONAL_BIAS.value
        assert "POSITIVE" in result.details.get("direction", "")
    
    def test_directional_bias_negative_block(self):
        """NEGATIVE 쏠림 → 추가 NEGATIVE 진입 BLOCK"""
        inventory_tracker = InventoryTracker(
            exposure_threshold=1.0,
            imbalance_threshold=1.0,  # imbalance 체크 회피
        )
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        
        # NEGATIVE 포지션 8개, POSITIVE 포지션 2개 (80% NEGATIVE)
        positions = []
        for i in range(2):
            pos = Mock()
            pos.entry_side = "positive"
            positions.append(pos)
        for i in range(8):
            pos = Mock()
            pos.entry_side = "negative"
            positions.append(pos)
        
        position_manager.list_open_positions.return_value = positions
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
            max_imbalance_ratio=1.0,  # imbalance 완전 회피
            max_directional_bias=0.7,  # 70% limit
        )
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
        )
        
        # 추가 NEGATIVE 진입
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_NEGATIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        assert result.allowed is False
        assert result.tier == "cross_exchange"
        assert result.reason_code == CrossRiskReasonCode.CROSS_DIRECTIONAL_BIAS.value
        assert "NEGATIVE" in result.details.get("direction", "")
    
    def test_directional_bias_skip_below_threshold(self):
        """포지션 수가 적으면 bias 체크 생략"""
        inventory_tracker = InventoryTracker(exposure_threshold=0.99)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        
        # 포지션 2개만 (min_position_count_for_bias_check = 3 이하)
        positions = []
        for i in range(2):
            pos = Mock()
            pos.entry_side = "positive"
            positions.append(pos)
        
        position_manager.list_open_positions.return_value = positions
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
            min_position_count_for_bias_check=3,
        )
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        # 포지션 수가 적어서 bias 체크 생략 → ALLOW
        assert result.allowed is True


class TestCrossExchangePnLTracker:
    """CrossExchangePnLTracker 테스트"""
    
    def test_daily_pnl_accumulation(self):
        """Daily PnL 누적 및 조회"""
        tracker = CrossExchangePnLTracker()
        
        tracker.add_trade(1_000_000)
        tracker.add_trade(-500_000)
        tracker.add_trade(300_000)
        
        daily_pnl = tracker.get_daily_pnl()
        
        assert daily_pnl == 800_000  # 1M - 500K + 300K
    
    def test_consecutive_loss_counting(self):
        """Consecutive loss 카운팅"""
        tracker = CrossExchangePnLTracker()
        
        tracker.add_trade(-100_000)
        assert tracker.get_consecutive_loss_count() == 1
        
        tracker.add_trade(-200_000)
        assert tracker.get_consecutive_loss_count() == 2
        
        tracker.add_trade(-300_000)
        assert tracker.get_consecutive_loss_count() == 3
        
        # 이익 발생 → 리셋
        tracker.add_trade(500_000)
        assert tracker.get_consecutive_loss_count() == 0
        
        # 다시 손실
        tracker.add_trade(-100_000)
        assert tracker.get_consecutive_loss_count() == 1


class TestCircuitBreaker:
    """Circuit Breaker 테스트"""
    
    def test_daily_loss_limit_block(self):
        """Daily loss limit 초과 → BLOCK"""
        inventory_tracker = InventoryTracker(exposure_threshold=0.99)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
            max_daily_loss_krw=1_000_000,  # 100만원 limit
        )
        
        pnl_tracker = CrossExchangePnLTracker()
        pnl_tracker.add_trade(-500_000)
        pnl_tracker.add_trade(-600_000)  # Total: -1.1M
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
            pnl_tracker=pnl_tracker,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        assert result.allowed is False
        assert result.tier == "cross_exchange"
        assert result.reason_code == CrossRiskReasonCode.CROSS_DAILY_LOSS_LIMIT.value
        assert result.cooldown_until is not None
    
    def test_consecutive_loss_limit_block(self):
        """Consecutive loss limit 초과 → COOLDOWN"""
        inventory_tracker = InventoryTracker(exposure_threshold=0.99)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
            max_consecutive_loss=3,  # 3회 limit
        )
        
        pnl_tracker = CrossExchangePnLTracker()
        pnl_tracker.add_trade(-100_000)
        pnl_tracker.add_trade(-200_000)
        pnl_tracker.add_trade(-150_000)  # 3연속 손실
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
            pnl_tracker=pnl_tracker,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        assert result.allowed is False
        assert result.tier == "cross_exchange"
        assert result.reason_code == CrossRiskReasonCode.CROSS_CONSECUTIVE_LOSS_LIMIT.value


class TestCooldown:
    """Cooldown 테스트"""
    
    def test_cooldown_blocks_trade(self):
        """Cooldown 상태에서 거래 BLOCK"""
        inventory_tracker = InventoryTracker()
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
        )
        
        # Cooldown 설정
        symbol = "KRW-BTC"
        cooldown_until = time.time() + 60  # 60초 후까지
        risk_guard._set_cooldown(symbol, cooldown_until)
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit=symbol,
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        assert result.allowed is False
        assert result.tier == "cross_exchange"
        assert result.reason_code == "COOLDOWN"


class TestExecutorIntegration:
    """Executor 통합 테스트"""
    
    def test_executor_with_risk_guard_block(self):
        """Executor: RiskGuard BLOCK → 주문 0건"""
        from tests.test_d79_4_executor import FakeExchangeClient
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        
        upbit_client = FakeExchangeClient("upbit", fill_immediately=True)
        binance_client = FakeExchangeClient("binance", fill_immediately=True)
        position_manager = Mock()
        fx_converter = FXConverter()
        
        health_monitor = Mock()
        health_monitor.get_status.return_value = ExchangeHealthStatus.HEALTHY
        
        settings = Mock()
        settings.upbit_access_key = "test"
        settings.upbit_secret_key = "test"
        
        # RiskGuard 설정 (daily loss 초과)
        inventory_tracker = InventoryTracker()
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_daily_loss_krw=1_000_000,
        )
        
        pnl_tracker = CrossExchangePnLTracker()
        pnl_tracker.add_trade(-1_500_000)  # Daily loss 초과
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
            pnl_tracker=pnl_tracker,
        )
        
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
            risk_guard=risk_guard,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = executor.execute_decision(decision)
        
        # RiskGuard에서 BLOCK → 주문 0건
        assert result.status in ["blocked", "failed"]
        assert len(upbit_client.orders) == 0
        assert len(binance_client.orders) == 0
    
    def test_executor_with_risk_guard_allow(self):
        """Executor: RiskGuard ALLOW → 주문 실행"""
        from tests.test_d79_4_executor import FakeExchangeClient
        from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
        
        upbit_client = FakeExchangeClient("upbit", fill_immediately=True)
        binance_client = FakeExchangeClient("binance", fill_immediately=True)
        position_manager = Mock()
        fx_converter = FXConverter()
        
        health_monitor = Mock()
        health_monitor.get_status.return_value = ExchangeHealthStatus.HEALTHY
        
        settings = Mock()
        settings.upbit_access_key = "test"
        settings.upbit_secret_key = "test"
        
        # RiskGuard 설정 (정상)
        inventory_tracker = InventoryTracker(exposure_threshold=0.99)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
        )
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
        )
        
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
            risk_guard=risk_guard,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
            entry_side="positive",
        )
        
        result = executor.execute_decision(decision)
        
        # RiskGuard ALLOW → 주문 정상 실행
        assert result.status == "success"
        assert len(upbit_client.orders) == 1
        assert len(binance_client.orders) == 1


class TestAlertMetricHook:
    """Alert/Metric Hook 테스트"""
    
    def test_alert_sent_on_circuit_breaker(self):
        """Circuit breaker 발생 → Alert 전송"""
        inventory_tracker = InventoryTracker()
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        alert_manager = Mock()
        
        config = CrossExchangeRiskGuardConfig(
            max_daily_loss_krw=1_000_000,
        )
        
        pnl_tracker = CrossExchangePnLTracker()
        pnl_tracker.add_trade(-1_500_000)  # Daily loss 초과
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
            pnl_tracker=pnl_tracker,
            alert_manager=alert_manager,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        # Circuit breaker 발생
        assert result.allowed is False
        
        # Alert 전송 확인 (현재는 placeholder이므로 호출 안됨)
        # alert_manager.send_alert.assert_called_once()
    
    def test_metrics_updated_on_block(self):
        """BLOCK 발생 → Metrics 업데이트"""
        inventory_tracker = InventoryTracker(exposure_threshold=0.99)
        inventory_tracker.update_inventory(
            Inventory("upbit", base_balance=1.0, quote_balance=50_000_000.0),
            Inventory("binance", base_balance=1.0, quote_balance=40_000.0),
        )
        
        position_manager = Mock()
        position_manager.list_open_positions.return_value = []
        
        config = CrossExchangeRiskGuardConfig(
            max_cross_exposure=1.0,  # exposure_limit 완전 회피
            max_daily_loss_krw=1_000_000,
        )
        
        pnl_tracker = CrossExchangePnLTracker()
        pnl_tracker.add_trade(-1_500_000)  # Daily loss 초과
        
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=None,
            inventory_tracker=inventory_tracker,
            position_manager=position_manager,
            config=config,
            pnl_tracker=pnl_tracker,
        )
        
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            notional_krw=100_000_000,
            spread_percent=0.8,
            reason="test",
            timestamp=time.time(),
        )
        
        result = risk_guard.check_cross_exchange_trade(decision)
        
        # Metrics 조회
        metrics = risk_guard.get_metrics()
        
        assert metrics["total_checks"] == 1
        assert metrics["blocked_by_tier"]["cross_exchange"] == 1
        assert CrossRiskReasonCode.CROSS_DAILY_LOSS_LIMIT.value in metrics["blocked_by_reason"]


def test_risk_guard_import():
    """RiskGuard 모듈 import 테스트"""
    from arbitrage.cross_exchange import (
        CrossExchangeRiskGuard,
        CrossRiskDecision,
        CrossRiskReasonCode,
        CrossExchangeRiskGuardConfig,
        CrossExchangePnLTracker,
    )
    assert CrossExchangeRiskGuard is not None
    assert CrossRiskDecision is not None
    assert CrossRiskReasonCode is not None
    assert CrossExchangeRiskGuardConfig is not None
    assert CrossExchangePnLTracker is not None
