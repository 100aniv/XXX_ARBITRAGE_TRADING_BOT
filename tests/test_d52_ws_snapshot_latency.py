# -*- coding: utf-8 -*-
"""
D52 WebSocket Snapshot Latency 테스트
"""

import pytest
from arbitrage.monitoring.longrun_analyzer import (
    LongrunAnalyzer,
    LongrunReport,
)


class TestWSSnapshotLatency:
    """WebSocket Snapshot Latency 테스트"""
    
    def test_ws_latency_normal(self):
        """정상 WS 지연 시간 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 정상 지연 시간 (< 100ms)
        log_data = [
            {
                "loop_time_ms": 1000.0,
                "trades_opened": 1 if i % 30 == 0 else 0,  # 최소 체결 신호
                "spread_bps": 50.0,
                "snapshot_none": False,
                "guard_rejected": False,
                "guard_stop": False,
                "error_log": False,
                "warning_log": False,
                "ws_latency_ms": 50.0 + (i % 50),  # 50~100ms
                "ws_reconnect": False,
                "ws_message_gap": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # WS 지연 시간 정상
        assert report.ws_latency_stats.mean < 100
        assert report.ws_latency_warn_count == 0
        assert report.ws_latency_error_count == 0
        assert len(report.anomalies) == 0
        assert report.overall_status == "OK"
    
    def test_ws_latency_warning(self):
        """WS 지연 시간 경고 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 경고 수준 지연 시간 (500~2000ms)
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
                "ws_latency_ms": 600.0 + (i % 400),  # 600~1000ms
                "ws_reconnect": False,
                "ws_message_gap": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # WS 지연 시간 경고 탐지
        assert report.ws_latency_warn_count > 0
        assert report.ws_latency_error_count == 0
        assert len(report.anomalies) > 0
        assert any(a.category == "WS_LATENCY" for a in report.anomalies)
    
    def test_ws_latency_error(self):
        """WS 지연 시간 에러 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 에러 수준 지연 시간 (> 2000ms)
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
                "ws_latency_ms": 2500.0 + (i % 500),  # 2500~3000ms
                "ws_reconnect": False,
                "ws_message_gap": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # WS 지연 시간 에러 탐지
        assert report.ws_latency_error_count > 0
        assert len(report.anomalies) > 0
        assert any(a.category == "WS_LATENCY" and a.severity == "ERROR" for a in report.anomalies)
        assert report.overall_status == "FAIL"
    
    def test_ws_reconnect_normal(self):
        """정상 WS 재연결 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 정상 재연결 (< 5회)
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
                "ws_latency_ms": 50.0,
                "ws_reconnect": i in [10, 20, 30],  # 3회 재연결
                "ws_message_gap": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # WS 재연결 정상
        assert report.ws_reconnect_count == 3
        assert len([a for a in report.anomalies if a.category == "WS_RECONNECT"]) == 0
    
    def test_ws_reconnect_warning(self):
        """WS 재연결 경고 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 경고 수준 재연결 (> 10회)
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
                "ws_latency_ms": 50.0,
                "ws_reconnect": i < 15,  # 15회 재연결
                "ws_message_gap": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # WS 재연결 경고 탐지
        assert report.ws_reconnect_count == 15
        assert len(report.anomalies) > 0
        assert any(a.category == "WS_RECONNECT" for a in report.anomalies)
    
    def test_ws_message_gap_normal(self):
        """정상 WS 메시지 갭 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 정상 메시지 갭 (< 5회)
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
                "ws_latency_ms": 50.0,
                "ws_reconnect": False,
                "ws_message_gap": i in [10, 20, 30],  # 3회 갭
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # WS 메시지 갭 정상
        assert report.ws_message_gap_count == 3
        assert len([a for a in report.anomalies if a.category == "WS_MESSAGE_GAP"]) == 0
    
    def test_ws_message_gap_warning(self):
        """WS 메시지 갭 경고 탐지 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 경고 수준 메시지 갭 (> 5회)
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
                "ws_latency_ms": 50.0,
                "ws_reconnect": False,
                "ws_message_gap": i < 8,  # 8회 갭
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # WS 메시지 갭 경고 탐지
        assert report.ws_message_gap_count == 8
        assert len(report.anomalies) > 0
        assert any(a.category == "WS_MESSAGE_GAP" for a in report.anomalies)
    
    def test_ws_combined_metrics(self):
        """WS 복합 메트릭 테스트"""
        analyzer = LongrunAnalyzer(scenario="S2")
        
        # 복합 메트릭 (지연 + 재연결 + 갭)
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
                "ws_latency_ms": 100.0 + (i % 200),  # 100~300ms
                "ws_reconnect": i % 20 == 0,  # 18회 재연결
                "ws_message_gap": i % 30 == 0,  # 12회 갭
            }
            for i in range(360)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # 모든 WS 메트릭 수집
        assert report.ws_latency_stats.count == 360
        assert report.ws_reconnect_count == 18
        assert report.ws_message_gap_count == 12
        
        # 이상 징후 탐지 (S2는 더 높은 임계값)
        # 재연결 > 10회 → 경고
        assert len([a for a in report.anomalies if a.category == "WS_RECONNECT"]) > 0
    
    def test_ws_latency_stats(self):
        """WS 지연 시간 통계 테스트"""
        analyzer = LongrunAnalyzer(scenario="S1")
        
        # 다양한 지연 시간
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
                "ws_latency_ms": float(i * 10),  # 0, 10, 20, ..., 590ms
                "ws_reconnect": False,
                "ws_message_gap": False,
            }
            for i in range(60)
        ]
        
        report = analyzer.analyze_metrics_log(log_data)
        
        # 통계 검증
        assert report.ws_latency_stats.count == 60
        assert report.ws_latency_stats.min == 0.0
        assert report.ws_latency_stats.max == 590.0
        assert 290.0 < report.ws_latency_stats.mean < 300.0  # 평균 약 295ms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
