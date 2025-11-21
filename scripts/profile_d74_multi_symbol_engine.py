#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D74-2: Multi-Symbol Engine Profiling Harness

Purpose:
- cProfile 기반 멀티심볼 엔진 병목 분석
- 상위 N개 함수의 cumtime/calls/percall 측정
- D74-3 최적화 우선순위 결정을 위한 데이터 수집

Usage:
    # Top-10 심볼, 100 iterations
    python scripts/profile_d74_multi_symbol_engine.py \
        --symbols 10 \
        --iterations 100 \
        --output profiles/d74_2_top10.prof

    # Predefined case
    python scripts/profile_d74_multi_symbol_engine.py \
        --case dev_top10 \
        --output profiles/d74_2_top10.prof

    # With custom log level
    python scripts/profile_d74_multi_symbol_engine.py \
        --symbols 5 \
        --iterations 50 \
        --log-level WARNING \
        --output profiles/d74_2_dev.prof
"""

import argparse
import asyncio
import cProfile
import io
import logging
import pstats
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

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

# 로깅 설정 (프로파일링 시에는 WARNING 이상만)
logger = logging.getLogger(__name__)


# ============================================================
# Predefined Cases
# ============================================================

PREDEFINED_CASES = {
    "dev_top5": {
        "symbols": 5,
        "iterations": 50,
        "description": "개발용 작은 케이스 (5 symbols, 50 iterations)"
    },
    "dev_top10": {
        "symbols": 10,
        "iterations": 100,
        "description": "개발용 기본 케이스 (10 symbols, 100 iterations)"
    },
    "dev_top20": {
        "symbols": 20,
        "iterations": 100,
        "description": "개발용 큰 케이스 (20 symbols, 100 iterations)"
    },
}


# ============================================================
# Config Generation
# ============================================================

def create_profiling_config(num_symbols: int = 10) -> ArbitrageConfig:
    """
    프로파일링용 minimal config 생성
    
    benchmark_d74_performance.py와 동일한 설정 사용
    
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
            metrics_enabled=False,  # 프로파일링 중에는 비활성화
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
            exchange="binance_futures",
            min_24h_quote_volume=0.0,  # 모든 심볼 허용 (Dummy source)
            blacklist=[],
        ),
        engine=EngineConfig(
            mode="multi",  # 멀티심볼 모드
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
            cooldown_seconds=60.0,
            max_symbol_daily_loss_usd=200.0,
            circuit_breaker_loss_count=3,
            circuit_breaker_duration=300.0,
        ),
    )


# ============================================================
# Profiling Target
# ============================================================

async def run_profiling_case(num_symbols: int, num_iterations: int) -> Dict[str, Any]:
    """
    프로파일링 대상 케이스 실행
    
    benchmark_d74_performance.py의 benchmark_loop_latency와 동일한 로직
    
    Args:
        num_symbols: 심볼 수
        num_iterations: iteration 수
    
    Returns:
        실행 통계
    """
    config = create_profiling_config(num_symbols=num_symbols)
    
    # PaperExchange 생성
    exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0})
    exchange_b = PaperExchange(initial_balance={"USDT": 100000.0})
    
    # MultiSymbolEngineRunner 생성
    runner = create_multi_symbol_runner(config, exchange_a, exchange_b)
    
    # 실행
    start_time = time.perf_counter()
    stats = await runner.run_multi(max_iterations=num_iterations)
    elapsed = time.perf_counter() - start_time
    
    return {
        "symbols": num_symbols,
        "iterations": num_iterations,
        "elapsed_s": elapsed,
        "stats": stats,
    }


# ============================================================
# Main Profiler
# ============================================================

def run_profiler(
    num_symbols: int,
    num_iterations: int,
    output_path: str,
    top_n: int = 30
) -> Dict[str, Any]:
    """
    cProfile로 프로파일링 실행
    
    Args:
        num_symbols: 심볼 수
        num_iterations: iteration 수
        output_path: 프로파일 출력 경로 (.prof)
        top_n: 상위 N개 함수 출력
    
    Returns:
        프로파일링 결과 요약
    """
    print(f"\n[D74-2] Profiling Multi-Symbol Engine")
    print(f"  Symbols: {num_symbols}")
    print(f"  Iterations: {num_iterations}")
    print(f"  Output: {output_path}")
    print()
    
    # 출력 디렉토리 생성
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # cProfile 실행
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 비동기 함수 실행
    result = asyncio.run(run_profiling_case(num_symbols, num_iterations))
    
    profiler.disable()
    
    # 바이너리 프로파일 파일 저장
    profiler.dump_stats(str(output_file))
    print(f"  [OK] Binary profile saved: {output_file}")
    
    # 텍스트 요약 생성
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.sort_stats("cumulative")
    ps.print_stats(top_n)
    
    stats_text = s.getvalue()
    
    # 텍스트 파일 저장
    stats_file = output_file.with_suffix(".txt")
    with open(stats_file, "w", encoding="utf-8") as f:
        f.write(f"D74-2 Profiling Report\n")
        f.write(f"======================\n\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Symbols: {num_symbols}\n")
        f.write(f"Iterations: {num_iterations}\n")
        f.write(f"Elapsed: {result['elapsed_s']:.2f}s\n")
        f.write(f"\n")
        f.write(f"Top {top_n} Functions (sorted by cumtime)\n")
        f.write(f"{'='*80}\n")
        f.write(stats_text)
    
    print(f"  [OK] Text report saved: {stats_file}")
    
    # 콘솔에도 일부 출력
    print(f"\n  Top 10 Functions (cumulative time):")
    print(f"  {'-'*80}")
    lines = stats_text.split("\n")
    # pstats 출력 형식: 헤더 5줄 + 함수 목록
    for line in lines[5:15]:  # 상위 10개만
        if line.strip():
            print(f"  {line}")
    
    return {
        "output_path": str(output_file),
        "stats_path": str(stats_file),
        "elapsed_s": result["elapsed_s"],
        "iterations": num_iterations,
        "symbols": num_symbols,
    }


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="D74-2: Multi-Symbol Engine Profiling Harness"
    )
    
    # Case 선택 (predefined vs custom)
    parser.add_argument(
        "--case",
        type=str,
        choices=list(PREDEFINED_CASES.keys()),
        help="Predefined profiling case (overrides --symbols/--iterations)"
    )
    
    # Custom 파라미터
    parser.add_argument(
        "--symbols",
        type=int,
        default=10,
        help="Number of symbols to profile (default: 10)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of iterations per symbol (default: 100)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="profiles/d74_2_default.prof",
        help="Output profile path (default: profiles/d74_2_default.prof)"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of top functions to report (default: 30)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level (default: WARNING)"
    )
    
    args = parser.parse_args()
    
    # 로깅 설정
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    )
    
    # Predefined case 사용 시 파라미터 덮어쓰기
    if args.case:
        case_params = PREDEFINED_CASES[args.case]
        num_symbols = case_params["symbols"]
        num_iterations = case_params["iterations"]
        print(f"[D74-2] Using predefined case: {args.case}")
        print(f"  Description: {case_params['description']}")
    else:
        num_symbols = args.symbols
        num_iterations = args.iterations
    
    # 프로파일링 실행
    try:
        result = run_profiler(
            num_symbols=num_symbols,
            num_iterations=num_iterations,
            output_path=args.output,
            top_n=args.top_n
        )
        
        print(f"\n{'='*80}")
        print(f"Profiling Summary")
        print(f"{'='*80}")
        print(f"  Elapsed: {result['elapsed_s']:.2f}s")
        print(f"  Avg latency: {result['elapsed_s'] / result['iterations'] * 1000:.2f}ms")
        print(f"  Profile: {result['output_path']}")
        print(f"  Report: {result['stats_path']}")
        print(f"{'='*80}\n")
        
        return 0
    
    except Exception as e:
        logger.error(f"Profiling failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
