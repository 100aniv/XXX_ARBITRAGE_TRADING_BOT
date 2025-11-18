#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D64: TRADE_LIFECYCLE_FIX – Paper Mode Test

목표: Exit/Winrate/PnL 문제 해결 검증
- Entry 신호 생성 확인
- Exit 신호 생성 확인 (D64 개선)
- Winrate 계산 확인
- PnL 변화 확인

실행:
  python scripts/run_d64_paper_test.py --duration-minutes 5 --log-level INFO
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits
from arbitrage.monitoring.metrics_collector import MetricsCollector

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(f'logs/d64_paper_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def setup_engine() -> ArbitrageEngine:
    """ArbitrageEngine 설정"""
    config = ArbitrageConfig(
        min_spread_bps=20.0,  # 최소 스프레드 20 bps
        taker_fee_a_bps=10.0,  # Upbit 테이커 수수료
        taker_fee_b_bps=10.0,  # Binance 테이커 수수료
        slippage_bps=5.0,  # 슬리피지
        max_position_usd=5000.0,  # 최대 포지션
        max_open_trades=1,  # 최대 동시 거래 수
        close_on_spread_reversal=True,  # 스프레드 역전 시 종료 (D64 핵심)
        exchange_a_to_b_rate=2.5,  # 1 BTC = 100,000 KRW = 40,000 USDT
        bid_ask_spread_bps=100.0,  # bid/ask 스프레드
    )
    engine = ArbitrageEngine(config)
    logger.info(f"[D64_TEST] Engine initialized: {config}")
    return engine


def setup_runner(engine: ArbitrageEngine, duration_minutes: int) -> ArbitrageLiveRunner:
    """ArbitrageLiveRunner 설정"""
    # Paper Exchange 생성
    exchange_a = PaperExchange()
    exchange_b = PaperExchange()
    
    # 초기 호가 설정
    from arbitrage.exchanges.base import OrderBookSnapshot
    
    snapshot_a = OrderBookSnapshot(
        symbol="KRW-BTC",
        timestamp=time.time(),
        bids=[(100000.0, 1.0)],
        asks=[(100000.0, 1.0)],
    )
    exchange_a.set_orderbook("KRW-BTC", snapshot_a)
    
    snapshot_b = OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp=time.time(),
        bids=[(40000.0, 1.0)],
        asks=[(40000.0, 1.0)],
    )
    exchange_b.set_orderbook("BTCUSDT", snapshot_b)
    
    # Config 설정
    risk_limits = RiskLimits(
        max_notional_per_trade=5000.0,
        max_daily_loss=10000.0,
        max_open_trades=1,
    )
    
    config = ArbitrageLiveConfig(
        symbol_a="KRW-BTC",
        symbol_b="BTCUSDT",
        mode="paper",
        data_source="rest",
        paper_simulation_enabled=True,
        paper_spread_injection_interval=5.0,  # 5초마다 호가 주입
        risk_limits=risk_limits,
    )
    
    # MetricsCollector 생성
    metrics_collector = MetricsCollector()
    
    # Runner 생성
    runner = ArbitrageLiveRunner(
        engine=engine,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        config=config,
        metrics_collector=metrics_collector,
    )
    
    logger.info(f"[D64_TEST] Runner initialized: {config}")
    return runner


async def run_paper_test(runner: ArbitrageLiveRunner, duration_minutes: int):
    """Paper 모드 테스트 실행"""
    logger.info(f"[D64_TEST] Starting Paper test for {duration_minutes} minutes...")
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    loop_count = 0
    entry_count = 0
    exit_count = 0
    
    try:
        while time.time() < end_time:
            loop_count += 1
            
            # 1회 루프 실행
            success = runner.run_once()
            
            if not success:
                logger.warning(f"[D64_TEST] Loop {loop_count} failed")
                await asyncio.sleep(1)
                continue
            
            # 거래 통계 업데이트
            current_entry = runner._total_trades_opened
            current_exit = runner._total_trades_closed
            
            if current_entry > entry_count:
                logger.info(f"[D64_TEST] Entry signal detected! Total: {current_entry}")
                entry_count = current_entry
            
            if current_exit > exit_count:
                logger.info(f"[D64_TEST] Exit signal detected! Total: {current_exit}")
                exit_count = current_exit
            
            # 진행 상황 로깅 (10초마다)
            if loop_count % 2 == 0:
                elapsed = time.time() - start_time
                logger.info(
                    f"[D64_TEST] Loop {loop_count}: "
                    f"elapsed={elapsed:.1f}s, "
                    f"entries={entry_count}, "
                    f"exits={exit_count}, "
                    f"pnl=${runner._total_pnl_usd:.2f}"
                )
            
            # 루프 간격
            await asyncio.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("[D64_TEST] Test interrupted by user")
    except Exception as e:
        logger.error(f"[D64_TEST] Error during test: {e}", exc_info=True)
    
    # 최종 통계
    elapsed = time.time() - start_time
    logger.info(
        f"\n[D64_TEST] Test completed:\n"
        f"  Duration: {elapsed:.1f}s\n"
        f"  Loops: {loop_count}\n"
        f"  Entries: {entry_count}\n"
        f"  Exits: {exit_count}\n"
        f"  PnL: ${runner._total_pnl_usd:.2f}\n"
        f"  Winrate: {(exit_count / entry_count * 100) if entry_count > 0 else 0:.1f}% (exits/entries)"
    )
    
    return {
        'duration': elapsed,
        'loops': loop_count,
        'entries': entry_count,
        'exits': exit_count,
        'pnl': runner._total_pnl_usd,
        'winrate': (exit_count / entry_count * 100) if entry_count > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="D64 Paper Mode Test")
    parser.add_argument('--duration-minutes', type=int, default=5, help='Test duration in minutes')
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    args = parser.parse_args()
    
    # 로깅 레벨 설정
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info("=" * 80)
    logger.info("D64: TRADE_LIFECYCLE_FIX – Paper Mode Test")
    logger.info("=" * 80)
    
    # 엔진 및 러너 설정
    engine = setup_engine()
    runner = setup_runner(engine, args.duration_minutes)
    
    # 테스트 실행
    results = asyncio.run(run_paper_test(runner, args.duration_minutes))
    
    # 결과 검증
    logger.info("\n" + "=" * 80)
    logger.info("D64 Acceptance Criteria Check:")
    logger.info("=" * 80)
    
    checks = {
        "Entry > 0": results['entries'] > 0,
        "Exit > 0": results['exits'] > 0,
        "Winrate calculable": results['entries'] > 0,
        "PnL != 0": results['pnl'] != 0.0,
    }
    
    for check, passed in checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"  {status}: {check}")
    
    all_passed = all(checks.values())
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("🎉 D64_ACCEPTED: All criteria met!")
    else:
        logger.info("❌ D64_FAILED: Some criteria not met")
    logger.info("=" * 80)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
