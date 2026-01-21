"""
D50: Metrics Server

HTTP 엔드포인트를 통해 메트릭을 노출한다.
"""

import asyncio
import inspect
import logging
import threading
import time
from typing import Optional
import sys

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from arbitrage.monitoring.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class MetricsServer:
    """
    HTTP 기반 메트릭 서버
    
    책임:
    - FastAPI 기반 HTTP 엔드포인트 제공
    - /health, /metrics 라우트
    - 별도 스레드에서 실행
    """
    
    def __init__(
        self,
        metrics_collector: MetricsCollector,
        host: str = "127.0.0.1",
        port: int = 8001,
        metrics_format: str = "json",
    ):
        """
        Args:
            metrics_collector: MetricsCollector 인스턴스
            host: 바인드 호스트 (기본값: 127.0.0.1)
            port: 바인드 포트 (기본값: 8001)
            metrics_format: 메트릭 포맷 ("json" 또는 "prometheus")
        """
        if not HAS_FASTAPI:
            raise ImportError("FastAPI is required for MetricsServer. Install with: pip install fastapi uvicorn")
        
        self.metrics_collector = metrics_collector
        self.host = host
        self.port = port
        self.metrics_format = metrics_format

        if sys.version_info >= (3, 14):
            asyncio.iscoroutinefunction = inspect.iscoroutinefunction

        self.app = FastAPI(title="Arbitrage Metrics Server")
        self._setup_routes()
        
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
    
    def _setup_routes(self) -> None:
        """FastAPI 라우트 설정"""
        
        @self.app.get("/health")
        async def health():
            """헬스 체크 엔드포인트"""
            return JSONResponse(self.metrics_collector.get_health())
        
        @self.app.get("/metrics")
        async def metrics():
            """메트릭 엔드포인트"""
            if self.metrics_format == "prometheus":
                return self._format_prometheus()
            else:
                return JSONResponse(self.metrics_collector.get_metrics())
    
    def _format_prometheus(self) -> str:
        """Prometheus 형식으로 메트릭 포맷팅"""
        metrics = self.metrics_collector.get_metrics()
        
        lines = [
            "# HELP arbitrage_loop_time_ms Recent loop execution time",
            "# TYPE arbitrage_loop_time_ms gauge",
            f"arbitrage_loop_time_ms {metrics['loop_time_ms']:.2f}",
            "",
            "# HELP arbitrage_loop_time_avg_ms Average loop execution time",
            "# TYPE arbitrage_loop_time_avg_ms gauge",
            f"arbitrage_loop_time_avg_ms {metrics['loop_time_avg_ms']:.2f}",
            "",
            "# HELP arbitrage_loop_time_max_ms Maximum loop execution time",
            "# TYPE arbitrage_loop_time_max_ms gauge",
            f"arbitrage_loop_time_max_ms {metrics['loop_time_max_ms']:.2f}",
            "",
            "# HELP arbitrage_loop_time_min_ms Minimum loop execution time",
            "# TYPE arbitrage_loop_time_min_ms gauge",
            f"arbitrage_loop_time_min_ms {metrics['loop_time_min_ms']:.2f}",
            "",
            "# HELP arbitrage_trades_opened_total Total trades opened",
            "# TYPE arbitrage_trades_opened_total counter",
            f"arbitrage_trades_opened_total {metrics['trades_opened_total']}",
            "",
            "# HELP arbitrage_trades_opened_recent Recent trades opened",
            "# TYPE arbitrage_trades_opened_recent gauge",
            f"arbitrage_trades_opened_recent {metrics['trades_opened_recent']}",
            "",
            "# HELP arbitrage_spread_bps Recent spread in basis points",
            "# TYPE arbitrage_spread_bps gauge",
            f"arbitrage_spread_bps {metrics['spread_bps']:.2f}",
            "",
            "# HELP arbitrage_spread_avg_bps Average spread in basis points",
            "# TYPE arbitrage_spread_avg_bps gauge",
            f"arbitrage_spread_avg_bps {metrics['spread_avg_bps']:.2f}",
            "",
            "# HELP arbitrage_data_source Current data source",
            "# TYPE arbitrage_data_source gauge",
            f"arbitrage_data_source{{source=\"{metrics['data_source']}\"}} 1",
            "",
            "# HELP arbitrage_ws_connected WebSocket connection status",
            "# TYPE arbitrage_ws_connected gauge",
            f"arbitrage_ws_connected {1 if metrics['ws_connected'] else 0}",
            "",
            "# HELP arbitrage_ws_reconnect_count WebSocket reconnection count",
            "# TYPE arbitrage_ws_reconnect_count counter",
            f"arbitrage_ws_reconnect_count {metrics['ws_reconnect_count']}",
        ]
        
        return "\n".join(lines)
    
    def start(self) -> None:
        """메트릭 서버 시작 (별도 스레드)"""
        if self.is_running:
            logger.warning("[D50_METRICS_SERVER] Server already running")
            return
        
        self.is_running = True
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="MetricsServer",
        )
        self.server_thread.start()
        logger.info(f"[D50_METRICS_SERVER] Started on {self.host}:{self.port}")
    
    def _run_server(self) -> None:
        """서버 실행 (스레드 내)"""
        try:
            uvicorn.run(
                self.app,
                host=self.host,
                port=self.port,
                log_level="warning",
            )
        except Exception as e:
            logger.error(f"[D50_METRICS_SERVER] Error: {e}")
            self.is_running = False
    
    def stop(self) -> None:
        """메트릭 서버 종료"""
        if not self.is_running:
            logger.warning("[D50_METRICS_SERVER] Server not running")
            return
        
        self.is_running = False
        logger.info("[D50_METRICS_SERVER] Stopped")
