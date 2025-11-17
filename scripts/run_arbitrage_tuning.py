"""
D38: Arbitrage Tuning Job Runner CLI

A CLI tool that runs a single arbitrage tuning job and outputs JSON metrics.

Usage:
    python -m scripts.run_arbitrage_tuning \
      --data-file data/sample_arbitrage_prices.csv \
      --min-spread-bps 30 \
      --taker-fee-a-bps 5 \
      --taker-fee-b-bps 5 \
      --slippage-bps 5 \
      --max-position-usd 1000 \
      --output-json outputs/tuning_result.json

Exit codes:
    0: Success
    1: Configuration or data error (file not found, invalid arguments)
    2: Unexpected runtime error
"""

import argparse
import json
import sys
from pathlib import Path

from arbitrage.arbitrage_tuning import (
    TuningConfig,
    ArbitrageTuningRunner,
)


def main():
    """Main entry point for the tuning job runner CLI."""
    parser = argparse.ArgumentParser(
        description="Run a single arbitrage tuning job and export JSON metrics."
    )

    # Required arguments
    parser.add_argument(
        "--data-file",
        type=str,
        required=True,
        help="Path to CSV file with price snapshots",
    )
    parser.add_argument(
        "--min-spread-bps",
        type=float,
        required=True,
        help="Minimum spread threshold (basis points)",
    )
    parser.add_argument(
        "--taker-fee-a-bps",
        type=float,
        required=True,
        help="Exchange A taker fee (basis points)",
    )
    parser.add_argument(
        "--taker-fee-b-bps",
        type=float,
        required=True,
        help="Exchange B taker fee (basis points)",
    )
    parser.add_argument(
        "--slippage-bps",
        type=float,
        required=True,
        help="Slippage (basis points)",
    )
    parser.add_argument(
        "--max-position-usd",
        type=float,
        required=True,
        help="Maximum position size (USD)",
    )

    # Optional arguments
    parser.add_argument(
        "--max-open-trades",
        type=int,
        default=1,
        help="Maximum number of concurrent trades (default: 1)",
    )
    parser.add_argument(
        "--initial-balance-usd",
        type=float,
        default=10_000.0,
        help="Initial balance (USD, default: 10000)",
    )
    parser.add_argument(
        "--stop-on-drawdown-pct",
        type=float,
        default=None,
        help="Stop backtest if drawdown exceeds this percentage (optional)",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Optional tag for experiment identification",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Path to output JSON file (if omitted, print to stdout)",
    )

    args = parser.parse_args()

    try:
        # Build TuningConfig
        tuning_config = TuningConfig(
            data_file=args.data_file,
            min_spread_bps=args.min_spread_bps,
            taker_fee_a_bps=args.taker_fee_a_bps,
            taker_fee_b_bps=args.taker_fee_b_bps,
            slippage_bps=args.slippage_bps,
            max_position_usd=args.max_position_usd,
            max_open_trades=args.max_open_trades,
            initial_balance_usd=args.initial_balance_usd,
            stop_on_drawdown_pct=args.stop_on_drawdown_pct,
            tag=args.tag,
        )

        # Run tuning job
        runner = ArbitrageTuningRunner(tuning_config)
        metrics = runner.run()

        # Build output JSON
        output_json = {
            "status": "success",
            "config": {
                "data_file": tuning_config.data_file,
                "min_spread_bps": tuning_config.min_spread_bps,
                "taker_fee_a_bps": tuning_config.taker_fee_a_bps,
                "taker_fee_b_bps": tuning_config.taker_fee_b_bps,
                "slippage_bps": tuning_config.slippage_bps,
                "max_position_usd": tuning_config.max_position_usd,
                "max_open_trades": tuning_config.max_open_trades,
                "initial_balance_usd": tuning_config.initial_balance_usd,
                "stop_on_drawdown_pct": tuning_config.stop_on_drawdown_pct,
                "tag": tuning_config.tag,
            },
            "metrics": {
                "total_trades": metrics.total_trades,
                "closed_trades": metrics.closed_trades,
                "open_trades": metrics.open_trades,
                "final_balance_usd": metrics.final_balance_usd,
                "realized_pnl_usd": metrics.realized_pnl_usd,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "win_rate": metrics.win_rate,
                "avg_pnl_per_trade_usd": metrics.avg_pnl_per_trade_usd,
                "runtime_seconds": metrics.runtime_seconds,
            },
        }

        # Add config_summary if available
        if metrics.config_summary:
            output_json["config_summary"] = metrics.config_summary

        # Output JSON
        if args.output_json:
            # Write to file
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_json, f, indent=2)
            print(f"[D38_TUNING] Result written to: {output_path}")
        else:
            # Print to stdout
            print(json.dumps(output_json, indent=2))

        return 0

    except (ValueError, FileNotFoundError) as e:
        # Configuration or data error
        print(f"[D38_TUNING] ERROR: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        # Unexpected runtime error
        print(f"[D38_TUNING] FATAL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
