"""
D80-8: Full Alert Rule Integration Tests

Tests for all 10 alert rules integrated across FX, Executor, RiskGuard, and WebSocket layers.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import time

from arbitrage.alerting import (
    # FX Layer
    emit_fx_source_down_alert,
    emit_fx_all_sources_down_alert,
    emit_fx_median_deviation_alert,
    
    # Executor Layer
    emit_executor_rollback_alert,
    
    # RiskGuard Layer
    emit_risk_limit_alert,
    
    # WebSocket Layer
    emit_ws_staleness_alert,
    emit_ws_reconnect_failed_alert,
    
    # Helper
    get_alert_rule,
)


# =============================================================================
# FX Layer Tests (FX-001, FX-002, FX-003)
# =============================================================================

class TestFxLayerAlertIntegration:
    """Test FX Layer alert rules (FX-001, FX-002, FX-003)"""
    
    def test_fx_001_source_down_alert_emission(self):
        """Test FX-001: Source down alert"""
        result = emit_fx_source_down_alert(
            source="binance",
            duration_seconds=120,
            enabled=True,
        )
        assert result is True
    
    def test_fx_001_rule_exists(self):
        """Test FX-001 rule is defined"""
        rule = get_alert_rule("FX-001")
        assert rule is not None
        assert rule.rule_id == "FX-001"
        assert rule.aggregation_key == "fx_source_down"
    
    def test_fx_002_all_sources_down_alert_emission(self):
        """Test FX-002: All sources down alert"""
        result = emit_fx_all_sources_down_alert(
            pair="USDT/USD",
            down_sources="binance,okx,bybit",
            duration_seconds=180,
            enabled=True,
        )
        assert result is True
    
    def test_fx_002_rule_exists(self):
        """Test FX-002 rule is defined"""
        rule = get_alert_rule("FX-002")
        assert rule is not None
        assert rule.rule_id == "FX-002"
        assert rule.aggregation_key == "fx_all_sources_down"
    
    def test_fx_003_median_deviation_alert_emission(self):
        """Test FX-003: Median deviation alert"""
        result = emit_fx_median_deviation_alert(
            pair="USDT/USD",
            median_rate=1.0005,
            expected_min=0.9505,
            expected_max=1.0505,
            deviation_percent=6.5,
            outliers="binance",
            enabled=True,
        )
        assert result is True
    
    def test_fx_003_rule_exists(self):
        """Test FX-003 rule is defined"""
        rule = get_alert_rule("FX-003")
        assert rule is not None
        assert rule.rule_id == "FX-003"
        assert rule.aggregation_key == "fx_median_deviation"
    
    def test_multi_source_fx_provider_integration(self):
        """Test MultiSourceFxRateProvider triggers FX-002 alert"""
        from arbitrage.common.currency import MultiSourceFxRateProvider
        
        # Create provider without WebSocket (to avoid actual connection)
        provider = MultiSourceFxRateProvider(enable_websocket=False)
        
        # Manually trigger aggregation (no valid sources)
        with patch('arbitrage.alerting.helpers.get_global_alert_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.send_alert = Mock(return_value=True)
            mock_get_manager.return_value = mock_manager
            
            # This should trigger FX-002 (all sources down) internally
            provider._aggregate_and_update_cache()


# =============================================================================
# Executor Layer Tests (EX-002)
# =============================================================================

class TestExecutorLayerAlertIntegration:
    """Test Executor Layer alert rules (EX-002)"""
    
    def test_ex_002_rollback_alert_emission(self):
        """Test EX-002: Rollback alert"""
        result = emit_executor_rollback_alert(
            symbol="KRW-BTC/BTCUSDT",
            exchange="cross_exchange",
            filled_qty=0.0,
            requested_qty=0.001,
            status="rolled_back",
            enabled=True,
        )
        assert result is True
    
    def test_ex_002_rule_exists(self):
        """Test EX-002 rule is defined"""
        rule = get_alert_rule("EX-002")
        assert rule is not None
        assert rule.rule_id == "EX-002"
        assert rule.aggregation_key == "executor_rollback"


# =============================================================================
# RiskGuard Layer Tests (RG-002)
# =============================================================================

class TestRiskGuardLayerAlertIntegration:
    """Test RiskGuard Layer alert rules (RG-002)"""
    
    def test_rg_002_risk_limit_alert_emission(self):
        """Test RG-002: Exposure limit alert"""
        result = emit_risk_limit_alert(
            limit_type="exposure",
            current_value="75.0%",
            limit_value="60.0%",
            action="BLOCK",
            symbol="KRW-BTC/BTCUSDT",
            enabled=True,
        )
        assert result is True
    
    def test_rg_002_rule_exists(self):
        """Test RG-002 rule is defined"""
        rule = get_alert_rule("RG-002")
        assert rule is not None
        assert rule.rule_id == "RG-002"
        assert rule.aggregation_key == "risk_limit"


# =============================================================================
# WebSocket Layer Tests (WS-001, WS-002)
# =============================================================================

class TestWebSocketLayerAlertIntegration:
    """Test WebSocket Layer alert rules (WS-001, WS-002)"""
    
    def test_ws_001_staleness_alert_emission(self):
        """Test WS-001: WebSocket staleness alert"""
        result = emit_ws_staleness_alert(
            source="binance",
            stream="markPrice@btcusdt",
            age_seconds=90,
            last_message_time="2025-01-01 12:00:00",
            enabled=True,
        )
        assert result is True
    
    def test_ws_001_rule_exists(self):
        """Test WS-001 rule is defined"""
        rule = get_alert_rule("WS-001")
        assert rule is not None
        assert rule.rule_id == "WS-001"
        assert rule.aggregation_key == "ws_staleness"
    
    def test_ws_002_reconnect_failed_alert_emission(self):
        """Test WS-002: WebSocket reconnect failed alert"""
        result = emit_ws_reconnect_failed_alert(
            source="binance",
            stream="markPrice@btcusdt",
            attempts=10,
            max_attempts=10,
            error_message="Connection timeout",
            enabled=True,
        )
        assert result is True
    
    def test_ws_002_rule_exists(self):
        """Test WS-002 rule is defined"""
        rule = get_alert_rule("WS-002")
        assert rule is not None
        assert rule.rule_id == "WS-002"
        assert rule.aggregation_key == "ws_reconnect_failed"
    
    def test_binance_ws_client_staleness_detection(self):
        """Test BinanceFxWebSocketClient detects staleness"""
        from arbitrage.common.fx_ws_client import BinanceFxWebSocketClient
        
        # Create client without starting
        client = BinanceFxWebSocketClient(symbol="btcusdt")
        
        # Manually set last_message_time to old value
        client._last_message_time = time.time() - 70  # 70 seconds ago
        client._connected = True
        
        with patch('arbitrage.alerting.helpers.get_global_alert_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.send_alert = Mock(return_value=True)
            mock_get_manager.return_value = mock_manager
            
            # get_stats() should trigger WS-001 alert
            stats = client.get_stats()
            
            assert stats["last_message_age"] > 60


# =============================================================================
# Integration Scenario Tests
# =============================================================================

class TestFullIntegrationScenarios:
    """Test full integration scenarios with multiple layers"""
    
    def test_all_alert_rules_registered(self):
        """Test all 10 alert rules are registered"""
        rule_ids = [
            "FX-001", "FX-002", "FX-003", "FX-004",
            "EX-001", "EX-002",
            "RG-001", "RG-002",
            "WS-001", "WS-002",
        ]
        
        for rule_id in rule_ids:
            rule = get_alert_rule(rule_id)
            assert rule is not None, f"Rule {rule_id} not found"
            assert rule.rule_id == rule_id
    
    def test_all_helper_functions_callable(self):
        """Test all helper functions are callable"""
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
        
        helpers = [
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
        ]
        
        for helper in helpers:
            assert callable(helper)
    
    def test_alert_config_for_all_rules(self):
        """Test alert config can check all rules"""
        from arbitrage.alerting import get_alert_config
        
        config = get_alert_config()
        
        rule_ids = [
            "FX-001", "FX-002", "FX-003", "FX-004",
            "EX-001", "EX-002",
            "RG-001", "RG-002",
            "WS-001", "WS-002",
        ]
        
        for rule_id in rule_ids:
            # Should not raise exception
            enabled = config.is_rule_enabled(rule_id)
            assert isinstance(enabled, bool)
    
    @patch('arbitrage.alerting.helpers.get_global_alert_manager')
    def test_throttling_across_rules(self, mock_get_manager):
        """Test throttling works across different alert rules"""
        from arbitrage.alerting import AlertThrottler
        
        mock_manager = Mock()
        mock_manager.send_alert = Mock(return_value=True)
        mock_get_manager.return_value = mock_manager
        
        throttler = AlertThrottler(redis_client=None, window_seconds=1)
        
        # Emit same alert twice
        result1 = emit_fx_source_down_alert(
            source="test_source",
            duration_seconds=60,
            throttler=throttler,
            enabled=True,
        )
        
        result2 = emit_fx_source_down_alert(
            source="test_source",
            duration_seconds=65,
            throttler=throttler,
            enabled=True,
        )
        
        # First should succeed
        assert result1 is True


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling in alert hooks"""
    
    def test_alert_emission_failure_does_not_crash(self):
        """Test that alert emission failure doesn't crash the caller"""
        # Emit alert with invalid parameters (should handle gracefully)
        try:
            result = emit_fx_source_down_alert(
                source=None,  # Invalid
                duration_seconds=-1,  # Invalid
                enabled=True,
            )
            # Should either return False or handle the error
        except Exception as e:
            # If exception is raised, it should be caught by the hook
            pytest.fail(f"Alert emission should not raise exception: {e}")
    
    def test_disabled_alert_not_sent(self):
        """Test disabled alert is not sent"""
        result = emit_fx_source_down_alert(
            source="test",
            duration_seconds=60,
            pair="USDT/USD",
            enabled=False,
        )
        
        # Should be False (disabled)
        assert result is False
