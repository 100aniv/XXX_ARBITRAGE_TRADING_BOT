# -*- coding: utf-8 -*-
"""
D77-1: Prometheus Exporter for TopN Arbitrage PAPER Baseline

Prometheus 메트릭 수집 및 노출 모듈.
Core KPI 10종을 Prometheus 형식으로 변환하여 /metrics 엔드포인트로 제공.

Features:
- 11 Prometheus metrics (Core KPI 10종 + active positions)
- Label-based filtering (env, universe, strategy)
- Thread-safe operations
- HTTP server for /metrics endpoint
- Test-friendly (registry injection)

Usage:
    from arbitrage.monitoring.metrics import (
        init_metrics,
        start_metrics_server,
        record_pnl,
        record_trade,
        record_round_trip,
    )
    
    # Initialize
    init_metrics(env="paper", universe="top20", strategy="topn_arb")
    start_metrics_server(port=9100)
    
    # Record events
    record_trade("entry")
    record_round_trip()
    record_pnl(100.0)
"""

import logging
import threading
from typing import Dict, Optional

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Summary,
    generate_latest,
    start_http_server,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Global State
# ============================================================================

# Prometheus Registry (테스트 시 교체 가능)
_registry: Optional[CollectorRegistry] = None

# 메트릭 객체 캐시
_metrics: Dict[str, any] = {}

# HTTP 서버 상태
_http_server_started: bool = False
_http_server_lock = threading.Lock()

# 공통 Label 값
_common_labels: Dict[str, str] = {}

# ============================================================================
# Metric Definitions
# ============================================================================

def _create_metrics(registry: CollectorRegistry) -> Dict[str, any]:
    """
    Prometheus 메트릭 객체 생성.
    
    Args:
        registry: Prometheus CollectorRegistry
        
    Returns:
        메트릭 객체 딕셔너리
    """
    metrics = {}
    
    # 1. PnL Total (Gauge)
    metrics["pnl_total"] = Gauge(
        "arb_topn_pnl_total",
        "Total PnL in USD",
        ["env", "universe", "strategy"],
        registry=registry,
    )
    
    # 2. Win Rate (Gauge)
    metrics["win_rate"] = Gauge(
        "arb_topn_win_rate",
        "Win rate percentage (0-100)",
        ["env", "universe", "strategy"],
        registry=registry,
    )
    
    # 3. Round Trips Total (Counter)
    metrics["round_trips_total"] = Counter(
        "arb_topn_round_trips_total",
        "Total number of completed round trips",
        ["env", "universe", "strategy"],
        registry=registry,
    )
    
    # 4. Trades Total (Counter with trade_type label)
    metrics["trades_total"] = Counter(
        "arb_topn_trades_total",
        "Total number of trades",
        ["env", "universe", "strategy", "trade_type"],
        registry=registry,
    )
    
    # 5. Loop Latency (Summary with quantiles)
    metrics["loop_latency_seconds"] = Summary(
        "arb_topn_loop_latency_seconds",
        "Loop latency in seconds",
        ["env", "universe", "strategy"],
        registry=registry,
    )
    
    # 6. Memory Usage (Gauge)
    metrics["memory_usage_bytes"] = Gauge(
        "arb_topn_memory_usage_bytes",
        "Memory usage in bytes",
        ["env", "universe", "strategy"],
        registry=registry,
    )
    
    # 7. CPU Usage (Gauge)
    metrics["cpu_usage_percent"] = Gauge(
        "arb_topn_cpu_usage_percent",
        "CPU usage percentage",
        ["env", "universe", "strategy"],
        registry=registry,
    )
    
    # 8. Guard Triggers Total (Counter with guard_type label)
    metrics["guard_triggers_total"] = Counter(
        "arb_topn_guard_triggers_total",
        "Total number of guard triggers",
        ["env", "universe", "strategy", "guard_type"],
        registry=registry,
    )
    
    # 9. Alerts Total (Counter with severity and source labels)
    metrics["alerts_total"] = Counter(
        "arb_topn_alerts_total",
        "Total number of alerts",
        ["env", "universe", "strategy", "severity", "source"],
        registry=registry,
    )
    
    # 10. Exit Reasons Total (Counter with reason label)
    metrics["exit_reasons_total"] = Counter(
        "arb_topn_exit_reasons_total",
        "Total number of exits by reason",
        ["env", "universe", "strategy", "reason"],
        registry=registry,
    )
    
    # 11. Active Positions (Gauge)
    metrics["active_positions"] = Gauge(
        "arb_topn_active_positions",
        "Current number of active positions",
        ["env", "universe", "strategy"],
        registry=registry,
    )
    
    return metrics


# ============================================================================
# Initialization
# ============================================================================

def init_metrics(
    env: str,
    universe: str,
    strategy: str,
    registry: Optional[CollectorRegistry] = None,
) -> None:
    """
    Prometheus 메트릭 초기화.
    
    Args:
        env: 환경 ("paper", "live", "test")
        universe: 유니버스 모드 ("top20", "top50", "custom")
        strategy: 전략 이름 ("topn_arb" 등)
        registry: 커스텀 CollectorRegistry (테스트용, 기본값은 전역)
        
    Note:
        중복 호출 시 재초기화 (idempotent)
    """
    global _registry, _metrics, _common_labels
    
    # Registry 설정
    if registry is None:
        _registry = CollectorRegistry()
    else:
        _registry = registry
    
    # 공통 Label 저장
    _common_labels = {
        "env": env,
        "universe": universe,
        "strategy": strategy,
    }
    
    # 메트릭 생성
    _metrics = _create_metrics(_registry)
    
    logger.info(
        f"[D77-1] Metrics initialized: env={env}, universe={universe}, strategy={strategy}"
    )


def start_metrics_server(port: int = 9100) -> None:
    """
    Prometheus HTTP 서버 시작.
    
    Args:
        port: HTTP 서버 포트 (기본값: 9100)
        
    Note:
        중복 호출 시 무시 (이미 시작된 경우)
    """
    global _http_server_started
    
    with _http_server_lock:
        if _http_server_started:
            logger.warning(f"[D77-1] Metrics server already running on port {port}")
            return
        
        try:
            start_http_server(port, registry=_registry)
            _http_server_started = True
            logger.info(f"[D77-1] Metrics server started on port {port}")
        except OSError as e:
            if "Address already in use" in str(e):
                logger.warning(
                    f"[D77-1] Port {port} already in use, assuming server is already running"
                )
                _http_server_started = True
            else:
                raise


# ============================================================================
# KPI Recording Functions
# ============================================================================

def record_pnl(total_pnl: float) -> None:
    """
    PnL 업데이트 (Gauge).
    
    Args:
        total_pnl: 누적 PnL (USD)
    """
    if not _metrics:
        return
    
    _metrics["pnl_total"].labels(**_common_labels).set(total_pnl)


def record_trade(trade_type: str) -> None:
    """
    거래 기록 (Counter).
    
    Args:
        trade_type: 거래 타입 ("entry" or "exit")
    """
    if not _metrics:
        return
    
    _metrics["trades_total"].labels(
        **_common_labels,
        trade_type=trade_type,
    ).inc()


def record_round_trip() -> None:
    """
    라운드 트립 완료 (Counter).
    """
    if not _metrics:
        return
    
    _metrics["round_trips_total"].labels(**_common_labels).inc()


def record_win_rate(wins: int, losses: int) -> None:
    """
    승률 계산 및 업데이트 (Gauge).
    
    Args:
        wins: 승 수
        losses: 패 수
    """
    if not _metrics:
        return
    
    total = wins + losses
    if total > 0:
        win_rate_pct = (wins / total) * 100.0
    else:
        win_rate_pct = 0.0
    
    _metrics["win_rate"].labels(**_common_labels).set(win_rate_pct)


def record_loop_latency(seconds: float) -> None:
    """
    루프 레이턴시 기록 (Summary).
    
    Args:
        seconds: 루프 레이턴시 (초)
    """
    if not _metrics:
        return
    
    _metrics["loop_latency_seconds"].labels(**_common_labels).observe(seconds)


def record_memory_usage(bytes_used: float) -> None:
    """
    메모리 사용량 업데이트 (Gauge).
    
    Args:
        bytes_used: 메모리 사용량 (bytes)
    """
    if not _metrics:
        return
    
    _metrics["memory_usage_bytes"].labels(**_common_labels).set(bytes_used)


def record_cpu_usage(percent: float) -> None:
    """
    CPU 사용률 업데이트 (Gauge).
    
    Args:
        percent: CPU 사용률 (%)
    """
    if not _metrics:
        return
    
    _metrics["cpu_usage_percent"].labels(**_common_labels).set(percent)


def record_guard_trigger(guard_type: str) -> None:
    """
    Guard 트리거 기록 (Counter).
    
    Args:
        guard_type: Guard 타입 ("exchange", "route", "symbol", "global")
    """
    if not _metrics:
        return
    
    _metrics["guard_triggers_total"].labels(
        **_common_labels,
        guard_type=guard_type,
    ).inc()


def record_alert(severity: str, source: str) -> None:
    """
    알림 기록 (Counter).
    
    Args:
        severity: 알림 심각도 ("P0", "P1", "P2", "P3")
        source: 알림 소스 (예: "rate_limiter", "health_monitor")
    """
    if not _metrics:
        return
    
    _metrics["alerts_total"].labels(
        **_common_labels,
        severity=severity,
        source=source,
    ).inc()


def record_exit_reason(reason: str) -> None:
    """
    Exit 이유 기록 (Counter).
    
    Args:
        reason: Exit 이유 ("take_profit", "stop_loss", "time_limit", "spread_reversal")
    """
    if not _metrics:
        return
    
    _metrics["exit_reasons_total"].labels(
        **_common_labels,
        reason=reason,
    ).inc()


def set_active_positions(count: int) -> None:
    """
    활성 포지션 수 업데이트 (Gauge).
    
    Args:
        count: 활성 포지션 수
    """
    if not _metrics:
        return
    
    _metrics["active_positions"].labels(**_common_labels).set(count)


# ============================================================================
# Utility Functions (for Testing)
# ============================================================================

def get_metrics_text() -> str:
    """
    /metrics 엔드포인트 텍스트 반환 (테스트용).
    
    Returns:
        Prometheus 메트릭 텍스트
    """
    if not _registry:
        return ""
    
    return generate_latest(_registry).decode("utf-8")


def reset_metrics() -> None:
    """
    메트릭 초기화 (테스트용).
    
    Note:
        전역 상태를 리셋하여 테스트 간 격리 보장
    """
    global _registry, _metrics, _http_server_started, _common_labels
    
    _registry = None
    _metrics = {}
    _http_server_started = False
    _common_labels = {}
    
    logger.debug("[D77-1] Metrics reset")
