"""
D80-7: Alert Aggregator

Groups related alerts within a time window (default: 30 seconds).
"""

import time
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field

from .models import AlertRecord

logger = logging.getLogger(__name__)


@dataclass
class AggregatedAlert:
    """
    Aggregated alert containing multiple related alerts
    
    Attributes:
        aggregation_key: Key used for grouping
        alert_count: Number of alerts in this group
        alerts: List of individual alerts
        first_timestamp: Timestamp of first alert
        last_timestamp: Timestamp of last alert
        summary: Human-readable summary
    """
    aggregation_key: str
    alert_count: int
    alerts: List[AlertRecord]
    first_timestamp: datetime
    last_timestamp: datetime
    summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "aggregation_key": self.aggregation_key,
            "alert_count": self.alert_count,
            "first_timestamp": self.first_timestamp.isoformat(),
            "last_timestamp": self.last_timestamp.isoformat(),
            "summary": self.summary,
            "alerts": [alert.to_dict() for alert in self.alerts],
        }


class AlertAggregator:
    """
    Alert aggregator with time-based windowing
    
    Features:
    - Groups alerts by aggregation_key within a time window
    - Auto-flush on window expiration
    - Summary generation for aggregated alerts
    """
    
    def __init__(
        self,
        window_seconds: int = 30,
        auto_flush: bool = True,
    ):
        """
        Initialize aggregator
        
        Args:
            window_seconds: Aggregation window duration
            auto_flush: Auto-flush expired windows
        """
        self.window_seconds = window_seconds
        self.auto_flush = auto_flush
        
        # Alert buffers: aggregation_key -> [alerts]
        self._buffers: Dict[str, List[AlertRecord]] = defaultdict(list)
        
        # Window timestamps: aggregation_key -> first_timestamp
        self._window_start: Dict[str, float] = {}
        
        # Statistics
        self._stats = {
            "alerts_added": 0,
            "windows_flushed": 0,
            "alerts_aggregated": 0,
        }
    
    def add_alert(
        self,
        alert: AlertRecord,
        aggregation_key: Optional[str] = None,
    ) -> Optional[AggregatedAlert]:
        """
        Add alert to aggregator
        
        Args:
            alert: Alert record
            aggregation_key: Custom aggregation key (default: use alert metadata)
        
        Returns:
            AggregatedAlert if window expired and flushed, None otherwise
        """
        # Determine aggregation key
        if aggregation_key is None:
            aggregation_key = alert.metadata.get("aggregation_key", "default")
        
        current_time = time.time()
        
        # Check if window exists
        if aggregation_key not in self._window_start:
            # New window
            self._window_start[aggregation_key] = current_time
            self._buffers[aggregation_key] = [alert]
            self._stats["alerts_added"] += 1
            logger.debug(f"[AlertAggregator] New window started: {aggregation_key}")
            return None
        
        # Check if window expired
        window_start = self._window_start[aggregation_key]
        elapsed = current_time - window_start
        
        if elapsed >= self.window_seconds:
            # Window expired, flush before adding new alert
            aggregated = self._flush_window(aggregation_key)
            
            # Start new window with current alert
            self._window_start[aggregation_key] = current_time
            self._buffers[aggregation_key] = [alert]
            self._stats["alerts_added"] += 1
            
            return aggregated
        else:
            # Add to existing window
            self._buffers[aggregation_key].append(alert)
            self._stats["alerts_added"] += 1
            logger.debug(
                f"[AlertAggregator] Alert added to window: {aggregation_key} "
                f"(count={len(self._buffers[aggregation_key])}, elapsed={elapsed:.1f}s)"
            )
            return None
    
    def flush(
        self,
        aggregation_key: Optional[str] = None,
    ) -> List[AggregatedAlert]:
        """
        Manually flush aggregation windows
        
        Args:
            aggregation_key: Specific key to flush, or None to flush all
        
        Returns:
            List of aggregated alerts
        """
        if aggregation_key:
            # Flush specific window
            aggregated = self._flush_window(aggregation_key)
            return [aggregated] if aggregated else []
        else:
            # Flush all windows
            results = []
            for key in list(self._buffers.keys()):
                aggregated = self._flush_window(key)
                if aggregated:
                    results.append(aggregated)
            return results
    
    def flush_expired(self) -> List[AggregatedAlert]:
        """
        Flush all expired windows
        
        Returns:
            List of aggregated alerts from expired windows
        """
        current_time = time.time()
        results = []
        
        for aggregation_key in list(self._buffers.keys()):
            window_start = self._window_start.get(aggregation_key)
            if window_start is None:
                continue
            
            elapsed = current_time - window_start
            if elapsed >= self.window_seconds:
                aggregated = self._flush_window(aggregation_key)
                if aggregated:
                    results.append(aggregated)
        
        return results
    
    def _flush_window(self, aggregation_key: str) -> Optional[AggregatedAlert]:
        """
        Flush a specific aggregation window
        
        Args:
            aggregation_key: Aggregation key
        
        Returns:
            AggregatedAlert or None if no alerts in buffer
        """
        alerts = self._buffers.get(aggregation_key, [])
        if not alerts:
            return None
        
        # Create aggregated alert
        alert_count = len(alerts)
        first_timestamp = alerts[0].timestamp
        last_timestamp = alerts[-1].timestamp
        
        # Generate summary
        summary = self._generate_summary(aggregation_key, alerts)
        
        aggregated = AggregatedAlert(
            aggregation_key=aggregation_key,
            alert_count=alert_count,
            alerts=alerts,
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
            summary=summary,
        )
        
        # Clear buffer
        del self._buffers[aggregation_key]
        del self._window_start[aggregation_key]
        
        # Update stats
        self._stats["windows_flushed"] += 1
        self._stats["alerts_aggregated"] += alert_count
        
        logger.info(
            f"[AlertAggregator] Window flushed: {aggregation_key} "
            f"(count={alert_count}, duration={(last_timestamp - first_timestamp).total_seconds():.1f}s)"
        )
        
        return aggregated
    
    def _generate_summary(
        self,
        aggregation_key: str,
        alerts: List[AlertRecord],
    ) -> str:
        """
        Generate human-readable summary for aggregated alerts
        
        Args:
            aggregation_key: Aggregation key
            alerts: List of alerts
        
        Returns:
            Summary string
        """
        alert_count = len(alerts)
        
        if alert_count == 1:
            # Single alert, no aggregation needed
            alert = alerts[0]
            return f"{alert.title}\n{alert.message}"
        
        # Multiple alerts, create summary
        first = alerts[0]
        last = alerts[-1]
        duration = (last.timestamp - first.timestamp).total_seconds()
        
        # Group by severity
        severity_counts = defaultdict(int)
        for alert in alerts:
            severity_counts[alert.severity.value] += 1
        
        severity_summary = ", ".join(
            f"{severity}: {count}" for severity, count in sorted(severity_counts.items())
        )
        
        summary_lines = [
            f"📊 Aggregated Alert Report ({aggregation_key})",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Total alerts: {alert_count}",
            f"Duration: {duration:.1f}s",
            f"Severity breakdown: {severity_summary}",
            f"",
            f"First alert: {first.title}",
            f"Last alert: {last.title}",
            f"",
            f"📝 Details:",
        ]
        
        # Add individual alert summaries (limit to 10)
        max_details = 10
        for i, alert in enumerate(alerts[:max_details], 1):
            timestamp_str = alert.timestamp.strftime("%H:%M:%S")
            summary_lines.append(
                f"{i}. [{timestamp_str}] {alert.severity.value} - {alert.title}"
            )
        
        if alert_count > max_details:
            summary_lines.append(f"... and {alert_count - max_details} more alerts")
        
        return "\n".join(summary_lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get aggregator statistics
        
        Returns:
            Statistics dictionary
        """
        return {
            "window_seconds": self.window_seconds,
            "active_windows": len(self._buffers),
            "alerts_added": self._stats["alerts_added"],
            "windows_flushed": self._stats["windows_flushed"],
            "alerts_aggregated": self._stats["alerts_aggregated"],
        }
    
    def get_pending_alerts(self) -> Dict[str, int]:
        """
        Get count of pending alerts per aggregation key
        
        Returns:
            Dictionary of aggregation_key -> alert_count
        """
        return {
            key: len(alerts)
            for key, alerts in self._buffers.items()
        }
