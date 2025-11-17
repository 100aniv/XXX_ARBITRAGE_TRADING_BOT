#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Metrics Server Module (PHASE D4)
=================================

FastAPI 기반 메트릭 HTTP 서버.

특징:
- /metrics 엔드포인트 (Prometheus 형식)
- /health 엔드포인트
- 실시간 메트릭 계산
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# FastAPI 선택적 import
try:
    from fastapi import FastAPI, Response
    from fastapi.responses import PlainTextResponse
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.warning("[MetricsServer] FastAPI not installed, metrics server disabled")


class MetricsServer:
    """FastAPI 기반 메트릭 서버"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8000, metrics_path: str = "/metrics"):
        """
        Args:
            host: 바인드 호스트
            port: 바인드 포트
            metrics_path: 메트릭 엔드포인트 경로
        """
        self.host = host
        self.port = port
        self.metrics_path = metrics_path
        self.metrics_collector: Optional[Any] = None
        self.app: Optional[FastAPI] = None
        
        if FASTAPI_AVAILABLE:
            self._setup_app()
    
    def _setup_app(self) -> None:
        """FastAPI 앱 설정"""
        if not FASTAPI_AVAILABLE:
            return
        
        self.app = FastAPI(title="Arbitrage Metrics Server")
        
        @self.app.get(self.metrics_path, response_class=PlainTextResponse)
        async def metrics():
            """Prometheus 형식 메트릭"""
            if self.metrics_collector:
                return self.metrics_collector.get_prometheus_text()
            return "# No metrics available\n"
        
        @self.app.get("/health")
        async def health():
            """헬스 체크"""
            return {"status": "ok"}
    
    def set_metrics_collector(self, collector: Any) -> None:
        """메트릭 수집기 설정
        
        Args:
            collector: MetricsCollector 인스턴스
        """
        self.metrics_collector = collector
        logger.info("[MetricsServer] Metrics collector set")
    
    def run(self) -> None:
        """서버 실행"""
        if not FASTAPI_AVAILABLE:
            logger.error("[MetricsServer] FastAPI not available, cannot run server")
            return
        
        if not self.app:
            logger.error("[MetricsServer] App not initialized")
            return
        
        try:
            import uvicorn
            logger.info(f"[MetricsServer] Starting on {self.host}:{self.port}")
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")
        except ImportError:
            logger.error("[MetricsServer] uvicorn not installed")
        except Exception as e:
            logger.error(f"[MetricsServer] Failed to start: {e}")


# 글로벌 메트릭 서버 인스턴스
_metrics_server: Optional[MetricsServer] = None


def get_metrics_server(host: str = "0.0.0.0", port: int = 8000) -> MetricsServer:
    """메트릭 서버 싱글톤 반환
    
    Args:
        host: 바인드 호스트
        port: 바인드 포트
    
    Returns:
        MetricsServer 인스턴스
    """
    global _metrics_server
    if _metrics_server is None:
        _metrics_server = MetricsServer(host=host, port=port)
    return _metrics_server


def reset_metrics_server() -> None:
    """메트릭 서버 리셋 (테스트용)"""
    global _metrics_server
    _metrics_server = None
