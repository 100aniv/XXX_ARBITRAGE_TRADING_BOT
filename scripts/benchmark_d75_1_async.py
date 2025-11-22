#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D75-1: run_once() Async Conversion Benchmark

Loop latency 측정:
- Before (D74): ~62ms
- Target (D75-1): <10ms (avg), <25ms (p99)
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import List
import statistics

# 프로젝트 루트 추가
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.config import ArbitrageConfig
from arbitrage.live_runner import ArbitrageLiveRunner
from arbitrage.paper_exchange import PaperExchange

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def benchmark_async_run_once(iterations: int = 100) -> dict:
    """
    D75-1: Async run_once() 성능 벤치마크
    
    Args:
        iterations: 벤치마크 반복 횟수
    
    Returns:
        성능 측정 결과
    """
    # Config 생성
    config = ArbitrageConfig()
    config.symbol_a = "BTC"
    config.symbol_b = "BTCUSDT"
    config.min_profit_threshold = 0.001
    config.max_position_size_usd = 1000.0
    
    # Paper Exchange 생성
    exchange_a = PaperExchange("KRW")
    exchange_b = PaperExchange("USDT")
    
    # Runner 생성
    live_config = config.to_live_config()
    runner = ArbitrageLiveRunner(
        config=live_config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    logger.info(f"[D75-1_BENCHMARK] Starting benchmark: {iterations} iterations")
    
    # 벤치마크 실행
    latencies: List[float] = []
    
    benchmark_start = time.time()
    
    for i in range(iterations):
        iter_start = time.time()
        
        # D75-1: Async run_once() 실행
        success = await runner.run_once()
        
        iter_end = time.time()
        latency_ms = (iter_end - iter_start) * 1000.0
        latencies.append(latency_ms)
        
        if (i + 1) % 10 == 0:
            logger.info(f"[D75-1_BENCHMARK] Progress: {i+1}/{iterations} iterations")
    
    benchmark_end = time.time()
    total_time = benchmark_end - benchmark_start
    
    # 통계 계산
    latencies_sorted = sorted(latencies)
    avg_latency = statistics.mean(latencies)
    median_latency = statistics.median(latencies)
    p95_latency = latencies_sorted[int(len(latencies_sorted) * 0.95)]
    p99_latency = latencies_sorted[int(len(latencies_sorted) * 0.99)]
    min_latency = min(latencies)
    max_latency = max(latencies)
    
    throughput = iterations / total_time
    
    results = {
        "iterations": iterations,
        "total_time_s": total_time,
        "throughput_iter_per_sec": throughput,
        "latency_avg_ms": avg_latency,
        "latency_median_ms": median_latency,
        "latency_p95_ms": p95_latency,
        "latency_p99_ms": p99_latency,
        "latency_min_ms": min_latency,
        "latency_max_ms": max_latency,
    }
    
    return results


def print_results(results: dict) -> None:
    """
    벤치마크 결과 출력
    """
    print("\n" + "="*60)
    print("D75-1: Async run_once() Benchmark Results")
    print("="*60)
    print(f"Iterations:      {results['iterations']}")
    print(f"Total Time:      {results['total_time_s']:.2f}s")
    print(f"Throughput:      {results['throughput_iter_per_sec']:.2f} iter/sec")
    print("-"*60)
    print("Loop Latency:")
    print(f"  Average:       {results['latency_avg_ms']:.2f}ms")
    print(f"  Median:        {results['latency_median_ms']:.2f}ms")
    print(f"  P95:           {results['latency_p95_ms']:.2f}ms")
    print(f"  P99:           {results['latency_p99_ms']:.2f}ms")
    print(f"  Min:           {results['latency_min_ms']:.2f}ms")
    print(f"  Max:           {results['latency_max_ms']:.2f}ms")
    print("="*60)
    
    # D74 대비 개선율 계산 (D74 baseline: 62ms)
    d74_baseline_ms = 62.0
    improvement_pct = ((d74_baseline_ms - results['latency_avg_ms']) / d74_baseline_ms) * 100.0
    
    print(f"\nD74 Baseline (avg): {d74_baseline_ms}ms")
    print(f"D75-1 Result (avg): {results['latency_avg_ms']:.2f}ms")
    print(f"Improvement:        {improvement_pct:.1f}%")
    print("="*60)
    
    # Acceptance Criteria 체크
    print("\nAcceptance Criteria:")
    print(f"✅ Avg latency < 10ms:  {'PASS' if results['latency_avg_ms'] < 10.0 else 'FAIL'} ({results['latency_avg_ms']:.2f}ms)")
    print(f"✅ P99 latency < 25ms:  {'PASS' if results['latency_p99_ms'] < 25.0 else 'FAIL'} ({results['latency_p99_ms']:.2f}ms)")
    print(f"✅ Throughput ≥ 15/s:   {'PASS' if results['throughput_iter_per_sec'] >= 15.0 else 'FAIL'} ({results['throughput_iter_per_sec']:.2f}/s)")
    print("="*60 + "\n")


async def main():
    """
    메인 실행 함수
    """
    logger.info("[D75-1_BENCHMARK] D75-1 Async Conversion Benchmark")
    
    # 벤치마크 실행
    results = await benchmark_async_run_once(iterations=100)
    
    # 결과 출력
    print_results(results)
    
    # 결과 저장
    import json
    output_file = project_root / "logs" / "d75_1_benchmark_results.json"
    output_file.parent.mkdir(exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"[D75-1_BENCHMARK] Results saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
