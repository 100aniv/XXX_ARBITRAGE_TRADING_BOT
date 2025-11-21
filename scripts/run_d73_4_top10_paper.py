#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D73-4: Small-Scale Multi-Symbol Integration Runner
Top-10 PAPER 모드 통합 캠페인

Purpose:
- D73-1 (Symbol Universe) + D73-2 (Multi-Symbol Engine) + D73-3 (RiskGuard) 통합
- Top-10 심볼 대상 짧은 PAPER 캠페인 실행
- 기능 검증 중심 (성능 튜닝은 D74에서)

Usage:
    python scripts/run_d73_4_top10_paper.py
    python scripts/run_d73_4_top10_paper.py --config configs/d73_4_top10_paper.yaml
    python scripts/run_d73_4_top10_paper.py --iterations 30 --runtime 60
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

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

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'logs/d73_4_top10_paper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def create_d73_4_config(max_iterations: int = 50, max_runtime: int = 120) -> ArbitrageConfig:
    """
    D73-4 테스트용 ArbitrageConfig 생성
    
    Args:
        max_iterations: 심볼당 최대 iteration 수
        max_runtime: 최대 실행 시간 (초)
    
    Returns:
        ArbitrageConfig
    """
    config = ArbitrageConfig(
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
            min_spread_bps=30.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
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
            loop_interval_ms=500,  # 0.5초
            state_persistence_enabled=False,  # 테스트에서는 비활성화
        ),
        universe=SymbolUniverseConfig(
            mode=SymbolUniverseMode.TOP_N,
            top_n=10,
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
    
    logger.info(f"[D73-4] Config created: TOP_N={config.universe.top_n}, runtime={max_runtime}s")
    return config


def setup_paper_exchanges() -> tuple[PaperExchange, PaperExchange]:
    """
    PAPER 모드 거래소 생성
    
    Returns:
        (exchange_a, exchange_b) tuple
    """
    # Exchange A (Upbit 역할)
    exchange_a = PaperExchange(
        initial_balance={"KRW": 100000000.0, "BTC": 1.0, "ETH": 10.0}
    )
    
    # Exchange B (Binance 역할)
    exchange_b = PaperExchange(
        initial_balance={"USDT": 100000.0, "BTC": 1.0, "ETH": 10.0}
    )
    
    logger.info("[D73-4] Paper exchanges created")
    return exchange_a, exchange_b


async def run_d73_4_campaign(
    config: ArbitrageConfig,
    max_iterations: int = 50,
    max_runtime: int = 120,
) -> Dict[str, Any]:
    """
    D73-4 통합 캠페인 실행
    
    Args:
        config: ArbitrageConfig
        max_iterations: 심볼당 최대 iteration 수
        max_runtime: 최대 실행 시간 (초)
    
    Returns:
        실행 통계 dict
    """
    logger.info(f"\n{'='*80}")
    logger.info("D73-4: Small-Scale Multi-Symbol Integration Campaign")
    logger.info(f"{'='*80}\n")
    
    # 1. Paper Exchange 생성
    exchange_a, exchange_b = setup_paper_exchanges()
    
    # 2. MultiSymbolEngineRunner 생성 (create_multi_symbol_runner 팩토리 사용)
    logger.info("[D73-4] Creating MultiSymbolEngineRunner...")
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    # 3. Universe 확인
    symbols = runner.universe.get_symbols()
    logger.info(f"[D73-4] Universe symbols ({len(symbols)}): {symbols}")
    
    # 4. RiskCoordinator 확인
    if runner.risk_coordinator:
        risk_stats = runner.risk_coordinator.get_stats()
        logger.info(f"[D73-4] RiskCoordinator initialized: {risk_stats}")
    
    # 5. 캠페인 실행
    logger.info(f"\n[D73-4] Starting campaign: max_iterations={max_iterations}, max_runtime={max_runtime}s\n")
    start_time = time.time()
    
    try:
        stats = await runner.run_multi(
            max_iterations=max_iterations,
            max_runtime_seconds=max_runtime
        )
        
        runtime = time.time() - start_time
        stats["actual_runtime_seconds"] = runtime
        
        logger.info(f"\n[D73-4] Campaign completed in {runtime:.2f}s")
        logger.info(f"[D73-4] Stats: {stats}")
        
        # 6. Final RiskCoordinator 통계
        if runner.risk_coordinator:
            final_risk_stats = runner.risk_coordinator.get_stats()
            logger.info(f"\n[D73-4] Final RiskCoordinator Stats:")
            for key, value in final_risk_stats.items():
                logger.info(f"  {key}: {value}")
            stats["risk_stats"] = final_risk_stats
        
        return stats
    
    except Exception as e:
        logger.error(f"[D73-4] Campaign failed: {e}", exc_info=True)
        return {"error": str(e), "runtime_seconds": time.time() - start_time}


def print_summary(stats: Dict[str, Any]) -> None:
    """
    캠페인 결과 요약 출력
    
    Args:
        stats: 실행 통계 dict
    """
    print(f"\n{'='*80}")
    print("D73-4 Campaign Summary")
    print(f"{'='*80}")
    
    if "error" in stats:
        print(f"❌ Campaign failed: {stats['error']}")
        return
    
    print(f"Runtime: {stats.get('actual_runtime_seconds', 0):.2f}s")
    print(f"Symbols: {len(stats.get('symbols', []))} ({stats.get('universe_mode', 'UNKNOWN')} mode)")
    print(f"Symbol list: {stats.get('symbols', [])}")
    
    # RiskGuard 통계
    if "risk_stats" in stats:
        risk = stats["risk_stats"]
        print(f"\nRiskGuard Stats:")
        print(f"  Global exposure: {risk.get('global_exposure_usd', 0):.2f} USD")
        print(f"  Daily loss: {risk.get('global_daily_loss_usd', 0):.2f} USD")
        print(f"  Total decisions: {risk.get('total_decisions', 0)}")
    
    print(f"\n{'='*80}\n")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="D73-4 Top-10 Multi-Symbol PAPER Integration")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/d73_4_top10_paper.yaml",
        help="Config file path (default: configs/d73_4_top10_paper.yaml)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=50,
        help="Max iterations per symbol (default: 50)"
    )
    parser.add_argument(
        "--runtime",
        type=int,
        default=120,
        help="Max runtime in seconds (default: 120)"
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
    
    # Config 생성
    config = create_d73_4_config(max_iterations=args.iterations, max_runtime=args.runtime)
    
    # 캠페인 실행
    stats = asyncio.run(run_d73_4_campaign(
        config=config,
        max_iterations=args.iterations,
        max_runtime=args.runtime,
    ))
    
    # 요약 출력
    print_summary(stats)
    
    # 성공 여부 반환
    return 0 if "error" not in stats else 1


if __name__ == "__main__":
    sys.exit(main())
