#!/usr/bin/env python3
"""
D82-6 Baseline Entry/TP Threshold Selection

Analyzes threshold_sweep_summary.json and selects the optimal Entry/TP combination
based on multi-criteria scoring.

Usage:
    python scripts/select_d82_6_baseline.py --summary-path logs/d82-5/threshold_sweep_summary.json

Author: AI Assistant
Date: 2025-12-05
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_summary_json(summary_path: Path) -> Dict[str, Any]:
    """Load threshold sweep summary JSON."""
    if not summary_path.exists():
        raise FileNotFoundError(f"Summary file not found: {summary_path}")
    
    with open(summary_path, "r") as f:
        return json.load(f)


def filter_valid_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter out invalid results based on minimum criteria.
    
    Criteria:
    - status == "success"
    - entries >= 1 (at least some trading activity)
    - loop_latency_avg_ms < 100 (not abnormally slow)
    
    Args:
        results: List of threshold sweep results
    
    Returns:
        Filtered list of valid results
    """
    valid = []
    for result in results:
        if result.get("status") != "success":
            logger.debug(f"Filtered out (status={result.get('status')}): Entry={result['entry_bps']}, TP={result['tp_bps']}")
            continue
        
        if result.get("entries", 0) < 1:
            logger.debug(f"Filtered out (entries={result.get('entries')}): Entry={result['entry_bps']}, TP={result['tp_bps']}")
            continue
        
        if result.get("loop_latency_avg_ms", 999) >= 100:
            logger.debug(f"Filtered out (latency={result.get('loop_latency_avg_ms')}ms): Entry={result['entry_bps']}, TP={result['tp_bps']}")
            continue
        
        valid.append(result)
    
    logger.info(f"Filtered: {len(valid)}/{len(results)} valid results")
    return valid


def compute_score(result: Dict[str, Any]) -> float:
    """
    Compute multi-criteria score for a threshold combination.
    
    Scoring formula (higher is better):
    - Primary: PnL (USD)
    - Secondary: Win Rate (%)
    - Tertiary: Entries (trading activity)
    - Penalty: High slippage, low latency
    
    Score = PnL * 100 + WinRate * 10 + log(Entries+1) * 5 - AvgSlippage * 2
    
    Args:
        result: Threshold sweep result dict
    
    Returns:
        Composite score (higher is better)
    """
    import math
    
    pnl = result.get("pnl_usd", 0.0)
    win_rate = result.get("win_rate_pct", 0.0)
    entries = result.get("entries", 0)
    avg_slippage = (result.get("avg_buy_slippage_bps", 0.0) + result.get("avg_sell_slippage_bps", 0.0)) / 2.0
    
    # Composite score
    score = (
        pnl * 100.0  # Primary: PnL
        + win_rate * 10.0  # Secondary: Win Rate
        + math.log(entries + 1) * 5.0  # Tertiary: Entry count (log scale)
        - avg_slippage * 2.0  # Penalty: Slippage
    )
    
    return score


def rank_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank results by composite score.
    
    Args:
        results: List of valid results
    
    Returns:
        Sorted list (highest score first)
    """
    # Compute scores
    for result in results:
        result["score"] = compute_score(result)
    
    # Sort by score (descending)
    ranked = sorted(results, key=lambda x: x["score"], reverse=True)
    
    return ranked


def select_baseline(ranked_results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Select the best Entry/TP baseline from ranked results.
    
    Args:
        ranked_results: List of results sorted by score
    
    Returns:
        Best result dict, or None if no valid candidates
    """
    if not ranked_results:
        logger.error("No valid results to select from")
        return None
    
    baseline = ranked_results[0]
    logger.info(f"Selected baseline: Entry={baseline['entry_bps']} bps, TP={baseline['tp_bps']} bps")
    logger.info(f"  Score: {baseline['score']:.2f}")
    logger.info(f"  Entries: {baseline['entries']}, Round Trips: {baseline['round_trips']}")
    logger.info(f"  Win Rate: {baseline['win_rate_pct']:.1f}%, PnL: ${baseline['pnl_usd']:.2f}")
    logger.info(f"  Avg Slippage: {(baseline.get('avg_buy_slippage_bps', 0) + baseline.get('avg_sell_slippage_bps', 0)) / 2:.2f} bps")
    logger.info(f"  Loop Latency: {baseline['loop_latency_avg_ms']:.2f} ms")
    
    return baseline


def print_ranking_table(ranked_results: List[Dict[str, Any]]) -> None:
    """Print ranking table with all candidates."""
    logger.info("\n" + "="*90)
    logger.info("Threshold Ranking Table (by composite score)")
    logger.info("="*90)
    logger.info(f"{'Rank':<5} {'Entry':<7} {'TP':<7} {'Score':<8} {'Entries':<8} {'RT':<5} {'WinRate':<9} {'PnL(USD)':<10} {'AvgSlip':<9}")
    logger.info("-"*90)
    
    for i, result in enumerate(ranked_results, 1):
        avg_slip = (result.get("avg_buy_slippage_bps", 0) + result.get("avg_sell_slippage_bps", 0)) / 2
        logger.info(
            f"{i:<5} {result['entry_bps']:<7.1f} {result['tp_bps']:<7.1f} "
            f"{result['score']:<8.2f} {result['entries']:<8} {result['round_trips']:<5} "
            f"{result['win_rate_pct']:<9.1f} ${result['pnl_usd']:<9.2f} {avg_slip:<9.2f}"
        )
    
    logger.info("="*90)


def main():
    parser = argparse.ArgumentParser(
        description="D82-6 Baseline Entry/TP Threshold Selection"
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=Path("logs/d82-5/threshold_sweep_summary.json"),
        help="Path to threshold sweep summary JSON",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("logs/d82-6/baseline_selection.json"),
        help="Path to save baseline selection result",
    )
    
    args = parser.parse_args()
    
    logger.info("="*90)
    logger.info("[D82-6] Baseline Entry/TP Threshold Selection")
    logger.info("="*90)
    logger.info(f"Summary path: {args.summary_path}")
    
    # Load summary
    summary = load_summary_json(args.summary_path)
    results = summary.get("results", [])
    logger.info(f"Total results: {len(results)}")
    
    # Filter valid results
    valid_results = filter_valid_results(results)
    
    if not valid_results:
        logger.error("No valid results found. Cannot select baseline.")
        return 1
    
    # Rank by score
    ranked_results = rank_results(valid_results)
    
    # Print ranking table
    print_ranking_table(ranked_results)
    
    # Select baseline
    baseline = select_baseline(ranked_results)
    
    if not baseline:
        logger.error("Failed to select baseline.")
        return 1
    
    # Save selection result
    selection_result = {
        "timestamp": summary.get("sweep_metadata", {}).get("end_time"),
        "sweep_summary_path": str(args.summary_path),
        "total_candidates": len(results),
        "valid_candidates": len(valid_results),
        "selected_baseline": {
            "entry_bps": baseline["entry_bps"],
            "tp_bps": baseline["tp_bps"],
            "run_id": baseline["run_id"],
            "score": baseline["score"],
            "entries": baseline["entries"],
            "round_trips": baseline["round_trips"],
            "win_rate_pct": baseline["win_rate_pct"],
            "pnl_usd": baseline["pnl_usd"],
            "avg_buy_slippage_bps": baseline.get("avg_buy_slippage_bps", 0.0),
            "avg_sell_slippage_bps": baseline.get("avg_sell_slippage_bps", 0.0),
            "loop_latency_avg_ms": baseline["loop_latency_avg_ms"],
        },
        "top_5_candidates": [
            {
                "rank": i + 1,
                "entry_bps": r["entry_bps"],
                "tp_bps": r["tp_bps"],
                "score": r["score"],
                "entries": r["entries"],
                "round_trips": r["round_trips"],
                "win_rate_pct": r["win_rate_pct"],
                "pnl_usd": r["pnl_usd"],
            }
            for i, r in enumerate(ranked_results[:5])
        ],
    }
    
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_path, "w") as f:
        json.dump(selection_result, f, indent=2)
    
    logger.info(f"\nBaseline selection saved to: {args.output_path}")
    logger.info("="*90)
    
    return 0


if __name__ == "__main__":
    exit(main())
