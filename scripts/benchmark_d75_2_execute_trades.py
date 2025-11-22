"""
D75-2 Phase 3: execute_trades() Micro-Benchmark

목표: avg < 6ms (10ms → 6ms, -40% 개선)

최적화 전략:
- snapshot 1회 조회 후 재사용
- logging isEnabledFor() 조건 체크
- RiskGuard 호출 최소화 (정책상 가능한 범위 내)
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import time
import logging
import numpy as np
from arbitrage.arbitrage_core import (
    ArbitrageEngine,
    ArbitrageConfig,
    ArbitrageTrade,
)
from arbitrage.live_runner import (
    ArbitrageLiveRunner,
    ArbitrageLiveConfig,
    RiskLimits,
)
from arbitrage.exchanges.paper_exchange import PaperExchange

# 로깅 레벨 WARNING으로 설정 (INFO/DEBUG 로깅 비활성화)
logging.basicConfig(level=logging.WARNING)


def create_test_trades(count: int = 10) -> list:
    """테스트용 거래 목록 생성"""
    trades = []
    for i in range(count):
        trade = ArbitrageTrade(
            open_timestamp=f"2025-01-01T00:00:{i:02d}Z",
            side="LONG_A_SHORT_B",
            entry_spread_bps=50.0,
            notional_usd=1000.0,
            is_open=True,
        )
        trades.append(trade)
    return trades


def main():
    print("=" * 80)
    print("D75-2 Phase 3: execute_trades() Micro-Benchmark")
    print("=" * 80)
    
    # ArbitrageEngine 생성
    engine_config = ArbitrageConfig(
        min_spread_bps=30.0,
        taker_fee_a_bps=5.0,
        taker_fee_b_bps=5.0,
        slippage_bps=10.0,
        max_position_usd=1000.0,
        max_open_trades=100,
        close_on_spread_reversal=True,
        exchange_a_to_b_rate=2.5,
        bid_ask_spread_bps=100.0,
    )
    
    engine = ArbitrageEngine(engine_config)
    
    # PaperExchange 생성
    exchange_a = PaperExchange("UPBIT", initial_balance={"KRW": 10000000.0, "BTC": 1.0})
    exchange_b = PaperExchange("BINANCE", initial_balance={"USDT": 10000.0, "BTC": 1.0})
    
    # ArbitrageLiveConfig 생성
    live_config = ArbitrageLiveConfig(
        symbol_a="BTC-KRW",
        symbol_b="BTCUSDT",
        mode="PAPER",
        risk_limits=RiskLimits(
            max_notional_per_trade=1000.0,
            max_daily_loss=10000.0,
        ),
    )
    
    # ArbitrageLiveRunner 생성
    runner = ArbitrageLiveRunner(
        engine=engine,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        config=live_config,
    )
    
    # 테스트 거래 목록 생성 (10개)
    test_trades = create_test_trades(count=10)
    
    # Warmup
    print("\nWarmup (50 iterations)...")
    for _ in range(50):
        trades_copy = [
            ArbitrageTrade(
                open_timestamp=t.open_timestamp,
                side=t.side,
                entry_spread_bps=t.entry_spread_bps,
                notional_usd=t.notional_usd,
                is_open=t.is_open,
            )
            for t in test_trades
        ]
        runner.execute_trades(trades_copy)
    
    # Benchmark
    iterations = 300
    print(f"\nBenchmark ({iterations} iterations, 10 trades each)...")
    latencies = []
    
    for i in range(iterations):
        # 거래 목록 복사 (새로운 인스턴스)
        trades_copy = [
            ArbitrageTrade(
                open_timestamp=t.open_timestamp,
                side=t.side,
                entry_spread_bps=t.entry_spread_bps,
                notional_usd=t.notional_usd,
                is_open=t.is_open,
            )
            for t in test_trades
        ]
        
        start = time.perf_counter()
        runner.execute_trades(trades_copy)
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
    print(f"Trades per iteration: 10")
    print(f"Avg:        {avg:.4f} ms")
    print(f"P50:        {p50:.4f} ms")
    print(f"P95:        {p95:.4f} ms")
    print(f"P99:        {p99:.4f} ms")
    print(f"Min:        {min_lat:.4f} ms")
    print(f"Max:        {max_lat:.4f} ms")
    print("=" * 80)
    
    # PASS/FAIL 판정
    target_ms = 6.0
    if avg < target_ms:
        print(f"✅ PASS: avg {avg:.4f}ms < target {target_ms}ms")
        print(f"   개선: 10ms → {avg:.4f}ms ({((10 - avg) / 10 * 100):.1f}% 감소)")
        exit_code = 0
    else:
        print(f"❌ FAIL: avg {avg:.4f}ms >= target {target_ms}ms")
        print(f"   현재 달성: {((10 - avg) / 10 * 100):.1f}% 개선")
        print(f"   목표 미달: {avg - target_ms:.4f}ms 초과")
        exit_code = 1
    
    print("=" * 80)
    return exit_code


if __name__ == "__main__":
    exit(main())
