"""
D50: Monitoring & Metrics Layer

메트릭 수집 및 HTTP 엔드포인트 제공
"""

from arbitrage.monitoring.metrics_collector import MetricsCollector
from arbitrage.monitoring.cross_exchange_metrics import (
    CrossExchangeMetrics,
    InMemoryMetricsBackend,
    CrossExchangePnLSnapshot,
    CrossExecutionResult,
)

try:
    from arbitrage.monitoring.status_monitors import (
        LiveStatusMonitor,
        TuningStatusMonitor,
        LiveStatusSnapshot,
        TuningStatusSnapshot,
        StateManager
    )
    _has_status_monitors = True
except ImportError:
    _has_status_monitors = False
    LiveStatusMonitor = None
    TuningStatusMonitor = None
    LiveStatusSnapshot = None
    TuningStatusSnapshot = None
    StateManager = None

__all__ = [
    "MetricsCollector",
    "CrossExchangeMetrics",
    "InMemoryMetricsBackend",
    "CrossExchangePnLSnapshot",
    "CrossExecutionResult",
]

if _has_status_monitors:
    __all__.extend([
        "LiveStatusMonitor",
        "TuningStatusMonitor",
        "LiveStatusSnapshot",
        "TuningStatusSnapshot",
        "StateManager"
    ])
