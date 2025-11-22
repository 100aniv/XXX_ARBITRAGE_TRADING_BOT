"""In-memory alert storage"""

from typing import List, Optional
from datetime import datetime, timedelta
import threading

from ..models import AlertRecord, AlertSeverity, AlertSource
from .base import StorageBase


class InMemoryStorage(StorageBase):
    """
    In-memory alert storage
    
    Features:
    - Thread-safe operations
    - Time-based retention (default: 7 days)
    - Automatic cleanup of old alerts
    """
    
    def __init__(self, retention_days: int = 7):
        """
        Initialize in-memory storage
        
        Args:
            retention_days: Number of days to retain alerts
        """
        self.retention_days = retention_days
        self._alerts: List[AlertRecord] = []
        self._lock = threading.RLock()
    
    def save(self, alert: AlertRecord) -> bool:
        """Save alert record"""
        with self._lock:
            self._alerts.append(alert)
            self._cleanup_old_alerts()
            return True
    
    def get_recent(
        self,
        minutes: int = 60,
        severity: Optional[AlertSeverity] = None,
        source: Optional[AlertSource] = None,
    ) -> List[AlertRecord]:
        """Get recent alerts with optional filters"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            
            alerts = [
                alert for alert in self._alerts
                if alert.timestamp >= cutoff_time
            ]
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            if source:
                alerts = [a for a in alerts if a.source == source]
            
            return alerts
    
    def get_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> List[AlertRecord]:
        """Get alerts within time range"""
        with self._lock:
            return [
                alert for alert in self._alerts
                if start_time <= alert.timestamp <= end_time
            ]
    
    def clear(self) -> bool:
        """Clear all alerts"""
        with self._lock:
            self._alerts.clear()
            return True
    
    def _cleanup_old_alerts(self):
        """Remove alerts older than retention period"""
        cutoff_time = datetime.now() - timedelta(days=self.retention_days)
        self._alerts = [
            alert for alert in self._alerts
            if alert.timestamp >= cutoff_time
        ]
    
    def get_count(self) -> int:
        """Get total alert count"""
        with self._lock:
            return len(self._alerts)
