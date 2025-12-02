"""
D80-7: Alert Aggregator Tests
"""

import pytest
import time
from datetime import datetime
from arbitrage.alerting import (
    AlertAggregator,
    AggregatedAlert,
    AlertRecord,
    AlertSeverity,
    AlertSource,
)


class TestAlertAggregator:
    """Test AlertAggregator"""
    
    def test_init(self):
        """Test initialization"""
        aggregator = AlertAggregator(window_seconds=30)
        
        assert aggregator.window_seconds == 30
        assert aggregator.auto_flush is True
        
        stats = aggregator.get_stats()
        assert stats["window_seconds"] == 30
        assert stats["active_windows"] == 0
    
    def test_add_first_alert(self):
        """Test adding first alert"""
        aggregator = AlertAggregator(window_seconds=30)
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="FX Source Down",
            message="binance down",
            metadata={"aggregation_key": "fx_source_down"},
        )
        
        result = aggregator.add_alert(alert)
        
        # First alert should not trigger flush
        assert result is None
        
        stats = aggregator.get_stats()
        assert stats["active_windows"] == 1
        assert stats["alerts_added"] == 1
    
    def test_aggregation_within_window(self):
        """Test aggregation within window"""
        aggregator = AlertAggregator(window_seconds=2)
        
        # Add multiple alerts within window
        for i in range(3):
            alert = AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title=f"FX Source Down {i}",
                message=f"Error {i}",
                metadata={"aggregation_key": "fx_source_down"},
            )
            result = aggregator.add_alert(alert)
            assert result is None  # No flush yet
        
        pending = aggregator.get_pending_alerts()
        assert pending["fx_source_down"] == 3
    
    def test_window_expiration(self):
        """Test window expiration triggers flush"""
        aggregator = AlertAggregator(window_seconds=1)
        
        # Add first alert
        alert1 = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="Alert 1",
            message="Message 1",
            metadata={"aggregation_key": "test_key"},
        )
        aggregator.add_alert(alert1)
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Add second alert (triggers flush)
        alert2 = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="Alert 2",
            message="Message 2",
            metadata={"aggregation_key": "test_key"},
        )
        result = aggregator.add_alert(alert2)
        
        # Should return aggregated alert
        assert result is not None
        assert isinstance(result, AggregatedAlert)
        assert result.aggregation_key == "test_key"
        assert result.alert_count == 1  # Only first alert in aggregated
    
    def test_manual_flush(self):
        """Test manual flush"""
        aggregator = AlertAggregator(window_seconds=30)
        
        # Add alerts
        for i in range(3):
            alert = AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title=f"Alert {i}",
                message=f"Message {i}",
                metadata={"aggregation_key": "test_key"},
            )
            aggregator.add_alert(alert)
        
        # Manual flush
        results = aggregator.flush("test_key")
        
        assert len(results) == 1
        aggregated = results[0]
        assert aggregated.alert_count == 3
        assert len(aggregated.alerts) == 3
    
    def test_flush_all(self):
        """Test flush all windows"""
        aggregator = AlertAggregator(window_seconds=30)
        
        # Add alerts to different windows
        for key in ["key1", "key2", "key3"]:
            alert = AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title=f"Alert {key}",
                message=f"Message {key}",
                metadata={"aggregation_key": key},
            )
            aggregator.add_alert(alert)
        
        # Flush all
        results = aggregator.flush()
        
        assert len(results) == 3
        assert {r.aggregation_key for r in results} == {"key1", "key2", "key3"}
    
    def test_multiple_aggregation_keys(self):
        """Test multiple independent aggregation keys"""
        aggregator = AlertAggregator(window_seconds=30)
        
        # FX alerts
        for i in range(2):
            alert = AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title=f"FX Alert {i}",
                message=f"FX Message {i}",
                metadata={"aggregation_key": "fx_source_down"},
            )
            aggregator.add_alert(alert)
        
        # Executor alerts
        for i in range(3):
            alert = AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.EXECUTOR,
                title=f"Executor Alert {i}",
                message=f"Executor Message {i}",
                metadata={"aggregation_key": "executor_error"},
            )
            aggregator.add_alert(alert)
        
        pending = aggregator.get_pending_alerts()
        assert pending["fx_source_down"] == 2
        assert pending["executor_error"] == 3


class TestAggregatedAlert:
    """Test AggregatedAlert"""
    
    def test_aggregated_alert_creation(self):
        """Test aggregated alert creation"""
        alerts = [
            AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title="Alert 1",
                message="Message 1",
            ),
            AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title="Alert 2",
                message="Message 2",
            ),
        ]
        
        aggregated = AggregatedAlert(
            aggregation_key="test_key",
            alert_count=2,
            alerts=alerts,
            first_timestamp=datetime.now(),
            last_timestamp=datetime.now(),
            summary="Test summary",
        )
        
        assert aggregated.aggregation_key == "test_key"
        assert aggregated.alert_count == 2
        assert len(aggregated.alerts) == 2
    
    def test_aggregated_alert_to_dict(self):
        """Test aggregated alert serialization"""
        alerts = [
            AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title="Alert 1",
                message="Message 1",
            ),
        ]
        
        now = datetime.now()
        aggregated = AggregatedAlert(
            aggregation_key="test_key",
            alert_count=1,
            alerts=alerts,
            first_timestamp=now,
            last_timestamp=now,
            summary="Test summary",
        )
        
        data = aggregated.to_dict()
        
        assert data["aggregation_key"] == "test_key"
        assert data["alert_count"] == 1
        assert data["summary"] == "Test summary"
        assert "alerts" in data
        assert len(data["alerts"]) == 1


class TestSummaryGeneration:
    """Test aggregated alert summary generation"""
    
    def test_summary_single_alert(self):
        """Test summary for single alert"""
        aggregator = AlertAggregator(window_seconds=30)
        
        alert = AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.FX_LAYER,
            title="Single Alert",
            message="Single Message",
            metadata={"aggregation_key": "test_key"},
        )
        aggregator.add_alert(alert)
        
        results = aggregator.flush("test_key")
        aggregated = results[0]
        
        assert "Single Alert" in aggregated.summary
        assert "Single Message" in aggregated.summary
    
    def test_summary_multiple_alerts(self):
        """Test summary for multiple alerts"""
        aggregator = AlertAggregator(window_seconds=30)
        
        # Add multiple alerts
        for i in range(5):
            alert = AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title=f"Alert {i}",
                message=f"Message {i}",
                metadata={"aggregation_key": "test_key"},
            )
            aggregator.add_alert(alert)
        
        results = aggregator.flush("test_key")
        aggregated = results[0]
        
        # Summary should contain key information
        assert "Aggregated Alert Report" in aggregated.summary
        assert "Total alerts: 5" in aggregated.summary
        assert "test_key" in aggregated.summary
    
    def test_summary_severity_breakdown(self):
        """Test summary severity breakdown"""
        aggregator = AlertAggregator(window_seconds=30)
        
        # Add alerts with different severities
        for severity in [AlertSeverity.P0, AlertSeverity.P1, AlertSeverity.P2]:
            alert = AlertRecord(
                severity=severity,
                source=AlertSource.FX_LAYER,
                title=f"{severity.value} Alert",
                message="Message",
                metadata={"aggregation_key": "test_key"},
            )
            aggregator.add_alert(alert)
        
        results = aggregator.flush("test_key")
        aggregated = results[0]
        
        # Summary should show severity breakdown
        assert "P0" in aggregated.summary
        assert "P1" in aggregated.summary
        assert "P2" in aggregated.summary


class TestAggregatorStats:
    """Test aggregator statistics"""
    
    def test_initial_stats(self):
        """Test initial statistics"""
        aggregator = AlertAggregator(window_seconds=30)
        
        stats = aggregator.get_stats()
        
        assert stats["window_seconds"] == 30
        assert stats["active_windows"] == 0
        assert stats["alerts_added"] == 0
        assert stats["windows_flushed"] == 0
        assert stats["alerts_aggregated"] == 0
    
    def test_stats_updates(self):
        """Test statistics updates"""
        aggregator = AlertAggregator(window_seconds=30)
        
        # Add alerts
        for i in range(5):
            alert = AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.FX_LAYER,
                title=f"Alert {i}",
                message=f"Message {i}",
                metadata={"aggregation_key": "test_key"},
            )
            aggregator.add_alert(alert)
        
        # Flush
        aggregator.flush("test_key")
        
        stats = aggregator.get_stats()
        
        assert stats["alerts_added"] == 5
        assert stats["windows_flushed"] == 1
        assert stats["alerts_aggregated"] == 5
        assert stats["active_windows"] == 0
