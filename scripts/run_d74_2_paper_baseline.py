#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D74-2: Real Multi-Symbol PAPER Baseline Runner
Top-10 PAPER 모드 실제 캠페인 (10분) - 베이스라인 측정

Purpose:
- D73-4는 짧은 스모크 테스트 (2분, 구조 검증만)
- D74-2는 실제 멀티심볼 PAPER 베이스라인 검증:
  * 여러 심볼에서 실제 체결 발생 (최소 3개 이상)
  * RiskGuard/Portfolio 정상 동작 확인
  * 베이스라인 성능 수치 측정
  * D74-3 최적화 전 비교 기준 확보

Usage:
    python scripts/run_d74_2_paper_baseline.py
    python scripts/run_d74_2_paper_baseline.py --duration-minutes 10
    python scripts/run_d74_2_paper_baseline.py --duration-minutes 15 --log-level INFO
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
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

# logs/ 디렉토리 생성
Path("logs").mkdir(exist_ok=True)

# 로깅 설정
log_filename = f'logs/d74_2_paper_baseline_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def create_d74_2_config(duration_minutes: float = 10.0) -> ArbitrageConfig:
    """
    D74-2 Real PAPER Baseline용 ArbitrageConfig 생성
    
    Args:
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
            max_open_trades=20,
        ),
        trading=TradingConfig(
            min_spread_bps=40.0,  # validation: > 1.5 * (fees + slippage) = 37.5
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
            loop_interval_ms=100,  # D74-1 기준과 동일
            state_persistence_enabled=False,
        ),
        universe=SymbolUniverseConfig(
            mode=SymbolUniverseMode.TOP_N,
            top_n=10,
            base_quote="USDT",
            blacklist=["BUSDUSDT", "USDCUSDT", "TUSDUSDT", "USDPUSDT"],  # Stablecoin 제외
            min_24h_quote_volume=0.0,
        ),
        engine=EngineConfig(
            mode="multi",
            multi_symbol_enabled=True,
            per_symbol_isolation=True,
        ),
        multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(
            # Global Guard (완화)
            max_total_exposure_usd=20000.0,
            max_daily_loss_usd=5000.0,
            emergency_stop_loss_usd=10000.0,
            # Portfolio Guard (완화)
            total_capital_usd=20000.0,
            max_symbol_allocation_pct=0.40,
            # Symbol Guard (완화)
            max_position_size_usd=2000.0,
            max_position_count=3,
            cooldown_seconds=20.0,
            max_symbol_daily_loss_usd=1000.0,
            circuit_breaker_loss_count=5,
            circuit_breaker_duration=120.0,
        ),
    )
    
    logger.info(f"[D74-2] Config created: TOP_N={config.universe.top_n}, runtime={max_runtime}s ({duration_minutes:.1f}min)")
    return config


def setup_paper_exchanges() -> tuple[PaperExchange, PaperExchange]:
    """
    PAPER 모드 거래소 생성
    
    Returns:
        (exchange_a, exchange_b) tuple
    """
    # Exchange A (Upbit 역할) - 충분한 잔고
    exchange_a = PaperExchange(
        initial_balance={"KRW": 200000000.0, "BTC": 2.0, "ETH": 20.0}
    )
    
    # Exchange B (Binance 역할) - 충분한 잔고
    exchange_b = PaperExchange(
        initial_balance={"USDT": 200000.0, "BTC": 2.0, "ETH": 20.0}
    )
    
    logger.info("[D74-2] Paper exchanges created with sufficient balance")
    return exchange_a, exchange_b


def analyze_paper_exchange_trades(exchange: PaperExchange) -> Dict[str, Any]:
    """
    PaperExchange에서 체결 정보 추출
    
    Args:
        exchange: PaperExchange 인스턴스
    
    Returns:
        체결 정보 dict
    """
    from arbitrage.exchanges.base import OrderStatus
    
    # PaperExchange는 _orders dict에 체결 정보를 저장
    # OrderResult에 symbol, side, quantity, status 등이 있음
    
    trade_stats = {
        "total_orders": 0,
        "filled_orders": 0,
        "symbols_with_trades": set(),
        "by_symbol": defaultdict(int),
    }
    
    if hasattr(exchange, "_orders"):
        for order_id, order in exchange._orders.items():
            trade_stats["total_orders"] += 1
            
            # OrderResult의 status가 FILLED enum이면 체결된 것
            if hasattr(order, "status") and order.status == OrderStatus.FILLED:
                trade_stats["filled_orders"] += 1
                
                if hasattr(order, "symbol"):
                    symbol = order.symbol
                    trade_stats["symbols_with_trades"].add(symbol)
                    trade_stats["by_symbol"][symbol] += 1
    
    # set을 list로 변환
    trade_stats["symbols_with_trades"] = list(trade_stats["symbols_with_trades"])
    trade_stats["by_symbol"] = dict(trade_stats["by_symbol"])
    
    return trade_stats


async def run_d74_2_campaign(
    config: ArbitrageConfig,
    duration_minutes: float = 10.0,
) -> Dict[str, Any]:
    """
    D74-2 Real PAPER Baseline 캠페인 실행
    
    Args:
        config: ArbitrageConfig
        duration_minutes: 실행 시간 (분)
    
    Returns:
        실행 통계 dict
    """
    logger.info(f"\n{'='*80}")
    logger.info("D74-2: Real Multi-Symbol PAPER Baseline Campaign")
    logger.info(f"Duration: {duration_minutes:.1f} minutes")
    logger.info(f"{'='*80}\n")
    
    # 1. Paper Exchange 생성
    exchange_a, exchange_b = setup_paper_exchanges()
    
    # 2. MultiSymbolEngineRunner 생성
    logger.info("[D74-2] Creating MultiSymbolEngineRunner...")
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    # 3. Universe 확인
    symbols = runner.universe.get_symbols()
    logger.info(f"[D74-2] Universe symbols ({len(symbols)}): {symbols}")
    
    # 4. RiskCoordinator 확인
    if runner.risk_coordinator:
        risk_stats = runner.risk_coordinator.get_stats()
        logger.info(f"[D74-2] RiskCoordinator initialized: {risk_stats}")
    
    # 5. 캠페인 실행
    max_runtime = int(duration_minutes * 60)
    logger.info(f"\n[D74-2] Starting {duration_minutes:.1f}min campaign (max_runtime={max_runtime}s)...\n")
    start_time = time.time()
    
    try:
        stats = await runner.run_multi(
            max_iterations=None,  # 시간 제한만 사용
            max_runtime_seconds=max_runtime
        )
        
        runtime = time.time() - start_time
        stats["actual_runtime_seconds"] = runtime
        stats["actual_runtime_minutes"] = runtime / 60
        
        logger.info(f"\n[D74-2] Campaign completed in {runtime:.2f}s ({runtime/60:.2f}min)")
        
        # 6. Final RiskCoordinator 통계
        if runner.risk_coordinator:
            final_risk_stats = runner.risk_coordinator.get_stats()
            logger.info(f"\n[D74-2] Final RiskCoordinator Stats:")
            for key, value in final_risk_stats.items():
                logger.info(f"  {key}: {value}")
            stats["risk_stats"] = final_risk_stats
        
        # 7. PaperExchange 체결 분석
        logger.info("\n[D74-2] Analyzing Paper Exchange trades...")
        
        trade_stats_a = analyze_paper_exchange_trades(exchange_a)
        trade_stats_b = analyze_paper_exchange_trades(exchange_b)
        
        logger.info(f"[D74-2] Exchange A trades: {trade_stats_a['filled_orders']} filled, {len(trade_stats_a['symbols_with_trades'])} symbols")
        logger.info(f"[D74-2] Exchange B trades: {trade_stats_b['filled_orders']} filled, {len(trade_stats_b['symbols_with_trades'])} symbols")
        
        stats["exchange_a_trades"] = trade_stats_a
        stats["exchange_b_trades"] = trade_stats_b
        
        # 전체 체결 심볼 (A + B)
        all_traded_symbols = set(trade_stats_a["symbols_with_trades"]) | set(trade_stats_b["symbols_with_trades"])
        stats["total_traded_symbols"] = len(all_traded_symbols)
        stats["traded_symbols_list"] = list(all_traded_symbols)
        stats["total_filled_orders"] = trade_stats_a["filled_orders"] + trade_stats_b["filled_orders"]
        
        # 8. 성능 지표 계산 (간단)
        if runtime > 0 and stats.get("total_iterations", 0) > 0:
            total_iterations = stats["total_iterations"]
            avg_latency_ms = (runtime / total_iterations) * 1000
            throughput = total_iterations / runtime
            
            stats["performance_metrics"] = {
                "avg_loop_latency_ms": round(avg_latency_ms, 2),
                "throughput_decisions_per_sec": round(throughput, 2),
                "total_iterations": total_iterations,
            }
            
            logger.info(f"\n[D74-2] Performance Metrics:")
            logger.info(f"  Avg loop latency: {avg_latency_ms:.2f}ms")
            logger.info(f"  Throughput: {throughput:.2f} decisions/sec")
            logger.info(f"  Total iterations: {total_iterations}")
        
        return stats
    
    except Exception as e:
        logger.error(f"[D74-2] Campaign failed: {e}", exc_info=True)
        return {
            "error": str(e),
            "runtime_seconds": time.time() - start_time,
            "success": False
        }


def print_summary(stats: Dict[str, Any]) -> None:
    """
    캠페인 결과 요약 출력
    
    Args:
        stats: 실행 통계 dict
    """
    print(f"\n{'='*80}")
    print("D74-2 Real PAPER Baseline Campaign Summary")
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
    print(f"  Mode: {stats.get('universe_mode', 'UNKNOWN')}")
    print(f"  Symbols: {symbols}")
    
    # 체결 정보
    print(f"\n[Trade Execution]")
    print(f"  Total filled orders: {stats.get('total_filled_orders', 0)}")
    print(f"  Traded symbols count: {stats.get('total_traded_symbols', 0)}")
    print(f"  Traded symbols: {stats.get('traded_symbols_list', [])}")
    
    # Exchange별 체결
    if "exchange_a_trades" in stats:
        exch_a = stats["exchange_a_trades"]
        print(f"\n  Exchange A:")
        print(f"    Filled: {exch_a['filled_orders']} / {exch_a['total_orders']}")
        print(f"    Symbols: {len(exch_a['symbols_with_trades'])}")
        if exch_a["by_symbol"]:
            print(f"    By symbol: {exch_a['by_symbol']}")
    
    if "exchange_b_trades" in stats:
        exch_b = stats["exchange_b_trades"]
        print(f"\n  Exchange B:")
        print(f"    Filled: {exch_b['filled_orders']} / {exch_b['total_orders']}")
        print(f"    Symbols: {len(exch_b['symbols_with_trades'])}")
        if exch_b["by_symbol"]:
            print(f"    By symbol: {exch_b['by_symbol']}")
    
    # RiskGuard 통계
    if "risk_stats" in stats:
        risk = stats["risk_stats"]
        print(f"\n[RiskGuard]")
        print(f"  Global exposure: {risk.get('global_exposure_usd', 0):.2f} USD")
        print(f"  Daily loss: {risk.get('global_daily_loss_usd', 0):.2f} USD")
        print(f"  Total decisions: {risk.get('total_decisions', 0)}")
        
        # Allow/Reject 비율
        total_dec = risk.get('total_decisions', 0)
        if total_dec > 0:
            allowed = risk.get('total_allowed', 0)
            rejected = risk.get('total_rejected', 0)
            print(f"  Allowed: {allowed} ({allowed/total_dec*100:.1f}%)")
            print(f"  Rejected: {rejected} ({rejected/total_dec*100:.1f}%)")
    
    # 성능 지표
    if "performance_metrics" in stats:
        perf = stats["performance_metrics"]
        print(f"\n[Performance]")
        print(f"  Avg loop latency: {perf.get('avg_loop_latency_ms', 0):.2f}ms")
        print(f"  Throughput: {perf.get('throughput_decisions_per_sec', 0):.2f} decisions/sec")
        print(f"  Total iterations: {perf.get('total_iterations', 0)}")
    
    print(f"\n{'='*80}\n")


def check_acceptance_criteria(stats: Dict[str, Any]) -> bool:
    """
    Acceptance Criteria 체크
    
    Args:
        stats: 실행 통계 dict
    
    Returns:
        True if all criteria met, False otherwise
    """
    print(f"\n{'='*80}")
    print("D74-2 Acceptance Criteria Check")
    print(f"{'='*80}\n")
    
    passed = True
    
    # 1. 에러 없이 완료
    if "error" in stats:
        print("[FAIL] Campaign crashed with error")
        passed = False
    else:
        print("[PASS] No unhandled exceptions")
    
    # 2. 최소 3개 심볼에서 체결
    traded_symbols = stats.get('total_traded_symbols', 0)
    if traded_symbols >= 3:
        print(f"[PASS] Traded symbols: {traded_symbols} >= 3")
    else:
        print(f"[FAIL] Traded symbols: {traded_symbols} < 3")
        passed = False
    
    # 3. 최소 10건 체결
    total_filled = stats.get('total_filled_orders', 0)
    if total_filled >= 10:
        print(f"[PASS] Total filled orders: {total_filled} >= 10")
    else:
        print(f"[FAIL] Total filled orders: {total_filled} < 10")
        passed = False
    
    # 4. RiskGuard가 100% 차단하지 않음
    if "risk_stats" in stats:
        risk = stats["risk_stats"]
        total_dec = risk.get('total_decisions', 0)
        allowed = risk.get('total_allowed', 0)
        
        if total_dec > 0:
            allow_rate = allowed / total_dec * 100
            if allow_rate > 0:
                print(f"[PASS] RiskGuard allow rate: {allow_rate:.1f}% > 0%")
            else:
                print(f"[FAIL] RiskGuard blocks 100% of trades")
                passed = False
        else:
            print("[WARN] No RiskGuard decisions recorded")
    else:
        print("[WARN] No RiskGuard stats available")
    
    # 5. 성능 지표 측정됨 (Soft criteria)
    if "performance_metrics" in stats:
        perf = stats["performance_metrics"]
        print(f"[PASS] Performance metrics captured:")
        print(f"       - Loop latency: {perf.get('avg_loop_latency_ms', 0):.2f}ms")
        print(f"       - Throughput: {perf.get('throughput_decisions_per_sec', 0):.2f} decisions/sec")
    else:
        print("[WARN] Performance metrics not captured")
    
    print(f"\n{'='*80}")
    if passed:
        print("ALL ACCEPTANCE CRITERIA PASSED")
    else:
        print("SOME ACCEPTANCE CRITERIA FAILED")
    print(f"{'='*80}\n")
    
    return passed


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="D74-2 Real Multi-Symbol PAPER Baseline")
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=10.0,
        help="Campaign duration in minutes (default: 10.0)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    logging.getLogger().setLevel(args.log_level)
    
    logger.info(f"[D74-2] Starting Real PAPER Baseline Campaign")
    logger.info(f"[D74-2] Log file: {log_filename}")
    
    # Config 생성
    config = create_d74_2_config(duration_minutes=args.duration_minutes)
    
    # 캠페인 실행
    stats = asyncio.run(run_d74_2_campaign(
        config=config,
        duration_minutes=args.duration_minutes,
    ))
    
    # 요약 출력
    print_summary(stats)
    
    # Acceptance Criteria 체크
    passed = check_acceptance_criteria(stats)
    
    # 성공 여부 반환
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
