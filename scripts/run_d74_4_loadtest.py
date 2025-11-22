#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D74-4: Multi-Symbol Load Test Runner (Top10/Top20/Top50)
멀티심볼 확장성 검증 - CPU/Memory 측정 포함

Purpose:
- Top10/Top20/Top50 PAPER 로드테스트 수행
- 성능 스케일링 분석 (iteration/sec, latency)
- CPU/Memory 사용량 측정
- 엔진 구조 변경 없음 (D74-3 기반 검증만)

Usage:
    python scripts/run_d74_4_loadtest.py --top-n 10
    python scripts/run_d74_4_loadtest.py --top-n 20 --duration-minutes 15
    python scripts/run_d74_4_loadtest.py --top-n 50 --duration-minutes 10 --log-level INFO
"""

import argparse
import asyncio
import logging
import sys
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from collections import defaultdict

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.base import (
    ArbitrageConfig,
    ExchangeConfig,
    DatabaseConfig,
    RiskConfig,
    TradingConfig,
    MonitoringConfig,
    SessionConfig,
    SymbolUniverseConfig,
    EngineConfig,
    MultiSymbolRiskGuardConfig,
)
from arbitrage.symbol_universe import build_symbol_universe, SymbolUniverseMode
from arbitrage.multi_symbol_engine import create_multi_symbol_runner
from arbitrage.exchanges.paper_exchange import PaperExchange

# psutil 사용 가능 여부 확인
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# logs/ 디렉토리 생성
Path("logs").mkdir(exist_ok=True)

# 로깅 설정 (전역)
log_filename = f'logs/d74_4_top{{top_n}}_loadtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(log_filename.format(top_n="X")),  # 임시
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ResourceMonitor:
    """
    CPU/Memory 사용량 모니터링 클래스
    D74-4 전용 - 가벼운 측정만 수행
    """
    
    def __init__(self, process_pid: Optional[int] = None):
        """
        Args:
            process_pid: 모니터링할 프로세스 PID (None이면 현재 프로세스)
        """
        self.psutil_available = PSUTIL_AVAILABLE
        self.process_pid = process_pid or os.getpid()
        self.process = None
        
        if self.psutil_available:
            try:
                self.process = psutil.Process(self.process_pid)
                logger.info(f"[D74-4_MONITOR] ResourceMonitor initialized with psutil (PID={self.process_pid})")
            except Exception as e:
                logger.warning(f"[D74-4_MONITOR] psutil Process init failed: {e}")
                self.psutil_available = False
        else:
            logger.warning("[D74-4_MONITOR] psutil not available, CPU/Memory monitoring disabled")
    
    def get_snapshot(self) -> Dict[str, Any]:
        """
        현재 리소스 사용량 스냅샷
        
        Returns:
            {cpu_percent, memory_mb, memory_percent} 또는 {}
        """
        if not self.psutil_available or not self.process:
            return {}
        
        try:
            # CPU percent (interval=None이면 non-blocking)
            cpu_percent = self.process.cpu_percent(interval=None)
            
            # Memory info
            mem_info = self.process.memory_info()
            memory_mb = mem_info.rss / (1024 * 1024)  # MB
            memory_percent = self.process.memory_percent()
            
            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(memory_mb, 2),
                "memory_percent": round(memory_percent, 2),
            }
        except Exception as e:
            logger.warning(f"[D74-4_MONITOR] Resource snapshot failed: {e}")
            return {}


def create_d74_4_config(top_n: int, duration_minutes: float = 15.0) -> ArbitrageConfig:
    """
    D74-4 Load Test용 ArbitrageConfig 생성
    
    Args:
        top_n: 심볼 개수 (10, 20, 50)
        duration_minutes: 캠페인 실행 시간 (분)
    
    Returns:
        ArbitrageConfig
    """
    max_runtime = int(duration_minutes * 60)
    
    config = ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(
            upbit_access_key="paper_mock",
            upbit_secret_key="paper_mock",
            binance_api_key="paper_mock",
            binance_secret_key="paper_mock",
        ),
        database=DatabaseConfig(
            redis_port=6380,  # arbitrage-redis 포트
        ),
        risk=RiskConfig(
            max_notional_per_trade=2000.0,
            max_daily_loss=10000.0,
            max_open_trades=1000,  # D74-3 확장 값
        ),
        trading=TradingConfig(
            min_spread_bps=40.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
            close_on_spread_reversal=True,
        ),
        monitoring=MonitoringConfig(
            metrics_enabled=True,
            metrics_interval_seconds=60,
            log_level="INFO",
        ),
        session=SessionConfig(
            mode="paper",
            data_source="paper",
            max_runtime_seconds=max_runtime,
            loop_interval_ms=100,
            state_persistence_enabled=False,
        ),
        universe=SymbolUniverseConfig(
            mode=SymbolUniverseMode.TOP_N,
            top_n=top_n,  # 가변
            base_quote="USDT",
            blacklist=["BUSDUSDT", "USDCUSDT", "TUSDUSDT", "USDPUSDT"],
            min_24h_quote_volume=0.0,
        ),
        engine=EngineConfig(
            mode="multi",
            multi_symbol_enabled=True,
            per_symbol_isolation=True,
        ),
        multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(
            # D74-3 설정 재사용
            max_total_exposure_usd=20000.0,
            max_daily_loss_usd=5000.0,
            emergency_stop_loss_usd=10000.0,
            total_capital_usd=20000.0,
            max_symbol_allocation_pct=0.40,
            max_position_size_usd=2000.0,
            max_position_count=3,
            cooldown_seconds=20.0,
            max_symbol_daily_loss_usd=1000.0,
            circuit_breaker_loss_count=5,
            circuit_breaker_duration=120.0,
        ),
    )
    
    logger.info(f"[D74-4] Config created: TOP_N={top_n}, runtime={max_runtime}s ({duration_minutes:.1f}min)")
    return config


def setup_paper_exchanges() -> tuple[PaperExchange, PaperExchange]:
    """PAPER 모드 거래소 생성"""
    exchange_a = PaperExchange(
        initial_balance={"KRW": 200000000.0, "BTC": 2.0, "ETH": 20.0}
    )
    exchange_b = PaperExchange(
        initial_balance={"USDT": 200000.0, "BTC": 2.0, "ETH": 20.0}
    )
    logger.info("[D74-4] Paper exchanges created")
    return exchange_a, exchange_b


def analyze_paper_exchange_trades(exchange: PaperExchange) -> Dict[str, Any]:
    """PaperExchange 체결 정보 추출"""
    from arbitrage.exchanges.base import OrderStatus
    
    trade_stats = {
        "total_orders": 0,
        "filled_orders": 0,
        "symbols_with_trades": set(),
        "by_symbol": defaultdict(int),
    }
    
    if hasattr(exchange, "_orders"):
        for order_id, order in exchange._orders.items():
            trade_stats["total_orders"] += 1
            
            if hasattr(order, "status") and order.status == OrderStatus.FILLED:
                trade_stats["filled_orders"] += 1
                
                if hasattr(order, "symbol"):
                    symbol = order.symbol
                    trade_stats["symbols_with_trades"].add(symbol)
                    trade_stats["by_symbol"][symbol] += 1
    
    trade_stats["symbols_with_trades"] = list(trade_stats["symbols_with_trades"])
    trade_stats["by_symbol"] = dict(trade_stats["by_symbol"])
    
    return trade_stats


async def run_d74_4_campaign(
    config: ArbitrageConfig,
    top_n: int,
    duration_minutes: float = 15.0,
) -> Dict[str, Any]:
    """
    D74-4 Load Test 캠페인 실행 (CPU/Memory 측정 포함)
    
    Args:
        config: ArbitrageConfig
        top_n: 심볼 개수
        duration_minutes: 실행 시간 (분)
    
    Returns:
        실행 통계 dict
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"D74-4: Multi-Symbol Load Test (Top-{top_n})")
    logger.info(f"Duration: {duration_minutes:.1f} minutes")
    logger.info(f"{'='*80}\n")
    
    # 1. Paper Exchange 생성
    exchange_a, exchange_b = setup_paper_exchanges()
    
    # 2. ResourceMonitor 초기화
    resource_monitor = ResourceMonitor()
    resource_snapshots = []
    
    # 3. MultiSymbolEngineRunner 생성
    logger.info("[D74-4] Creating MultiSymbolEngineRunner...")
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    # 4. Universe 확인
    symbols = runner.universe.get_symbols()
    logger.info(f"[D74-4] Universe symbols ({len(symbols)}): {symbols}")
    
    # 5. 초기 리소스 측정
    initial_snapshot = resource_monitor.get_snapshot()
    if initial_snapshot:
        resource_snapshots.append({"time": 0, **initial_snapshot})
        logger.info(f"[D74-4] Initial resource: {initial_snapshot}")
    
    # 6. 캠페인 실행
    max_runtime = int(duration_minutes * 60)
    logger.info(f"\n[D74-4] Starting {duration_minutes:.1f}min campaign (max_runtime={max_runtime}s)...\n")
    start_time = time.time()
    
    # 7. 비동기 리소스 모니터링 태스크
    async def monitor_resources():
        """주기적으로 리소스 측정 (30초마다)"""
        while True:
            await asyncio.sleep(30)
            elapsed = time.time() - start_time
            snapshot = resource_monitor.get_snapshot()
            if snapshot:
                snapshot["time"] = round(elapsed, 1)
                resource_snapshots.append(snapshot)
                logger.info(f"[D74-4_MONITOR] Resource @ T+{elapsed:.0f}s: {snapshot}")
    
    monitor_task = None
    if resource_monitor.psutil_available:
        monitor_task = asyncio.create_task(monitor_resources())
    
    try:
        stats = await runner.run_multi(
            max_iterations=None,
            max_runtime_seconds=max_runtime
        )
        
        runtime = time.time() - start_time
        stats["actual_runtime_seconds"] = runtime
        stats["actual_runtime_minutes"] = runtime / 60
        
        logger.info(f"\n[D74-4] Campaign completed in {runtime:.2f}s ({runtime/60:.2f}min)")
        
        # 8. 최종 리소스 측정
        final_snapshot = resource_monitor.get_snapshot()
        if final_snapshot:
            final_snapshot["time"] = round(runtime, 1)
            resource_snapshots.append(final_snapshot)
            logger.info(f"[D74-4] Final resource: {final_snapshot}")
        
        # 9. 리소스 통계 계산
        if resource_snapshots:
            cpu_values = [s["cpu_percent"] for s in resource_snapshots if "cpu_percent" in s]
            mem_values = [s["memory_mb"] for s in resource_snapshots if "memory_mb" in s]
            
            stats["resource_metrics"] = {
                "cpu_percent_avg": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0,
                "cpu_percent_max": round(max(cpu_values), 2) if cpu_values else 0,
                "memory_mb_avg": round(sum(mem_values) / len(mem_values), 2) if mem_values else 0,
                "memory_mb_max": round(max(mem_values), 2) if mem_values else 0,
                "snapshots_count": len(resource_snapshots),
                "snapshots": resource_snapshots,
            }
            
            logger.info(f"\n[D74-4] Resource Summary:")
            logger.info(f"  CPU: avg={stats['resource_metrics']['cpu_percent_avg']:.2f}%, max={stats['resource_metrics']['cpu_percent_max']:.2f}%")
            logger.info(f"  Memory: avg={stats['resource_metrics']['memory_mb_avg']:.2f}MB, max={stats['resource_metrics']['memory_mb_max']:.2f}MB")
        
        # 10. RiskCoordinator 통계
        if runner.risk_coordinator:
            final_risk_stats = runner.risk_coordinator.get_stats()
            stats["risk_stats"] = final_risk_stats
        
        # 11. PaperExchange 체결 분석
        trade_stats_a = analyze_paper_exchange_trades(exchange_a)
        trade_stats_b = analyze_paper_exchange_trades(exchange_b)
        
        logger.info(f"[D74-4] Exchange A trades: {trade_stats_a['filled_orders']} filled")
        logger.info(f"[D74-4] Exchange B trades: {trade_stats_b['filled_orders']} filled")
        
        stats["exchange_a_trades"] = trade_stats_a
        stats["exchange_b_trades"] = trade_stats_b
        
        all_traded_symbols = set(trade_stats_a["symbols_with_trades"]) | set(trade_stats_b["symbols_with_trades"])
        stats["total_traded_symbols"] = len(all_traded_symbols)
        stats["traded_symbols_list"] = list(all_traded_symbols)
        stats["total_filled_orders"] = trade_stats_a["filled_orders"] + trade_stats_b["filled_orders"]
        
        # 12. 성능 지표 계산
        if runtime > 0 and stats.get("total_iterations", 0) > 0:
            total_iterations = stats["total_iterations"]
            avg_latency_ms = (runtime / total_iterations) * 1000
            throughput = total_iterations / runtime
            
            stats["performance_metrics"] = {
                "avg_loop_latency_ms": round(avg_latency_ms, 2),
                "throughput_iter_per_sec": round(throughput, 2),
                "total_iterations": total_iterations,
            }
            
            logger.info(f"\n[D74-4] Performance Metrics:")
            logger.info(f"  Avg loop latency: {avg_latency_ms:.2f}ms")
            logger.info(f"  Throughput: {throughput:.2f} iter/sec")
            logger.info(f"  Total iterations: {total_iterations}")
        
        # 13. Top-N 정보 추가
        stats["top_n"] = top_n
        stats["symbol_count"] = len(symbols)
        stats["symbols"] = symbols
        
        return stats
    
    except Exception as e:
        logger.error(f"[D74-4] Campaign failed: {e}", exc_info=True)
        return {
            "error": str(e),
            "runtime_seconds": time.time() - start_time,
            "top_n": top_n,
            "success": False
        }
    
    finally:
        # 모니터링 태스크 취소
        if monitor_task:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass


def print_summary(stats: Dict[str, Any]) -> None:
    """캠페인 결과 요약 출력"""
    top_n = stats.get('top_n', 'X')
    print(f"\n{'='*80}")
    print(f"D74-4: Multi-Symbol Load Test (Top-{top_n}) - Summary")
    print(f"{'='*80}")
    
    if "error" in stats:
        print(f"❌ Campaign failed: {stats['error']}")
        return
    
    # 기본 정보
    print(f"\n[Runtime]")
    print(f"  Duration: {stats.get('actual_runtime_minutes', 0):.2f} min ({stats.get('actual_runtime_seconds', 0):.2f}s)")
    
    # Universe
    symbols = stats.get('symbols', [])
    print(f"\n[Universe]")
    print(f"  Total symbols: {len(symbols)}")
    print(f"  Top-N: {top_n}")
    
    # 체결 정보
    print(f"\n[Trade Execution]")
    print(f"  Total filled orders: {stats.get('total_filled_orders', 0)}")
    print(f"  Traded symbols count: {stats.get('total_traded_symbols', 0)}")
    
    # 성능 지표
    if "performance_metrics" in stats:
        perf = stats["performance_metrics"]
        print(f"\n[Performance]")
        print(f"  Avg loop latency: {perf.get('avg_loop_latency_ms', 0):.2f}ms")
        print(f"  Throughput: {perf.get('throughput_iter_per_sec', 0):.2f} iter/sec")
        print(f"  Total iterations: {perf.get('total_iterations', 0)}")
    
    # 리소스 사용량
    if "resource_metrics" in stats:
        res = stats["resource_metrics"]
        print(f"\n[Resource Usage]")
        print(f"  CPU: avg={res.get('cpu_percent_avg', 0):.2f}%, max={res.get('cpu_percent_max', 0):.2f}%")
        print(f"  Memory: avg={res.get('memory_mb_avg', 0):.2f}MB, max={res.get('memory_mb_max', 0):.2f}MB")
        print(f"  Snapshots: {res.get('snapshots_count', 0)}")
    else:
        print(f"\n[Resource Usage]")
        print(f"  (psutil not available - monitoring disabled)")
    
    print(f"\n{'='*80}\n")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="D74-4 Multi-Symbol Load Test")
    parser.add_argument(
        "--top-n",
        type=int,
        required=True,
        choices=[10, 20, 50],
        help="Number of symbols to test (10, 20, or 50)"
    )
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=15.0,
        help="Campaign duration in minutes (default: 15.0)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # 로그 파일명 업데이트
    global log_filename
    log_filename = f'logs/d74_4_top{args.top_n}_loadtest_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # 로그 핸들러 재설정
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(args.log_level)
    root_logger.addHandler(logging.FileHandler(log_filename))
    root_logger.addHandler(logging.StreamHandler())
    
    logger.info(f"[D74-4] Starting Load Test - Top-{args.top_n}")
    logger.info(f"[D74-4] Log file: {log_filename}")
    logger.info(f"[D74-4] psutil available: {PSUTIL_AVAILABLE}")
    
    # Config 생성
    config = create_d74_4_config(
        top_n=args.top_n,
        duration_minutes=args.duration_minutes
    )
    
    # 캠페인 실행
    stats = asyncio.run(run_d74_4_campaign(
        config=config,
        top_n=args.top_n,
        duration_minutes=args.duration_minutes,
    ))
    
    # 요약 출력
    print_summary(stats)
    
    # 성공 여부 반환
    if "error" in stats:
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
