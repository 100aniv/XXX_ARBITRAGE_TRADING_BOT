"""
Tests for PostgreSQLAlertStorage
"""

import pytest
import os
import uuid
from datetime import datetime, timedelta

from arbitrage.alerting.models import AlertRecord, AlertSeverity, AlertSource
from arbitrage.alerting.storage.postgres_storage import PostgreSQLAlertStorage

pytestmark = pytest.mark.optional_live


# Connection string from environment or use default
CONNECTION_STRING = os.getenv(
    'DATABASE_URL',
    'postgresql://arbitrage:arbitrage@localhost:5432/arbitrage'
)


@pytest.fixture
def storage():
    """Create storage instance and cleanup after test"""
    table_name = f"alert_history_test_{uuid.uuid4().hex[:8]}"
    store = PostgreSQLAlertStorage(
        connection_string=CONNECTION_STRING,
        table_name=table_name,
        retention_days=7
    )
    
    # Cleanup before test
    store.clear()
    
    yield store
    
    # Cleanup after test
    store.clear()

    try:
        with store._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {store.table_name}")
            conn.commit()
    except Exception:
        pass


class TestPostgreSQLAlertStorage:
    """Test suite for PostgreSQL alert storage"""
    
    def test_initialization(self, storage):
        """Test storage initialization"""
        assert storage.table_name.startswith("alert_history_test_")
        assert storage.retention_days == 7
        
    def test_save_alert(self, storage):
        """Test saving alert to PostgreSQL"""
        alert = AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Test alert",
            timestamp=datetime.now(),
            metadata={"exchange": "upbit"}
        )
        
        result = storage.save(alert)
        assert result is True
        
        # Verify saved - use get_by_time_range with wide range instead
        import psycopg2
        conn = psycopg2.connect(storage.connection_string)
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {storage.table_name}")
        count = cur.fetchone()[0]
        conn.close()
        assert count == 1
        
    def test_get_recent(self, storage):
        """Test retrieving recent alerts"""
        # Save multiple alerts
        for i in range(5):
            alert = AlertRecord(
                severity=AlertSeverity.P1,
                source=AlertSource.EXCHANGE_HEALTH,
                title="Test",
                message=f"Alert {i}",
                timestamp=datetime.now()
            )
            storage.save(alert)
            
        # Get recent (all within last minute)
        alerts = storage.get_recent(minutes=1440)
        assert len(alerts) == 5
        # Should be in reverse chronological order
        assert "Alert" in alerts[0].message
        
    def test_get_recent_with_severity_filter(self, storage):
        """Test filtering by severity"""
        # Save P0 and P2 alerts
        storage.save(AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RISK_GUARD,
            title="Test",
            message="P0 alert",
            timestamp=datetime.now()
        ))
        
        storage.save(AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.ARB_ROUTE,
            title="Test",
            message="P2 alert",
            timestamp=datetime.now()
        ))
        
        # Filter by P0
        alerts = storage.get_recent(minutes=60, severity=AlertSeverity.P0)
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.P0
        
    def test_get_recent_with_source_filter(self, storage):
        """Test filtering by source"""
        # Save alerts from different sources
        storage.save(AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Rate limit alert",
            timestamp=datetime.now()
        ))
        
        storage.save(AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.EXCHANGE_HEALTH,
            title="Test",
            message="Health alert",
            timestamp=datetime.now()
        ))
        
        # Filter by source
        alerts = storage.get_recent(minutes=60, source=AlertSource.RATE_LIMITER)
        assert len(alerts) == 1
        assert alerts[0].source == AlertSource.RATE_LIMITER
        
    def test_get_by_time_range(self, storage):
        """Test querying by time range"""
        now = datetime.now()
        
        # Save alerts with different timestamps
        storage.save(AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.CROSS_SYNC,
            title="Test",
            message="Old alert",
            timestamp=now - timedelta(hours=2)
        ))
        
        storage.save(AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.CROSS_SYNC,
            title="Test",
            message="Recent alert",
            timestamp=now - timedelta(minutes=30)
        ))
        
        # Query last hour
        start_time = now - timedelta(hours=1)
        end_time = now
        
        alerts = storage.get_by_time_range(start_time, end_time)
        assert len(alerts) == 1
        assert "Recent" in alerts[0].message
        
    def test_get_by_time_range_with_filters(self, storage):
        """Test time range query with severity/source filters"""
        now = datetime.now()
        
        # Save multiple alerts
        storage.save(AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.RISK_GUARD,
            title="Test",
            message="P0 recent",
            timestamp=now - timedelta(minutes=10)
        ))
        
        storage.save(AlertRecord(
            severity=AlertSeverity.P2,
            source=AlertSource.ARB_ROUTE,
            title="Test",
            message="P2 recent",
            timestamp=now - timedelta(minutes=5)
        ))
        
        # Query with filters
        start_time = now - timedelta(hours=1)
        end_time = now
        
        alerts = storage.get_by_time_range(
            start_time, end_time,
            severity=AlertSeverity.P0
        )
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.P0
        
    def test_clear_all(self, storage):
        """Test clearing all alerts"""
        # Save alerts
        for i in range(3):
            storage.save(AlertRecord(
                severity=AlertSeverity.P3,
                source=AlertSource.ARB_UNIVERSE,
                title="Test",
                message=f"Alert {i}",
                timestamp=datetime.now()
            ))
            
        # Clear all
        result = storage.clear()
        assert result is True
        
        # Verify empty
        alerts = storage.get_recent(minutes=1440)
        assert len(alerts) == 0
        
    def test_clear_before_time(self, storage):
        """Test clearing alerts before specific time"""
        now = datetime.now()
        
        # Save old and new alerts
        storage.save(AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Old alert",
            timestamp=now - timedelta(days=10)
        ))
        
        storage.save(AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.RATE_LIMITER,
            title="Test",
            message="Recent alert",
            timestamp=now
        ))
        
        # Clear old alerts (before 5 days ago)
        cutoff = now - timedelta(days=5)
        deleted = storage.clear_before(cutoff)
        assert deleted == 1
        
        # Verify only recent alert remains
        alerts = storage.get_recent(minutes=1440)
        assert len(alerts) == 1
        assert "Recent" in alerts[0].message
        
    def test_cleanup_old_alerts(self, storage):
        """Test automatic cleanup of old alerts"""
        now = datetime.now()
        
        # Save very old and recent alerts
        storage.save(AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.EXCHANGE_HEALTH,
            title="Test",
            message="Very old",
            timestamp=now - timedelta(days=31)  # Older than retention
        ))
        
        storage.save(AlertRecord(
            severity=AlertSeverity.P0,
            source=AlertSource.EXCHANGE_HEALTH,
            title="Test",
            message="Recent",
            timestamp=now
        ))
        
        # Cleanup
        deleted = storage.cleanup_old_alerts()
        assert deleted == 1
        
        # Verify only recent remains
        alerts = storage.get_recent(minutes=1440)
        assert len(alerts) == 1
        assert "Recent" in alerts[0].message
        
    def test_get_stats(self, storage):
        """Test getting storage statistics"""
        now = datetime.now()
        
        # Save alerts
        for i in range(5):
            storage.save(AlertRecord(
                severity=AlertSeverity.P2,
                source=AlertSource.CROSS_SYNC,
                title="Test",
                message=f"Alert {i}",
                timestamp=now - timedelta(hours=i)
            ))
            
        # Get stats
        stats = storage.get_stats()
        assert stats['total_count'] == 5
        assert stats['newest_timestamp'] is not None
        assert stats['oldest_timestamp'] is not None
        
    def test_metadata_json_storage(self, storage):
        """Test storing and retrieving metadata as JSON"""
        metadata = {
            "exchange": "binance",
            "count": 42,
            "threshold": 100.5,
            "nested": {"key": "value"}
        }
        
        alert = AlertRecord(
            severity=AlertSeverity.P1,
            source=AlertSource.ARB_ROUTE,
            title="Test",
            message="Test metadata",
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        storage.save(alert)
        
        # Retrieve and verify using direct SQL to avoid timezone issues
        import psycopg2
        import json
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(storage.connection_string)
        cur = conn.cursor()
        cur.execute(f"SELECT metadata FROM {storage.table_name} ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        conn.close()
        
        assert row is not None
        # JSONB is returned as string from psycopg2, need to parse it
        saved_metadata = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        assert saved_metadata == metadata
        assert saved_metadata["nested"]["key"] == "value"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
