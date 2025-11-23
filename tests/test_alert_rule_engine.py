"""
Tests for Alert Rule Engine (D76-3)

Tests rule-based alerting with environment-aware channel routing
"""

import pytest
import os
from arbitrage.alerting.rule_engine import (
    RuleEngine,
    RuleRegistry,
    AlertRule,
    AlertDispatchPlan,
    AlertChannel,
    Environment,
)
from arbitrage.alerting.models import AlertSeverity, AlertSource, AlertRecord


class TestRuleRegistry:
    """Test Rule Registry"""
    
    def test_initialization(self):
        """Test registry initialization with default rules"""
        registry = RuleRegistry()
        
        # Should have rules defined
        assert len(registry.rules) > 0
        
        # Check some key rules exist
        assert "D75.RATE_LIMITER.LOW_REMAINING" in registry.rules
        assert "D75.HEALTH.FROZEN" in registry.rules
        assert "D75.RISK_GUARD.GLOBAL_BLOCK" in registry.rules
    
    def test_get_rule(self):
        """Test getting rule by ID"""
        registry = RuleRegistry()
        
        rule = registry.get_rule("D75.RISK_GUARD.GLOBAL_BLOCK")
        assert rule is not None
        assert rule.severity == AlertSeverity.P0
        assert rule.source == AlertSource.RISK_GUARD
    
    def test_get_rules_by_source(self):
        """Test getting rules by source"""
        registry = RuleRegistry()
        
        rate_limiter_rules = registry.get_rules_by_source(AlertSource.RATE_LIMITER)
        assert len(rate_limiter_rules) >= 2
        
        # All should be from rate limiter
        for rule in rate_limiter_rules:
            assert rule.source == AlertSource.RATE_LIMITER
    
    def test_get_rules_by_severity(self):
        """Test getting rules by severity"""
        registry = RuleRegistry()
        
        p0_rules = registry.get_rules_by_severity(AlertSeverity.P0)
        assert len(p0_rules) >= 2  # At least GLOBAL_BLOCK and FROZEN
        
        for rule in p0_rules:
            assert rule.severity == AlertSeverity.P0


class TestRuleEngine:
    """Test Rule Engine"""
    
    def test_initialization_default_environment(self):
        """Test engine initialization with auto-detected environment"""
        # Set env var
        os.environ["APP_ENV"] = "development"
        
        engine = RuleEngine()
        assert engine.environment == Environment.DEV
        
        # Clean up
        del os.environ["APP_ENV"]
    
    def test_initialization_prod_environment(self):
        """Test engine initialization in PROD"""
        os.environ["APP_ENV"] = "production"
        
        engine = RuleEngine()
        assert engine.environment == Environment.PROD
        
        del os.environ["APP_ENV"]
    
    def test_prod_channel_routing_p0(self):
        """Test PROD environment P0 routing (Telegram + PostgreSQL)"""
        os.environ["APP_ENV"] = "production"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RISK_GUARD,
            title="Test",
            message="Test P0",
        )
        
        plan = engine.evaluate_alert(alert)
        
        # PROD P0: Telegram + PostgreSQL
        assert plan.telegram is True
        assert plan.postgres is True
        assert plan.slack is False
        assert plan.email is False
        
        del os.environ["APP_ENV"]
    
    def test_prod_channel_routing_p1(self):
        """Test PROD environment P1 routing (Telegram + PostgreSQL)"""
        os.environ["APP_ENV"] = "production"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.HEALTH_MONITOR,
            title="Test",
            message="Test P1",
        )
        
        plan = engine.evaluate_alert(alert)
        
        # PROD P1: Telegram + PostgreSQL
        assert plan.telegram is True
        assert plan.postgres is True
        assert plan.slack is False
        assert plan.email is False
        
        del os.environ["APP_ENV"]
    
    def test_prod_channel_routing_p2(self):
        """Test PROD environment P2 routing (PostgreSQL only by default)"""
        os.environ["APP_ENV"] = "production"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.ARB_ROUTE,
            title="Test",
            message="Test P2",
        )
        
        plan = engine.evaluate_alert(alert)
        
        # PROD P2: PostgreSQL only (Telegram via env var)
        assert plan.telegram is False  # Unless ALERT_P2_TELEGRAM=true
        assert plan.postgres is True
        assert plan.slack is False
        assert plan.email is False
        
        del os.environ["APP_ENV"]
    
    def test_prod_channel_routing_p3(self):
        """Test PROD environment P3 routing (PostgreSQL only)"""
        os.environ["APP_ENV"] = "production"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P3,
            source=AlertSource.SYSTEM,
            title="Test",
            message="Test P3",
        )
        
        plan = engine.evaluate_alert(alert)
        
        # PROD P3: PostgreSQL only
        assert plan.telegram is False
        assert plan.postgres is True
        assert plan.slack is False
        assert plan.email is False
        
        del os.environ["APP_ENV"]
    
    def test_dev_channel_routing_p0(self):
        """Test DEV environment P0 routing (Telegram + Slack + PostgreSQL)"""
        os.environ["APP_ENV"] = "development"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RISK_GUARD,
            title="Test",
            message="Test P0",
        )
        
        plan = engine.evaluate_alert(alert)
        
        # DEV P0: Telegram + Slack + PostgreSQL
        assert plan.telegram is True
        assert plan.slack is True
        assert plan.postgres is True
        assert plan.email is False
        
        del os.environ["APP_ENV"]
    
    def test_dev_channel_routing_p1(self):
        """Test DEV environment P1 routing (Telegram + Slack + PostgreSQL)"""
        os.environ["APP_ENV"] = "development"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.HEALTH_MONITOR,
            title="Test",
            message="Test P1",
        )
        
        plan = engine.evaluate_alert(alert)
        
        # DEV P1: Telegram + Slack + PostgreSQL
        assert plan.telegram is True
        assert plan.slack is True
        assert plan.postgres is True
        assert plan.email is False
        
        del os.environ["APP_ENV"]
    
    def test_dev_channel_routing_p2(self):
        """Test DEV environment P2 routing (All channels)"""
        os.environ["APP_ENV"] = "development"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.ARB_ROUTE,
            title="Test",
            message="Test P2",
        )
        
        plan = engine.evaluate_alert(alert)
        
        # DEV P2: All channels
        assert plan.telegram is True
        assert plan.slack is True
        assert plan.email is True
        assert plan.postgres is True
        
        del os.environ["APP_ENV"]
    
    def test_dev_channel_routing_p3(self):
        """Test DEV environment P3 routing (Email + PostgreSQL)"""
        os.environ["APP_ENV"] = "development"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P3,
            source=AlertSource.SYSTEM,
            title="Test",
            message="Test P3",
        )
        
        plan = engine.evaluate_alert(alert)
        
        # DEV P3: Email + PostgreSQL
        assert plan.telegram is False
        assert plan.slack is False
        assert plan.email is True
        assert plan.postgres is True
        
        del os.environ["APP_ENV"]
    
    def test_rule_based_routing_with_specific_rule(self):
        """Test routing with specific rule ID"""
        os.environ["APP_ENV"] = "production"
        engine = RuleEngine()
        
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RISK_GUARD,
            title="Global Block",
            message="Global daily loss limit exceeded",
        )
        
        # Use specific rule
        plan = engine.evaluate_alert(alert, rule_id="D75.RISK_GUARD.GLOBAL_BLOCK")
        
        # Should follow P0 routing
        assert plan.telegram is True
        assert plan.postgres is True
        
        del os.environ["APP_ENV"]
    
    def test_disabled_rule(self):
        """Test that disabled rule returns empty dispatch plan"""
        os.environ["APP_ENV"] = "development"
        engine = RuleEngine()
        
        # Disable a rule
        rule = engine.registry.get_rule("D75.RATE_LIMITER.LOW_REMAINING")
        rule.enabled = False
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Test",
        )
        
        plan = engine.evaluate_alert(alert, rule_id="D75.RATE_LIMITER.LOW_REMAINING")
        
        # All channels should be OFF for disabled rule
        assert plan.telegram is False
        assert plan.slack is False
        assert plan.email is False
        assert plan.postgres is False
        
        del os.environ["APP_ENV"]
    
    def test_get_enabled_channels_for_severity(self):
        """Test getting enabled channels for severity"""
        os.environ["APP_ENV"] = "production"
        engine = RuleEngine()
        
        # PROD P0: Telegram + PostgreSQL
        p0_channels = engine.get_enabled_channels_for_severity(AlertSeverity.P0)
        assert AlertChannel.TELEGRAM in p0_channels
        assert AlertChannel.POSTGRES in p0_channels
        assert AlertChannel.SLACK not in p0_channels
        
        # PROD P3: PostgreSQL only
        p3_channels = engine.get_enabled_channels_for_severity(AlertSeverity.P3)
        assert AlertChannel.POSTGRES in p3_channels
        assert AlertChannel.TELEGRAM not in p3_channels
        
        del os.environ["APP_ENV"]
    
    def test_get_environment_info(self):
        """Test getting environment info"""
        os.environ["APP_ENV"] = "production"
        engine = RuleEngine()
        
        info = engine.get_environment_info()
        
        assert info["environment"] == "production"
        assert info["telegram_primary"] is True
        assert "channel_policy" in info
        assert "P0" in info["channel_policy"]
        assert info["total_rules"] > 0
        
        # Check channel policy structure
        p0_channels = info["channel_policy"]["P0"]
        assert "telegram" in p0_channels
        assert "postgres" in p0_channels
        
        del os.environ["APP_ENV"]
    
    def test_telegram_first_policy_verification(self):
        """
        Verify Telegram-first policy across all severity levels
        
        PROD: Telegram for P0/P1, PostgreSQL always
        DEV: All channels available
        """
        # PROD verification
        os.environ["APP_ENV"] = "production"
        engine_prod = RuleEngine()
        
        # P0: Must have Telegram
        p0_plan = engine_prod._determine_channels(AlertSeverity.P0)
        assert p0_plan.telegram is True, "P0 must use Telegram in PROD"
        assert p0_plan.postgres is True, "P0 must use PostgreSQL in PROD"
        
        # P1: Must have Telegram
        p1_plan = engine_prod._determine_channels(AlertSeverity.P1)
        assert p1_plan.telegram is True, "P1 must use Telegram in PROD"
        assert p1_plan.postgres is True, "P1 must use PostgreSQL in PROD"
        
        # P2: PostgreSQL only (Telegram optional)
        p2_plan = engine_prod._determine_channels(AlertSeverity.P2)
        assert p2_plan.postgres is True, "P2 must use PostgreSQL in PROD"
        assert p2_plan.slack is False, "P2 should not use Slack in PROD by default"
        
        # P3: PostgreSQL only
        p3_plan = engine_prod._determine_channels(AlertSeverity.P3)
        assert p3_plan.postgres is True, "P3 must use PostgreSQL in PROD"
        assert p3_plan.telegram is False, "P3 should not use Telegram in PROD"
        
        del os.environ["APP_ENV"]
        
        # DEV verification
        os.environ["APP_ENV"] = "development"
        engine_dev = RuleEngine()
        
        # P0: Telegram + Slack + PostgreSQL
        p0_plan_dev = engine_dev._determine_channels(AlertSeverity.P0)
        assert p0_plan_dev.telegram is True
        assert p0_plan_dev.slack is True
        assert p0_plan_dev.postgres is True
        
        # P2: All channels
        p2_plan_dev = engine_dev._determine_channels(AlertSeverity.P2)
        assert p2_plan_dev.telegram is True
        assert p2_plan_dev.slack is True
        assert p2_plan_dev.email is True
        assert p2_plan_dev.postgres is True
        
        del os.environ["APP_ENV"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
