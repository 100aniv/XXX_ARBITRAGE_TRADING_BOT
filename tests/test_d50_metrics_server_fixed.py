"""
D50: MetricsServer 테스트

HTTP 엔드포인트 기능을 검증한다.
"""

import pytest
from unittest.mock import Mock, patch

from arbitrage.monitoring.metrics_collector import MetricsCollector

# FastAPI 선택적 임포트
try:
    from arbitrage.monitoring.metrics_server import MetricsServer
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
@pytest.mark.d50_metrics
class TestD50MetricsServerBasics:
    """D50 MetricsServer 기본 테스트 (D99-16: httpx/starlette 호환 이슈 - async 전환 필요)"""
    
    def test_metrics_server_initialization(self):
        """MetricsServer 초기화"""
        collector = MetricsCollector()
        server = MetricsServer(
            metrics_collector=collector,
            host="127.0.0.1",
            port=8001,
            metrics_format="json",
        )
        
        assert server.metrics_collector == collector
        assert server.host == "127.0.0.1"
        assert server.port == 8001
        assert server.metrics_format == "json"
        assert server.is_running is False
    
    def test_metrics_server_has_routes(self):
        """MetricsServer 라우트 설정"""
        collector = MetricsCollector()
        server = MetricsServer(collector)
        
        # FastAPI 앱에 라우트가 있는지 확인
        routes = [route.path for route in server.app.routes]
        
        assert "/health" in routes
        assert "/metrics" in routes
    
    async def test_metrics_server_health_endpoint(self):
        """GET /health 엔드포인트"""
        import httpx
        
        collector = MetricsCollector()
        collector.update_loop_metrics(1000.0, 0, 5000.0, "rest")
        
        server = MetricsServer(collector)
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["data_source"] == "rest"
            assert "uptime_seconds" in data
    
    def test_metrics_server_metrics_endpoint_json(self):
        """GET /metrics 엔드포인트 (JSON)"""
        import httpx
        
        collector = MetricsCollector()
        collector.update_loop_metrics(1000.0, 1, 5000.0, "rest")
        
        server = MetricsServer(collector, metrics_format="json")
        transport = httpx.ASGITransport(app=server.app)
        client = httpx.Client(transport=transport, base_url="http://test")
        
        response = client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "loop_time_ms" in data
        assert "trades_opened_total" in data
        assert "spread_bps" in data
        assert data["trades_opened_total"] == 1
        
        client.close()
    
    def test_metrics_server_metrics_endpoint_prometheus(self):
        """GET /metrics 엔드포인트 (Prometheus)"""
        import httpx
        
        collector = MetricsCollector()
        collector.update_loop_metrics(1000.0, 1, 5000.0, "rest")
        
        server = MetricsServer(collector, metrics_format="prometheus")
        transport = httpx.ASGITransport(app=server.app)
        client = httpx.Client(transport=transport, base_url="http://test")
        
        response = client.get("/metrics")
        
        assert response.status_code == 200
        text = response.text
        assert "arbitrage_loop_time_ms" in text
        assert "arbitrage_trades_opened_total" in text
        assert "arbitrage_spread_bps" in text
        
        client.close()


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
@pytest.mark.d50_metrics
class TestD50MetricsServerPrometheus:
    """D50 MetricsServer Prometheus 형식 테스트"""
    
    def test_prometheus_format_structure(self):
        """Prometheus 형식 구조"""
        collector = MetricsCollector()
        collector.update_loop_metrics(1000.0, 1, 5000.0, "rest")
        
        server = MetricsServer(collector, metrics_format="prometheus")
        prometheus_text = server._format_prometheus()
        
        # HELP 및 TYPE 라인 확인
        assert "# HELP" in prometheus_text
        assert "# TYPE" in prometheus_text
        
        # 메트릭 라인 확인
        assert "arbitrage_loop_time_ms" in prometheus_text
        assert "arbitrage_trades_opened_total" in prometheus_text
    
    def test_prometheus_format_values(self):
        """Prometheus 형식 값"""
        collector = MetricsCollector()
        collector.update_loop_metrics(1234.56, 5, 7890.12, "ws")
        
        server = MetricsServer(collector, metrics_format="prometheus")
        prometheus_text = server._format_prometheus()
        
        # 값 확인
        assert "arbitrage_loop_time_ms 1234.56" in prometheus_text
        assert "arbitrage_trades_opened_total 5" in prometheus_text
        assert "arbitrage_spread_bps 7890.12" in prometheus_text
        assert 'source="ws"' in prometheus_text


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
@pytest.mark.d50_metrics
class TestD50MetricsServerJSON:
    """D50 MetricsServer JSON 형식 테스트"""
    
    def test_json_format_complete(self):
        """JSON 형식 완전성"""
        import httpx
        
        collector = MetricsCollector()
        collector.update_loop_metrics(1000.0, 2, 5000.0, "rest")
        collector.update_loop_metrics(1100.0, 1, 4500.0, "rest")
        
        server = MetricsServer(collector, metrics_format="json")
        transport = httpx.ASGITransport(app=server.app)
        client = httpx.Client(transport=transport, base_url="http://test")
        
        response = client.get("/metrics")
        data = response.json()
        
        # 모든 필드 확인
        required_fields = [
            "loop_time_ms",
            "loop_time_avg_ms",
            "loop_time_max_ms",
            "loop_time_min_ms",
            "trades_opened_total",
            "trades_opened_recent",
            "spread_bps",
            "spread_avg_bps",
            "data_source",
            "ws_connected",
            "ws_reconnect_count",
            "uptime_seconds",
        ]
        
        for field in required_fields:
            assert field in data
        
        client.close()


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
@pytest.mark.d50_metrics
class TestD50MetricsServerEdgeCases:
    """D50 MetricsServer 엣지 케이스"""
    
    def test_metrics_server_empty_collector(self):
        """빈 MetricsCollector"""
        import httpx
        
        collector = MetricsCollector()
        server = MetricsServer(collector)
        transport = httpx.ASGITransport(app=server.app)
        client = httpx.Client(transport=transport, base_url="http://test")
        
        response = client.get("/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["loop_time_ms"] == 0.0
        
        client.close()
    
    def test_metrics_server_ws_status_true(self):
        """WebSocket 연결 상태 (연결됨)"""
        import httpx
        
        collector = MetricsCollector()
        collector.update_loop_metrics(
            1000.0,
            0,
            5000.0,
            "ws",
            ws_connected=True,
            ws_reconnects=3,
        )
        
        server = MetricsServer(collector)
        transport = httpx.ASGITransport(app=server.app)
        client = httpx.Client(transport=transport, base_url="http://test")
        
        response = client.get("/metrics")
        data = response.json()
        
        assert data["ws_connected"] is True
        assert data["ws_reconnect_count"] == 3
        
        client.close()
    
    def test_metrics_server_ws_status_false(self):
        """WebSocket 연결 상태 (연결 안 됨)"""
        import httpx
        
        collector = MetricsCollector()
        collector.update_loop_metrics(
            1000.0,
            0,
            5000.0,
            "ws",
            ws_connected=False,
            ws_reconnects=0,
        )
        
        server = MetricsServer(collector)
        transport = httpx.ASGITransport(app=server.app)
        client = httpx.Client(transport=transport, base_url="http://test")
        
        response = client.get("/metrics")
        data = response.json()
        
        assert data["ws_connected"] is False
        assert data["ws_reconnect_count"] == 0
        
        client.close()


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
@pytest.mark.d50_metrics
class TestD50MetricsServerLifecycle:
    """D50 MetricsServer 라이프사이클 테스트"""
    
    def test_metrics_server_start_stop(self):
        """서버 시작/종료"""
        collector = MetricsCollector()
        server = MetricsServer(collector)
        
        assert server.is_running is False
        
        # 시작 (스레드 생성)
        server.start()
        assert server.is_running is True
        assert server.server_thread is not None
        
        # 종료
        server.stop()
        assert server.is_running is False
    
    def test_metrics_server_double_start(self):
        """중복 시작 방지"""
        collector = MetricsCollector()
        server = MetricsServer(collector)
        
        server.start()
        first_thread = server.server_thread
        
        # 다시 시작 시도
        server.start()
        
        # 같은 스레드여야 함
        assert server.server_thread == first_thread
        
        server.stop()
