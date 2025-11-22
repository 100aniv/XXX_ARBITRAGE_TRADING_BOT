"""
D75-2 Phase 2: process_snapshot() Micro-Benchmark

목표: avg < 17ms (30ms → 17ms, -43% 개선)

최적화 전략:
- 수수료/슬리피지 pre-calculation
- 환율 정규화 1회 계산 후 재사용
- len() 호출 최소화
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import time
import numpy as np
from arbitrage.arbitrage_core import (
    ArbitrageEngine,
    ArbitrageConfig,
    OrderBookSnapshot,
)


def create_test_snapshot() -> OrderBookSnapshot:
    """테스트용 스냅샷 생성"""
    return OrderBookSnapshot(
        timestamp="2025-01-01T00:00:00Z",
        best_bid_a=100000.0,  # Upbit KRW
        best_ask_a=100100.0,
        best_bid_b=39900.0,  # Binance USDT
        best_ask_b=40000.0,
    )


def main():
    print("=" * 80)
    print("D75-2 Phase 2: process_snapshot() Micro-Benchmark")
    print("=" * 80)
    
    # ArbitrageEngine 생성 (기존 테스트 패턴 재사용)
    config = ArbitrageConfig(
        min_spread_bps=30.0,
        taker_fee_a_bps=5.0,
        taker_fee_b_bps=5.0,
        slippage_bps=10.0,
        max_position_usd=1000.0,
        max_open_trades=10,
        close_on_spread_reversal=True,
        exchange_a_to_b_rate=2.5,  # 1 KRW = 2.5 USDT 환산
        bid_ask_spread_bps=100.0,
    )
    
    engine = ArbitrageEngine(config)
    snapshot = create_test_snapshot()
    
    # Warmup (JIT, 캐시 워밍)
    print("\nWarmup (100 iterations)...")
    for _ in range(100):
        engine.on_snapshot(snapshot)
    
    # Benchmark
    iterations = 500
    print(f"\nBenchmark ({iterations} iterations)...")
    latencies = []
    
    for i in range(iterations):
        start = time.perf_counter()
        trades = engine.on_snapshot(snapshot)
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # ms
    
    # 통계 출력
    latencies_arr = np.array(latencies)
    avg = np.mean(latencies_arr)
    p50 = np.percentile(latencies_arr, 50)
    p95 = np.percentile(latencies_arr, 95)
    p99 = np.percentile(latencies_arr, 99)
    min_lat = np.min(latencies_arr)
    max_lat = np.max(latencies_arr)
    
    print("\n" + "=" * 80)
    print("Results:")
    print("=" * 80)
    print(f"Iterations: {iterations}")
    print(f"Avg:        {avg:.4f} ms")
    print(f"P50:        {p50:.4f} ms")
    print(f"P95:        {p95:.4f} ms")
    print(f"P99:        {p99:.4f} ms")
    print(f"Min:        {min_lat:.4f} ms")
    print(f"Max:        {max_lat:.4f} ms")
    print("=" * 80)
    
    # PASS/FAIL 판정
    target_ms = 17.0
    if avg < target_ms:
        print(f"✅ PASS: avg {avg:.4f}ms < target {target_ms}ms")
        print(f"   개선: 30ms → {avg:.4f}ms ({((30 - avg) / 30 * 100):.1f}% 감소)")
        exit_code = 0
    else:
        print(f"❌ FAIL: avg {avg:.4f}ms >= target {target_ms}ms")
        print(f"   현재 달성: {((30 - avg) / 30 * 100):.1f}% 개선")
        print(f"   목표 미달: {avg - target_ms:.4f}ms 초과")
        exit_code = 1
    
    print("=" * 80)
    return exit_code


if __name__ == "__main__":
    exit(main())
