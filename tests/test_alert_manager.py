"""Tests for AlertManager"""

import pytest
import time
from arbitrage.alerting import AlertManager, AlertSeverity, AlertSource, AlertRecord


class TestAlertManager:
    """AlertManager tests"""
    
    def test_initialization(self):
        """Initialization"""
        manager = AlertManager()
        assert manager.rate_limit_window_seconds == 60
        assert manager.rate_limit_per_window[AlertSeverity.P0] == 10
    
    def test_send_alert_basic(self):
        """Send basic alert"""
        manager = AlertManager()
        
        result = manager.send_alert(
            severity=AlertSeverity.P1,
            source=AlertSource.RATE_LIMITER,
            title="Test Alert",
            message="This is a test alert",
            metadata={"key": "value"},
        )
        
        assert result is True
        assert len(manager._alert_history) == 1
        
        alert = manager._alert_history[0]
        assert alert.severity == AlertSeverity.P1
        assert alert.source == AlertSource.RATE_LIMITER
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
        assert alert.metadata["key"] == "value"
    
    def test_rate_limiting(self):
        """Rate limiting per severity"""
        manager = AlertManager(rate_limit_window_seconds=1)
        
        # P3: max 1 per window
        for i in range(5):
            result = manager.send_alert(
                severity=AlertSeverity.P3,
                source=AlertSource.SYSTEM,
                title=f"Alert {i}",
                message=f"Message {i}",
            )
            
            if i == 0:
                assert result is True  # First alert should succeed
            else:
                assert result is False  # Subsequent alerts should be rate limited
        
        # Only 1 alert should be stored
        p3_alerts = [a for a in manager._alert_history if a.severity == AlertSeverity.P3]
        assert len(p3_alerts) == 1
    
    def test_rate_limiting_per_source(self):
        """Rate limiting is per (severity, source) combination"""
        manager = AlertManager()
        
        # Different sources should not interfere
        result1 = manager.send_alert(
            severity=AlertSeverity.P2,
            source=AlertSource.RATE_LIMITER,
            title="Alert 1",
            message="Message 1",
        )
        
        result2 = manager.send_alert(
            severity=AlertSeverity.P2,
            source=AlertSource.HEALTH_MONITOR,
            title="Alert 2",
            message="Message 2",
        )
        
        assert result1 is True
        assert result2 is True
        assert len(manager._alert_history) == 2
    
    def test_get_recent_alerts(self):
        """Get recent alerts with filters"""
        manager = AlertManager()
        
        manager.send_alert(AlertSeverity.P0, AlertSource.RISK_GUARD, "Alert 1", "Msg 1")
        manager.send_alert(AlertSeverity.P1, AlertSource.HEALTH_MONITOR, "Alert 2", "Msg 2")
        manager.send_alert(AlertSeverity.P0, AlertSource.RATE_LIMITER, "Alert 3", "Msg 3")
        
        # All alerts
        all_alerts = manager.get_recent_alerts(minutes=60)
        assert len(all_alerts) == 3
        
        # Filter by severity
        p0_alerts = manager.get_recent_alerts(minutes=60, severity=AlertSeverity.P0)
        assert len(p0_alerts) == 2
        
        # Filter by source
        health_alerts = manager.get_recent_alerts(minutes=60, source=AlertSource.HEALTH_MONITOR)
        assert len(health_alerts) == 1
        
        # Filter by both
        filtered = manager.get_recent_alerts(
            minutes=60,
            severity=AlertSeverity.P0,
            source=AlertSource.RISK_GUARD,
        )
        assert len(filtered) == 1
    
    def test_get_alert_stats(self):
        """Get alert statistics"""
        manager = AlertManager()
        
        manager.send_alert(AlertSeverity.P0, AlertSource.RISK_GUARD, "Alert 1", "Msg 1")
        manager.send_alert(AlertSeverity.P0, AlertSource.RISK_GUARD, "Alert 2", "Msg 2")
        manager.send_alert(AlertSeverity.P1, AlertSource.HEALTH_MONITOR, "Alert 3", "Msg 3")
        
        stats = manager.get_alert_stats()
        
        assert stats["total_alerts"] == 3
        assert stats["by_severity"]["P0"] == 2
        assert stats["by_severity"]["P1"] == 1
        assert stats["by_source"]["RISK_GUARD"] == 2
        assert stats["by_source"]["HEALTH_MONITOR"] == 1
    
    def test_notifier_registration(self):
        """Register notifiers"""
        import os
        # Set to DEV environment so P1 alerts go to all channels
        os.environ["APP_ENV"] = "development"
        
        manager = AlertManager()
        
        class MockNotifier:
            def __init__(self):
                self.sent_alerts = []
            
            def send(self, alert):
                self.sent_alerts.append(alert)
        
        notifier = MockNotifier()
        manager.register_notifier("telegram", notifier)
        
        manager.send_alert(
            AlertSeverity.P1,
            AlertSource.RATE_LIMITER,
            "Test",
            "Test message",
        )
        
        assert len(notifier.sent_alerts) == 1
        assert notifier.sent_alerts[0].title == "Test"
        
        # Clean up
        del os.environ["APP_ENV"]
    
    def test_storage_registration(self):
        """Register storage"""
        import os
        # Set to DEV environment so P1 alerts are stored
        os.environ["APP_ENV"] = "development"
        
        manager = AlertManager()
        
        class MockStorage:
            def __init__(self):
                self.saved_alerts = []
            
            def save(self, alert):
                self.saved_alerts.append(alert)
                return True
        
        storage = MockStorage()
        manager.register_storage(storage)
        
        manager.send_alert(
            AlertSeverity.P1,
            AlertSource.RATE_LIMITER,
            "Test",
            "Test message",
        )
        
        assert len(storage.saved_alerts) == 1
        assert storage.saved_alerts[0].title == "Test"
        
        # Clean up
        del os.environ["APP_ENV"]
    
    def test_clear_history(self):
        """Clear alert history"""
        manager = AlertManager()
        
        manager.send_alert(AlertSeverity.P0, AlertSource.SYSTEM, "Alert", "Message")
        assert len(manager._alert_history) > 0
        
        manager.clear_history()
        assert len(manager._alert_history) == 0
