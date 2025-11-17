#!/usr/bin/env python3
"""
D37 Arbitrage Strategy MVP – Backtest CLI

로컬 CSV 파일에서 차익거래 백테스트 실행.
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

from arbitrage.arbitrage_core import ArbitrageConfig, ArbitrageEngine, OrderBookSnapshot
from arbitrage.arbitrage_backtest import BacktestConfig, ArbitrageBacktester

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_snapshots_from_csv(csv_file: str) -> list:
    """
    CSV 파일에서 주문서 스냅샷 로드.

    CSV 형식:
    timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b
    """
    snapshots = []

    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                logger.error("CSV 파일이 비어있습니다.")
                return []

            required_fields = {
                "timestamp",
                "best_bid_a",
                "best_ask_a",
                "best_bid_b",
                "best_ask_b",
            }
            if not required_fields.issubset(set(reader.fieldnames)):
                logger.error(
                    f"CSV 파일에 필수 필드가 없습니다. 필요: {required_fields}"
                )
                return []

            for row_num, row in enumerate(reader, start=2):
                try:
                    snapshot = OrderBookSnapshot(
                        timestamp=row["timestamp"],
                        best_bid_a=float(row["best_bid_a"]),
                        best_ask_a=float(row["best_ask_a"]),
                        best_bid_b=float(row["best_bid_b"]),
                        best_ask_b=float(row["best_ask_b"]),
                    )
                    snapshots.append(snapshot)
                except (ValueError, KeyError) as e:
                    logger.warning(f"행 {row_num} 파싱 오류: {e}")
                    continue

    except FileNotFoundError:
        logger.error(f"파일을 찾을 수 없습니다: {csv_file}")
        return []
    except Exception as e:
        logger.error(f"CSV 파일 읽기 오류: {e}")
        return []

    logger.info(f"로드된 스냅샷: {len(snapshots)}")
    return snapshots


def main():
    """메인 함수."""
    parser = argparse.ArgumentParser(
        description="D37 차익거래 MVP 백테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # 기본 백테스트
  python scripts/run_arbitrage_backtest.py \\
    --data-file data/sample_arbitrage_prices.csv \\
    --min-spread-bps 30 \\
    --taker-fee-a-bps 5 \\
    --taker-fee-b-bps 5 \\
    --slippage-bps 5 \\
    --max-position-usd 1000

  # 낙폭 제한 포함
  python scripts/run_arbitrage_backtest.py \\
    --data-file data/sample_arbitrage_prices.csv \\
    --min-spread-bps 30 \\
    --taker-fee-a-bps 5 \\
    --taker-fee-b-bps 5 \\
    --slippage-bps 5 \\
    --max-position-usd 1000 \\
    --stop-on-drawdown-pct 20
        """,
    )

    # 필수 인수
    parser.add_argument(
        "--data-file",
        required=True,
        help="CSV 파일 경로 (timestamp,best_bid_a,best_ask_a,best_bid_b,best_ask_b)",
    )

    # 전략 설정
    parser.add_argument(
        "--min-spread-bps",
        type=float,
        required=True,
        help="최소 스프레드 (basis points)",
    )
    parser.add_argument(
        "--taker-fee-a-bps",
        type=float,
        required=True,
        help="Exchange A 테이커 수수료 (bps)",
    )
    parser.add_argument(
        "--taker-fee-b-bps",
        type=float,
        required=True,
        help="Exchange B 테이커 수수료 (bps)",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        required=True,
        help="슬리피지 (bps)",
    )
    parser.add_argument(
        "--max-position-usd",
        type=float,
        required=True,
        help="최대 포지션 크기 (USD)",
    )

    # 선택 인수
    parser.add_argument(
        "--max-open-trades",
        type=int,
        default=1,
        help="최대 동시 거래 수 (기본값: 1)",
    )
    parser.add_argument(
        "--initial-balance-usd",
        type=float,
        default=10_000.0,
        help="초기 잔액 (USD, 기본값: 10000)",
    )
    parser.add_argument(
        "--stop-on-drawdown-pct",
        type=float,
        default=None,
        help="낙폭 한계 (%, 선택사항)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="최대 처리 단계 (선택사항)",
    )

    args = parser.parse_args()

    # 입력 검증
    if not Path(args.data_file).exists():
        logger.error(f"데이터 파일을 찾을 수 없습니다: {args.data_file}")
        return 1

    # 스냅샷 로드
    logger.info(f"데이터 파일 로드: {args.data_file}")
    snapshots = load_snapshots_from_csv(args.data_file)

    if not snapshots:
        logger.error("스냅샷을 로드할 수 없습니다.")
        return 1

    # 전략 설정 생성
    arb_config = ArbitrageConfig(
        min_spread_bps=args.min_spread_bps,
        taker_fee_a_bps=args.taker_fee_a_bps,
        taker_fee_b_bps=args.taker_fee_b_bps,
        slippage_bps=args.slippage_bps,
        max_position_usd=args.max_position_usd,
        max_open_trades=args.max_open_trades,
    )

    # 백테스트 설정 생성
    backtest_config = BacktestConfig(
        initial_balance_usd=args.initial_balance_usd,
        max_steps=args.max_steps,
        stop_on_drawdown_pct=args.stop_on_drawdown_pct,
    )

    # 엔진 및 백테스터 생성
    engine = ArbitrageEngine(arb_config)
    backtester = ArbitrageBacktester(engine, backtest_config)

    # 백테스트 실행
    logger.info("백테스트 실행 중...")
    result = backtester.run(snapshots)

    # 결과 출력
    print("\n" + "=" * 80)
    print("[D37_BACKTEST] RESULT SUMMARY")
    print("=" * 80)
    print(f"Total Trades:              {result.total_trades}")
    print(f"Closed Trades:             {result.closed_trades}")
    print(f"Open Trades:               {result.open_trades}")
    print(f"Final Balance (USD):       ${result.final_balance_usd:,.2f}")
    print(f"Realized PnL (USD):        ${result.realized_pnl_usd:,.2f}")
    print(f"Max Drawdown (%):          {result.max_drawdown_pct:.2f}%")
    print(f"Win Rate:                  {result.win_rate*100:.2f}%")
    print(f"Avg PnL per Trade (USD):   ${result.avg_pnl_per_trade_usd:,.2f}")
    print("=" * 80)

    if result.stats:
        print("\nAdditional Stats:")
        for key, value in result.stats.items():
            print(f"  {key}: {value}")

    print("=" * 80 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
