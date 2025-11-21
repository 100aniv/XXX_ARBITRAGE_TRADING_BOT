#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D74-1: Performance Micro-Benchmarks

Purpose:
- Loop latency 측정 (MultiSymbolEngineRunner 기반)
- Redis roundtrip latency 측정
- 성능 baseline 수립

Usage:
    python scripts/benchmark_d74_performance.py --case loop --symbols 10 --iterations 200
    python scripts/benchmark_d74_performance.py --case redis --requests 1000
    python scripts/benchmark_d74_performance.py --case summary
"""

import argparse
import asyncio
import logging
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import json

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
from arbitrage.symbol_universe import SymbolUniverseMode
from arbitrage.multi_symbol_engine import create_multi_symbol_runner
from arbitrage.exchanges.paper_exchange import PaperExchange

# 로깅 설정
logging.basicConfig(
    level=logging.WARNING,  # 벤치마크 중에는 WARNING 이상만 출력
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)
logger = logging.getLogger(__name__)


def create_benchmark_config(num_symbols: int = 10) -> ArbitrageConfig:
    """
    벤치마크용 minimal config 생성
    
    Args:
        num_symbols: TOP_N 심볼 수
    
    Returns:
        ArbitrageConfig
    """
    return ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(
            upbit_access_key="paper_mock",
            upbit_secret_key="paper_mock",
            binance_api_key="paper_mock",
            binance_secret_key="paper_mock",
        ),
        database=DatabaseConfig(),
        risk=RiskConfig(
            max_notional_per_trade=1000.0,
            max_daily_loss=5000.0,
            max_open_trades=10,
        ),
        trading=TradingConfig(
            min_spread_bps=40.0,  # > 1.5 * (10 + 10 + 5) = 37.5
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
        ),
        monitoring=MonitoringConfig(
            metrics_enabled=False,  # 벤치마크 중에는 비활성화
            metrics_interval_seconds=9999,
            log_level="WARNING",
        ),
        session=SessionConfig(
            mode="paper",
            data_source="paper",
            max_runtime_seconds=999,
            loop_interval_ms=100,  # 빠른 iteration
            state_persistence_enabled=False,
        ),
        universe=SymbolUniverseConfig(
            mode=SymbolUniverseMode.TOP_N,
            top_n=num_symbols,
            base_quote="USDT",
            blacklist=[],
            min_24h_quote_volume=0.0,
        ),
        engine=EngineConfig(
            mode="multi",
            multi_symbol_enabled=True,
            per_symbol_isolation=True,
        ),
        multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(
            max_total_exposure_usd=10000.0,
            max_daily_loss_usd=1000.0,
            emergency_stop_loss_usd=2000.0,
            total_capital_usd=10000.0,
            max_symbol_allocation_pct=0.30,
            max_position_size_usd=1000.0,
            max_position_count=2,
            cooldown_seconds=30.0,
            max_symbol_daily_loss_usd=500.0,
            circuit_breaker_loss_count=3,
            circuit_breaker_duration=120.0,
        ),
    )


async def benchmark_loop_latency(
    num_symbols: int = 10,
    num_iterations: int = 200,
) -> Dict[str, Any]:
    """
    MultiSymbolEngineRunner 기반 loop latency 측정
    
    Args:
        num_symbols: 심볼 수
        num_iterations: iteration 수
    
    Returns:
        {
            "case": "loop",
            "params": {...},
            "metrics": {...},
            "timestamp": "...",
        }
    """
    print(f"\n[D74-1] Loop Latency Benchmark: symbols={num_symbols}, iterations={num_iterations}")
    
    config = create_benchmark_config(num_symbols=num_symbols)
    
    # Paper Exchange 생성
    exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0})
    exchange_b = PaperExchange(initial_balance={"USDT": 100000.0})
    
    # Runner 생성
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    symbols = runner.universe.get_symbols()
    print(f"  Symbols: {symbols}")
    
    # 짧은 캠페인 실행 (latency 측정)
    start_time = time.perf_counter()
    
    stats = await runner.run_multi(
        max_iterations=num_iterations,
        max_runtime_seconds=60  # 최대 1분
    )
    
    total_time = (time.perf_counter() - start_time) * 1000  # ms
    
    # 메트릭 계산 (근사치)
    # 실제로는 runner 내부에서 iteration별 timestamp를 기록해야 정확하지만,
    # 여기서는 전체 시간 / iteration 수로 평균 계산
    avg_latency_ms = total_time / max(num_iterations, 1)
    
    metrics = {
        "latency_avg_ms": round(avg_latency_ms, 2),
        "total_time_ms": round(total_time, 2),
        "iterations": num_iterations,
        "symbols": len(symbols),
        "throughput_decisions_per_sec": round(num_iterations / (total_time / 1000), 2),
    }
    
    # p95/p99는 실제 iteration별 측정이 필요 (TODO: D74-2+)
    # 여기서는 placeholder
    metrics["latency_p95_ms"] = "TBD"
    metrics["latency_p99_ms"] = "TBD"
    
    print(f"  Results:")
    print(f"    Avg latency: {metrics['latency_avg_ms']}ms")
    print(f"    Total time: {metrics['total_time_ms']}ms")
    print(f"    Throughput: {metrics['throughput_decisions_per_sec']} decisions/sec")
    
    return {
        "case": "loop",
        "params": {
            "symbols": num_symbols,
            "iterations": num_iterations,
        },
        "metrics": metrics,
        "timestamp": datetime.now().isoformat(),
    }


async def benchmark_redis_latency(num_requests: int = 1000) -> Dict[str, Any]:
    """
    Redis roundtrip latency 측정 (PING)
    
    Args:
        num_requests: 요청 수
    
    Returns:
        {
            "case": "redis",
            "params": {...},
            "metrics": {...},
            "timestamp": "...",
        }
    """
    print(f"\n[D74-1] Redis Latency Benchmark: requests={num_requests}")
    
    try:
        import aioredis
    except ImportError:
        print("  ⚠️  aioredis not installed, using mock results")
        return {
            "case": "redis",
            "params": {"requests": num_requests},
            "metrics": {
                "latency_avg_ms": "N/A (aioredis not installed)",
                "latency_p95_ms": "N/A",
                "latency_p99_ms": "N/A",
            },
            "timestamp": datetime.now().isoformat(),
        }
    
    # Redis 연결 (로컬 Docker 기준)
    try:
        redis = await aioredis.create_redis_pool('redis://localhost:6379')
    except Exception as e:
        print(f"  ⚠️  Redis connection failed: {e}")
        return {
            "case": "redis",
            "params": {"requests": num_requests},
            "metrics": {
                "latency_avg_ms": f"N/A (connection failed: {e})",
                "latency_p95_ms": "N/A",
                "latency_p99_ms": "N/A",
            },
            "timestamp": datetime.now().isoformat(),
        }
    
    latencies: List[float] = []
    
    # PING 반복 측정
    for _ in range(num_requests):
        start = time.perf_counter()
        await redis.ping()
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)
    
    redis.close()
    await redis.wait_closed()
    
    # 통계 계산
    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
    p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
    
    metrics = {
        "latency_avg_ms": round(avg_latency, 3),
        "latency_p95_ms": round(p95_latency, 3),
        "latency_p99_ms": round(p99_latency, 3),
        "requests": num_requests,
    }
    
    print(f"  Results:")
    print(f"    Avg latency: {metrics['latency_avg_ms']}ms")
    print(f"    P95 latency: {metrics['latency_p95_ms']}ms")
    print(f"    P99 latency: {metrics['latency_p99_ms']}ms")
    
    return {
        "case": "redis",
        "params": {"requests": num_requests},
        "metrics": metrics,
        "timestamp": datetime.now().isoformat(),
    }


async def benchmark_summary() -> Dict[str, Any]:
    """
    여러 케이스를 조합 실행 후 요약
    
    Returns:
        {
            "case": "summary",
            "results": [...],
            "timestamp": "...",
        }
    """
    print(f"\n{'='*80}")
    print("D74-1 Performance Benchmark Summary")
    print(f"{'='*80}\n")
    
    results = []
    
    # Loop latency (5/10/20 symbols)
    for num_symbols in [5, 10, 20]:
        result = await benchmark_loop_latency(
            num_symbols=num_symbols,
            num_iterations=200
        )
        results.append(result)
    
    # Redis latency
    redis_result = await benchmark_redis_latency(num_requests=500)
    results.append(redis_result)
    
    # 요약 출력
    print(f"\n{'='*80}")
    print("Summary")
    print(f"{'='*80}\n")
    
    for result in results:
        case = result["case"]
        metrics = result["metrics"]
        
        if case == "loop":
            params = result["params"]
            print(f"Loop Latency (symbols={params['symbols']}, iterations={params['iterations']}):")
            print(f"  Avg: {metrics['latency_avg_ms']}ms")
            print(f"  Throughput: {metrics['throughput_decisions_per_sec']} decisions/sec")
        
        elif case == "redis":
            print(f"Redis Latency (requests={result['params']['requests']}):")
            print(f"  Avg: {metrics['latency_avg_ms']}ms")
            print(f"  P95: {metrics['latency_p95_ms']}ms")
            print(f"  P99: {metrics['latency_p99_ms']}ms")
        
        print()
    
    return {
        "case": "summary",
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="D74-1 Performance Micro-Benchmarks")
    parser.add_argument(
        "--case",
        type=str,
        choices=["loop", "redis", "summary"],
        default="summary",
        help="Benchmark case (default: summary)"
    )
    parser.add_argument(
        "--symbols",
        type=int,
        default=10,
        help="Number of symbols for loop benchmark (default: 10)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Number of iterations for loop benchmark (default: 200)"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=1000,
        help="Number of requests for Redis benchmark (default: 1000)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (optional)"
    )
    
    args = parser.parse_args()
    
    # 벤치마크 실행
    if args.case == "loop":
        result = asyncio.run(benchmark_loop_latency(
            num_symbols=args.symbols,
            num_iterations=args.iterations
        ))
    elif args.case == "redis":
        result = asyncio.run(benchmark_redis_latency(
            num_requests=args.requests
        ))
    elif args.case == "summary":
        result = asyncio.run(benchmark_summary())
    
    # JSON 출력 (optional)
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\n✅ Results saved to: {args.output}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
