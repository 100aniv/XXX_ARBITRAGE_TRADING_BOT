"""
D39: Aggregate Tuning Results CLI

CLI to scan a directory of D38 result JSONs and print a ranked summary.

Usage:
    python -m scripts.aggregate_tuning_results \
      --results-dir outputs/tuning/session001 \
      --max-results 10 \
      --max-drawdown-pct 15 \
      --min-trades 5 \
      --output-json outputs/tuning/session001_summary.json

Exit codes:
    0: Success
    1: Results directory not found
    2: Unexpected runtime error
"""

import argparse
import json
import sys
from pathlib import Path

from arbitrage.tuning_aggregate import TuningResultsAggregator


def format_summary(summary) -> str:
    """Format summary for human-readable output."""
    lines = []
    lines.append("=" * 70)
    lines.append("[D39_AGG] TUNING SESSION SUMMARY")
    lines.append("=" * 70)
    lines.append("")

    lines.append(f"Total Jobs:           {summary.total_jobs}")
    lines.append(f"Success Jobs:         {summary.success_jobs}")
    lines.append(f"Error Jobs:           {summary.error_jobs}")
    lines.append("")

    if summary.filters:
        lines.append("Filters:")
        for key, value in summary.filters.items():
            lines.append(f"  {key}: {value}")
        lines.append("")

    lines.append(f"Top {len(summary.top_by_pnl)} by Realized PnL (USD):")
    for idx, result in enumerate(summary.top_by_pnl, 1):
        metrics = result.metrics
        config = result.config

        pnl = metrics.get("realized_pnl_usd", 0.0)
        dd = metrics.get("max_drawdown_pct", 0.0)
        trades = metrics.get("total_trades", 0)

        # Extract key config params
        min_spread = config.get("min_spread_bps", "N/A")
        slippage = config.get("slippage_bps", "N/A")

        lines.append(
            f"  {idx}) job_id={result.job_id}  "
            f"PnL=${pnl:+,.2f}  DD={dd:.2f}%  trades={trades}  "
            f"min_spread_bps={min_spread}  slippage_bps={slippage}"
        )

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Aggregate D38 tuning result JSON files and show ranked summary."
    )

    parser.add_argument(
        "--results-dir",
        required=True,
        help="Directory containing D38 result JSON files",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum number of top results to show (default: 10)",
    )
    parser.add_argument(
        "--max-drawdown-pct",
        type=float,
        help="Filter: maximum drawdown percentage",
    )
    parser.add_argument(
        "--min-trades",
        type=int,
        help="Filter: minimum number of trades",
    )
    parser.add_argument(
        "--output-json",
        help="Optional: write machine-readable summary to JSON file",
    )

    args = parser.parse_args()

    try:
        # Check if results directory exists
        results_path = Path(args.results_dir)
        if not results_path.exists():
            raise FileNotFoundError(f"Results directory not found: {args.results_dir}")

        # Aggregate results
        aggregator = TuningResultsAggregator(
            results_dir=args.results_dir,
            max_results=args.max_results,
            max_drawdown_pct=args.max_drawdown_pct,
            min_trades=args.min_trades,
        )
        summary = aggregator.summarize()

        # Print human-readable summary
        print(format_summary(summary))

        # Write JSON summary if requested
        if args.output_json:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            summary_dict = {
                "total_jobs": summary.total_jobs,
                "success_jobs": summary.success_jobs,
                "error_jobs": summary.error_jobs,
                "filters": summary.filters,
                "top_by_pnl": [
                    {
                        "job_id": r.job_id,
                        "tag": r.tag,
                        "config": r.config,
                        "metrics": r.metrics,
                        "status": r.status,
                    }
                    for r in summary.top_by_pnl
                ],
            }

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(summary_dict, f, indent=2)

            print(f"[D39_AGG] Summary written to: {output_path}", file=sys.stderr)

        return 0

    except FileNotFoundError as e:
        print(f"[D39_AGG] ERROR: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"[D39_AGG] FATAL: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
