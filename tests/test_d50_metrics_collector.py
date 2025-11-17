"""
D50: MetricsCollector 테스트

메트릭 수집 및 관리 기능을 검증한다.
"""

import pytest
import time
from arbitrage.monitoring.metrics_collector import MetricsCollector


class TestD50MetricsCollectorBasics:
    """D50 MetricsCollector 기본 테스트"""
    
    def test_metrics_collector_initialization(self):
        """MetricsCollector 초기화"""
        collector = MetricsCollector(buffer_size=100)
        
        assert collector.buffer_size == 100
        assert collector.data_source == "rest"
        assert collector.ws_connected is False
        assert collector.ws_reconnect_count == 0
        assert collector.trades_opened_total == 0
    
    def test_metrics_collector_update_single(self):
        """단일 메트릭 업데이트"""
        collector = MetricsCollector()
        
        collector.update_loop_metrics(
            loop_time_ms=1000.0,
            trades_opened=1,
            spread_bps=5000.0,
            data_source="rest",
            ws_status={"connected": False, "reconnects": 0},
        )
        
        metrics = collector.get_metrics()
        
        assert metrics["loop_time_ms"] == 1000.0
        assert metrics["trades_opened_total"] == 1
        assert metrics["spread_bps"] == 5000.0
        assert metrics["data_source"] == "rest"
        assert metrics["ws_connected"] is False
    
    def test_metrics_collector_averaging(self):
        """평균 계산"""
        collector = MetricsCollector(buffer_size=10)
        
        # 5개 루프 추가
        for i in range(5):
            collector.update_loop_metrics(
                loop_time_ms=1000.0 + i * 10,
                trades_opened=0,
                spread_bps=5000.0,
                data_source="rest",
            )
        
        metrics = collector.get_metrics()
        
        # 평균: (1000 + 1010 + 1020 + 1030 + 1040) / 5 = 1020
        assert metrics["loop_time_avg_ms"] == 1020.0
        assert metrics["loop_time_max_ms"] == 1040.0
        assert metrics["loop_time_min_ms"] == 1000.0
    
    def test_metrics_collector_trades_accumulation(self):
        """체결 누적"""
        collector = MetricsCollector()
        
        collector.update_loop_metrics(1000.0, 1, 5000.0, "rest")
        collector.update_loop_metrics(1000.0, 2, 5000.0, "rest")
        collector.update_loop_metrics(1000.0, 0, 5000.0, "rest")
        
        metrics = collector.get_metrics()
        
        assert metrics["trades_opened_total"] == 3
        assert metrics["trades_opened_recent"] == 3
    
    def test_metrics_collector_ws_status(self):
        """WebSocket 상태 추적"""
        collector = MetricsCollector()
        
        # WS 연결 상태
        collector.update_loop_metrics(
            1000.0,
            0,
            5000.0,
            "ws",
            ws_status={"connected": True, "reconnects": 2},
        )
        
        metrics = collector.get_metrics()
        
        assert metrics["data_source"] == "ws"
        assert metrics["ws_connected"] is True
        assert metrics["ws_reconnect_count"] == 2
    
    def test_metrics_collector_buffer_limit(self):
        """버퍼 크기 제한"""
        collector = MetricsCollector(buffer_size=5)
        
        # 10개 루프 추가 (버퍼는 5개만 유지)
        for i in range(10):
            collector.update_loop_metrics(
                loop_time_ms=1000.0 + i,
                trades_opened=0,
                spread_bps=5000.0,
                data_source="rest",
            )
        
        metrics = collector.get_metrics()
        
        # 최근 5개만 유지: 1005, 1006, 1007, 1008, 1009
        assert metrics["loop_time_max_ms"] == 1009.0
        assert metrics["loop_time_min_ms"] == 1005.0
        assert metrics["buffer_usage"] == 5
    
    def test_metrics_collector_get_health(self):
        """헬스 체크 정보"""
        collector = MetricsCollector()
        
        collector.update_loop_metrics(
            1000.0,
            0,
            5000.0,
            "rest",
            ws_status={"connected": False, "reconnects": 0},
        )
        
        health = collector.get_health()
        
        assert health["status"] == "ok"
        assert health["data_source"] == "rest"
        assert health["ws_connected"] is False
        assert "uptime_seconds" in health
    
    def test_metrics_collector_reset(self):
        """메트릭 리셋"""
        collector = MetricsCollector()
        
        collector.update_loop_metrics(1000.0, 5, 5000.0, "rest")
        
        metrics_before = collector.get_metrics()
        assert metrics_before["trades_opened_total"] == 5
        
        collector.reset()
        
        metrics_after = collector.get_metrics()
        assert metrics_after["trades_opened_total"] == 0
        assert len(list(collector.loop_times)) == 0


class TestD50MetricsCollectorEdgeCases:
    """D50 MetricsCollector 엣지 케이스"""
    
    def test_metrics_collector_empty_buffer(self):
        """빈 버퍼 처리"""
        collector = MetricsCollector()
        
        metrics = collector.get_metrics()
        
        assert metrics["loop_time_ms"] == 0.0
        assert metrics["loop_time_avg_ms"] == 0.0
        assert metrics["loop_time_max_ms"] == 0.0
        assert metrics["loop_time_min_ms"] == 0.0
    
    def test_metrics_collector_single_value(self):
        """단일 값 처리"""
        collector = MetricsCollector()
        
        collector.update_loop_metrics(1000.0, 0, 5000.0, "rest")
        
        metrics = collector.get_metrics()
        
        assert metrics["loop_time_ms"] == 1000.0
        assert metrics["loop_time_avg_ms"] == 1000.0
        assert metrics["loop_time_max_ms"] == 1000.0
        assert metrics["loop_time_min_ms"] == 1000.0
    
    def test_metrics_collector_recent_trades(self):
        """최근 1분 체결 횟수"""
        collector = MetricsCollector(buffer_size=100)
        
        # 70개 루프 추가 (최근 60개만 계산)
        for i in range(70):
            trades = 1 if i < 50 else 2  # 처음 50개는 1, 나머지는 2
            collector.update_loop_metrics(1000.0, trades, 5000.0, "rest")
        
        metrics = collector.get_metrics()
        
        # 최근 60개: 마지막 60개 = 인덱스 10~69
        # 인덱스 10~49: 1 (40개)
        # 인덱스 50~69: 2 (20개)
        # 합계: 40*1 + 20*2 = 80
        assert metrics["trades_opened_recent"] == 80
    
    def test_metrics_collector_uptime(self):
        """업타임 계산"""
        collector = MetricsCollector()
        
        collector.update_loop_metrics(1000.0, 0, 5000.0, "rest")
        
        metrics = collector.get_metrics()
        
        # 업타임은 0 이상이어야 함
        assert metrics["uptime_seconds"] >= 0.0
    
    def test_metrics_collector_data_source_switch(self):
        """데이터 소스 전환"""
        collector = MetricsCollector()
        
        # REST에서 시작
        collector.update_loop_metrics(1000.0, 0, 5000.0, "rest")
        assert collector.get_metrics()["data_source"] == "rest"
        
        # WS로 전환
        collector.update_loop_metrics(1000.0, 0, 5000.0, "ws")
        assert collector.get_metrics()["data_source"] == "ws"
        
        # 다시 REST로 전환
        collector.update_loop_metrics(1000.0, 0, 5000.0, "rest")
        assert collector.get_metrics()["data_source"] == "rest"


class TestD50MetricsCollectorConcurrency:
    """D50 MetricsCollector 동시성 테스트"""
    
    def test_metrics_collector_thread_safe_update(self):
        """스레드 안전성 (기본 테스트)"""
        import threading
        
        collector = MetricsCollector()
        
        def update_metrics():
            for i in range(10):
                collector.update_loop_metrics(1000.0, 1, 5000.0, "rest")
        
        threads = [threading.Thread(target=update_metrics) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        metrics = collector.get_metrics()
        
        # 최소 30개 업데이트 (3 스레드 * 10 업데이트)
        assert metrics["trades_opened_total"] >= 30
