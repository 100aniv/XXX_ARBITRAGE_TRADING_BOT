#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Watchdog System (PHASE D11)
===========================

장시간 운용 중 비정상 상황을 감시하고 경고/조치를 수행하는 모듈.

특징:
- 메트릭 기반 상태 판단
- 단계적 경고 (WARN → ERROR → SHUTDOWN)
- 선택적 graceful shutdown 요청
- AlertSystem과 자연스럽게 연동
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """경고 레벨"""
    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class AlertEvent:
    """경고 이벤트"""
    level: AlertLevel
    component: str
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None


@dataclass
class WatchdogConfig:
    """워치독 설정"""
    # WebSocket 감시
    max_ws_lag_ms: float = 5000.0           # 최대 WS 지연 (ms)
    ws_lag_warn_threshold_ms: float = 2000.0
    
    # Redis heartbeat 감시
    max_redis_heartbeat_age_ms: float = 30000.0  # 최대 30초
    redis_heartbeat_warn_threshold_ms: float = 15000.0
    
    # 루프 지연 감시
    max_loop_latency_ms: float = 5000.0
    loop_latency_warn_threshold_ms: float = 2000.0
    
    # 안전 검증 감시
    max_safety_rejections_per_minute: int = 10
    
    # Live 모드 감시
    max_live_errors_per_minute: int = 5
    
    # 리소스 감시 (sys_monitor와 연동)
    max_cpu_pct: float = 90.0
    max_rss_mb: float = 2048.0
    
    # D12: 튜닝 & Auto-reset
    warn_reset_cycles: int = 5              # WARN 상태 자동 리셋 사이클 수
    error_reset_cycles: int = 20            # ERROR 상태 자동 리셋 사이클 수
    cooldown_after_critical: float = 60.0   # CRITICAL 후 쿨다운 (초)


@dataclass
class WatchdogStatus:
    """워치독 상태"""
    is_healthy: bool = True
    alerts: List[AlertEvent] = field(default_factory=list)
    last_check_ts: Optional[float] = None
    consecutive_errors: int = 0
    should_shutdown: bool = False
    shutdown_reason: Optional[str] = None


class Watchdog:
    """워치독 시스템"""
    
    def __init__(self, config: Optional[WatchdogConfig] = None):
        """
        Args:
            config: WatchdogConfig 인스턴스
        """
        self.config = config or WatchdogConfig()
        self.status = WatchdogStatus()
        self.metrics_history: Dict[str, List[float]] = {}
        self.rejection_count_per_minute = 0
        self.error_count_per_minute = 0
        self.last_minute_reset_ts = 0.0
        
        # D12: Auto-reset 상태
        self.warn_cycle_count = 0           # WARN 상태 사이클 카운트
        self.error_cycle_count = 0          # ERROR 상태 사이클 카운트
        self.last_critical_ts = 0.0         # 마지막 CRITICAL 시간
        self.consecutive_warn_count = 0     # 연속 WARN 경고 수
    
    def update_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        메트릭 업데이트
        
        Args:
            metrics: MetricsCollector.get_all_metrics() 결과
        """
        import time
        
        current_ts = time.time()
        
        # 분 단위 카운터 리셋
        if current_ts - self.last_minute_reset_ts > 60:
            self.rejection_count_per_minute = 0
            self.error_count_per_minute = 0
            self.last_minute_reset_ts = current_ts
        
        # 메트릭 히스토리 저장
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                if key not in self.metrics_history:
                    self.metrics_history[key] = []
                self.metrics_history[key].append(value)
                # 최근 100개만 보관
                if len(self.metrics_history[key]) > 100:
                    self.metrics_history[key].pop(0)
        
        self.status.last_check_ts = current_ts
    
    def evaluate(self, metrics: Dict[str, Any]) -> WatchdogStatus:
        """
        현재 상태 평가
        
        Args:
            metrics: MetricsCollector.get_all_metrics() 결과
        
        Returns:
            WatchdogStatus
        """
        self.status.alerts = []
        self.status.is_healthy = True
        
        # WebSocket 지연 확인
        ws_lag = metrics.get("ws_lag_ms", 0.0)
        if ws_lag > self.config.max_ws_lag_ms:
            self.status.alerts.append(AlertEvent(
                level=AlertLevel.ERROR,
                component="WebSocket",
                message=f"WS lag critical: {ws_lag:.1f}ms > {self.config.max_ws_lag_ms}ms",
                metric_name="ws_lag_ms",
                metric_value=ws_lag,
                threshold=self.config.max_ws_lag_ms
            ))
            self.status.is_healthy = False
        elif ws_lag > self.config.ws_lag_warn_threshold_ms:
            self.status.alerts.append(AlertEvent(
                level=AlertLevel.WARN,
                component="WebSocket",
                message=f"WS lag warning: {ws_lag:.1f}ms > {self.config.ws_lag_warn_threshold_ms}ms",
                metric_name="ws_lag_ms",
                metric_value=ws_lag,
                threshold=self.config.ws_lag_warn_threshold_ms
            ))
        
        # Redis heartbeat 확인
        redis_age = metrics.get("redis_heartbeat_age_ms", 0.0)
        if redis_age > self.config.max_redis_heartbeat_age_ms:
            self.status.alerts.append(AlertEvent(
                level=AlertLevel.ERROR,
                component="Redis",
                message=f"Redis heartbeat stale: {redis_age:.1f}ms > {self.config.max_redis_heartbeat_age_ms}ms",
                metric_name="redis_heartbeat_age_ms",
                metric_value=redis_age,
                threshold=self.config.max_redis_heartbeat_age_ms
            ))
            self.status.is_healthy = False
        elif redis_age > self.config.redis_heartbeat_warn_threshold_ms:
            self.status.alerts.append(AlertEvent(
                level=AlertLevel.WARN,
                component="Redis",
                message=f"Redis heartbeat aging: {redis_age:.1f}ms > {self.config.redis_heartbeat_warn_threshold_ms}ms",
                metric_name="redis_heartbeat_age_ms",
                metric_value=redis_age,
                threshold=self.config.redis_heartbeat_warn_threshold_ms
            ))
        
        # 루프 지연 확인
        loop_latency = metrics.get("loop_latency_ms", 0.0)
        if loop_latency > self.config.max_loop_latency_ms:
            self.status.alerts.append(AlertEvent(
                level=AlertLevel.ERROR,
                component="MainLoop",
                message=f"Loop latency critical: {loop_latency:.1f}ms > {self.config.max_loop_latency_ms}ms",
                metric_name="loop_latency_ms",
                metric_value=loop_latency,
                threshold=self.config.max_loop_latency_ms
            ))
            self.status.is_healthy = False
        elif loop_latency > self.config.loop_latency_warn_threshold_ms:
            self.status.alerts.append(AlertEvent(
                level=AlertLevel.WARN,
                component="MainLoop",
                message=f"Loop latency warning: {loop_latency:.1f}ms > {self.config.loop_latency_warn_threshold_ms}ms",
                metric_name="loop_latency_ms",
                metric_value=loop_latency,
                threshold=self.config.loop_latency_warn_threshold_ms
            ))
        
        # 안전 검증 거부 확인
        safety_rejections = metrics.get("safety_rejections_count", 0)
        if safety_rejections > self.config.max_safety_rejections_per_minute:
            self.status.alerts.append(AlertEvent(
                level=AlertLevel.WARN,
                component="Safety",
                message=f"Safety rejections high: {safety_rejections} > {self.config.max_safety_rejections_per_minute}",
                metric_name="safety_rejections_count",
                metric_value=float(safety_rejections),
                threshold=float(self.config.max_safety_rejections_per_minute)
            ))
        
        # ERROR 레벨 경고가 있으면 상태 업데이트
        error_alerts = [a for a in self.status.alerts if a.level == AlertLevel.ERROR]
        warn_alerts = [a for a in self.status.alerts if a.level == AlertLevel.WARN]
        
        if error_alerts:
            self.status.is_healthy = False
            self.status.consecutive_errors += 1
            self.error_cycle_count += 1
            self.warn_cycle_count = 0  # ERROR 발생 시 WARN 카운트 리셋
            
            # D12: ERROR 상태 자동 리셋 (error_reset_cycles 후)
            if self.error_cycle_count >= self.config.error_reset_cycles:
                self.soft_reset()
            
            # 연속 ERROR 3회 이상 → CRITICAL (graceful shutdown 요청)
            if self.status.consecutive_errors >= 3:
                self.status.should_shutdown = True
                self.status.shutdown_reason = f"Consecutive errors: {self.status.consecutive_errors}"
                self.status.alerts.append(AlertEvent(
                    level=AlertLevel.CRITICAL,
                    component="Watchdog",
                    message=f"Requesting graceful shutdown: {self.status.shutdown_reason}"
                ))
                # CRITICAL 시간 기록
                import time
                self.last_critical_ts = time.time()
        elif warn_alerts:
            # WARN만 있는 경우
            self.warn_cycle_count += 1
            self.error_cycle_count = 0  # WARN 상태에서는 ERROR 카운트 리셋
            self.consecutive_warn_count = len(warn_alerts)
            
            # D12: WARN 상태 자동 리셋 (warn_reset_cycles 후)
            if self.warn_cycle_count >= self.config.warn_reset_cycles:
                self.soft_reset()
        else:
            # 정상 상태
            self.status.consecutive_errors = 0
            self.warn_cycle_count = 0
            self.error_cycle_count = 0
            self.consecutive_warn_count = 0
        
        return self.status
    
    def get_status_summary(self) -> str:
        """상태 요약 문자열"""
        if self.status.should_shutdown:
            return f"🔴 WATCHDOG CRITICAL - Shutdown requested: {self.status.shutdown_reason}"
        elif not self.status.is_healthy:
            error_count = len([a for a in self.status.alerts if a.level == AlertLevel.ERROR])
            return f"🟠 WATCHDOG ERROR ({error_count} errors)"
        elif self.status.alerts:
            warn_count = len([a for a in self.status.alerts if a.level == AlertLevel.WARN])
            return f"🟡 WATCHDOG WARN ({warn_count} warnings)"
        else:
            return "🟢 WATCHDOG OK"
    
    def get_alert_summary(self) -> str:
        """경고 요약 문자열"""
        if not self.status.alerts:
            return ""
        
        lines = []
        for alert in self.status.alerts:
            lines.append(f"  [{alert.level.value}] {alert.component}: {alert.message}")
        
        return "\n".join(lines)
    
    def soft_reset(self) -> None:
        """
        소프트 리셋 (비파괴적 상태 초기화)
        
        D12: 장시간 운영 중 경고 상태에서 자동 복구
        - 카운터 초기화
        - 경고 상태 유지 (히스토리)
        - 비즈니스 로직 영향 없음
        """
        logger.info("[Watchdog] Soft reset triggered (auto-recovery)")
        self.warn_cycle_count = 0
        self.error_cycle_count = 0
        self.consecutive_warn_count = 0
        # consecutive_errors는 유지 (CRITICAL 판단용)
