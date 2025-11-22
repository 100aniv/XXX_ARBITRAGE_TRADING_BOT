"""
D75-3: Exchange Health Monitor Unit Tests

HealthMonitor 검증:
- Latency tracking (avg, p99)
- Error ratio 계산
- Health status transition
- Failover 기준
"""

import time
import pytest
from arbitrage.infrastructure.exchange_health import (
    HealthMetrics,
    ExchangeHealthStatus,
    HealthMonitor,
)


class TestHealthMonitor:
    """HealthMonitor 테스트"""
    
    def test_initialization(self):
        """초기화"""
        monitor = HealthMonitor("UPBIT")
        assert monitor.exchange_name == "UPBIT"
        assert monitor.get_health_status() == ExchangeHealthStatus.HEALTHY
    
    def test_latency_tracking(self):
        """Latency 추적"""
        monitor = HealthMonitor("UPBIT", history_size=10)
        
        # 10개 latency 추가
        for i in range(10):
            monitor.update_latency(float(i * 10))  # 0, 10, 20, ..., 90 ms
        
        metrics = monitor.metrics
        assert metrics.rest_latency_ms == 45.0  # avg
        assert metrics.rest_latency_p99_ms == 90.0  # p99
    
    def test_error_ratio_calculation(self):
        """Error ratio 계산"""
        monitor = HealthMonitor("UPBIT")
        
        # 95개 성공, 5개 실패
        for _ in range(95):
            monitor.update_error(200)  # Success
        
        for _ in range(3):
            monitor.update_error(400)  # 4xx
        
        for _ in range(2):
            monitor.update_error(500)  # 5xx
        
        metrics = monitor.metrics
        assert metrics.total_requests == 100
        assert metrics.error_4xx_count == 3
        assert metrics.error_5xx_count == 2
        assert abs(metrics.error_ratio - 0.05) < 0.001  # 5%
    
    def test_orderbook_freshness(self):
        """Orderbook freshness"""
        monitor = HealthMonitor("UPBIT")
        
        snapshot_time = time.time() - 2.5  # 2.5초 전
        monitor.update_orderbook_freshness(snapshot_time)
        
        metrics = monitor.metrics
        assert 2400 < metrics.orderbook_age_ms < 2600  # ~2500ms
    
    def test_health_status_healthy(self):
        """HEALTHY 상태"""
        monitor = HealthMonitor("UPBIT")
        
        monitor.update_latency(50.0)  # < 100ms
        monitor.update_error(200)
        monitor.update_orderbook_freshness(time.time() - 0.5)  # 0.5s ago
        
        assert monitor.get_health_status() == ExchangeHealthStatus.HEALTHY
    
    def test_health_status_degraded(self):
        """DEGRADED 상태"""
        monitor = HealthMonitor("UPBIT")
        
        # High latency
        for _ in range(10):
            monitor.update_latency(150.0)  # 100~500ms
        
        assert monitor.get_health_status() == ExchangeHealthStatus.DEGRADED
    
    def test_health_status_down(self):
        """DOWN 상태"""
        monitor = HealthMonitor("UPBIT")
        
        # Very high latency
        for _ in range(10):
            monitor.update_latency(600.0)  # > 500ms
        
        assert monitor.get_health_status() == ExchangeHealthStatus.DOWN
    
    def test_health_status_frozen(self):
        """FROZEN 상태"""
        monitor = HealthMonitor("UPBIT")
        
        # Extremely high latency
        for _ in range(10):
            monitor.update_latency(2500.0)  # > 2000ms
        
        assert monitor.get_health_status() == ExchangeHealthStatus.FROZEN
    
    def test_health_status_frozen_by_stale_orderbook(self):
        """Stale orderbook로 FROZEN"""
        monitor = HealthMonitor("UPBIT")
        
        # Orderbook 15초 전
        monitor.update_orderbook_freshness(time.time() - 15.0)
        
        assert monitor.get_health_status() == ExchangeHealthStatus.FROZEN
    
    def test_health_status_transition(self):
        """상태 전환 추적"""
        monitor = HealthMonitor("UPBIT", history_size=10)
        
        # HEALTHY → DEGRADED
        for _ in range(10):
            monitor.update_latency(150.0)
        
        assert monitor.get_health_status() == ExchangeHealthStatus.DEGRADED
        
        # DEGRADED → DOWN (history를 완전히 교체)
        for _ in range(20):  # history_size(10)보다 많이 추가하여 이전 값 제거
            monitor.update_latency(600.0)
        
        assert monitor.get_health_status() == ExchangeHealthStatus.DOWN
    
    def test_should_failover_frozen(self):
        """FROZEN 상태에서 즉시 failover"""
        monitor = HealthMonitor("UPBIT")
        
        # FROZEN 상태
        for _ in range(10):
            monitor.update_latency(2500.0)
        
        # FROZEN 상태는 duration threshold 무시하고 즉시 failover
        # (should_failover 로직에서 FROZEN은 즉시 True 반환)
        assert monitor.get_health_status() == ExchangeHealthStatus.FROZEN
        assert monitor.should_failover() is True
    
    def test_should_failover_high_error_ratio(self):
        """높은 error ratio에서 failover"""
        monitor = HealthMonitor("UPBIT")
        
        # 15% error ratio
        for _ in range(85):
            monitor.update_error(200)
        for _ in range(15):
            monitor.update_error(500)
        
        assert monitor.should_failover() is True
    
    def test_rate_limit_status_update(self):
        """Rate limit 상태 업데이트"""
        monitor = HealthMonitor("UPBIT")
        
        monitor.update_rate_limit_status(remaining=100, near_exhausted_threshold=10)
        assert monitor.metrics.rate_limit_near_exhausted is False
        
        monitor.update_rate_limit_status(remaining=5, near_exhausted_threshold=10)
        assert monitor.metrics.rate_limit_near_exhausted is True
    
    def test_ws_status_update(self):
        """WebSocket 상태 업데이트"""
        monitor = HealthMonitor("UPBIT")
        
        monitor.update_ws_status(connected=True, reconnect_count=0)
        assert monitor.metrics.ws_connected is True
        assert monitor.metrics.ws_reconnect_count == 0
        
        monitor.update_ws_status(connected=False, reconnect_count=3)
        assert monitor.metrics.ws_connected is False
        assert monitor.metrics.ws_reconnect_count == 3
    
    def test_get_metrics_summary(self):
        """메트릭 요약"""
        monitor = HealthMonitor("UPBIT")
        
        monitor.update_latency(50.0)
        monitor.update_error(200)
        monitor.update_orderbook_freshness(time.time())
        
        summary = monitor.get_metrics_summary()
        
        assert summary["exchange"] == "UPBIT"
        assert summary["status"] == "healthy"
        assert summary["latency_ms"] == 50.0
        assert summary["error_ratio"] == 0.0
        assert "orderbook_age_ms" in summary
    
    def test_reset(self):
        """리셋"""
        monitor = HealthMonitor("UPBIT")
        
        # 메트릭 추가
        for _ in range(10):
            monitor.update_latency(500.0)
            monitor.update_error(500)
        
        assert monitor.get_health_status() == ExchangeHealthStatus.DOWN
        
        # 리셋
        monitor.reset()
        
        assert monitor.get_health_status() == ExchangeHealthStatus.HEALTHY
        assert monitor.metrics.total_requests == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
