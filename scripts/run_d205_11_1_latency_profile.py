"""
D205-11-1: Latency Profiling v1 Runner (Thin CLI)

Purpose:
- 3~5분 짧게 실행하여 latency profile 생성
- stage별 p50/p95/p99/max 측정
- Evidence: manifest.json + latency_profile.json + README.md

Usage:
    python scripts/run_d205_11_1_latency_profile.py --duration 3
    python scripts/run_d205_11_1_latency_profile.py --duration 5 --output-dir logs/evidence/custom
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from arbitrage.v2.observability import LatencyProfiler, LatencyStage
from arbitrage.v2.core import OrderIntent, OrderSide, OrderType
from arbitrage.v2.opportunity import (
    BreakEvenParams,
    build_candidate,
    candidate_to_order_intents,
)
from arbitrage.v2.adapters import MockAdapter
from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_latency_profiling(duration_minutes: int, output_dir: str):
    """
    레이턴시 프로파일링 메인 루프
    
    Flow:
        1. LatencyProfiler 초기화 (enabled=True)
        2. duration_minutes 동안 반복:
           - RECEIVE_TICK: MarketData fetch
           - DECIDE: candidate → intents
           - ADAPTER_PLACE: MockAdapter execute
           - DB_RECORD: (skip for v1, 측정만)
        3. Evidence 생성 (latency_profile.json)
    """
    profiler = LatencyProfiler(enabled=True)
    
    # MarketData providers
    upbit_provider = UpbitRestProvider(timeout=10.0)
    binance_provider = BinanceRestProvider(timeout=10.0)
    
    # MockAdapter
    mock_adapter = MockAdapter()
    
    # Break-even params (최소 설정)
    fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=25.0)
    fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=25.0)
    fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
    break_even_params = BreakEvenParams(
        fee_model=fee_model,
        slippage_bps=15.0,
        latency_bps=10.0,
        buffer_bps=0.0,
    )
    
    # Run loop
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    cycle_count = 0
    
    logger.info(f"[D205-11-1] Starting latency profiling for {duration_minutes} minutes")
    
    while time.time() < end_time:
        cycle_count += 1
        
        try:
            # Stage 1: RECEIVE_TICK (MarketData fetch)
            profiler.start_span(LatencyStage.RECEIVE_TICK)
            ticker_upbit = upbit_provider.get_ticker("BTC/KRW")
            ticker_binance = binance_provider.get_ticker("BTC/USDT")
            profiler.end_span(LatencyStage.RECEIVE_TICK)
            
            if not ticker_upbit or not ticker_binance:
                continue
            
            # Stage 2: DECIDE (candidate → intents)
            profiler.start_span(LatencyStage.DECIDE)
            candidate = build_candidate(
                symbol="BTC/KRW",
                exchange_a="upbit",
                exchange_b="binance",
                price_a=ticker_upbit.last,
                price_b=ticker_binance.last * 1450.0,  # Fixed FX
                params=break_even_params,
            )
            
            if candidate:
                intents = candidate_to_order_intents(candidate)
            else:
                intents = []
            profiler.end_span(LatencyStage.DECIDE)
            
            # Stage 3: ADAPTER_PLACE (MockAdapter execute)
            if intents:
                for intent in intents[:1]:  # 첫 번째만 실행
                    profiler.start_span(LatencyStage.ADAPTER_PLACE)
                    result = mock_adapter.execute(intent)
                    profiler.end_span(LatencyStage.ADAPTER_PLACE)
            
            # Stage 4: DB_RECORD (v1에서는 skip, 측정만)
            profiler.start_span(LatencyStage.DB_RECORD)
            time.sleep(0.001)  # Simulate DB write (1ms)
            profiler.end_span(LatencyStage.DB_RECORD)
            
        except Exception as e:
            logger.warning(f"[D205-11-1] Cycle {cycle_count} error: {e}")
        
        # Poll interval (5초)
        time.sleep(5)
    
    logger.info(f"[D205-11-1] Profiling completed: {cycle_count} cycles")
    
    # Evidence 생성
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # latency_profile.json
    snapshot = profiler.snapshot()
    profile_path = output_path / "latency_profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    logger.info(f"[D205-11-1] Saved latency_profile.json to {profile_path}")
    
    # manifest.json
    manifest = {
        "run_id": output_path.name,
        "mode": "latency_profiling_v1",
        "timestamp": datetime.now().isoformat(),
        "duration_minutes": duration_minutes,
        "cycle_count": cycle_count,
    }
    manifest_path = output_path / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"[D205-11-1] Saved manifest.json to {manifest_path}")
    
    # README.md (재현 명령)
    readme_path = output_path / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(f"""# D205-11-1 Latency Profiling v1

## 재현 명령
```bash
python scripts/run_d205_11_1_latency_profile.py --duration {duration_minutes}
```

## Evidence
- latency_profile.json: stage별 p50/p95/p99/max/mean
- manifest.json: run metadata
- README.md: 재현 명령

## 결과 요약
- Cycles: {cycle_count}
- Duration: {duration_minutes} minutes
""")
    logger.info(f"[D205-11-1] Saved README.md to {readme_path}")
    
    # 콘솔 출력 (Top 병목)
    logger.info("[D205-11-1] Latency Profile Summary:")
    for stage, stats in snapshot.items():
        logger.info(f"  {stage}: p50={stats['p50_ms']:.2f}ms, p95={stats['p95_ms']:.2f}ms, max={stats['max_ms']:.2f}ms")
    
    # 병목 지점 자동 식별 (max latency 기준)
    max_stage = max(snapshot.items(), key=lambda x: x[1]['max_ms'])
    logger.info(f"[D205-11-1] 🔴 Bottleneck: {max_stage[0]} (max={max_stage[1]['max_ms']:.2f}ms)")


def main():
    parser = argparse.ArgumentParser(description="D205-11-1 Latency Profiling v1 Runner")
    parser.add_argument("--duration", type=int, required=True, help="Duration in minutes (3~5 recommended)")
    parser.add_argument("--output-dir", default="", help="Output directory (default: logs/evidence/d205_11_1_<timestamp>)")
    
    args = parser.parse_args()
    
    # Output dir 자동 생성
    if not args.output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"logs/evidence/d205_11_1_latency_{timestamp}"
    else:
        output_dir = args.output_dir
    
    logger.info(f"[D205-11-1] Output directory: {output_dir}")
    
    run_latency_profiling(args.duration, output_dir)


if __name__ == "__main__":
    main()
