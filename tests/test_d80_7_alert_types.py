"""
D80-7: Alert Types Tests
"""

import pytest
from arbitrage.alerting import (
    AlertCategory,
    AlertRuleDefinition,
    ALERT_RULES,
    get_alert_rule,
    format_alert,
    AlertSeverity,
    AlertSource,
)


class TestAlertRuleDefinition:
    """Test AlertRuleDefinition"""
    
    def test_format(self):
        """Test template formatting"""
        rule = AlertRuleDefinition(
            rule_id="TEST-001",
            category=AlertCategory.FX,
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title_template="Test: {source}",
            message_template="Error: {error_message}",
        )
        
        title, message = rule.format(source="binance", error_message="Connection lost")
        
        assert title == "Test: binance"
        assert message == "Error: Connection lost"


class TestAlertRules:
    """Test alert rules registry"""
    
    def test_all_fx_rules_exist(self):
        """Test all FX rules exist"""
        fx_rules = ["FX-001", "FX-002", "FX-003", "FX-004"]
        for rule_id in fx_rules:
            assert rule_id in ALERT_RULES
            rule = ALERT_RULES[rule_id]
            assert rule.category == AlertCategory.FX
            assert rule.source == AlertSource.FX_LAYER
    
    def test_all_executor_rules_exist(self):
        """Test all Executor rules exist"""
        ex_rules = ["EX-001", "EX-002"]
        for rule_id in ex_rules:
            assert rule_id in ALERT_RULES
            rule = ALERT_RULES[rule_id]
            assert rule.category == AlertCategory.EXECUTOR
            assert rule.source == AlertSource.EXECUTOR
    
    def test_all_riskguard_rules_exist(self):
        """Test all RiskGuard rules exist"""
        rg_rules = ["RG-001", "RG-002"]
        for rule_id in rg_rules:
            assert rule_id in ALERT_RULES
            rule = ALERT_RULES[rule_id]
            assert rule.category == AlertCategory.RISK_GUARD
            assert rule.source == AlertSource.RISK_GUARD
    
    def test_all_websocket_rules_exist(self):
        """Test all WebSocket rules exist"""
        ws_rules = ["WS-001", "WS-002"]
        for rule_id in ws_rules:
            assert rule_id in ALERT_RULES
            rule = ALERT_RULES[rule_id]
            assert rule.category == AlertCategory.WEBSOCKET
            assert rule.source == AlertSource.WS_CLIENT
    
    def test_get_alert_rule(self):
        """Test get_alert_rule"""
        rule = get_alert_rule("FX-001")
        assert rule is not None
        assert rule.rule_id == "FX-001"
        
        # Non-existent rule
        assert get_alert_rule("INVALID") is None
    
    def test_format_alert(self):
        """Test format_alert"""
        result = format_alert(
            "FX-001",
            source="binance",
            duration_seconds=35,
            pair="USDT/USD",
            last_update="2025-01-01 00:00:00",
        )
        
        assert result is not None
        rule, title, message = result
        
        assert rule.rule_id == "FX-001"
        assert "binance" in title
        assert "35s" in message
        assert "USDT/USD" in message
    
    def test_format_alert_invalid_rule(self):
        """Test format_alert with invalid rule"""
        result = format_alert("INVALID", param="value")
        assert result is None


class TestCriticalAlerts:
    """Test critical alert rules"""
    
    def test_fx_002_all_sources_down(self):
        """Test FX-002 (all sources down)"""
        rule = get_alert_rule("FX-002")
        assert rule.severity == AlertSeverity.P0  # Critical
        
        title, message = rule.format(
            pair="USDT/USD",
            down_sources="binance,okx,bybit",
            duration_seconds=120,
        )
        
        assert "CRITICAL" in title
        assert "ALL FX sources are DOWN" in message
        assert "binance,okx,bybit" in message
    
    def test_fx_003_median_deviation(self):
        """Test FX-003 (median deviation)"""
        rule = get_alert_rule("FX-003")
        assert rule.severity == AlertSeverity.P0  # Critical
        
        title, message = rule.format(
            pair="USDT/USD",
            median_rate=1.05,
            expected_min=0.95,
            expected_max=1.05,
            deviation_percent=6.5,
            outliers="source_a",
        )
        
        assert "CRITICAL" in message
        assert "6.50%" in message
    
    def test_rg_001_circuit_breaker(self):
        """Test RG-001 (circuit breaker)"""
        rule = get_alert_rule("RG-001")
        assert rule.severity == AlertSeverity.P0  # Critical
        
        title, message = rule.format(
            reason="Daily loss limit",
            threshold="1000000",
            current_value="1050000",
            cooldown_seconds=300,
        )
        
        assert "Circuit Breaker" in title
        assert "CRITICAL" in message
        assert "Daily loss limit" in message


class TestSeverityMapping:
    """Test severity mapping"""
    
    def test_p0_critical_rules(self):
        """Test P0 (Critical) rules"""
        p0_rules = ["FX-002", "FX-003", "RG-001"]
        for rule_id in p0_rules:
            rule = get_alert_rule(rule_id)
            assert rule.severity == AlertSeverity.P0
    
    def test_p2_warning_rules(self):
        """Test P2 (Warning) rules"""
        p2_rules = ["FX-001", "FX-004", "EX-001", "EX-002", "RG-002", "WS-001", "WS-002"]
        for rule_id in p2_rules:
            rule = get_alert_rule(rule_id)
            assert rule.severity == AlertSeverity.P2


class TestAggregationKeys:
    """Test aggregation keys"""
    
    def test_aggregation_keys_defined(self):
        """Test all rules have aggregation keys"""
        for rule_id, rule in ALERT_RULES.items():
            assert rule.aggregation_key is not None
            assert rule.aggregation_key != ""
    
    def test_fx_aggregation_keys(self):
        """Test FX aggregation keys"""
        assert ALERT_RULES["FX-001"].aggregation_key == "fx_source_down"
        assert ALERT_RULES["FX-002"].aggregation_key == "fx_all_sources_down"
        assert ALERT_RULES["FX-003"].aggregation_key == "fx_median_deviation"
        assert ALERT_RULES["FX-004"].aggregation_key == "fx_staleness"
