"""
D80-13: Alert Routing Rules Tests

Tests for alert routing with:
- Priority-based routing (P1/P2/P3)
- Multi-destination support
- Aggregation logic
- Escalation tracking
- YAML configuration
- Backward compatibility
"""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock

from arbitrage.alerting import (
    AlertRecord,
    AlertSeverity,
    AlertSource,
    AlertDispatcher,
    AlertPriority,
    DestinationType,
    RoutingRule,
    RoutingTable,
    AlertRouter,
    AggregatedAlertBatch,
    get_global_alert_router,
    reset_global_alert_router,
)


# =============================================================================
# RoutingTable Tests
# =============================================================================

class TestRoutingTable:
    """Test routing table YAML loading and rule lookup"""
    
    def test_routing_table_loads_from_yaml(self):
        """RoutingTable should load rules from YAML config"""
        config_path = Path("configs/alert_routing.yml")
        
        if not config_path.exists():
            pytest.skip(f"Config not found: {config_path}")
        
        table = RoutingTable(config_path)
        
        # Check FX-001 rule
        rule = table.get_rule("FX-001")
        assert rule is not None
        assert rule.priority == AlertPriority.P1
        assert DestinationType.TELEGRAM in rule.destinations
        assert rule.escalate_after_failures == 3
        assert rule.escalation_target == DestinationType.EMAIL
    
    def test_routing_table_default_rule(self):
        """RoutingTable should provide default rule for unmapped alerts"""
        table = RoutingTable()
        
        # Unmapped rule should return default
        rule = table.get_rule("UNMAPPED-RULE")
        assert rule is not None
        assert rule.priority == AlertPriority.P3
        assert DestinationType.LOCAL_LOG in rule.destinations
    
    def test_routing_table_get_destinations(self):
        """get_destinations should return correct destination list"""
        table = RoutingTable()
        
        # Mock a rule
        table._rules["TEST-001"] = RoutingRule(
            rule_id="TEST-001",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM, DestinationType.SLACK],
        )
        
        dests = table.get_destinations("TEST-001")
        assert len(dests) == 2
        assert DestinationType.TELEGRAM in dests
        assert DestinationType.SLACK in dests
    
    def test_routing_table_get_priority(self):
        """get_priority should return correct priority"""
        table = RoutingTable()
        
        # Mock a rule
        table._rules["TEST-002"] = RoutingRule(
            rule_id="TEST-002",
            priority=AlertPriority.P2,
            destinations=[DestinationType.TELEGRAM],
        )
        
        priority = table.get_priority("TEST-002")
        assert priority == AlertPriority.P2
    
    def test_routing_table_should_escalate(self):
        """should_escalate should check failure count"""
        table = RoutingTable()
        
        # Mock a rule with escalation
        table._rules["TEST-003"] = RoutingRule(
            rule_id="TEST-003",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM],
            escalate_after_failures=3,
            escalation_target=DestinationType.EMAIL,
        )
        
        # Should not escalate with 2 failures
        assert table.should_escalate("TEST-003", 2) is False
        
        # Should escalate with 3 failures
        assert table.should_escalate("TEST-003", 3) is True
        
        # Should escalate with 5 failures
        assert table.should_escalate("TEST-003", 5) is True
    
    def test_routing_table_get_escalation_target(self):
        """get_escalation_target should return escalation destination"""
        table = RoutingTable()
        
        # Mock a rule with escalation
        table._rules["TEST-004"] = RoutingRule(
            rule_id="TEST-004",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM],
            escalate_after_failures=3,
            escalation_target=DestinationType.EMAIL,
        )
        
        target = table.get_escalation_target("TEST-004")
        assert target == DestinationType.EMAIL


# =============================================================================
# AlertRouter Tests
# =============================================================================

class TestAlertRouter:
    """Test alert router with aggregation and escalation"""
    
    def setup_method(self):
        """Setup router"""
        self.table = RoutingTable()
        self.router = AlertRouter(self.table)
    
    def test_router_route_alert_p1(self):
        """Router should route P1 alerts without aggregation"""
        # Mock P1 rule
        self.table._rules["P1-TEST"] = RoutingRule(
            rule_id="P1-TEST",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM],
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="P1 Test",
            message="Test",
        )
        
        decision = self.router.route_alert(alert, "P1-TEST")
        
        assert decision["rule_id"] == "P1-TEST"
        assert decision["priority"] == AlertPriority.P1
        assert decision["should_aggregate"] is False
        assert decision["escalated"] is False
    
    def test_router_route_alert_p2_aggregation(self):
        """Router should aggregate P2 alerts"""
        # Mock P2 rule
        self.table._rules["P2-TEST"] = RoutingRule(
            rule_id="P2-TEST",
            priority=AlertPriority.P2,
            destinations=[DestinationType.TELEGRAM],
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="P2 Test",
            message="Test",
        )
        
        decision = self.router.route_alert(alert, "P2-TEST")
        
        assert decision["priority"] == AlertPriority.P2
        assert decision["should_aggregate"] is True
    
    def test_router_aggregation_buffer(self):
        """Router should buffer alerts for aggregation"""
        # Mock P2 rule
        self.table._rules["AGG-TEST"] = RoutingRule(
            rule_id="AGG-TEST",
            priority=AlertPriority.P2,
            destinations=[DestinationType.TELEGRAM],
            aggregation_window_seconds=300,
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="Agg Test",
            message="Test",
        )
        
        # First alert: buffered
        batch = self.router.aggregate_alert(alert, "AGG-TEST")
        assert batch is None  # Not flushed yet
        
        # Check buffer exists
        assert "AGG-TEST" in self.router._aggregation_buffers
        assert len(self.router._aggregation_buffers["AGG-TEST"].alerts) == 1
    
    def test_router_aggregation_flush_on_window(self):
        """Router should flush batch after window expires"""
        # Mock P2 rule with short window
        self.table._rules["FLUSH-TEST"] = RoutingRule(
            rule_id="FLUSH-TEST",
            priority=AlertPriority.P2,
            destinations=[DestinationType.TELEGRAM],
            aggregation_window_seconds=0.1,  # 100ms
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="Flush Test",
            message="Test",
        )
        
        # Add first alert
        self.router.aggregate_alert(alert, "FLUSH-TEST")
        
        # Wait for window to expire
        time.sleep(0.15)
        
        # Add second alert → should flush
        batch = self.router.aggregate_alert(alert, "FLUSH-TEST")
        
        assert batch is not None
        assert len(batch.alerts) >= 1  # At least one alert (could be 2 if timing is tight)
        assert batch.rule_id == "FLUSH-TEST"
    
    def test_router_aggregation_flush_on_max_count(self):
        """Router should flush batch after max count (100)"""
        # Mock P2 rule
        self.table._rules["COUNT-TEST"] = RoutingRule(
            rule_id="COUNT-TEST",
            priority=AlertPriority.P2,
            destinations=[DestinationType.TELEGRAM],
            aggregation_window_seconds=3600,  # Long window
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="Count Test",
            message="Test",
        )
        
        # Add 100 alerts
        batch = None
        for i in range(100):
            batch = self.router.aggregate_alert(alert, "COUNT-TEST")
        
        # Should flush on 100th alert
        assert batch is not None
        assert len(batch.alerts) == 100
    
    def test_router_escalation_tracking(self):
        """Router should track failures and escalate"""
        # Mock rule with escalation
        self.table._rules["ESC-TEST"] = RoutingRule(
            rule_id="ESC-TEST",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM],
            escalate_after_failures=3,
            escalation_target=DestinationType.EMAIL,
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Esc Test",
            message="Test",
        )
        
        # Record 3 failures
        self.router.record_failure("ESC-TEST")
        self.router.record_failure("ESC-TEST")
        self.router.record_failure("ESC-TEST")
        
        # Next routing should escalate
        decision = self.router.route_alert(alert, "ESC-TEST")
        
        assert decision["escalated"] is True
        assert decision["escalation_target"] == DestinationType.EMAIL
        assert DestinationType.EMAIL in decision["destinations"]
    
    def test_router_reset_escalation(self):
        """Router should reset escalation after success"""
        # Record failure
        self.router.record_failure("RESET-TEST")
        assert "RESET-TEST" in self.router._escalation_tracker
        
        # Reset
        self.router.reset_escalation("RESET-TEST")
        assert "RESET-TEST" not in self.router._escalation_tracker
    
    def test_router_flush_all_batches(self):
        """flush_all_batches should clear all buffers"""
        # Add alerts to multiple buffers
        for rule_id in ["BATCH-1", "BATCH-2", "BATCH-3"]:
            self.table._rules[rule_id] = RoutingRule(
                rule_id=rule_id,
                priority=AlertPriority.P2,
                destinations=[DestinationType.TELEGRAM],
            )
            
            alert = AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title=f"Test {rule_id}",
                message="Test",
            )
            
            self.router.aggregate_alert(alert, rule_id)
        
        # Flush all
        batches = self.router.flush_all_batches()
        
        assert len(batches) == 3
        assert len(self.router._aggregation_buffers) == 0
    
    def test_router_get_stats(self):
        """get_stats should return routing statistics"""
        stats = self.router.get_stats()
        
        assert "routed" in stats
        assert "aggregated" in stats
        assert "escalated" in stats
        assert "flushed_batches" in stats
        assert "aggregation_buffers" in stats
        assert "escalation_trackers" in stats


# =============================================================================
# Dispatcher Integration Tests
# =============================================================================

class TestDispatcherIntegration:
    """Test dispatcher integration with routing"""
    
    def setup_method(self):
        """Setup dispatcher"""
        from arbitrage.alerting import reset_global_alert_metrics
        from arbitrage.alerting.metrics_exporter import AlertMetrics
        import arbitrage.alerting.metrics_exporter as metrics_module
        
        reset_global_alert_router()
        reset_global_alert_metrics()
        
        # Force non-Prometheus metrics for testing
        metrics_module._global_metrics = AlertMetrics(enable_prometheus=False)
        
        # Create dispatcher WITHOUT routing (backward compatibility)
        self.dispatcher_legacy = AlertDispatcher(redis_client=None, queue_name="legacy_test")
        
        # Create dispatcher WITH routing
        self.dispatcher_routing = AlertDispatcher(
            redis_client=None,
            queue_name="routing_test",
            enable_routing=True,
        )
    
    def teardown_method(self):
        """Cleanup"""
        from arbitrage.alerting import reset_global_alert_metrics
        
        if self.dispatcher_legacy._worker_running:
            self.dispatcher_legacy.stop_worker()
        
        if self.dispatcher_routing._worker_running:
            self.dispatcher_routing.stop_worker()
        
        reset_global_alert_router()
        reset_global_alert_metrics()
    
    def test_dispatcher_backward_compatibility(self):
        """Dispatcher should work without routing (backward compatible)"""
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="Legacy Test",
            message="Test",
        )
        
        # Enqueue without routing
        result = self.dispatcher_legacy.enqueue(alert, rule_id="TEST-001")
        
        assert result is True
        
        stats = self.dispatcher_legacy.get_stats()
        assert stats["enqueued"] == 1
    
    def test_dispatcher_with_routing_p1(self):
        """Dispatcher with routing should route P1 alerts"""
        # Configure routing table
        router = self.dispatcher_routing._router
        router.routing_table._rules["P1-ROUTE"] = RoutingRule(
            rule_id="P1-ROUTE",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM],
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="P1 Route Test",
            message="Test",
        )
        
        # Enqueue with routing
        result = self.dispatcher_routing.enqueue(alert, rule_id="P1-ROUTE")
        
        assert result is True
        
        stats = self.dispatcher_routing.get_stats()
        assert stats["enqueued"] == 1
    
    def test_dispatcher_with_routing_aggregation(self):
        """Dispatcher with routing should aggregate P2 alerts"""
        # Configure routing table
        router = self.dispatcher_routing._router
        router.routing_table._rules["P2-AGG"] = RoutingRule(
            rule_id="P2-AGG",
            priority=AlertPriority.P2,
            destinations=[DestinationType.TELEGRAM],
            aggregation_window_seconds=300,
        )
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="P2 Agg Test",
            message="Test",
        )
        
        # Enqueue with routing
        result = self.dispatcher_routing.enqueue(alert, rule_id="P2-AGG")
        
        assert result is True  # Returns True (added to buffer)
        
        # Check aggregation buffer
        assert "P2-AGG" in router._aggregation_buffers


# =============================================================================
# Priority Tests
# =============================================================================

class TestPriorityHandling:
    """Test priority-based routing"""
    
    def test_p1_no_aggregation(self):
        """P1 alerts should not be aggregated"""
        table = RoutingTable()
        table._rules["P1"] = RoutingRule(
            rule_id="P1",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM],
        )
        
        router = AlertRouter(table)
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.FX_LAYER,
            title="P1",
            message="Test",
        )
        
        decision = router.route_alert(alert, "P1")
        assert decision["should_aggregate"] is False
    
    def test_p2_aggregation(self):
        """P2 alerts should be aggregated"""
        table = RoutingTable()
        table._rules["P2"] = RoutingRule(
            rule_id="P2",
            priority=AlertPriority.P2,
            destinations=[DestinationType.TELEGRAM],
        )
        
        router = AlertRouter(table)
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="P2",
            message="Test",
        )
        
        decision = router.route_alert(alert, "P2")
        assert decision["should_aggregate"] is True
    
    def test_p3_aggregation(self):
        """P3 alerts should be aggregated"""
        table = RoutingTable()
        table._rules["P3"] = RoutingRule(
            rule_id="P3",
            priority=AlertPriority.P3,
            destinations=[DestinationType.LOCAL_LOG],
        )
        
        router = AlertRouter(table)
        alert = AlertRecord(
            severity=AlertSeverity.P3,
            source=AlertSource.FX_LAYER,
            title="P3",
            message="Test",
        )
        
        decision = router.route_alert(alert, "P3")
        assert decision["should_aggregate"] is True


# =============================================================================
# Destination Tests
# =============================================================================

class TestDestinationRouting:
    """Test multi-destination routing"""
    
    def test_single_destination(self):
        """Rule with single destination"""
        table = RoutingTable()
        table._rules["SINGLE"] = RoutingRule(
            rule_id="SINGLE",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM],
        )
        
        dests = table.get_destinations("SINGLE")
        assert len(dests) == 1
        assert DestinationType.TELEGRAM in dests
    
    def test_multiple_destinations(self):
        """Rule with multiple destinations"""
        table = RoutingTable()
        table._rules["MULTI"] = RoutingRule(
            rule_id="MULTI",
            priority=AlertPriority.P1,
            destinations=[DestinationType.TELEGRAM, DestinationType.SLACK, DestinationType.EMAIL],
        )
        
        dests = table.get_destinations("MULTI")
        assert len(dests) == 3
        assert DestinationType.TELEGRAM in dests
        assert DestinationType.SLACK in dests
        assert DestinationType.EMAIL in dests


# =============================================================================
# Global Router Tests
# =============================================================================

class TestGlobalRouter:
    """Test global router singleton"""
    
    def test_get_global_router(self):
        """get_global_alert_router should return singleton"""
        reset_global_alert_router()
        
        router1 = get_global_alert_router()
        router2 = get_global_alert_router()
        
        assert router1 is router2
    
    def test_reset_global_router(self):
        """reset_global_alert_router should clear singleton"""
        router1 = get_global_alert_router()
        reset_global_alert_router()
        router2 = get_global_alert_router()
        
        assert router1 is not router2


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_destinations_raises_error(self):
        """RoutingRule with empty destinations should raise error"""
        with pytest.raises(ValueError, match="destinations cannot be empty"):
            RoutingRule(
                rule_id="EMPTY",
                priority=AlertPriority.P1,
                destinations=[],
            )
    
    def test_escalation_without_target_raises_error(self):
        """Escalation without target should raise error"""
        with pytest.raises(ValueError, match="escalation_target required"):
            RoutingRule(
                rule_id="NO-TARGET",
                priority=AlertPriority.P1,
                destinations=[DestinationType.TELEGRAM],
                escalate_after_failures=3,
                escalation_target=None,
            )
    
    def test_invalid_escalation_count_raises_error(self):
        """Invalid escalation count should raise error"""
        with pytest.raises(ValueError, match="must be >= 1"):
            RoutingRule(
                rule_id="INVALID-COUNT",
                priority=AlertPriority.P1,
                destinations=[DestinationType.TELEGRAM],
                escalate_after_failures=0,
                escalation_target=DestinationType.EMAIL,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
