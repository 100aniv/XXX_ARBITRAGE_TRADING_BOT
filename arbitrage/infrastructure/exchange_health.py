"""
D75-3: Exchange Health Monitor

거래소 건강 상태 모니터링:
- REST latency (avg, p99)
- Orderbook freshness
- Error ratio (4xx/5xx)
- Health status (HEALTHY/DEGRADED/DOWN/FROZEN)
- Failover 기준
"""

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Optional


@dataclass
class HealthMetrics:
    """거래소 건강 상태 메트릭"""
    
    # Latency
    rest_latency_ms: float = 0.0  # REST API 평균 latency (ms)
    rest_latency_p99_ms: float = 0.0  # REST API p99 latency (ms)
    ws_latency_ms: float = 0.0  # WebSocket message latency (ms)
    
    # Freshness
    orderbook_age_ms: float = 0.0  # Orderbook 데이터 나이 (ms)
    last_update_timestamp: float = 0.0  # 마지막 업데이트 시각
    
    # Error Ratio
    error_4xx_count: int = 0  # 4xx 에러 수 (client error)
    error_5xx_count: int = 0  # 5xx 에러 수 (server error)
    total_requests: int = 0  # 총 요청 수
    error_ratio: float = 0.0  # 전체 에러 비율
    
    # Rate Limit
    rate_limit_near_exhausted: bool = False  # Rate limit 임박
    rate_limit_remaining: int = 0  # 남은 요청 수 (API header 기반)
    
    # Connection
    ws_connected: bool = True  # WebSocket 연결 상태
    ws_reconnect_count: int = 0  # WebSocket 재연결 횟수


class ExchangeHealthStatus(Enum):
    """거래소 건강 상태"""
    HEALTHY = "healthy"  # 정상
    DEGRADED = "degraded"  # 성능 저하
    DOWN = "down"  # 다운
    FROZEN = "frozen"  # API 응답 없음


class HealthMonitor:
    """
    거래소 건강 상태 모니터.
    
    역할:
    - REST latency, error ratio 추적
    - Orderbook freshness 계산
    - Health status 판단 (HEALTHY/DEGRADED/DOWN/FROZEN)
    - Failover 기준 제공
    
    Example:
        >>> monitor = HealthMonitor("UPBIT")
        >>> monitor.update_latency(50.0)  # 50ms
        >>> monitor.update_error(200)  # Success
        >>> monitor.get_health_status()  # HEALTHY
    """
    
    def __init__(self, exchange_name: str, history_size: int = 100):
        """
        Args:
            exchange_name: 거래소 이름
            history_size: Latency history 크기
        """
        self.exchange_name = exchange_name
        self.metrics = HealthMetrics()
        self._latency_history = deque(maxlen=history_size)
        self._error_history = deque(maxlen=1000)  # 최근 1000개 요청
        self._lock = Lock()
        
        # Health status transition tracking
        self._current_status = ExchangeHealthStatus.HEALTHY
        self._status_change_time = time.time()
        self._down_duration_threshold = 300.0  # 5분
        self._frozen_duration_threshold = 60.0  # 1분
    
    def update_latency(self, latency_ms: float):
        """
        REST API latency 업데이트.
        
        Args:
            latency_ms: Latency (milliseconds)
        """
        with self._lock:
            self._latency_history.append(latency_ms)
            if self._latency_history:
                self.metrics.rest_latency_ms = sum(self._latency_history) / len(self._latency_history)
                sorted_latency = sorted(self._latency_history)
                p99_idx = min(int(len(sorted_latency) * 0.99), len(sorted_latency) - 1)
                self.metrics.rest_latency_p99_ms = sorted_latency[p99_idx]
    
    def update_error(self, status_code: int):
        """
        HTTP 상태 코드 업데이트 (에러 추적).
        
        Args:
            status_code: HTTP status code (200, 400, 500 등)
        """
        with self._lock:
            self._error_history.append(status_code)
            self.metrics.total_requests = len(self._error_history)
            self.metrics.error_4xx_count = sum(1 for code in self._error_history if 400 <= code < 500)
            self.metrics.error_5xx_count = sum(1 for code in self._error_history if 500 <= code < 600)
            error_count = self.metrics.error_4xx_count + self.metrics.error_5xx_count
            self.metrics.error_ratio = error_count / self.metrics.total_requests if self.metrics.total_requests > 0 else 0.0
    
    def update_orderbook_freshness(self, snapshot_timestamp: float):
        """
        Orderbook freshness 업데이트.
        
        Args:
            snapshot_timestamp: Snapshot 생성 시각 (Unix timestamp)
        """
        with self._lock:
            now = time.time()
            self.metrics.orderbook_age_ms = (now - snapshot_timestamp) * 1000
            self.metrics.last_update_timestamp = snapshot_timestamp
    
    def update_rate_limit_status(self, remaining: int, near_exhausted_threshold: int = 10):
        """
        Rate limit 상태 업데이트.
        
        Args:
            remaining: 남은 요청 수 (API header X-RateLimit-Remaining)
            near_exhausted_threshold: Near-exhausted 기준
        """
        with self._lock:
            self.metrics.rate_limit_remaining = remaining
            self.metrics.rate_limit_near_exhausted = remaining <= near_exhausted_threshold
    
    def update_ws_status(self, connected: bool, reconnect_count: Optional[int] = None):
        """
        WebSocket 연결 상태 업데이트.
        
        Args:
            connected: 연결 여부
            reconnect_count: 재연결 횟수 (선택)
        """
        with self._lock:
            self.metrics.ws_connected = connected
            if reconnect_count is not None:
                self.metrics.ws_reconnect_count = reconnect_count
    
    def get_health_status(self) -> ExchangeHealthStatus:
        """
        현재 건강 상태 판단.
        
        기준:
        - HEALTHY: latency < 100ms, error_ratio < 1%, orderbook < 1s
        - DEGRADED: latency 100~500ms, error_ratio 1~5%, orderbook 1~3s
        - DOWN: latency > 500ms, error_ratio > 5%, orderbook > 3s
        - FROZEN: latency > 2000ms or no update > 10s
        
        Returns:
            ExchangeHealthStatus
        """
        with self._lock:
            # FROZEN: 응답 없음
            if self.metrics.rest_latency_ms > 2000 or self.metrics.orderbook_age_ms > 10000:
                new_status = ExchangeHealthStatus.FROZEN
            # DOWN: 심각한 문제
            elif (self.metrics.rest_latency_ms > 500 or 
                  self.metrics.error_ratio > 0.05 or 
                  self.metrics.orderbook_age_ms > 3000):
                new_status = ExchangeHealthStatus.DOWN
            # DEGRADED: 성능 저하
            elif (self.metrics.rest_latency_ms > 100 or 
                  self.metrics.error_ratio > 0.01 or 
                  self.metrics.orderbook_age_ms > 1000):
                new_status = ExchangeHealthStatus.DEGRADED
            else:
                # HEALTHY
                new_status = ExchangeHealthStatus.HEALTHY
            
            # Status transition tracking
            if new_status != self._current_status:
                self._status_change_time = time.time()
                self._current_status = new_status
            
            return self._current_status
    
    def should_failover(self) -> bool:
        """
        Failover 실행 여부 판단.
        
        기준:
        - FROZEN 상태: 즉시 failover (가장 심각한 상태)
        - DOWN 상태 5분 이상 지속
        - Error ratio > 10% (즉시 failover)
        
        Returns:
            True: Failover 필요, False: 정상
        """
        with self._lock:
            status = self._current_status
            duration = time.time() - self._status_change_time
            
            # FROZEN: 즉시 failover (duration 무시)
            if status == ExchangeHealthStatus.FROZEN:
                return True
            
            # DOWN: 5분 이상 지속
            if status == ExchangeHealthStatus.DOWN and duration >= self._down_duration_threshold:
                return True
            
            # Error ratio > 10% (즉시 failover)
            if self.metrics.error_ratio > 0.10:
                return True
            
            return False
    
    def get_metrics_summary(self) -> dict:
        """
        현재 메트릭 요약.
        
        Returns:
            메트릭 dictionary
        """
        with self._lock:
            return {
                "exchange": self.exchange_name,
                "status": self.get_health_status().value,
                "latency_ms": round(self.metrics.rest_latency_ms, 2),
                "latency_p99_ms": round(self.metrics.rest_latency_p99_ms, 2),
                "orderbook_age_ms": round(self.metrics.orderbook_age_ms, 2),
                "error_ratio": round(self.metrics.error_ratio * 100, 2),  # %
                "error_4xx": self.metrics.error_4xx_count,
                "error_5xx": self.metrics.error_5xx_count,
                "total_requests": self.metrics.total_requests,
                "rate_limit_near_exhausted": self.metrics.rate_limit_near_exhausted,
                "ws_connected": self.metrics.ws_connected,
                "ws_reconnects": self.metrics.ws_reconnect_count,
            }
    
    def reset(self):
        """메트릭 리셋"""
        with self._lock:
            self.metrics = HealthMetrics()
            self._latency_history.clear()
            self._error_history.clear()
            self._current_status = ExchangeHealthStatus.HEALTHY
            self._status_change_time = time.time()
