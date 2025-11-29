"""
D76-4: Incident Simulation Tests

Tests for incident simulation infrastructure and scenarios.
"""

import pytest
from arbitrage.alerting import AlertManager, RuleEngine, Environment
from arbitrage.alerting.models import AlertSeverity
from arbitrage.alerting.simulation import (
    simulate_redis_connection_loss,
    simulate_high_loop_latency,
    simulate_global_risk_block,
    simulate_ws_reconnect_storm,
    simulate_rate_limiter_low_remaining,
    simulate_rate_limiter_http_429,
    simulate_exchange_health_down,
    simulate_arb_universe_all_skip,
    simulate_cross_sync_high_imbalance,
    simulate_state_save_failed,
    simulate_exchange_health_frozen,
    simulate_cross_sync_high_exposure,
    get_all_incidents,
)


class TestIncidentSimulation:
    """Test incident simulation functions"""
    
    def test_redis_connection_loss_prod(self):
        """Test Redis connection loss incident in PROD environment"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        result = simulate_redis_connection_loss(manager, Environment.PROD)
        
        assert result.name == "Redis Connection Loss"
        assert result.rule_id == "D75.SYSTEM.REDIS_CONNECTION_LOST"
        assert result.severity == AlertSeverity.P0
        assert result.dispatch_plan.telegram == True
        assert result.dispatch_plan.postgres == True
        assert result.dispatch_plan.slack == False
        assert result.dispatch_plan.email == False
    
    def test_high_loop_latency_dev(self):
        """Test high loop latency incident in DEV environment"""
        rule_engine = RuleEngine(environment=Environment.DEV)
        manager = AlertManager(rule_engine=rule_engine)
        
        result = simulate_high_loop_latency(manager, Environment.DEV)
        
        assert result.name == "High Loop Latency Spike"
        assert result.rule_id == "D75.SYSTEM.ENGINE_LATENCY"
        assert result.severity == AlertSeverity.P1
        assert result.dispatch_plan.telegram == True
        assert result.dispatch_plan.slack == True
        assert result.dispatch_plan.postgres == True
    
    def test_global_risk_block(self):
        """Test global risk block incident"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        result = simulate_global_risk_block(manager, Environment.PROD)
        
        assert result.rule_id == "D75.RISK_GUARD.GLOBAL_BLOCK"
        assert result.severity == AlertSeverity.P0
        assert result.dispatch_plan.telegram == True
        assert result.dispatch_plan.postgres == True
    
    def test_rate_limiter_low_remaining_prod(self):
        """Test rate limiter low remaining (P2) in PROD"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        result = simulate_rate_limiter_low_remaining(manager, Environment.PROD)
        
        assert result.severity == AlertSeverity.P2
        # PROD P2: PostgreSQL only (no Telegram unless opt-in)
        assert result.dispatch_plan.telegram == False
        assert result.dispatch_plan.postgres == True
        assert result.dispatch_plan.slack == False
    
    def test_rate_limiter_low_remaining_dev(self):
        """Test rate limiter low remaining (P2) in DEV"""
        rule_engine = RuleEngine(environment=Environment.DEV)
        manager = AlertManager(rule_engine=rule_engine)
        
        result = simulate_rate_limiter_low_remaining(manager, Environment.DEV)
        
        assert result.severity == AlertSeverity.P2
        # DEV P2: All channels
        assert result.dispatch_plan.telegram == True
        assert result.dispatch_plan.slack == True
        assert result.dispatch_plan.email == True
        assert result.dispatch_plan.postgres == True
    
    def test_all_incidents_count(self):
        """Test that get_all_incidents returns 12+ incidents"""
        incidents = get_all_incidents()
        assert len(incidents) >= 12
    
    def test_all_incidents_execute_prod(self):
        """Test all incidents execute without errors in PROD"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        incidents = get_all_incidents()
        for name, incident_func in incidents:
            result = incident_func(manager, Environment.PROD)
            assert result is not None
            assert result.name is not None
            assert result.rule_id is not None
            assert result.severity is not None
    
    def test_telegram_first_policy_prod(self):
        """Test Telegram-first policy in PROD environment"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        # P0: Should have Telegram
        p0_result = simulate_redis_connection_loss(manager, Environment.PROD)
        assert p0_result.dispatch_plan.telegram == True
        assert p0_result.dispatch_plan.slack == False
        
        # P1: Should have Telegram
        p1_result = simulate_high_loop_latency(manager, Environment.PROD)
        assert p1_result.dispatch_plan.telegram == True
        assert p1_result.dispatch_plan.slack == False
        
        # P2: Should NOT have Telegram (unless opt-in)
        p2_result = simulate_rate_limiter_low_remaining(manager, Environment.PROD)
        assert p2_result.dispatch_plan.telegram == False
        assert p2_result.dispatch_plan.slack == False
    
    def test_dev_all_channels_policy(self):
        """Test all channels available in DEV environment"""
        rule_engine = RuleEngine(environment=Environment.DEV)
        manager = AlertManager(rule_engine=rule_engine)
        
        # P0/P1: Telegram + Slack (no Email for critical)
        p0_result = simulate_redis_connection_loss(manager, Environment.DEV)
        assert p0_result.dispatch_plan.telegram == True
        assert p0_result.dispatch_plan.slack == True
        
        # P2: All channels
        p2_result = simulate_rate_limiter_low_remaining(manager, Environment.DEV)
        assert p2_result.dispatch_plan.telegram == True
        assert p2_result.dispatch_plan.slack == True
        assert p2_result.dispatch_plan.email == True
    
    def test_incident_result_to_dict(self):
        """Test IncidentResult serialization"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        result = simulate_redis_connection_loss(manager, Environment.PROD)
        result_dict = result.to_dict()
        
        assert "name" in result_dict
        assert "rule_id" in result_dict
        assert "severity" in result_dict
        assert "dispatch_plan" in result_dict
        assert "actual_delivery" in result_dict
        assert result_dict["severity"] == "P0"


class TestTelegramFirstPolicy:
    """Test Telegram-first policy validation"""
    
    def test_prod_p0_routing(self):
        """PROD P0: Telegram + PostgreSQL only"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        # Test with multiple P0 incidents
        result1 = simulate_redis_connection_loss(manager, Environment.PROD)
        result2 = simulate_global_risk_block(manager, Environment.PROD)
        result3 = simulate_exchange_health_frozen(manager, Environment.PROD)
        
        for result in [result1, result2, result3]:
            assert result.severity == AlertSeverity.P0
            assert result.dispatch_plan.telegram == True
            assert result.dispatch_plan.postgres == True
            assert result.dispatch_plan.slack == False
            assert result.dispatch_plan.email == False
    
    def test_prod_p1_routing(self):
        """PROD P1: Telegram + PostgreSQL only"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        # Test with multiple P1 incidents
        result1 = simulate_high_loop_latency(manager, Environment.PROD)
        result2 = simulate_ws_reconnect_storm(manager, Environment.PROD)
        result3 = simulate_rate_limiter_http_429(manager, Environment.PROD)
        
        for result in [result1, result2, result3]:
            assert result.severity == AlertSeverity.P1
            assert result.dispatch_plan.telegram == True
            assert result.dispatch_plan.postgres == True
            assert result.dispatch_plan.slack == False
            assert result.dispatch_plan.email == False
    
    def test_prod_p2_routing(self):
        """PROD P2: PostgreSQL only (no Telegram/Slack/Email)"""
        rule_engine = RuleEngine(environment=Environment.PROD)
        manager = AlertManager(rule_engine=rule_engine)
        
        # Test with multiple P2 incidents
        result1 = simulate_rate_limiter_low_remaining(manager, Environment.PROD)
        result2 = simulate_cross_sync_high_imbalance(manager, Environment.PROD)
        result3 = simulate_state_save_failed(manager, Environment.PROD)
        
        for result in [result1, result2, result3]:
            assert result.severity == AlertSeverity.P2
            assert result.dispatch_plan.telegram == False
            assert result.dispatch_plan.postgres == True
            assert result.dispatch_plan.slack == False
            assert result.dispatch_plan.email == False


class TestEnvironmentRouting:
    """Test environment-aware routing"""
    
    def test_same_incident_different_environments(self):
        """Test same incident routes differently in PROD vs DEV"""
        # PROD
        prod_engine = RuleEngine(environment=Environment.PROD)
        prod_manager = AlertManager(rule_engine=prod_engine)
        prod_result = simulate_high_loop_latency(prod_manager, Environment.PROD)
        
        # DEV
        dev_engine = RuleEngine(environment=Environment.DEV)
        dev_manager = AlertManager(rule_engine=dev_engine)
        dev_result = simulate_high_loop_latency(dev_manager, Environment.DEV)
        
        # Both should be P1
        assert prod_result.severity == AlertSeverity.P1
        assert dev_result.severity == AlertSeverity.P1
        
        # But different routing
        assert prod_result.dispatch_plan.telegram == True
        assert prod_result.dispatch_plan.slack == False
        
        assert dev_result.dispatch_plan.telegram == True
        assert dev_result.dispatch_plan.slack == True
