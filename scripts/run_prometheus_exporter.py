#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-1: Prometheus Exporter 실행 스크립트

CrossExchangeMetrics + Alert Metrics를 통합하여
단일 /metrics 엔드포인트로 노출합니다.

Usage:
    python -m scripts.run_prometheus_exporter --port 9100

Features:
    - CrossExchange Trading Metrics (PnL, trades, latency, etc.)
    - Alert Metrics (sent, failed, latency, circuit breaker, etc.)
    - Single HTTP /metrics endpoint
    - Graceful shutdown (Ctrl+C)
"""

import argparse
import logging
import signal
import sys
import time
from typing import Optional

# Prometheus client
from prometheus_client import CollectorRegistry, start_http_server, generate_latest

# CrossExchange Metrics
from arbitrage.monitoring.metrics import (
    init_metrics as init_crossexchange_metrics,
    reset_metrics as reset_crossexchange_metrics,
)

# Alert Metrics
from arbitrage.alerting.metrics_exporter import (
    get_global_alert_metrics,
    reset_global_alert_metrics,
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class PrometheusExporterService:
    """
    통합 Prometheus Exporter 서비스
    
    CrossExchange Metrics + Alert Metrics를 단일 /metrics 엔드포인트로 노출
    """
    
    def __init__(
        self,
        port: int = 9100,
        env: str = "paper",
        universe: str = "top20",
        strategy: str = "topn_arb",
    ):
        """
        Args:
            port: HTTP 서버 포트
            env: 환경 (paper, live)
            universe: Universe (top20, top50)
            strategy: 전략 이름
        """
        self.port = port
        self.env = env
        self.universe = universe
        self.strategy = strategy
        self.registry = CollectorRegistry()
        self._running = False
        self._http_server_started = False
    
    def initialize_metrics(self):
        """메트릭 초기화"""
        logger.info(f"[EXPORTER] Initializing metrics (env={self.env}, universe={self.universe})")
        
        # 1. CrossExchange Metrics 초기화
        init_crossexchange_metrics(
            env=self.env,
            universe=self.universe,
            strategy=self.strategy,
            registry=self.registry,
        )
        logger.info("[EXPORTER] CrossExchange metrics initialized")
        
        # 2. Alert Metrics 초기화 (Prometheus 활성화)
        alert_metrics = get_global_alert_metrics()
        # Alert metrics는 enable_prometheus=False가 기본이지만,
        # global instance는 이미 생성되어 있을 수 있으므로 새로 생성
        reset_global_alert_metrics()
        
        # Prometheus 활성화된 Alert Metrics 생성
        from arbitrage.alerting.metrics_exporter import AlertMetrics
        alert_metrics = AlertMetrics(enable_prometheus=True)
        
        # Global로 설정
        import arbitrage.alerting.metrics_exporter as metrics_module
        metrics_module._global_metrics = alert_metrics
        
        logger.info("[EXPORTER] Alert metrics initialized (Prometheus enabled)")
    
    def start(self):
        """HTTP 서버 시작"""
        if self._http_server_started:
            logger.warning("[EXPORTER] HTTP server already started")
            return
        
        # 메트릭 초기화
        self.initialize_metrics()
        
        # HTTP 서버 시작
        logger.info(f"[EXPORTER] Starting HTTP server on port {self.port}")
        try:
            start_http_server(port=self.port, registry=self.registry)
            self._http_server_started = True
            self._running = True
            
            logger.info(
                f"\n"
                f"{'='*60}\n"
                f"  Prometheus Exporter Started\n"
                f"  Metrics: http://localhost:{self.port}/metrics\n"
                f"  Env: {self.env}\n"
                f"  Universe: {self.universe}\n"
                f"  Strategy: {self.strategy}\n"
                f"{'='*60}\n"
            )
        except OSError as e:
            logger.error(f"[EXPORTER] Failed to start HTTP server: {e}")
            raise
    
    def stop(self):
        """서비스 종료"""
        logger.info("[EXPORTER] Stopping service...")
        self._running = False
        
        # 메트릭 정리
        reset_crossexchange_metrics()
        reset_global_alert_metrics()
        
        logger.info("[EXPORTER] Service stopped")
    
    def run_forever(self):
        """서비스 실행 (무한 루프)"""
        try:
            logger.info("[EXPORTER] Service running. Press Ctrl+C to stop.")
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n[EXPORTER] KeyboardInterrupt received")
        finally:
            self.stop()


def parse_args():
    """커맨드라인 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="D77-1 Prometheus Exporter (CrossExchange + Alert Metrics)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9100,
        help="HTTP server port (default: 9100)",
    )
    parser.add_argument(
        "--env",
        type=str,
        default="paper",
        choices=["paper", "live"],
        help="Environment (default: paper)",
    )
    parser.add_argument(
        "--universe",
        type=str,
        default="top20",
        help="Universe (default: top20)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="topn_arb",
        help="Strategy name (default: topn_arb)",
    )
    
    return parser.parse_args()


def main():
    """메인 함수"""
    args = parse_args()
    
    # Exporter 생성
    exporter = PrometheusExporterService(
        port=args.port,
        env=args.env,
        universe=args.universe,
        strategy=args.strategy,
    )
    
    # Signal handler 등록 (Ctrl+C)
    def signal_handler(sig, frame):
        logger.info("\n[EXPORTER] Signal received, shutting down...")
        exporter.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 서비스 시작
    exporter.start()
    exporter.run_forever()


if __name__ == "__main__":
    main()
