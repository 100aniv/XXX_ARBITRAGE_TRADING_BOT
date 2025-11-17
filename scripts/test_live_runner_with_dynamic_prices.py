# -*- coding: utf-8 -*-
"""
D43 Live Runner - Dynamic Price Test

Paper 모드에서 동적 호가를 주입하여 실제 거래 신호 생성 테스트.
"""

import sys
import logging
import time
import threading
from pathlib import Path

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.exchanges import PaperExchange
from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """설정 파일 로드"""
    path = Path(config_path)
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def inject_dynamic_prices(exchange_a, exchange_b, runner, duration=30):
    """
    동적 호가 주입 스레드.
    
    시간에 따라 호가를 변경하여 거래 신호 생성.
    
    스프레드 계산:
    - LONG_A_SHORT_B: (bid_b - ask_a) / ask_a * 10000 (bps)
    - LONG_B_SHORT_A: (bid_a - ask_b) / ask_b * 10000 (bps)
    
    예시:
    - ask_a = 100,000 KRW, bid_b = 40,500 USDT
    - spread = (40500 - 100000) / 100000 * 10000 = -5950 bps (음수, 불가능)
    
    따라서 정규화가 필요:
    - ask_a = 100,000 KRW, bid_b = 40,500 USDT
    - 환율 고려: 1 BTC = 100,000 KRW = 40,000 USDT
    - 정규화: bid_b_krw = 40,500 * 2.5 = 101,250 KRW
    - spread = (101,250 - 100,000) / 100,000 * 10000 = 125 bps
    """
    start_time = time.time()
    loop_count = 0
    
    # 환율 (1 BTC = 100,000 KRW = 40,000 USDT)
    exchange_rate = 100000.0 / 40000.0  # 2.5
    
    while time.time() - start_time < duration:
        elapsed = time.time() - start_time
        loop_count += 1
        
        # 시간에 따라 호가 변동 (스프레드 생성)
        if elapsed < 5:
            # 처음 5초: 정상 호가 (스프레드 없음)
            bid_a, ask_a = 100000.0, 100000.0
            bid_b, ask_b = 40000.0, 40000.0
            logger.info(f"[PRICE_INJECT] Phase 1 (0-5s): Normal prices (no spread)")
        
        elif elapsed < 15:
            # 5-15초: A에서 저가, B에서 고가 (LONG_A_SHORT_B 신호)
            # A: ask_a = 99,500 KRW (저가)
            # B: bid_b = 40,500 USDT (고가)
            # 정규화: bid_b_krw = 40,500 * 2.5 = 101,250 KRW
            # spread = (101,250 - 99,500) / 99,500 * 10000 = 176 bps
            bid_a, ask_a = 99000.0, 99500.0
            bid_b, ask_b = 40500.0, 41000.0
            logger.info(f"[PRICE_INJECT] Phase 2 (5-15s): LONG_A_SHORT_B opportunity")
        
        elif elapsed < 25:
            # 15-25초: A에서 고가, B에서 저가 (LONG_B_SHORT_A 신호)
            # A: bid_a = 100,500 KRW (고가)
            # B: ask_b = 39,500 USDT (저가)
            # 정규화: ask_b_krw = 39,500 * 2.5 = 98,750 KRW
            # spread = (100,500 - 98,750) / 98,750 * 10000 = 177 bps
            bid_a, ask_a = 100500.0, 101000.0
            bid_b, ask_b = 39000.0, 39500.0
            logger.info(f"[PRICE_INJECT] Phase 3 (15-25s): LONG_B_SHORT_A opportunity")
        
        else:
            # 25-30초: 정상 호가로 복귀
            bid_a, ask_a = 100000.0, 100000.0
            bid_b, ask_b = 40000.0, 40000.0
            logger.info(f"[PRICE_INJECT] Phase 4 (25-30s): Back to normal")
        
        # 호가 주입
        snapshot_a = OrderBookSnapshot(
            symbol="KRW-BTC",
            timestamp=time.time(),
            bids=[(bid_a, 1.0)],
            asks=[(ask_a, 1.0)],
        )
        exchange_a.set_orderbook("KRW-BTC", snapshot_a)
        
        snapshot_b = OrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=time.time(),
            bids=[(bid_b, 1.0)],
            asks=[(ask_b, 1.0)],
        )
        exchange_b.set_orderbook("BTCUSDT", snapshot_b)
        
        time.sleep(0.5)


def main():
    """메인 진입점"""
    logger.info("="*60)
    logger.info("D43 Live Runner - Dynamic Price Test")
    logger.info("="*60)
    
    # 설정 로드
    config = load_config("configs/live/arbitrage_live_paper_test.yaml")
    
    # 거래소 생성
    exchange_a = PaperExchange(
        initial_balance=config["exchanges"]["initial_balance_a"]
    )
    exchange_b = PaperExchange(
        initial_balance=config["exchanges"]["initial_balance_b"]
    )
    
    logger.info(f"[TEST] Created Paper exchanges")
    logger.info(f"  Exchange A: {config['exchanges']['initial_balance_a']}")
    logger.info(f"  Exchange B: {config['exchanges']['initial_balance_b']}")
    
    # 엔진 생성
    engine = ArbitrageEngine(
        ArbitrageConfig(
            min_spread_bps=config["engine"]["min_spread_bps"],
            taker_fee_a_bps=config["engine"]["taker_fee_a_bps"],
            taker_fee_b_bps=config["engine"]["taker_fee_b_bps"],
            slippage_bps=config["engine"]["slippage_bps"],
            max_position_usd=config["engine"]["max_position_usd"],
            max_open_trades=config["engine"]["max_open_trades"],
        )
    )
    
    logger.info(f"[TEST] Created ArbitrageEngine")
    
    # Live Config 생성
    live_config = ArbitrageLiveConfig(
        symbol_a=config["symbols"]["symbol_a"],
        symbol_b=config["symbols"]["symbol_b"],
        min_spread_bps=config["engine"]["min_spread_bps"],
        taker_fee_a_bps=config["engine"]["taker_fee_a_bps"],
        taker_fee_b_bps=config["engine"]["taker_fee_b_bps"],
        slippage_bps=config["engine"]["slippage_bps"],
        max_position_usd=config["engine"]["max_position_usd"],
        poll_interval_seconds=config["live"]["poll_interval_seconds"],
        max_runtime_seconds=config["live"]["max_runtime_seconds"],
    )
    
    # Runner 생성
    runner = ArbitrageLiveRunner(
        engine=engine,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        config=live_config,
    )
    
    logger.info(f"[TEST] Created ArbitrageLiveRunner")
    
    # 동적 호가 주입 스레드 시작
    price_thread = threading.Thread(
        target=inject_dynamic_prices,
        args=(exchange_a, exchange_b, runner, config["live"]["max_runtime_seconds"]),
        daemon=True,
    )
    price_thread.start()
    logger.info(f"[TEST] Started dynamic price injection thread")
    
    # Live Runner 실행
    logger.info(f"[TEST] Starting live runner...")
    logger.info("="*60)
    
    runner.run_forever()
    
    logger.info("="*60)
    
    # 최종 통계
    stats = runner.get_stats()
    
    logger.info("="*60)
    logger.info("🎯 Final Report")
    logger.info("="*60)
    logger.info(f"Duration: {stats['elapsed_seconds']:.1f}s")
    logger.info(f"Loops: {stats['loop_count']}")
    logger.info(f"Trades Opened: {stats['total_trades_opened']}")
    logger.info(f"Trades Closed: {stats['total_trades_closed']}")
    logger.info(f"Total PnL: ${stats['total_pnl_usd']:.2f}")
    logger.info(f"Active Orders: {stats['active_orders']}")
    logger.info(f"Avg Loop Time: {stats['avg_loop_time_ms']:.2f}ms")
    logger.info("="*60)
    
    # 거래소 최종 잔고
    balance_a = exchange_a.get_balance()
    balance_b = exchange_b.get_balance()
    
    logger.info("Final Balances:")
    logger.info(f"  Exchange A: {balance_a}")
    logger.info(f"  Exchange B: {balance_b}")
    logger.info("="*60)


if __name__ == "__main__":
    main()
