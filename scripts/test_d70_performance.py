"""
D70-3_FIX: Performance Impact Measurement
상태 저장/복원 기능의 루프 시간 영향 측정
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import time
import redis
import psycopg2
from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits
from arbitrage.state_store import StateStore
from arbitrage.test_utils import create_default_paper_exchanges

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_redis_client() -> redis.Redis:
    """Redis 클라이언트 생성"""
    return redis.Redis(host='localhost', port=6380, db=0, decode_responses=True)


def get_db_connection() -> psycopg2.extensions.connection:
    """PostgreSQL 연결 생성"""
    return psycopg2.connect(
        host='localhost',
        port=5432,
        dbname='arbitrage',
        user='arbitrage',
        password='arbitrage'
    )


def create_test_runner(with_state_store: bool, duration_seconds: int = 60) -> ArbitrageLiveRunner:
    """테스트용 Runner 생성"""
    # Engine
    config = ArbitrageConfig(
        symbol_a="KRW-BTC",
        symbol_b="BTCUSDT",
        exchange_a_to_b_rate=0.00073,
        min_spread_bps=20.0,
        max_position_usd=5000.0,
    )
    engine = ArbitrageEngine(config)
    
    # Exchanges
    exchange_a, exchange_b = create_default_paper_exchanges()
    
    # Runner config
    risk_limits = RiskLimits(
        max_notional_per_trade=5000.0,
        max_daily_loss_usd=10000.0,
        max_open_trades=3
    )
    
    live_config = ArbitrageLiveConfig(
        symbol_a="KRW-BTC",
        symbol_b="BTCUSDT",
        mode="paper",
        data_source="paper",
        loop_interval_seconds=0.5,  # Faster for measurement
        max_runtime_seconds=duration_seconds,
        risk_limits=risk_limits
    )
    
    # StateStore
    state_store = None
    if with_state_store:
        redis_client = get_redis_client()
        db_conn = get_db_connection()
        state_store = StateStore(redis_client, db_conn, env="perf_test")
    
    # Runner
    runner = ArbitrageLiveRunner(
        engine=engine,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        config=live_config,
        state_store=state_store,
        paper_campaign_id=f"PERF_{'ON' if with_state_store else 'OFF'}"
    )
    
    if with_state_store:
        runner._initialize_session(mode="CLEAN_RESET", session_id=None)
    
    return runner


def measure_performance(with_state_store: bool, duration_seconds: int = 60) -> dict:
    """성능 측정"""
    logger.info(f"[PERF] Starting measurement: state_store={'ON' if with_state_store else 'OFF'}")
    
    runner = create_test_runner(with_state_store, duration_seconds)
    
    start_time = time.time()
    import asyncio
    asyncio.run(runner.arun_multisymbol_loop())
    end_time = time.time()
    
    total_time = end_time - start_time
    loop_count = runner._loop_count
    avg_loop_time_ms = (total_time / loop_count * 1000) if loop_count > 0 else 0
    
    result = {
        'with_state_store': with_state_store,
        'duration_seconds': duration_seconds,
        'total_time': total_time,
        'loop_count': loop_count,
        'avg_loop_time_ms': avg_loop_time_ms,
        'trades_opened': runner._total_trades_opened,
        'trades_closed': runner._total_trades_closed
    }
    
    logger.info(f"[PERF] Result: {result}")
    return result


def main():
    """메인 함수"""
    logger.info("=" * 70)
    logger.info("D70-3_FIX: Performance Impact Measurement")
    logger.info("=" * 70)
    
    DURATION = 60  # 60초 측정
    
    # Baseline: StateStore OFF
    logger.info("[PERF] Measuring baseline (state_store=OFF)...")
    result_off = measure_performance(with_state_store=False, duration_seconds=DURATION)
    
    time.sleep(2)  # 간격
    
    # With StateStore: StateStore ON
    logger.info("[PERF] Measuring with state persistence (state_store=ON)...")
    result_on = measure_performance(with_state_store=True, duration_seconds=DURATION)
    
    # 결과 비교
    logger.info("=" * 70)
    logger.info("PERFORMANCE COMPARISON")
    logger.info("=" * 70)
    logger.info(f"  StateStore OFF:")
    logger.info(f"    Loop count: {result_off['loop_count']}")
    logger.info(f"    Avg loop time: {result_off['avg_loop_time_ms']:.2f}ms")
    logger.info(f"    Trades: {result_off['trades_opened']} opened, {result_off['trades_closed']} closed")
    logger.info("")
    logger.info(f"  StateStore ON:")
    logger.info(f"    Loop count: {result_on['loop_count']}")
    logger.info(f"    Avg loop time: {result_on['avg_loop_time_ms']:.2f}ms")
    logger.info(f"    Trades: {result_on['trades_opened']} opened, {result_on['trades_closed']} closed")
    logger.info("")
    
    # 증가율 계산
    if result_off['avg_loop_time_ms'] > 0:
        increase_pct = ((result_on['avg_loop_time_ms'] - result_off['avg_loop_time_ms']) 
                       / result_off['avg_loop_time_ms'] * 100)
        logger.info(f"  Loop Time Increase: {increase_pct:.2f}%")
        
        if increase_pct <= 10.0:
            logger.info(f"  ✅ PASS: Performance impact ≤ 10% (Acceptance: {increase_pct:.2f}% ≤ 10%)")
        else:
            logger.info(f"  ❌ FAIL: Performance impact > 10% (Actual: {increase_pct:.2f}%)")
    else:
        logger.info("  ⚠️  Unable to calculate increase (baseline too fast)")
    
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
