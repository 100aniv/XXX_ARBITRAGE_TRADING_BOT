"""
D77-1: Prometheus Exporter 통합 테스트

Tests:
1. CrossExchange Metrics + Alert Metrics 통합 노출
2. /metrics 엔드포인트 형식 검증
3. Prometheus registry 중복 등록 방지
4. 메트릭 값 업데이트 및 확인
"""

import pytest
import time
from prometheus_client import CollectorRegistry, generate_latest

# CrossExchange Metrics
from arbitrage.monitoring.metrics import (
    init_metrics,
    record_pnl,
    record_trade,
    record_round_trip,
    record_win_rate,
    record_loop_latency,
    record_guard_trigger,
    record_alert as record_crossexchange_alert,
    get_metrics_text,
    reset_metrics,
)

# Alert Metrics
from arbitrage.alerting.metrics_exporter import (
    AlertMetrics,
    get_global_alert_metrics,
    reset_global_alert_metrics,
)

# Alerting 기본 타입
from arbitrage.alerting import (
    AlertRecord,
    AlertSeverity,
    AlertSource,
)


@pytest.fixture(autouse=True)
def cleanup():
    """각 테스트 전후로 메트릭 리셋"""
    reset_metrics()
    reset_global_alert_metrics()
    yield
    reset_metrics()
    reset_global_alert_metrics()


class TestPrometheusExporterIntegration:
    """Prometheus Exporter 통합 테스트"""
    
    def test_crossexchange_and_alert_metrics_coexist(self):
        """CrossExchange + Alert metrics가 동일 registry에서 공존"""
        # Separate registries (권장)
        crossexchange_registry = CollectorRegistry()
        alert_registry = CollectorRegistry()
        
        # 1. CrossExchange Metrics 초기화
        init_metrics("paper", "top20", "topn_arb", registry=crossexchange_registry)
        
        # 2. Alert Metrics 초기화 (Prometheus 활성화, custom registry)
        alert_metrics = AlertMetrics(enable_prometheus=True, registry=alert_registry)
        
        # 3. CrossExchange 메트릭 기록
        record_pnl(1000.0)
        record_trade("entry")
        record_round_trip()
        
        # 4. Alert 메트릭 기록
        alert_metrics.record_sent("FX-001", "telegram")
        alert_metrics.record_failed("EX-001", "telegram", "timeout")
        alert_metrics.record_delivery_latency("telegram", 0.150)
        
        # 5. CrossExchange metrics 텍스트 생성
        crossexchange_text = get_metrics_text()
        
        # 6. CrossExchange 메트릭 존재 확인
        assert "arb_topn_pnl_total" in crossexchange_text
        assert "arb_topn_trades_total" in crossexchange_text
        assert "arb_topn_round_trips_total" in crossexchange_text
        
        # Prometheus 텍스트 생성 (custom registry 사용!)
        metrics_text = generate_latest(alert_registry).decode("utf-8")
        
        # 메트릭 이름 확인
        assert "alert_sent_total" in metrics_text
        assert "alert_failed_total" in metrics_text
        assert "alert_delivery_latency_seconds" in metrics_text
    
    def test_alert_metrics_prometheus_format(self):
        """Alert Metrics Prometheus 형식 검증"""
        # Custom registry 사용 (중복 방지)
        registry = CollectorRegistry()
        
        # Alert Metrics 초기화 (Prometheus 활성화)
        alert_metrics = AlertMetrics(enable_prometheus=True, registry=registry)
        
        # 메트릭 기록
        alert_metrics.record_sent("FX-001", "telegram")
        alert_metrics.record_sent("FX-001", "telegram")
        alert_metrics.record_failed("EX-001", "telegram", "timeout")
        alert_metrics.record_fallback("telegram", "email")
        alert_metrics.record_retry("RG-001")
        alert_metrics.record_dlq("WS-001", "max_retries")
        alert_metrics.record_delivery_latency("telegram", 0.100)
        alert_metrics.record_delivery_latency("telegram", 0.250)
        alert_metrics.set_notifier_status("telegram", "available", 1.0)
        
        # Prometheus 텍스트 생성 (custom registry 사용!)
        metrics_text = generate_latest(registry).decode("utf-8")
        
        # 메트릭 이름 확인
        assert "alert_sent_total" in metrics_text
        assert "alert_failed_total" in metrics_text
        assert "alert_fallback_total" in metrics_text
        assert "alert_retry_total" in metrics_text
        assert "alert_dlq_total" in metrics_text
        assert "alert_delivery_latency_seconds" in metrics_text
        assert "notifier_available" in metrics_text
        
        # 레이블 확인
        assert 'rule_id="FX-001"' in metrics_text
        assert 'notifier="telegram"' in metrics_text
        assert 'reason="timeout"' in metrics_text
        assert 'from_notifier="telegram"' in metrics_text
        assert 'to_notifier="email"' in metrics_text
    
    def test_no_duplicate_registration_error(self):
        """중복 등록 에러 방지 테스트"""
        # 첫 번째 registry
        registry1 = CollectorRegistry()
        alert_metrics1 = AlertMetrics(enable_prometheus=True, registry=registry1)
        alert_metrics1.record_sent("TEST-001", "telegram")
        
        # 두 번째 registry (별도)
        registry2 = CollectorRegistry()
        alert_metrics2 = AlertMetrics(enable_prometheus=True, registry=registry2)
        alert_metrics2.record_sent("TEST-002", "slack")
        
        # 메트릭 생성 성공 확인
        metrics_text = generate_latest(registry2).decode("utf-8")
        
        assert "alert_sent_total" in metrics_text
    
    def test_crossexchange_metrics_update_and_verify(self):
        """CrossExchange 메트릭 값 업데이트 및 검증"""
        registry = CollectorRegistry()
        init_metrics("paper", "top20", "topn_arb", registry=registry)
        
        # 메트릭 기록
        record_pnl(500.0)
        record_pnl(1500.0)  # 최종값
        record_trade("entry")
        record_trade("entry")
        record_trade("exit")
        record_round_trip()
        record_win_rate(3, 1)  # 75% 승률
        record_loop_latency(0.005)  # 5ms
        record_guard_trigger("exchange")
        record_crossexchange_alert("P1", "health_monitor")
        
        # 메트릭 텍스트 생성
        text = get_metrics_text()
        
        # 값 확인
        assert "1500.0" in text  # PnL
        assert "75.0" in text  # Win rate
        assert 'trade_type="entry"' in text
        assert 'trade_type="exit"' in text
        assert 'guard_type="exchange"' in text
        assert 'severity="P1"' in text
        assert 'source="health_monitor"' in text
    
    def test_alert_metrics_stats_collection(self):
        """Alert Metrics 통계 수집 테스트"""
        alert_metrics = AlertMetrics(enable_prometheus=False)  # In-memory only
        
        # 메트릭 기록
        alert_metrics.record_sent("FX-001", "telegram")
        alert_metrics.record_sent("FX-001", "telegram")
        alert_metrics.record_failed("EX-001", "telegram", "timeout")
        alert_metrics.record_delivery_latency("telegram", 0.100)
        alert_metrics.record_delivery_latency("telegram", 0.200)
        alert_metrics.record_delivery_latency("telegram", 0.300)
        
        # 통계 가져오기
        stats = alert_metrics.get_stats()
        
        # 검증
        assert stats["counters"]["sent:FX-001:telegram"] == 2
        assert stats["counters"]["failed:EX-001:telegram:timeout"] == 1
        assert stats["histograms"]["latency:telegram"]["count"] == 3
        assert stats["histograms"]["latency:telegram"]["p50"] == 0.200
    
    def test_global_alert_metrics_singleton(self):
        """Global alert metrics singleton 패턴 테스트"""
        # Global metrics는 enable_prometheus=False 모드로 사용 (registry 충돌 방지)
        # 첫 번째 호출
        metrics1 = get_global_alert_metrics()
        metrics1.record_sent("TEST-001", "telegram")
        
        # 두 번째 호출 (같은 인스턴스)
        metrics2 = get_global_alert_metrics()
        
        assert metrics1 is metrics2
        
        # 통계 확인 (같은 인스턴스이므로 공유)
        stats = metrics2.get_stats()
        assert stats["counters"]["sent:TEST-001:telegram"] == 1
    
    def test_metrics_clear_and_reset(self):
        """메트릭 clear 및 reset 테스트"""
        alert_metrics = AlertMetrics(enable_prometheus=False)
        
        # 메트릭 기록
        alert_metrics.record_sent("TEST-001", "telegram")
        alert_metrics.record_failed("TEST-002", "slack", "timeout")
        
        # Clear
        alert_metrics.clear()
        
        # 통계 확인 (빈 상태)
        stats = alert_metrics.get_stats()
        assert len(stats["counters"]) == 0
        assert len(stats["gauges"]) == 0
        assert len(stats["histograms"]) == 0


class TestPrometheusExporterPerformance:
    """Prometheus Exporter 성능 테스트"""
    
    def test_high_volume_metrics_recording(self):
        """대량 메트릭 기록 성능 테스트"""
        alert_metrics = AlertMetrics(enable_prometheus=False)  # 빠른 테스트
        
        start_time = time.time()
        
        # 10,000개 메트릭 기록
        for i in range(10000):
            alert_metrics.record_sent(f"RULE-{i % 10}", "telegram")
            alert_metrics.record_delivery_latency("telegram", 0.100)
        
        elapsed = time.time() - start_time
        
        # 10,000개 기록에 1초 미만 소요 (성능 검증)
        assert elapsed < 1.0, f"Too slow: {elapsed:.3f}s for 10K metrics"
        
        # 통계 확인
        stats = alert_metrics.get_stats()
        total_sent = sum(
            v for k, v in stats["counters"].items() if k.startswith("sent:")
        )
        assert total_sent == 10000


class TestPrometheusExporterEdgeCases:
    """Prometheus Exporter 엣지 케이스 테스트"""
    
    def test_metrics_without_prometheus_client(self):
        """prometheus_client 없이 메트릭 기록 (fallback)"""
        # enable_prometheus=False로 In-memory 모드 테스트
        alert_metrics = AlertMetrics(enable_prometheus=False)
        
        # 메트릭 기록 (에러 없어야 함)
        alert_metrics.record_sent("TEST-001", "telegram")
        alert_metrics.record_failed("TEST-002", "slack", "timeout")
        
        # In-memory 통계 확인
        stats = alert_metrics.get_stats()
        assert stats["counters"]["sent:TEST-001:telegram"] == 1
        assert stats["counters"]["failed:TEST-002:slack:timeout"] == 1
    
    def test_empty_metrics_text(self):
        """빈 메트릭 텍스트 처리"""
        # 초기화 없이 텍스트 가져오기
        reset_metrics()
        text = get_metrics_text()
        
        # 빈 문자열 또는 최소 형식
        assert text == ""
    
    def test_metrics_with_special_characters_in_labels(self):
        """특수 문자 포함 레이블 처리"""
        alert_metrics = AlertMetrics(enable_prometheus=False)
        
        # 특수 문자 포함 레이블 (Prometheus는 자동 escape)
        alert_metrics.record_sent("FX-001:special", "telegram")
        alert_metrics.record_failed("EX-001/slash", "slack", "timeout:error")
        
        # 통계 확인 (에러 없이 기록되어야 함)
        stats = alert_metrics.get_stats()
        assert "sent:FX-001:special:telegram" in stats["counters"]
        assert "failed:EX-001/slash:slack:timeout:error" in stats["counters"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
