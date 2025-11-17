#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run Collect Only Script
========================
가격 수집 + 스프레드 계산만 출력하는 MVP 1단계 스크립트

실행 방법:
    python scripts/run_collect_only.py

기능:
- 업비트/바이낸스에서 현재가 조회
- 스프레드 계산 및 출력
- 진입 기회 여부 표시
- 주기적으로 반복 (poll_interval_seconds 간격)
"""

import sys
import time
from pathlib import Path

from rich.console import Console

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.collectors import get_upbit_ticker, get_binance_futures_ticker
from arbitrage.config_loader import load_config
from arbitrage.engine import compute_spread_opportunity
from arbitrage.storage import SimpleStorage


def main():
    console = Console()
    config = load_config()
    symbols = config.get("symbols", ["BTC"])
    poll_interval = config.get("poll_interval_seconds", 3)
    storage = SimpleStorage()

    console.rule("Arbitrage-Lite: Collect Only Mode")
    console.print(f"[INFO] 모니터링 심볼: {symbols}")
    console.print(f"[INFO] 폴링 주기: {poll_interval}초")
    console.print(f"[INFO] 최소 순 스프레드: {config.get('spread', {}).get('min_net_spread_pct', 0.0):.2f}%")

    try:
        while True:
            for symbol in symbols:
                console.rule(f"{symbol} 시세 조회")
                upbit_ticker = get_upbit_ticker(symbol, config)
                binance_ticker = get_binance_futures_ticker(symbol, config)

                if not upbit_ticker or not binance_ticker:
                    console.print(f"[WARN] {symbol} 시세 조회 실패", style="bold yellow")
                    continue

                opportunity = compute_spread_opportunity(upbit_ticker, binance_ticker, config)

                console.print(f"  업비트 KRW: {upbit_ticker.price:,.0f}")
                console.print(
                    f"  바이낸스 USDT: {binance_ticker.price:,.2f} → {opportunity.binance_price_krw:,.0f} KRW"
                )
                console.print(f"  스프레드: {opportunity.spread_pct:+.2f}%")
                console.print(f"  순 스프레드: {opportunity.net_spread_pct:+.2f}%")
                console.print(
                    "  [OPPORTUNITY] 진입 기회 발견!" if opportunity.is_opportunity else "  [WAIT] 대기",
                    style="bold green" if opportunity.is_opportunity else "dim"
                )

                storage.log_spread(opportunity)

            console.print(f"[WAIT] {poll_interval}초 대기 중...\n")
            time.sleep(poll_interval)

    except KeyboardInterrupt:
        console.print("[STOP] 사용자 중단 (Ctrl+C)")
        console.print("[OK] 종료")


if __name__ == "__main__":
    main()
