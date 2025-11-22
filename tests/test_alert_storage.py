"""Tests for Alert Storage"""

import pytest
import time
from datetime import datetime, timedelta
from arbitrage.alerting import AlertSeverity, AlertSource, AlertRecord
from arbitrage.alerting.storage import InMemoryStorage


class TestInMemoryStorage:
    """InMemoryStorage tests"""
    
    def test_initialization(self):
        """Initialization"""
        storage = InMemoryStorage(retention_days=7)
        assert storage.retention_days == 7
        assert storage.get_count() == 0
    
    def test_save_alert(self):
        """Save alert"""
        storage = InMemoryStorage()
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.HEALTH_MONITOR,
            title="Test Alert",
            message="Test message",
        )
        
        result = storage.save(alert)
        assert result is True
        assert storage.get_count() == 1
    
    def test_get_recent(self):
        """Get recent alerts"""
        storage = InMemoryStorage()
        
        # Save 3 alerts
        for i in range(3):
            alert = AlertRecord(
                severity=AlertSeverity.P1,
                source=AlertSource.SYSTEM,
                title=f"Alert {i}",
                message=f"Message {i}",
            )
            storage.save(alert)
        
        recent = storage.get_recent(minutes=60)
        assert len(recent) == 3
    
    def test_get_recent_with_filters(self):
        """Get recent alerts with filters"""
        storage = InMemoryStorage()
        
        # Save alerts with different severity and source
        storage.save(AlertRecord(AlertSeverity.P0, AlertSource.RISK_GUARD, "Alert 1", "Msg 1"))
        storage.save(AlertRecord(AlertSeverity.P1, AlertSource.HEALTH_MONITOR, "Alert 2", "Msg 2"))
        storage.save(AlertRecord(AlertSeverity.P0, AlertSource.RATE_LIMITER, "Alert 3", "Msg 3"))
        
        # Filter by severity
        p0_alerts = storage.get_recent(minutes=60, severity=AlertSeverity.P0)
        assert len(p0_alerts) == 2
        
        # Filter by source
        health_alerts = storage.get_recent(minutes=60, source=AlertSource.HEALTH_MONITOR)
        assert len(health_alerts) == 1
        
        # Filter by both
        filtered = storage.get_recent(
            minutes=60,
            severity=AlertSeverity.P0,
            source=AlertSource.RISK_GUARD,
        )
        assert len(filtered) == 1
    
    def test_get_by_time_range(self):
        """Get alerts by time range"""
        storage = InMemoryStorage()
        
        now = datetime.now()
        
        # Alert 1: Now
        alert1 = AlertRecord(AlertSeverity.P1, AlertSource.SYSTEM, "Alert 1", "Msg 1")
        alert1.timestamp = now
        storage.save(alert1)
        
        # Alert 2: 1 hour ago
        alert2 = AlertRecord(AlertSeverity.P1, AlertSource.SYSTEM, "Alert 2", "Msg 2")
        alert2.timestamp = now - timedelta(hours=1)
        storage.save(alert2)
        
        # Alert 3: 2 hours ago
        alert3 = AlertRecord(AlertSeverity.P1, AlertSource.SYSTEM, "Alert 3", "Msg 3")
        alert3.timestamp = now - timedelta(hours=2)
        storage.save(alert3)
        
        # Query: Last 90 minutes
        start_time = now - timedelta(minutes=90)
        end_time = now
        
        alerts = storage.get_by_time_range(start_time, end_time)
        assert len(alerts) == 2  # Alert 1 and Alert 2
    
    def test_clear(self):
        """Clear all alerts"""
        storage = InMemoryStorage()
        
        storage.save(AlertRecord(AlertSeverity.P0, AlertSource.SYSTEM, "Alert", "Message"))
        assert storage.get_count() > 0
        
        result = storage.clear()
        assert result is True
        assert storage.get_count() == 0
    
    def test_cleanup_old_alerts(self):
        """Automatic cleanup of old alerts"""
        storage = InMemoryStorage(retention_days=1)
        
        now = datetime.now()
        
        # Fresh alert
        alert1 = AlertRecord(AlertSeverity.P1, AlertSource.SYSTEM, "Fresh", "Fresh alert")
        alert1.timestamp = now
        storage.save(alert1)
        
        # Old alert (2 days ago)
        alert2 = AlertRecord(AlertSeverity.P1, AlertSource.SYSTEM, "Old", "Old alert")
        alert2.timestamp = now - timedelta(days=2)
        storage.save(alert2)
        
        # After cleanup, only fresh alert should remain
        assert storage.get_count() == 1
        remaining = storage.get_recent(minutes=10000)
        assert len(remaining) == 1
        assert remaining[0].title == "Fresh"
