# -*- coding: utf-8 -*-
"""
D80-6: FX Multi-Source Monitoring Demo

MultiSourceFxRateProvider + Prometheus Exporter 통합 데모.

Usage:
    python scripts/run_fx_monitoring_demo.py [--duration-minutes 10] [--port 9100]

실행 후:
    1. Prometheus 스크래핑: http://localhost:9100/metrics
    2. Grafana 대시보드에서 FX metrics 확인
"""

import argparse
import logging
import time
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.common.currency import MultiSourceFxRateProvider, Currency
from arbitrage.monitoring.cross_exchange_metrics import CrossExchangeMetrics
from arbitrage.monitoring.prometheus_backend import PrometheusClientBackend
from arbitrage.monitoring.prometheus_exporter import start_exporter, stop_exporter

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="FX Multi-Source Monitoring Demo")
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=10,
        help="Demo duration (minutes, default: 10)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9100,
        help="Prometheus exporter port (default: 9100)"
    )
    parser.add_argument(
        "--enable-websocket",
        action="store_true",
        help="Enable WebSocket clients (requires websocket-client library)"
    )
    args = parser.parse_args()
    
    duration_seconds = args.duration_minutes * 60
    
    logger.info("=" * 80)
    logger.info("D80-6: FX Multi-Source Monitoring Demo")
    logger.info("=" * 80)
    logger.info(f"Duration: {args.duration_minutes} minutes ({duration_seconds}s)")
    logger.info(f"Exporter Port: {args.port}")
    logger.info(f"WebSocket: {'Enabled' if args.enable_websocket else 'Disabled (HTTP-only)'}")
    logger.info("")
    logger.info("Endpoints:")
    logger.info(f"  - Metrics: http://localhost:{args.port}/metrics")
    logger.info(f"  - Health:  http://localhost:{args.port}/health")
    logger.info("")
    logger.info("Prometheus scrape config:")
    logger.info(f"  - job_name: 'arbitrage_fx'")
    logger.info(f"    static_configs:")
    logger.info(f"      - targets: ['host.docker.internal:{args.port}']")
    logger.info("")
    logger.info("=" * 80)
    logger.info("")
    
    # 1. Prometheus Backend 초기화
    logger.info("[SETUP] Initializing Prometheus backend...")
    backend = PrometheusClientBackend()
    
    # 2. CrossExchangeMetrics 초기화
    logger.info("[SETUP] Initializing CrossExchangeMetrics...")
    metrics = CrossExchangeMetrics(prometheus_backend=backend)
    
    # 3. Prometheus Exporter 시작
    logger.info(f"[SETUP] Starting Prometheus exporter on port {args.port}...")
    exporter = start_exporter(backend=backend, port=args.port)
    
    # 4. MultiSourceFxRateProvider 초기화
    logger.info("[SETUP] Initializing MultiSourceFxRateProvider...")
    fx_provider = MultiSourceFxRateProvider(
        enable_websocket=args.enable_websocket,
        cache_ttl_seconds=3.0
    )
    
    if args.enable_websocket:
        logger.info("[SETUP] Starting WebSocket clients...")
        fx_provider.start()
    else:
        logger.info("[SETUP] WebSocket disabled, using HTTP-only mode")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("DEMO RUNNING")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        start_time = time.time()
        iteration = 0
        
        while time.time() - start_time < duration_seconds:
            iteration += 1
            
            # FX rate 조회 (캐시 갱신 트리거)
            try:
                usdt_usd = fx_provider.get_rate(Currency.USDT, Currency.USD)
                usdt_krw = fx_provider.get_rate(Currency.USDT, Currency.KRW)
                
                # Source stats 조회
                source_stats = fx_provider.get_source_stats()
                
                # 유효 소스 개수 계산
                source_count = sum(
                    1 for stats in source_stats.values()
                    if stats["connected"] and stats["rate"] is not None
                )
                
                # Outlier count 조회
                outlier_count = fx_provider.get_outlier_count_total()
                
                # Metrics 기록
                metrics.record_fx_multi_source_metrics(
                    source_count=source_count,
                    outlier_count=outlier_count,
                    median_rate=float(usdt_usd),
                    source_stats=source_stats
                )
                
                # 10초마다 로그 출력
                if iteration % 10 == 0:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[{elapsed:6.1f}s] USDT→USD={usdt_usd:.6f}, USDT→KRW={usdt_krw:.2f}, "
                        f"Sources={source_count}/3, Outliers={outlier_count}"
                    )
                    logger.info(f"         Source Stats: {source_stats}")
                
            except Exception as e:
                logger.error(f"[ERROR] Failed to update FX metrics: {e}", exc_info=True)
            
            # 1초 대기
            time.sleep(1.0)
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("DEMO COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Total iterations: {iteration}")
        logger.info(f"Total duration: {time.time() - start_time:.1f}s")
        logger.info("")
        
    except KeyboardInterrupt:
        logger.info("")
        logger.info("[STOP] Keyboard interrupt received")
    
    finally:
        # Cleanup
        logger.info("[CLEANUP] Stopping WebSocket clients...")
        if args.enable_websocket:
            fx_provider.stop()
        
        logger.info("[CLEANUP] Stopping Prometheus exporter...")
        stop_exporter()
        
        logger.info("[CLEANUP] Done")
        logger.info("")


if __name__ == "__main__":
    main()
