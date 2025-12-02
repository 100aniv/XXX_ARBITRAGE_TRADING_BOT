"""
D80-11: Alert Metrics Exporter (Prometheus)

Exports alert delivery metrics for monitoring and observability.
"""

import time
import logging
from typing import Optional, Dict, Any
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class AlertMetrics:
    """
    Alert delivery metrics collector
    
    Metrics:
    - alert_sent_total: Counter by (rule_id, notifier)
    - alert_failed_total: Counter by (rule_id, notifier, reason)
    - alert_fallback_total: Counter by (from_notifier, to_notifier)
    - alert_retry_total: Counter by rule_id
    - alert_dlq_total: Counter by rule_id
    - alert_delivery_latency_seconds: Histogram by notifier
    - notifier_available: Gauge by (notifier, status)
    
    Compatible with Prometheus, but also works standalone.
    """
    
    def __init__(self, enable_prometheus: bool = False):
        """
        Initialize metrics collector
        
        Args:
            enable_prometheus: If True, use prometheus_client library
        """
        self.enable_prometheus = enable_prometheus
        
        # In-memory metrics (always available)
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, list] = defaultdict(list)
        
        # Prometheus metrics (if enabled)
        self._prom_counters: Dict[str, Any] = {}
        self._prom_gauges: Dict[str, Any] = {}
        self._prom_histograms: Dict[str, Any] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Initialize Prometheus metrics
        if enable_prometheus:
            self._init_prometheus_metrics()
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics using prometheus_client"""
        try:
            from prometheus_client import Counter, Gauge, Histogram
            
            # alert_sent_total
            self._prom_counters["sent"] = Counter(
                "alert_sent_total",
                "Total alerts sent",
                labelnames=["rule_id", "notifier"],
            )
            
            # alert_failed_total
            self._prom_counters["failed"] = Counter(
                "alert_failed_total",
                "Total alerts failed",
                labelnames=["rule_id", "notifier", "reason"],
            )
            
            # alert_fallback_total
            self._prom_counters["fallback"] = Counter(
                "alert_fallback_total",
                "Total alerts sent via fallback",
                labelnames=["from_notifier", "to_notifier"],
            )
            
            # alert_retry_total
            self._prom_counters["retry"] = Counter(
                "alert_retry_total",
                "Total alerts retried",
                labelnames=["rule_id"],
            )
            
            # alert_dlq_total
            self._prom_counters["dlq"] = Counter(
                "alert_dlq_total",
                "Total alerts moved to DLQ",
                labelnames=["rule_id", "reason"],
            )
            
            # alert_delivery_latency_seconds
            self._prom_histograms["delivery_latency"] = Histogram(
                "alert_delivery_latency_seconds",
                "Alert delivery latency in seconds",
                labelnames=["notifier"],
                buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 3.0, 5.0, 10.0),
            )
            
            # notifier_available
            self._prom_gauges["notifier_available"] = Gauge(
                "notifier_available",
                "Notifier availability status (1=available, 0.5=degraded, 0=unavailable)",
                labelnames=["notifier", "status"],
            )
            
            logger.info("Prometheus metrics initialized")
        
        except ImportError:
            logger.warning("prometheus_client not installed, Prometheus metrics disabled")
            self.enable_prometheus = False
    
    def record_sent(self, rule_id: str, notifier: str):
        """Record alert sent"""
        with self._lock:
            key = f"sent:{rule_id}:{notifier}"
            self._counters[key] += 1
            
            if self.enable_prometheus:
                self._prom_counters["sent"].labels(rule_id=rule_id, notifier=notifier).inc()
    
    def record_failed(self, rule_id: str, notifier: str, reason: str):
        """Record alert failed"""
        with self._lock:
            key = f"failed:{rule_id}:{notifier}:{reason}"
            self._counters[key] += 1
            
            if self.enable_prometheus:
                self._prom_counters["failed"].labels(
                    rule_id=rule_id, notifier=notifier, reason=reason
                ).inc()
    
    def record_fallback(self, from_notifier: str, to_notifier: str):
        """Record fallback to another notifier"""
        with self._lock:
            key = f"fallback:{from_notifier}:{to_notifier}"
            self._counters[key] += 1
            
            if self.enable_prometheus:
                self._prom_counters["fallback"].labels(
                    from_notifier=from_notifier, to_notifier=to_notifier
                ).inc()
    
    def record_retry(self, rule_id: str):
        """Record alert retry"""
        with self._lock:
            key = f"retry:{rule_id}"
            self._counters[key] += 1
            
            if self.enable_prometheus:
                self._prom_counters["retry"].labels(rule_id=rule_id).inc()
    
    def record_dlq(self, rule_id: str, reason: str):
        """Record alert moved to DLQ"""
        with self._lock:
            key = f"dlq:{rule_id}:{reason}"
            self._counters[key] += 1
            
            if self.enable_prometheus:
                self._prom_counters["dlq"].labels(rule_id=rule_id, reason=reason).inc()
    
    def record_delivery_latency(self, notifier: str, latency_seconds: float):
        """Record alert delivery latency"""
        with self._lock:
            key = f"latency:{notifier}"
            self._histograms[key].append(latency_seconds)
            
            if self.enable_prometheus:
                self._prom_histograms["delivery_latency"].labels(notifier=notifier).observe(
                    latency_seconds
                )
    
    def set_notifier_status(self, notifier: str, status: str, value: float):
        """
        Set notifier availability status
        
        Args:
            notifier: Notifier name
            status: Status string ("available", "degraded", "unavailable")
            value: Numeric value (1.0=available, 0.5=degraded, 0.0=unavailable)
        """
        with self._lock:
            key = f"notifier:{notifier}:{status}"
            self._gauges[key] = value
            
            if self.enable_prometheus:
                self._prom_gauges["notifier_available"].labels(
                    notifier=notifier, status=status
                ).set(value)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get all metrics as dict (for non-Prometheus monitoring)"""
        with self._lock:
            stats = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {},
            }
            
            # Calculate histogram stats
            for key, values in self._histograms.items():
                if values:
                    stats["histograms"][key] = {
                        "count": len(values),
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                        "p50": self._percentile(values, 0.5),
                        "p95": self._percentile(values, 0.95),
                        "p99": self._percentile(values, 0.99),
                    }
                else:
                    stats["histograms"][key] = {"count": 0}
            
            return stats
    
    def _percentile(self, values: list, p: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def clear(self):
        """Clear all metrics (for testing)"""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# Global metrics instance
_global_metrics: Optional[AlertMetrics] = None


def get_global_alert_metrics() -> AlertMetrics:
    """Get global alert metrics instance"""
    global _global_metrics
    if _global_metrics is None:
        # Try to enable Prometheus if available
        try:
            import prometheus_client
            _global_metrics = AlertMetrics(enable_prometheus=True)
        except ImportError:
            _global_metrics = AlertMetrics(enable_prometheus=False)
    return _global_metrics


def reset_global_alert_metrics():
    """Reset global metrics (for testing)"""
    global _global_metrics
    _global_metrics = None
