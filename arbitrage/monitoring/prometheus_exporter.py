# -*- coding: utf-8 -*-
"""
Prometheus HTTP Exporter (D80-6)

/metrics endpoint를 제공하는 HTTP 서버.
"""

import logging
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Optional

logger = logging.getLogger(__name__)


class MetricsHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for /metrics endpoint.
    """
    
    # Class variable: backend 주입
    backend = None
    
    def do_GET(self):
        """Handle GET request"""
        if self.path == "/metrics":
            self._serve_metrics()
        elif self.path == "/health":
            self._serve_health()
        else:
            self.send_error(404, "Not Found")
    
    def _serve_metrics(self):
        """Serve Prometheus metrics"""
        try:
            if self.backend is None:
                self.send_error(500, "Backend not configured")
                return
            
            metrics_text = self.backend.export_prometheus_text()
            
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.end_headers()
            self.wfile.write(metrics_text.encode("utf-8"))
            
        except Exception as e:
            logger.error(f"[EXPORTER] Error serving metrics: {e}", exc_info=True)
            self.send_error(500, str(e))
    
    def _serve_health(self):
        """Serve health check"""
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    
    def log_message(self, format, *args):
        """Suppress default logging (too verbose)"""
        pass


class PrometheusExporter:
    """
    Prometheus HTTP Exporter.
    
    Features:
    - /metrics endpoint (Prometheus scrape target)
    - /health endpoint (health check)
    - Background thread (non-blocking)
    - Graceful shutdown
    
    Usage:
        from arbitrage.monitoring.prometheus_backend import PrometheusClientBackend
        
        backend = PrometheusClientBackend()
        exporter = PrometheusExporter(backend=backend, port=9100)
        exporter.start()
        
        # ... 메트릭 기록 ...
        
        exporter.stop()
    """
    
    def __init__(self, backend, port: int = 9100):
        """
        Args:
            backend: PrometheusClientBackend 또는 InMemoryMetricsBackend
            port: HTTP 서버 포트 (기본 9100)
        """
        self.backend = backend
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        self._running = False
    
    def start(self) -> None:
        """Start HTTP server (background thread)"""
        if self._running:
            logger.warning(f"[EXPORTER] Already running on port {self.port}")
            return
        
        # Inject backend into handler class
        MetricsHandler.backend = self.backend
        
        # Create server
        try:
            self.server = HTTPServer(("0.0.0.0", self.port), MetricsHandler)
            logger.info(f"[EXPORTER] HTTP server created on port {self.port}")
        except OSError as e:
            logger.error(f"[EXPORTER] Failed to bind port {self.port}: {e}")
            raise
        
        # Start background thread
        self.thread = Thread(target=self._run, daemon=True, name="PrometheusExporter")
        self.thread.start()
        self._running = True
        
        logger.info(
            f"[EXPORTER] Started Prometheus exporter on port {self.port}\n"
            f"  Metrics: http://localhost:{self.port}/metrics\n"
            f"  Health:  http://localhost:{self.port}/health"
        )
    
    def stop(self) -> None:
        """Stop HTTP server"""
        if not self._running:
            return
        
        logger.info(f"[EXPORTER] Stopping HTTP server on port {self.port}")
        
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        
        if self.thread:
            self.thread.join(timeout=5.0)
        
        self._running = False
        logger.info("[EXPORTER] Stopped")
    
    def _run(self) -> None:
        """Run HTTP server (background thread)"""
        try:
            logger.info(f"[EXPORTER] Serving HTTP on port {self.port}")
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"[EXPORTER] Server error: {e}", exc_info=True)
        finally:
            logger.info("[EXPORTER] Server thread exiting")


# =============================================================================
# Convenience Functions
# =============================================================================

_global_exporter: Optional[PrometheusExporter] = None


def start_exporter(backend, port: int = 9100) -> PrometheusExporter:
    """
    Start global Prometheus exporter (convenience function).
    
    Args:
        backend: PrometheusClientBackend 또는 InMemoryMetricsBackend
        port: HTTP 서버 포트
    
    Returns:
        PrometheusExporter 인스턴스
    """
    global _global_exporter
    
    if _global_exporter is not None:
        logger.warning("[EXPORTER] Global exporter already exists, stopping it")
        _global_exporter.stop()
    
    _global_exporter = PrometheusExporter(backend=backend, port=port)
    _global_exporter.start()
    
    return _global_exporter


def stop_exporter() -> None:
    """Stop global Prometheus exporter (convenience function)"""
    global _global_exporter
    
    if _global_exporter is not None:
        _global_exporter.stop()
        _global_exporter = None
