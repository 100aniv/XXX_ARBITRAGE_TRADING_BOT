# -*- coding: utf-8 -*-
"""
D79-6: Cross-Exchange Metrics Collector

Cross-Exchange 아비트라지 전용 메트릭 수집 시스템.

Features:
- RiskGuard decision 기록
- Executor result 기록
- PnL snapshot 기록
- Prometheus export용 인터페이스 제공
- AlertManager 연계

Architecture:
    RiskGuard/Executor/PnLTracker
            ↓
    CrossExchangeMetrics
            ↓
    ├─> PrometheusBackend (D77 연계)
    └─> AlertManager (D76 연계)
"""

import logging
from typing import Dict, List, Optional, Any, Protocol
from dataclasses import dataclass
from arbitrage.common.currency import Currency, Money

logger = logging.getLogger(__name__)


# =============================================================================
# Metrics Backend 인터페이스
# =============================================================================

class PrometheusBackend(Protocol):
    """
    Prometheus-like metrics backend 인터페이스.
    
    실제 Prometheus client는 D77에서 주입.
    테스트/개발 시에는 InMemoryMetricsBackend 사용.
    """
    
    def inc_counter(self, name: str, labels: dict, value: float = 1.0) -> None:
        """Counter 증가"""
        ...
    
    def set_gauge(self, name: str, labels: dict, value: float) -> None:
        """Gauge 설정"""
        ...
    
    def observe_histogram(self, name: str, labels: dict, value: float) -> None:
        """Histogram 관측값 추가"""
        ...
    
    def export_prometheus_text(self) -> str:
        """Prometheus text format으로 export"""
        ...
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """전체 metrics 스냅샷 (테스트용)"""
        ...


class InMemoryMetricsBackend:
    """
    테스트/개발용 in-memory metrics backend.
    
    실제 Prometheus 없이도 metrics 수집/조회 가능.
    """
    
    def __init__(self):
        self.counters: Dict[str, float] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = {}
    
    def inc_counter(self, name: str, labels: dict, value: float = 1.0) -> None:
        """Counter 증가"""
        key = self._make_key(name, labels)
        self.counters[key] = self.counters.get(key, 0.0) + value
    
    def set_gauge(self, name: str, labels: dict, value: float) -> None:
        """Gauge 설정"""
        key = self._make_key(name, labels)
        self.gauges[key] = value
    
    def observe_histogram(self, name: str, labels: dict, value: float) -> None:
        """Histogram 관측값 추가"""
        key = self._make_key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = []
        self.histograms[key].append(value)
    
    def export_prometheus_text(self) -> str:
        """간단한 text format (실제 Prometheus 형식은 아님)"""
        lines = []
        for key, value in sorted(self.counters.items()):
            lines.append(f"{key} {value}")
        for key, value in sorted(self.gauges.items()):
            lines.append(f"{key} {value}")
        return "\n".join(lines)
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """전체 metrics 스냅샷"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                k: {"count": len(v), "values": v[:]}  # copy
                for k, v in self.histograms.items()
            },
        }
    
    def _make_key(self, name: str, labels: dict) -> str:
        """메트릭 이름 + 라벨로 unique key 생성"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# =============================================================================
# AlertManager 인터페이스 (D76 연계용)
# =============================================================================

class AlertManager(Protocol):
    """
    Alert 전송 인터페이스.
    
    실제 구현은 D76에서 주입.
    """
    
    def send_alert(
        self,
        level: str,
        title: str,
        message: str,
        context: dict,
    ) -> None:
        """Alert 전송 (Telegram, Email, Slack 등)"""
        ...


# =============================================================================
# CrossExchangeMetrics
# =============================================================================

@dataclass
class CrossExchangePnLSnapshot:
    """
    PnL 스냅샷 (Multi-Currency 지원, D80-1).
    
    Base Currency 기준으로 PnL 집계.
    """
    daily_pnl: Money
    unrealized_pnl: Optional[Money] = None
    consecutive_loss_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    symbol: Optional[str] = None  # None이면 전체
    
    # Backward compatibility properties
    @property
    def daily_pnl_krw(self) -> float:
        """Deprecated: KRW amount (backward compatible)"""
        if self.daily_pnl.currency == Currency.KRW:
            return float(self.daily_pnl.amount)
        # 다른 통화면 경고
        logger.warning(
            f"[SNAPSHOT] daily_pnl_krw called but currency is {self.daily_pnl.currency}. "
            "Use daily_pnl (Money) instead."
        )
        return float(self.daily_pnl.amount)
    
    @property
    def unrealized_pnl_krw(self) -> float:
        """Deprecated: KRW amount (backward compatible)"""
        if self.unrealized_pnl is None:
            return 0.0
        if self.unrealized_pnl.currency == Currency.KRW:
            return float(self.unrealized_pnl.amount)
        logger.warning(
            f"[SNAPSHOT] unrealized_pnl_krw called but currency is {self.unrealized_pnl.currency}. "
            "Use unrealized_pnl (Money) instead."
        )
        return float(self.unrealized_pnl.amount)


@dataclass
class CrossExecutionResult:
    """Executor 실행 결과 (Executor → Metrics 전달용)"""
    status: str  # success, failed, rollback, blocked
    upbit_result: Optional[Any] = None  # OrderResult
    binance_result: Optional[Any] = None  # OrderResult
    total_latency: Optional[float] = None  # 초 단위
    rollback_reason: Optional[str] = None  # partial_fill, one_side_fill 등


class CrossExchangeMetrics:
    """
    Cross-Exchange 아비트라지 전용 메트릭 수집기.
    
    Features:
    - RiskGuard decision 기록
    - Executor result 기록
    - PnL snapshot 기록
    - Prometheus export용 인터페이스 제공
    - AlertManager 연계
    """
    
    # Circuit breaker alert 대상 reason codes
    CIRCUIT_BREAKER_REASONS = {
        "cross_daily_loss_limit",
        "cross_consecutive_loss_limit",
        "cross_circuit_breaker",
    }
    
    def __init__(
        self,
        prometheus_backend: Optional[PrometheusBackend] = None,
        alert_manager: Optional[AlertManager] = None,
    ):
        """
        Args:
            prometheus_backend: Prometheus 백엔드 (None이면 InMemoryMetricsBackend 사용)
            alert_manager: AlertManager (None이면 alert 미전송)
        """
        self.backend = prometheus_backend or InMemoryMetricsBackend()
        self.alert_manager = alert_manager
        
        logger.info("[CROSS_METRICS] Initialized (backend=%s, alert=%s)",
                    type(self.backend).__name__,
                    type(self.alert_manager).__name__ if self.alert_manager else "None")
    
    # =========================================================================
    # RiskGuard Decision 기록
    # =========================================================================
    
    def record_risk_decision(
        self,
        decision: Any,  # CrossRiskDecision
        decision_context: dict,
    ) -> None:
        """
        RiskGuard 결정 기록.
        
        Args:
            decision: CrossRiskDecision
            decision_context: {
                "symbol_upbit": str,
                "symbol_binance": str,
                "action": str,
                "first_trigger_reason": Optional[str],  # 첫 번째 감지된 룰
            }
        """
        # Counter: Block count (tier별, reason별)
        if not decision.allowed:
            self.backend.inc_counter(
                "risk_guard_blocks_total",
                labels={
                    "tier": decision.tier,
                    "reason": decision.reason_code,
                }
            )
            
            # First trigger 기록 (있으면)
            if first_trigger := decision_context.get("first_trigger_reason"):
                self.backend.inc_counter(
                    "risk_first_trigger_total",
                    labels={"reason": first_trigger}
                )
            
            # Final block 기록
            self.backend.inc_counter(
                "risk_final_block_total",
                labels={"reason": decision.reason_code}
            )
            
            logger.debug(
                "[CROSS_METRICS] RiskGuard BLOCK: tier=%s, reason=%s, first_trigger=%s",
                decision.tier, decision.reason_code,
                decision_context.get("first_trigger_reason", "N/A")
            )
            
            # Alert 전송 (Circuit breaker 등 중요 이벤트)
            if decision.reason_code in self.CIRCUIT_BREAKER_REASONS:
                self._send_alert_if_enabled(
                    level="P1",
                    title=f"🚨 Circuit Breaker: {decision.reason_code}",
                    message=f"Cross-Exchange trading blocked: {decision.details}",
                    context=decision_context,
                )
        
        # Gauge: Exposure/Imbalance 업데이트
        if "exposure_risk" in decision.details:
            self.backend.set_gauge(
                "cross_exposure_ratio",
                value=decision.details["exposure_risk"],
                labels={
                    "symbol": decision_context.get("symbol_upbit", "unknown"),
                }
            )
        
        if "imbalance_ratio" in decision.details:
            self.backend.set_gauge(
                "inventory_imbalance_ratio",
                value=decision.details["imbalance_ratio"],
                labels={
                    "symbol": decision_context.get("symbol_upbit", "unknown"),
                }
            )
        
        # Gauge: Circuit breaker status
        if "cooldown_until" in decision.details and decision.details["cooldown_until"]:
            # Circuit breaker 활성
            cb_type = self._infer_circuit_breaker_type(decision.reason_code)
            self.backend.set_gauge(
                "circuit_breaker_active",
                value=1.0,
                labels={"type": cb_type}
            )
            
            # Cooldown 남은 시간
            import time
            remaining = max(0.0, decision.details["cooldown_until"] - time.time())
            self.backend.set_gauge(
                "circuit_breaker_cooldown_remaining",
                value=remaining,
                labels={"type": cb_type}
            )
    
    # =========================================================================
    # Execution Result 기록
    # =========================================================================
    
    def record_execution_result(
        self,
        result: CrossExecutionResult,
    ) -> None:
        """
        Executor 실행 결과 기록.
        
        Args:
            result: CrossExecutionResult (status, upbit_result, binance_result, latency, etc.)
        """
        # Counter: 주문 성공/실패
        for exchange_name, order_result in [
            ("upbit", result.upbit_result),
            ("binance", result.binance_result),
        ]:
            if order_result:
                status = getattr(order_result, "status", "unknown")
                self.backend.inc_counter(
                    "cross_orders_total",
                    labels={
                        "exchange": exchange_name,
                        "status": status,
                    }
                )
        
        # Histogram: Order fill latency
        if result.total_latency is not None:
            self.backend.observe_histogram(
                "cross_order_fill_duration_seconds",
                value=result.total_latency,
                labels={"exchange": "combined"}
            )
        
        # Counter: Rollback
        if result.status == "rollback":
            self.backend.inc_counter(
                "cross_rollbacks_total",
                labels={"reason": result.rollback_reason or "unknown"}
            )
        
        logger.debug(
            "[CROSS_METRICS] Execution result: status=%s, latency=%.3fs",
            result.status, result.total_latency or 0.0
        )
    
    # =========================================================================
    # PnL Snapshot 기록
    # =========================================================================
    
    def record_pnl_snapshot(
        self,
        snapshot: CrossExchangePnLSnapshot,
    ) -> None:
        """
        PnL 스냅샷 기록 (Multi-Currency 지원, D80-1).
        
        Args:
            snapshot: CrossExchangePnLSnapshot (Money 기반)
        """
        symbol_label = snapshot.symbol or "total"
        base_currency = snapshot.daily_pnl.currency.value
        
        # Gauge: Daily PnL (새 메트릭 이름, base_currency dimension)
        self.backend.set_gauge(
            "cross_daily_pnl",
            value=float(snapshot.daily_pnl.amount),
            labels={"base_currency": base_currency, "symbol": symbol_label}
        )
        
        # Gauge: Daily PnL (구 메트릭 이름, deprecated, backward compatible)
        self.backend.set_gauge(
            "cross_daily_pnl_krw",
            value=float(snapshot.daily_pnl.amount),
            labels={"symbol": symbol_label}
        )
        
        # Gauge: Unrealized PnL
        if snapshot.unrealized_pnl is not None:
            self.backend.set_gauge(
                "cross_unrealized_pnl",
                value=float(snapshot.unrealized_pnl.amount),
                labels={"base_currency": base_currency, "symbol": symbol_label}
            )
            
            # Deprecated
            self.backend.set_gauge(
                "cross_unrealized_pnl_krw",
                value=float(snapshot.unrealized_pnl.amount),
                labels={"symbol": symbol_label}
            )
        
        # Gauge: Consecutive loss
        self.backend.set_gauge(
            "cross_consecutive_loss_count",
            value=float(snapshot.consecutive_loss_count),
            labels={}
        )
        
        # Gauge: Winrate
        total_trades = snapshot.win_count + snapshot.loss_count
        if total_trades > 0:
            winrate = snapshot.win_count / total_trades
            self.backend.set_gauge(
                "cross_winrate",
                value=winrate,
                labels={"symbol": symbol_label}
            )
        
        logger.debug(
            "[CROSS_METRICS] PnL snapshot: daily=%s, consecutive_loss=%d, winrate=%.2f%%",
            snapshot.daily_pnl,
            snapshot.consecutive_loss_count,
            (snapshot.win_count / total_trades * 100) if total_trades > 0 else 0.0
        )
    
    # =========================================================================
    # Export & Utility
    # =========================================================================
    
    def export_prometheus(self) -> str:
        """
        Prometheus 형식으로 export.
        
        D77 PrometheusExporter가 호출할 수 있는 형태.
        """
        return self.backend.export_prometheus_text()
    
    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """테스트/디버깅용 스냅샷"""
        return self.backend.get_all_metrics()
    
    # =========================================================================
    # Internal Helpers
    # =========================================================================
    
    def _send_alert_if_enabled(
        self,
        level: str,
        title: str,
        message: str,
        context: dict,
    ) -> None:
        """AlertManager가 있으면 Alert 전송"""
        if self.alert_manager:
            try:
                self.alert_manager.send_alert(
                    level=level,
                    title=title,
                    message=message,
                    context=context,
                )
                logger.info("[CROSS_METRICS] Alert sent: level=%s, title=%s", level, title)
            except Exception as e:
                logger.error("[CROSS_METRICS] Alert send failed: %s", e, exc_info=True)
        else:
            logger.debug("[CROSS_METRICS] Alert NOT sent (AlertManager not configured): %s", title)
    
    def _infer_circuit_breaker_type(self, reason_code: str) -> str:
        """Reason code로부터 circuit breaker 타입 추론"""
        if "daily_loss" in reason_code:
            return "daily_loss"
        elif "consecutive_loss" in reason_code:
            return "consecutive_loss"
        else:
            return "unknown"
    
    # =========================================================================
    # D80-4: WebSocket FX Metrics
    # =========================================================================
    
    def record_fx_ws_metrics(
        self,
        connected: bool,
        reconnect_count: int,
        message_count: int,
        error_count: int,
        last_message_age: float,
    ) -> None:
        """
        WebSocket FX metrics 기록 (D80-4).
        
        Args:
            connected: WebSocket 연결 상태 (True/False)
            reconnect_count: 재연결 횟수
            message_count: 수신 메시지 수
            error_count: 에러 발생 횟수
            last_message_age: 마지막 메시지 이후 경과 시간 (초)
        """
        if self.backend is None:
            return
        
        labels = {}  # 필요 시 추가 label (예: symbol)
        
        # Gauge: WebSocket 연결 상태 (0/1)
        self.backend.set_gauge(
            "cross_fx_ws_connected",
            labels,
            1.0 if connected else 0.0
        )
        
        # Gauge: 재연결 횟수 (누적)
        self.backend.set_gauge(
            "cross_fx_ws_reconnect_total",
            labels,
            float(reconnect_count)
        )
        
        # Gauge: 수신 메시지 수 (누적)
        self.backend.set_gauge(
            "cross_fx_ws_message_total",
            labels,
            float(message_count)
        )
        
        # Gauge: 에러 발생 횟수 (누적)
        self.backend.set_gauge(
            "cross_fx_ws_error_total",
            labels,
            float(error_count)
        )
        
        # Gauge: 마지막 메시지 이후 경과 시간 (초)
        self.backend.set_gauge(
            "cross_fx_ws_last_message_seconds",
            labels,
            last_message_age
        )
        
        logger.debug(
            f"[CROSS_METRICS] FX WebSocket metrics recorded: "
            f"connected={connected}, reconnect={reconnect_count}, "
            f"messages={message_count}, errors={error_count}, "
            f"last_msg_age={last_message_age:.1f}s"
        )
    
    # =========================================================================
    # D80-5: Multi-Source FX Metrics
    # =========================================================================
    
    def record_fx_multi_source_metrics(
        self,
        source_count: int,
        outlier_count: int,
        median_rate: float,
        source_stats: Dict[str, Any],
    ) -> None:
        """
        Multi-Source FX metrics 기록 (D80-5).
        
        Args:
            source_count: 유효한 소스 개수 (0~3)
            outlier_count: 제거된 outlier 누적 개수
            median_rate: Median 환율 (USDT→USD)
            source_stats: 소스별 상태 {"binance": {...}, "okx": {...}, "bybit": {...}}
        """
        if self.backend is None:
            return
        
        labels = {}
        
        # Gauge: 유효한 소스 개수 (0~3)
        self.backend.set_gauge(
            "cross_fx_multi_source_count",
            labels,
            float(source_count)
        )
        
        # Gauge: 제거된 outlier 누적 개수
        self.backend.set_gauge(
            "cross_fx_multi_source_outlier_total",
            labels,
            float(outlier_count)
        )
        
        # Gauge: Median 환율
        self.backend.set_gauge(
            "cross_fx_multi_source_median",
            labels,
            median_rate
        )
        
        # Source-specific metrics
        for source, stats in source_stats.items():
            source_labels = {"source": source}
            
            # Gauge: 소스별 연결 상태 (0/1)
            self.backend.set_gauge(
                f"cross_fx_multi_source_{source}_connected",
                source_labels,
                1.0 if stats["connected"] else 0.0
            )
            
            # Gauge: 소스별 환율
            if stats["rate"] is not None:
                self.backend.set_gauge(
                    f"cross_fx_multi_source_{source}_rate",
                    source_labels,
                    stats["rate"]
                )
            
            # Gauge: 소스별 마지막 메시지 경과 시간 (초)
            self.backend.set_gauge(
                f"cross_fx_multi_source_{source}_age",
                source_labels,
                stats["age"]
            )
        
        logger.debug(
            f"[CROSS_METRICS] Multi-Source FX metrics recorded: "
            f"source_count={source_count}, outlier_count={outlier_count}, "
            f"median_rate={median_rate:.6f}"
        )
