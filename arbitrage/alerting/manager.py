"""AlertManager: Central alert dispatching with rate limiting"""

import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
import threading

from .models import AlertSeverity, AlertSource, AlertRecord
from .rule_engine import RuleEngine, AlertDispatchPlan


class AlertManager:
    """
    Central alert manager with rate limiting
    
    Features:
    - Alert dispatching to multiple channels
    - Rate limiting per (severity, source) combination
    - In-memory alert history
    - Thread-safe operations
    """
    
    def __init__(
        self,
        rate_limit_window_seconds: int = 60,
        rate_limit_per_window: Dict[AlertSeverity, int] = None,
        rule_engine: Optional[RuleEngine] = None,
    ):
        """
        Initialize AlertManager
        
        Args:
            rate_limit_window_seconds: Rate limit window duration
            rate_limit_per_window: Max alerts per window for each severity
            rule_engine: Rule engine for channel routing (creates default if None)
        """
        self.rate_limit_window_seconds = rate_limit_window_seconds
        self.rate_limit_per_window = rate_limit_per_window or {
            AlertSeverity.P0: 10,  # Critical: max 10/min
            AlertSeverity.P1: 5,   # High: max 5/min
            AlertSeverity.P2: 3,   # Medium: max 3/min
            AlertSeverity.P3: 1,   # Low: max 1/min
        }
        
        # Rule engine for channel routing
        self.rule_engine = rule_engine or RuleEngine()
        
        # Alert history (in-memory)
        self._alert_history: List[AlertRecord] = []
        
        # Rate limiting tracking: (severity, source) -> [timestamps]
        self._rate_limit_tracker: Dict[tuple, List[float]] = defaultdict(list)
        
        # Notifiers and storage (to be injected)
        # Key: channel name ("telegram", "slack", "email")
        self._notifiers: Dict[str, Any] = {}
        self._storage: Optional[Any] = None
        
        # Thread safety
        self._lock = threading.RLock()
    
    def register_notifier(self, channel_name: str, notifier: Any):
        """Register a notifier for a specific channel
        
        Args:
            channel_name: Channel name ("telegram", "slack", "email")
            notifier: Notifier instance
        """
        with self._lock:
            self._notifiers[channel_name] = notifier
    
    def register_storage(self, storage: Any):
        """Register storage backend (PostgreSQL, etc.)"""
        with self._lock:
            self._storage = storage
    
    def send_alert(
        self,
        severity: AlertSeverity,
        source: AlertSource,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        rule_id: Optional[str] = None,
    ) -> bool:
        """
        Send alert with rate limiting and rule-based channel routing
        
        Args:
            severity: Alert severity
            source: Alert source
            title: Alert title
            message: Alert message
            metadata: Additional metadata
            rule_id: Optional rule ID for specific rule routing
        
        Returns:
            True if alert was sent, False if rate limited
        """
        with self._lock:
            # Check rate limit
            if not self._check_rate_limit(severity, source):
                return False
            
            # Create alert record
            alert = AlertRecord(
                severity=severity,
                source=source,
                title=title,
                message=message,
                metadata=metadata or {},
            )
            
            # Store in history
            self._alert_history.append(alert)
            
            # Update rate limit tracker
            key = (severity, source)
            self._rate_limit_tracker[key].append(time.time())
            
            # Get dispatch plan from rule engine
            dispatch_plan = self.rule_engine.evaluate_alert(alert, rule_id)
            
            # Send to notifiers based on dispatch plan
            if dispatch_plan.telegram and "telegram" in self._notifiers:
                try:
                    self._notifiers["telegram"].send(alert)
                except Exception as e:
                    print(f"Telegram notifier error: {e}")
            
            if dispatch_plan.slack and "slack" in self._notifiers:
                try:
                    self._notifiers["slack"].send(alert)
                except Exception as e:
                    print(f"Slack notifier error: {e}")
            
            if dispatch_plan.email and "email" in self._notifiers:
                try:
                    self._notifiers["email"].send(alert)
                except Exception as e:
                    print(f"Email notifier error: {e}")
            
            # Persist to storage if dispatch plan enables it
            if dispatch_plan.postgres and self._storage:
                try:
                    self._storage.save(alert)
                except Exception as e:
                    print(f"Storage error: {e}")
            
            return True
    
    def _check_rate_limit(self, severity: AlertSeverity, source: AlertSource) -> bool:
        """Check if alert is within rate limit"""
        key = (severity, source)
        now = time.time()
        window_start = now - self.rate_limit_window_seconds
        
        # Clean up old timestamps
        self._rate_limit_tracker[key] = [
            ts for ts in self._rate_limit_tracker[key]
            if ts >= window_start
        ]
        
        # Check limit
        max_alerts = self.rate_limit_per_window.get(severity, 1)
        current_count = len(self._rate_limit_tracker[key])
        
        return current_count < max_alerts
    
    def get_recent_alerts(
        self,
        minutes: int = 60,
        severity: Optional[AlertSeverity] = None,
        source: Optional[AlertSource] = None,
    ) -> List[AlertRecord]:
        """Get recent alerts with optional filters"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            
            alerts = [
                alert for alert in self._alert_history
                if alert.timestamp >= cutoff_time
            ]
            
            if severity:
                alerts = [a for a in alerts if a.severity == severity]
            
            if source:
                alerts = [a for a in alerts if a.source == source]
            
            return alerts
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
        with self._lock:
            total = len(self._alert_history)
            
            by_severity = defaultdict(int)
            by_source = defaultdict(int)
            
            for alert in self._alert_history:
                by_severity[alert.severity.value] += 1
                by_source[alert.source.value] += 1
            
            return {
                "total_alerts": total,
                "by_severity": dict(by_severity),
                "by_source": dict(by_source),
                "rate_limit_windows": {
                    f"{sev.value}": self.rate_limit_per_window[sev]
                    for sev in AlertSeverity
                },
            }
    
    def clear_history(self):
        """Clear alert history (for testing)"""
        with self._lock:
            self._alert_history.clear()
            self._rate_limit_tracker.clear()
