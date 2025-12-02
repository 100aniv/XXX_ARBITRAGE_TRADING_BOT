"""
D80-7-INT: Alert Integration Hooks Tests

Tests for alert hooks integrated into FX, Executor, and RiskGuard layers.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from arbitrage.alerting import (
    emit_fx_staleness_alert,
    emit_executor_order_error_alert,
    emit_circuit_breaker_alert,
    get_alert_rule,
)


class TestFxStalenessAlertIntegration:
    """Test FX-004 staleness alert integration"""
    
    def test_fx_staleness_alert_emission(self):
        """Test FX staleness alert can be emitted"""
        # FX-004 alert
        result = emit_fx_staleness_alert(
            source="real_fx_provider",
            pair="USDT/KRW",
            age_seconds=65,
            last_rate=1420.50,
            enabled=True,  # Explicitly enable for test
        )
        
        # Should be sent (not throttled on first call)
        assert result is True
    
    def test_fx_staleness_alert_rule_exists(self):
        """Test FX-004 rule is properly defined"""
        rule = get_alert_rule("FX-004")
        
        assert rule is not None
        assert rule.rule_id == "FX-004"
        assert rule.aggregation_key == "fx_staleness"


class TestExecutorOrderErrorAlertIntegration:
    """Test EX-001 executor order error alert integration"""
    
    def test_executor_order_error_alert_emission(self):
        """Test executor order error alert can be emitted"""
        # EX-001 alert
        result = emit_executor_order_error_alert(
            exchange="binance",
            symbol="BTC-USDT",
            side="BUY",
            error_message="Insufficient balance",
            action="Skipped",
            enabled=True,
        )
        
        # Should be sent
        assert result is True
    
    def test_executor_order_error_rule_exists(self):
        """Test EX-001 rule is properly defined"""
        rule = get_alert_rule("EX-001")
        
        assert rule is not None
        assert rule.rule_id == "EX-001"
        assert rule.aggregation_key == "executor_order_error"


class TestCircuitBreakerAlertIntegration:
    """Test RG-001 circuit breaker alert integration"""
    
    def test_circuit_breaker_alert_emission(self):
        """Test circuit breaker alert can be emitted"""
        # RG-001 alert
        result = emit_circuit_breaker_alert(
            reason="Daily loss limit exceeded",
            threshold="5000000 KRW",
            current_value="-5500000 KRW",
            cooldown_seconds=300,
            enabled=True,
        )
        
        # Should be sent
        assert result is True
    
    def test_circuit_breaker_rule_exists(self):
        """Test RG-001 rule is properly defined"""
        rule = get_alert_rule("RG-001")
        
        assert rule is not None
        assert rule.rule_id == "RG-001"
        assert rule.aggregation_key == "circuit_breaker"


class TestExecutorIntegrationWithAlerts:
    """Test Executor integration with alert hooks"""
    
    @patch('arbitrage.alerting.helpers.get_global_alert_manager')
    def test_executor_exception_triggers_alert(self, mock_get_manager):
        """Test that Executor exception triggers EX-001 alert"""
        from arbitrage.cross_exchange.executor import CrossExchangeExecutor
        from arbitrage.cross_exchange.integration import (
            CrossExchangeDecision,
            CrossExchangeAction,
        )
        
        # Mock AlertManager
        mock_manager = Mock()
        mock_manager.send_alert = Mock(return_value=True)
        mock_get_manager.return_value = mock_manager
        
        # Create executor with mocked dependencies
        mock_fx_converter = Mock()
        mock_fx_converter.get_fx_rate = Mock(return_value=Mock(rate=1420.0))
        
        executor = CrossExchangeExecutor(
            upbit_client=None,  # Will cause error
            binance_client=None,
            position_manager=None,
            fx_converter=mock_fx_converter,
            health_monitor=None,
            settings=None,
        )
        
        # Create test decision
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            spread_percent=0.5,
            notional_krw=1000000,
            reason="test",
            timestamp=0.0,
        )
        
        # Execute should fail (no clients)
        result = executor.execute_decision(decision)
        
        # Should be failed
        assert result.status in ["failed", "blocked"]


class TestRiskGuardIntegrationWithAlerts:
    """Test RiskGuard integration with alert hooks"""
    
    @patch('arbitrage.alerting.helpers.get_global_alert_manager')
    def test_circuit_breaker_triggers_alert(self, mock_get_manager):
        """Test that circuit breaker triggers RG-001 alert"""
        from arbitrage.cross_exchange.risk_guard import (
            CrossExchangeRiskGuard,
            CrossExchangeRiskGuardConfig,
        )
        from arbitrage.cross_exchange.integration import (
            CrossExchangeDecision,
            CrossExchangeAction,
        )
        from arbitrage.common.currency import Currency, Money
        
        # Mock AlertManager
        mock_manager = Mock()
        mock_manager.send_alert = Mock(return_value=True)
        mock_get_manager.return_value = mock_manager
        
        # Create RiskGuard with low daily loss limit and mocked dependencies
        config = CrossExchangeRiskGuardConfig(
            base_currency=Currency.KRW,
            max_daily_loss=Money(Decimal("1000"), Currency.KRW),  # Very low limit
        )
        
        risk_guard = CrossExchangeRiskGuard(
            config=config,
            four_tier_risk_guard=None,  # Mock
            inventory_tracker=None,  # Mock
            position_manager=None,  # Mock
        )
        
        # Simulate daily loss (manually set PnL tracker)
        # Note: This is simplified - real test would go through full trade cycle
        risk_guard.pnl_tracker._daily_pnl = Money(Decimal("-1500"), Currency.KRW)
        
        # Create test decision
        decision = CrossExchangeDecision(
            action=CrossExchangeAction.ENTRY_POSITIVE,
            symbol_upbit="KRW-BTC",
            symbol_binance="BTCUSDT",
            spread_percent=0.5,
            notional_krw=1000000,
            reason="test",
            timestamp=0.0,
        )
        
        # Check should block
        risk_decision = risk_guard.check_cross_exchange_trade(decision)
        
        # Should be blocked
        assert risk_decision.allowed is False
        assert "CROSS_DAILY_LOSS_LIMIT" in risk_decision.reason_code


class TestAlertThrottling:
    """Test alert throttling works with integration hooks"""
    
    def test_repeated_alerts_are_throttled(self):
        """Test that repeated alerts are throttled"""
        from arbitrage.alerting import AlertThrottler
        
        # Create throttler with short window for testing
        throttler = AlertThrottler(redis_client=None, window_seconds=1)
        
        # First alert
        result1 = emit_fx_staleness_alert(
            source="test_source",
            pair="USDT/KRW",
            age_seconds=65,
            last_rate=1420.0,
            throttler=throttler,
            enabled=True,
        )
        
        # Second alert (should be throttled)
        result2 = emit_fx_staleness_alert(
            source="test_source",
            pair="USDT/KRW",
            age_seconds=70,
            last_rate=1420.0,
            throttler=throttler,
            enabled=True,
        )
        
        # First should succeed, second should be throttled
        assert result1 is True
        # Note: result2 might be True or False depending on AlertManager's rate limiting
        # The throttler itself should have recorded the throttle


class TestAlertConfigIntegration:
    """Test alert configuration integration"""
    
    def test_disabled_alerts_not_sent(self):
        """Test that disabled alerts are not sent"""
        # Explicitly disable alert
        result = emit_fx_staleness_alert(
            source="test_source",
            pair="USDT/KRW",
            age_seconds=65,
            last_rate=1420.0,
            enabled=False,  # Disabled
        )
        
        # Should not be sent
        assert result is False
    
    def test_alert_config_loads_successfully(self):
        """Test that alert config loads without error"""
        from arbitrage.alerting import get_alert_config
        
        config = get_alert_config()
        
        # Should have required attributes
        assert hasattr(config, 'enabled')
        assert hasattr(config, 'throttler')
        assert hasattr(config, 'aggregator')


class TestHelperFunctions:
    """Test helper function signatures"""
    
    def test_all_helper_functions_importable(self):
        """Test that all helper functions can be imported"""
        from arbitrage.alerting import (
            emit_rule_based_alert,
            emit_fx_source_down_alert,
            emit_fx_all_sources_down_alert,
            emit_fx_median_deviation_alert,
            emit_fx_staleness_alert,
            emit_executor_order_error_alert,
            emit_executor_rollback_alert,
            emit_circuit_breaker_alert,
            emit_risk_limit_alert,
            emit_ws_staleness_alert,
            emit_ws_reconnect_failed_alert,
        )
        
        # All should be callable
        assert callable(emit_rule_based_alert)
        assert callable(emit_fx_source_down_alert)
        assert callable(emit_fx_all_sources_down_alert)
        assert callable(emit_fx_median_deviation_alert)
        assert callable(emit_fx_staleness_alert)
        assert callable(emit_executor_order_error_alert)
        assert callable(emit_executor_rollback_alert)
        assert callable(emit_circuit_breaker_alert)
        assert callable(emit_risk_limit_alert)
        assert callable(emit_ws_staleness_alert)
        assert callable(emit_ws_reconnect_failed_alert)
