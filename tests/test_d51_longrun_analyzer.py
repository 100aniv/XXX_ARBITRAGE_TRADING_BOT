# -*- coding: utf-8 -*-
"""
D51 Long-run Analyzer 테스트
"""

import pytest
from arbitrage.monitoring.longrun_analyzer import (
    LongrunAnalyzer,
    LongrunReport,
    AnomalyAlert,
    MetricStats,
)


class TestMetricStats:
    """MetricStats 테스트"""
    
    def test_metric_stats_initialization(self):
        """초기화 테스트"""
        stats = MetricStats()
        assert stats.count == 0
        assert stats.mean == 0.0
        assert stats.min == float('inf')
        assert stats.max == float('-inf')
    
    def test_metric_stats_update(self):
        """값 추가 테스트"""
        stats = MetricStats()
        stats.update(100.0)
        stats.update(200.0)
        stats.update(300.0)
        
        assert stats.count == 3
        assert stats.mean == 200.0
        assert stats.min == 100.0
        assert stats.max == 300.0
    
    def test_metric_stats_stddev(self):
        """표준편차 계산 테스트"""
        stats = MetricStats()
        stats.update(1.0)
        stats.update(2.0)
        stats.update(3.0)
        
        # 평균: 2.0
        # 분산: ((1-2)^2 + (2-2)^2 + (3-2)^2) / 3 = 2/3
        # 표준편차: sqrt(2/3) ≈ 0.816
        assert abs(stats.stddev - 0.816) < 0.01


class TestAnomalyAlert:
    """AnomalyAlert 테스트"""
    
    def test_anomaly_alert_creation(self):
        """이상 징후 생성 테스트"""
        alert = AnomalyAlert(
            severity="WARN",
            category="LOOP_TIME",
            message="Loop time spike",
            value=2000.0,
            threshold=1500.0,
        )
        
        assert alert.severity == "WARN"
        assert alert.category == "LOOP_TIME"
        assert alert.value == 2000.0


class TestLongrunAnalyzer:
    """LongrunAnalyzer 테스트"""
    
    def test_analyzer_initialization(self):
        """초기화 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        assert analyzer.scenario == "S1"
        assert analyzer.thresholds["loop_time_max_ms"] == 1500
    
    def test_analyzer_thresholds_s1(self):
        """S1 임계값 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        thresholds = analyzer.thresholds
        
        assert thresholds["loop_time_max_ms"] == 1500
        assert thresholds["snapshot_none_max"] == 5
        assert thresholds["error_log_max"] == 10
        assert thresholds["trades_opened_min"] == 1
    
    def test_analyzer_thresholds_s2(self):
        """S2 임계값 테스트"""
        analyzer = LongrunAnalyzer(scenario="S2")
        thresholds = analyzer.thresholds
        
        assert thresholds["loop_time_max_ms"] == 1500
        assert thresholds["snapshot_none_max"] == 50
        assert thresholds["error_log_max"] == 50
        assert thresholds["trades_opened_min"] == 10
    
    def test_analyzer_thresholds_s3(self):
        """S3 임계값 테스트"""
        analyzer = LongrunAnalyzer(scenario="S3")
        thresholds = analyzer.thresholds
        
        assert thresholds["loop_time_max_ms"] == 2000
        assert thresholds["snapshot_none_max"] == 200
        assert thresholds["error_log_max"] == 200
        assert thresholds["trades_opened_min"] == 50
    
    def test_analyze_normal_metrics(self):
        """정상 메트릭 분석 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 정상 메트릭 데이터
        log_data = [
            {
                "loop_time_ms": 1000.0,
                "trades_opened": 0,
                "spread_bps": 50.0,
                "snapshot_none": False,
                "guard_rejected": False,
                "guard_stop": False,
                "error_log": False,
                "warning_log": False,
            }
            for _ in range(60)
        ]
        
        # 일부 체결 신호 추가
        log_data[10]["trades_opened"] = 1
        log_data[30]["trades_opened"] = 1
        
        report = analyzer.analyze_metrics_log(log_data)
        
        assert report.loop_time_stats.count == 60
        assert report.loop_time_stats.mean == 1000.0
        assert report.snapshot_none_count == 0
        assert report.error_log_count == 0
        assert len(report.anomalies) == 0
        assert report.overall_status == "OK"
    
    def test_analyze_high_loop_time(self):
        """높은 루프 시간 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 루프 시간이 높은 메트릭 데이터
        log_data = [
            {
                "loop_time_ms": 2000.0,  # 임계값 1500 초과
                "trades_opened": 0,
                "spread_bps": 50.0,
                "snapshot_none": False,
                "guard_rejected": False,
                "guard_stop": False,
                "error_log": False,
                "warning_log": False,
            }
            for _ in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # 루프 시간 스파이크 탐지
        assert len(report.anomalies) > 0
        assert any(a.category == "LOOP_TIME" for a in report.anomalies)
        assert report.overall_status in ["WARN", "FAIL"]
    
    def test_analyze_snapshot_none(self):
        """스냅샷 None 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 스냅샷 None이 많은 메트릭 데이터
        log_data = [
            {
                "loop_time_ms": 1000.0,
                "trades_opened": 0,
                "spread_bps": 50.0,
                "snapshot_none": i < 10,  # 처음 10개가 None
                "guard_rejected": False,
                "guard_stop": False,
                "error_log": False,
                "warning_log": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # 스냅샷 None 과다 탐지
        assert report.snapshot_none_count == 10
        assert len(report.anomalies) > 0
        assert any(a.category == "SNAPSHOT" for a in report.anomalies)
    
    def test_analyze_error_logs(self):
        """에러 로그 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 에러 로그가 많은 메트릭 데이터
        log_data = [
            {
                "loop_time_ms": 1000.0,
                "trades_opened": 0,
                "spread_bps": 50.0,
                "snapshot_none": False,
                "guard_rejected": False,
                "guard_stop": False,
                "error_log": i < 15,  # 처음 15개가 에러
                "warning_log": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # 에러 로그 과다 탐지
        assert report.error_log_count == 15
        assert len(report.anomalies) > 0
        assert any(a.category == "ERROR_LOG" for a in report.anomalies)
        assert report.overall_status == "FAIL"
    
    def test_analyze_low_trades(self):
        """체결 신호 부족 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 체결 신호가 없는 메트릭 데이터
        log_data = [
            {
                "loop_time_ms": 1000.0,
                "trades_opened": 0,  # 체결 없음
                "spread_bps": 50.0,
                "snapshot_none": False,
                "guard_rejected": False,
                "guard_stop": False,
                "error_log": False,
                "warning_log": False,
            }
            for _ in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # 체결 신호 부족 탐지 (총 체결 수가 0)
        # D53: stats.values 합계 계산 (최적화 전과 동일)
        total_trades = sum(report.trades_opened_stats.values) if report.trades_opened_stats.values else 0
        assert total_trades == 0
        assert len(report.anomalies) > 0
        assert any(a.category == "TRADES" for a in report.anomalies)
    
    def test_analyze_guard_stop(self):
        """Guard 세션 중지 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # Guard 세션 중지가 있는 메트릭 데이터
        log_data = [
            {
                "loop_time_ms": 1000.0,
                "trades_opened": 0,
                "spread_bps": 50.0,
                "snapshot_none": False,
                "guard_rejected": False,
                "guard_stop": i == 30,  # 30번째에 세션 중지
                "error_log": False,
                "warning_log": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # Guard 세션 중지 탐지
        assert report.guard_stop_count == 1
        assert len(report.anomalies) > 0
        assert any(a.category == "GUARD" and a.severity == "ERROR" for a in report.anomalies)
        assert report.overall_status == "FAIL"
    
    def test_generate_report_normal(self):
        """정상 리포트 생성 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        log_data = [
            {
                "loop_time_ms": 1000.0,
                "trades_opened": 1 if i % 30 == 0 else 0,
                "spread_bps": 50.0,
                "snapshot_none": False,
                "guard_rejected": False,
                "guard_stop": False,
                "error_log": False,
                "warning_log": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        report_text = analyzer.generate_report(report)
        
        assert "D51 Long-run Analysis Report" in report_text
        assert "Scenario S1" in report_text
        assert "✅" in report_text or "OK" in report_text
    
    def test_generate_report_with_anomalies(self):
        """이상 징후가 있는 리포트 생성 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        log_data = [
            {
                "loop_time_ms": 2000.0,  # 높은 루프 시간
                "trades_opened": 0,
                "spread_bps": 50.0,
                "snapshot_none": False,
                "guard_rejected": False,
                "guard_stop": False,
                "error_log": False,
                "warning_log": False,
            }
            for _ in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        report_text = analyzer.generate_report(report)
        
        assert "D51 Long-run Analysis Report" in report_text
        assert "탐지된 이상 징후" in report_text
        assert ("⚠️" in report_text or "WARN" in report_text)


class TestLongrunReport:
    """LongrunReport 테스트"""
    
    def test_report_initialization(self):
        """리포트 초기화 테스트"""
        report = LongrunReport(scenario="S1", duration_minutes=60)
        
        assert report.scenario == "S1"
        assert report.duration_minutes == 60
        assert report.overall_status == "UNKNOWN"
        assert len(report.anomalies) == 0
    
    def test_report_add_anomaly(self):
        """이상 징후 추가 테스트"""
        report = LongrunReport(scenario="S1", duration_minutes=60)
        
        alert = AnomalyAlert(
            severity="WARN",
            category="LOOP_TIME",
            message="Test warning",
        )
        report.add_anomaly(alert)
        
        assert len(report.anomalies) == 1
        assert report.overall_status == "WARN"
    
    def test_report_status_escalation(self):
        """상태 에스컬레이션 테스트"""
        report = LongrunReport(scenario="S1", duration_minutes=60)
        
        # WARN 추가
        report.add_anomaly(AnomalyAlert(
            severity="WARN",
            category="LOOP_TIME",
            message="Warning",
        ))
        assert report.overall_status == "WARN"
        
        # ERROR 추가 (상태 에스컬레이션)
        report.add_anomaly(AnomalyAlert(
            severity="ERROR",
            category="GUARD",
            message="Error",
        ))
        assert report.overall_status == "FAIL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
