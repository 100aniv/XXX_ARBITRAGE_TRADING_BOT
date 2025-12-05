# -*- coding: utf-8 -*-
"""
D82-9: Paper Results Summarizer
Aggregate KPI logs from Real PAPER runs into paper_summary.json
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def calculate_composite_score(kpi: Dict[str, Any]) -> float:
    """
    Calculate composite score from KPI metrics.
    Formula (D82-5 style): PnL * 100 + WinRate * 10 + log(RT+1) * 5 - AvgSlip * 2
    """
    pnl = kpi.get("total_pnl_usd", 0.0)
    win_rate = kpi.get("win_rate_pct", 0.0)
    rt = kpi.get("round_trips_completed", 0)
    
    # Slippage (buy + sell) / 2
    buy_slip = kpi.get("avg_buy_slippage_bps", 0.0)
    sell_slip = kpi.get("avg_sell_slippage_bps", 0.0)
    avg_slip = (buy_slip + sell_slip) / 2.0
    
    score = (
        pnl * 100.0 +
        win_rate * 10.0 +
        math.log(rt + 1) * 5.0 -
        avg_slip * 2.0
    )
    
    return round(score, 2)


def parse_run_id(run_id: str) -> Dict[str, float]:
    """
    Extract entry_bps and tp_bps from run_id.
    Example: d82-9-E10p0_TP13p0-20251205193220 -> {entry: 10.0, tp: 13.0}
    """
    parts = run_id.split("-")
    # E10p0_TP13p0 part
    entry_tp_part = parts[2]
    entry_str, tp_str = entry_tp_part.split("_")
    
    # E10p0 -> 10.0
    entry_bps = float(entry_str[1:].replace("p", "."))
    # TP13p0 -> 13.0
    tp_bps = float(tp_str[2:].replace("p", "."))
    
    return {"entry_bps": entry_bps, "tp_bps": tp_bps}


def summarize_results(kpi_files: List[Path], output_path: Path):
    """
    Aggregate KPI files into summary JSON with composite scoring.
    """
    logger.info("=" * 80)
    logger.info("D82-9 Paper Results Summarizer")
    logger.info("=" * 80)
    logger.info(f"Found {len(kpi_files)} KPI files")
    
    results = []
    
    for kpi_file in sorted(kpi_files):
        logger.info(f"Processing: {kpi_file.name}")
        
        with open(kpi_file, "r", encoding="utf-8") as f:
            kpi = json.load(f)
        
        # Extract entry/tp from filename
        # d82-9-E10p0_TP13p0-20251205193220_kpi.json
        run_id = kpi_file.stem.replace("_kpi", "")
        params = parse_run_id(run_id)
        
        # Calculate composite score
        score = calculate_composite_score(kpi)
        
        result = {
            "run_id": run_id,
            "entry_bps": params["entry_bps"],
            "tp_bps": params["tp_bps"],
            "duration_minutes": kpi.get("duration_minutes", 0.0),
            "actual_duration_seconds": kpi.get("actual_duration_seconds", 0.0),
            "total_trades": kpi.get("total_trades", 0),
            "entry_trades": kpi.get("entry_trades", 0),
            "exit_trades": kpi.get("exit_trades", 0),
            "round_trips_completed": kpi.get("round_trips_completed", 0),
            "win_rate_pct": kpi.get("win_rate_pct", 0.0),
            "total_pnl_usd": kpi.get("total_pnl_usd", 0.0),
            "loop_latency_avg_ms": kpi.get("loop_latency_avg_ms", 0.0),
            "loop_latency_p99_ms": kpi.get("loop_latency_p99_ms", 0.0),
            "avg_buy_slippage_bps": kpi.get("avg_buy_slippage_bps", 0.0),
            "avg_sell_slippage_bps": kpi.get("avg_sell_slippage_bps", 0.0),
            "avg_buy_fill_ratio": kpi.get("avg_buy_fill_ratio", 0.0),
            "avg_sell_fill_ratio": kpi.get("avg_sell_fill_ratio", 0.0),
            "partial_fills_count": kpi.get("partial_fills_count", 0),
            "failed_fills_count": kpi.get("failed_fills_count", 0),
            "memory_usage_mb": kpi.get("memory_usage_mb", 0.0),
            "cpu_usage_pct": kpi.get("cpu_usage_pct", 0.0),
            "composite_score": score,
        }
        
        results.append(result)
        
        logger.info(f"  Entry={params['entry_bps']} bps, TP={params['tp_bps']} bps")
        logger.info(f"  RT={result['round_trips_completed']}, WR={result['win_rate_pct']}%, PnL=${result['total_pnl_usd']:.2f}")
        logger.info(f"  Composite Score: {score}")
    
    # Sort by composite score (descending)
    results_sorted = sorted(results, key=lambda x: x["composite_score"], reverse=True)
    
    summary = {
        "execution_timestamp": datetime.now().isoformat(),
        "total_runs": len(results),
        "duration_per_run_seconds": 600,
        "results": results_sorted,
        "best_candidate": results_sorted[0] if results_sorted else None,
    }
    
    # Write summary
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info("=" * 80)
    logger.info(f"Summary saved to: {output_path}")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Top 3 Candidates by Composite Score:")
    for i, result in enumerate(results_sorted[:3], 1):
        logger.info(f"{i}. Entry={result['entry_bps']} bps, TP={result['tp_bps']} bps")
        logger.info(f"   Score={result['composite_score']}, RT={result['round_trips_completed']}, WR={result['win_rate_pct']}%")


def main():
    project_root = Path(__file__).parent.parent
    runs_dir = project_root / "logs" / "d82-9" / "runs"
    output_path = project_root / "logs" / "d82-9" / "paper_summary.json"
    
    if not runs_dir.exists():
        logger.error(f"Runs directory not found: {runs_dir}")
        return
    
    kpi_files = list(runs_dir.glob("d82-9-E*_kpi.json"))
    
    if not kpi_files:
        logger.error(f"No KPI files found in: {runs_dir}")
        return
    
    summarize_results(kpi_files, output_path)


if __name__ == "__main__":
    main()
