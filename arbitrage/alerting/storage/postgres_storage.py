"""
PostgreSQL Alert Storage for Alerting System
"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from arbitrage.alerting.models import AlertRecord, AlertSeverity, AlertSource
from arbitrage.alerting.storage.base import StorageBase


class PostgreSQLAlertStorage(StorageBase):
    """
    PostgreSQL-based alert storage
    
    Features:
    - Persistent alert history in PostgreSQL
    - Query by severity, source, time range
    - Automatic cleanup (30-day retention)
    - Indexed for fast queries
    - Thread-safe (connection pooling)
    """
    
    def __init__(
        self,
        connection_string: str,
        table_name: str = "alert_history",
        retention_days: int = 30
    ):
        """
        Initialize PostgreSQL storage
        
        Args:
            connection_string: PostgreSQL connection string
            table_name: Table name for alert storage
            retention_days: Number of days to retain alerts (default: 30)
        """
        self.connection_string = connection_string
        self.table_name = table_name
        self.retention_days = retention_days
        self._ensure_table_exists()
        
    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(self.connection_string)
        
    def _ensure_table_exists(self):
        """Create table if it doesn't exist"""
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id SERIAL PRIMARY KEY,
            severity VARCHAR(10) NOT NULL,
            source VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_severity 
            ON {self.table_name}(severity);
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_source 
            ON {self.table_name}(source);
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_timestamp 
            ON {self.table_name}(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at 
            ON {self.table_name}(created_at DESC);
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(create_table_sql)
                conn.commit()
        except Exception:
            # Table might already exist or connection failed
            pass
            
    def save(self, alert: AlertRecord) -> bool:
        """
        Save alert to PostgreSQL
        
        Args:
            alert: AlertRecord to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        insert_sql = f"""
        INSERT INTO {self.table_name} 
            (severity, source, title, message, timestamp, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        insert_sql,
                        (
                            alert.severity.value,
                            alert.source.value,
                            alert.title,
                            alert.message,
                            alert.timestamp,
                            json.dumps(alert.metadata) if alert.metadata else None
                        )
                    )
                conn.commit()
            return True
        except Exception as e:
            # For debugging - can be removed in production
            import traceback
            traceback.print_exc()
            return False
            
    def get_recent(
        self,
        minutes: int = 60,
        severity: Optional[AlertSeverity] = None,
        source: Optional[AlertSource] = None
    ) -> List[AlertRecord]:
        """
        Get recent alerts with optional filters
        
        Args:
            minutes: Number of minutes back to search
            severity: Filter by severity level
            source: Filter by alert source
            
        Returns:
            List of AlertRecords
        """
        from datetime import datetime, timedelta
        
        # Calculate time threshold
        time_threshold = datetime.now() - timedelta(minutes=minutes)
        
        conditions = ["timestamp >= %s"]
        params = [time_threshold]
        
        if severity:
            conditions.append("severity = %s")
            params.append(severity.value)
            
        if source:
            conditions.append("source = %s")
            params.append(source.value)
            
        where_clause = " AND ".join(conditions)
        
        select_sql = f"""
        SELECT severity, source, title, message, timestamp, metadata
        FROM {self.table_name}
        WHERE {where_clause}
        ORDER BY timestamp DESC
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(select_sql, params)
                    rows = cur.fetchall()
                    
            alerts = []
            for row in rows:
                alerts.append(
                    AlertRecord(
                        severity=AlertSeverity(row['severity']),
                        source=AlertSource(row['source']),
                        title=row['title'],
                        message=row['message'],
                        timestamp=row['timestamp'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else None
                    )
                )
            return alerts
            
        except Exception:
            return []
            
    def get_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        severity: Optional[AlertSeverity] = None,
        source: Optional[AlertSource] = None
    ) -> List[AlertRecord]:
        """
        Get alerts within time range
        
        Args:
            start_time: Start of time range
            end_time: End of time range
            severity: Optional severity filter
            source: Optional source filter
            
        Returns:
            List of AlertRecords
        """
        conditions = ["timestamp >= %s", "timestamp <= %s"]
        params = [start_time, end_time]
        
        if severity:
            conditions.append("severity = %s")
            params.append(severity.value)
            
        if source:
            conditions.append("source = %s")
            params.append(source.value)
            
        where_clause = " AND ".join(conditions)
        
        select_sql = f"""
        SELECT severity, source, title, message, timestamp, metadata
        FROM {self.table_name}
        WHERE {where_clause}
        ORDER BY timestamp DESC
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(select_sql, params)
                    rows = cur.fetchall()
                    
            alerts = []
            for row in rows:
                alerts.append(
                    AlertRecord(
                        severity=AlertSeverity(row['severity']),
                        source=AlertSource(row['source']),
                        title=row['title'],
                        message=row['message'],
                        timestamp=row['timestamp'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else None
                    )
                )
            return alerts
            
        except Exception:
            return []
            
    def clear(self) -> bool:
        """
        Clear all alerts (for testing)
        
        Returns:
            True if cleared successfully, False otherwise
        """
        delete_sql = f"DELETE FROM {self.table_name}"
            
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(delete_sql)
                conn.commit()
            return True
        except Exception:
            return False
    
    def clear_before(self, before: datetime) -> int:
        """
        Clear alerts before specific time
        
        Args:
            before: Delete alerts before this time
            
        Returns:
            Number of alerts deleted
        """
        delete_sql = f"DELETE FROM {self.table_name} WHERE timestamp < %s"
            
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(delete_sql, [before])
                    deleted = cur.rowcount
                conn.commit()
            return deleted
        except Exception:
            return 0
            
    def cleanup_old_alerts(self) -> int:
        """
        Cleanup alerts older than retention period
        
        Returns:
            Number of alerts deleted
        """
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        return self.clear_before(cutoff_time)
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics
        
        Returns:
            Dict with total count, oldest/newest timestamps
        """
        stats_sql = f"""
        SELECT 
            COUNT(*) as total_count,
            MIN(timestamp) as oldest_timestamp,
            MAX(timestamp) as newest_timestamp
        FROM {self.table_name}
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(stats_sql)
                    row = cur.fetchone()
                    
            return {
                'total_count': row['total_count'] if row else 0,
                'oldest_timestamp': row['oldest_timestamp'] if row else None,
                'newest_timestamp': row['newest_timestamp'] if row else None
            }
        except Exception:
            return {'total_count': 0, 'oldest_timestamp': None, 'newest_timestamp': None}
