#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run Paper Trading Script
=========================
가상 체결 모드 (PHASE A-3)

실행 방법:
    python scripts/run_paper.py

기능:
- 가격 수집 + 스프레드 계산
- 진입/청산 시그널 생성
- 가상 포지션 생성/청산
- 손익 추적 및 출력
"""

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.client import get_upbit_ticker, get_binance_futures_ticker
from arbitrage.engine import compute_spread_opportunity
from arbitrage.executor import PaperExecutor
from arbitrage.storage import SimpleStorage
from arbitrage.config import load_config
from arbitrage import fx

def setup_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("arbitrage.paper")
    if not logger.handlers:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_path, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def format_signal(signal) -> Table:
    table = Table(show_header=False, box=None)
    table.add_row("Signal", f"{signal.action} {signal.direction}")
    table.add_row("Reason", signal.reason)
    table.add_row("Spread", f"{signal.spread_opportunity.spread_pct:+.2f}% (Net {signal.spread_opportunity.net_spread_pct:+.2f}%)")
    table.add_row("Timestamp", signal.timestamp.isoformat())
    return table


def main():
    console = Console()
    config = load_config()
    
    # 심볼 목록 추출 (다중 심볼 지원)
    symbols_config = config.get("symbols", [{"name": "BTC"}])
    symbols = [s["name"] if isinstance(s, dict) else s for s in symbols_config]
    
    poll_interval = config.get("poll_interval_seconds", 3)
    logs_dir = Path("logs")
    storage = SimpleStorage(data_dir=str(logs_dir))
    logger = setup_logger(logs_dir / "run_paper_debug.log")
    executor = PaperExecutor(config, storage, console=console, logger=logger)

    # 기존 포지션 로드 (재기동 시 복원)
    executor.positions = storage.load_positions()
    logger.info("loaded %d existing positions from storage", len(executor.positions))

    console.rule("Arbitrage-Lite: Paper Trading Mode")
    console.print(f"Watching {symbols} | Poll every {poll_interval}s")
    logger.info("run_paper started symbols=%s poll=%s", symbols, poll_interval)

    try:
        while True:
            for symbol in symbols:
                now = datetime.now(timezone.utc)
                console.rule(f"{symbol} @ {now.strftime('%H:%M:%S')}")

                upbit_ticker = get_upbit_ticker(symbol, config)
                binance_ticker = get_binance_futures_ticker(symbol, config)

                if not upbit_ticker or not binance_ticker:
                    console.print("[WARN] 티커 조회 실패", style="bold yellow")
                    logger.warning("ticker fetch failed symbol=%s", symbol)
                    continue

                # FX 정보 출력
                usdkrw = fx.get_usdkrw(config)
                console.print(f"[FX] 1 USDT = {usdkrw:,.0f} KRW")

                opportunity = compute_spread_opportunity(upbit_ticker, binance_ticker, config, symbol=symbol)
                console.print(f"Upbit: {upbit_ticker.price:,.0f} KRW | Binance: {binance_ticker.price:.2f} USDT ({opportunity.binance_price_krw:,.0f} KRW)")
                console.print(f"Spread: {opportunity.spread_pct:+.2f}% / Net: {opportunity.net_spread_pct:+.2f}%")
                logger.info(
                    "spread symbol=%s spread=%.4f net=%.4f is_opportunity=%s",
                    symbol,
                    opportunity.spread_pct,
                    opportunity.net_spread_pct,
                    opportunity.is_opportunity,
                )

                signals = executor.on_opportunity(opportunity, now, symbol=symbol)
                if signals:
                    for signal in signals:
                        console.print(format_signal(signal))
                        logger.info(
                            "signal symbol=%s action=%s reason=%s net=%.4f",
                            signal.symbol,
                            signal.action,
                            signal.reason,
                            signal.spread_opportunity.net_spread_pct if signal.spread_opportunity else 0.0,
                        )
                else:
                    console.print("  현 포지션 유지", style="dim")

            console.print(f"[WAIT] {poll_interval}s 대기 중...\n")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        console.print("[STOP] Paper Trading 종료")
        logger.info("run_paper stopped by user")


if __name__ == "__main__":
    main()
