#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-5: Threshold Tuning Sweep Runner

Grid search over Entry/TP thresholds to evaluate impact on Entry count, Win Rate, and PnL.

Purpose:
- Systematically vary Entry Threshold (bps) and TP Threshold (bps)
- Execute 6-10 minute Real PAPER runs for each combination
- Collect KPI and Trade Log metrics
- Generate comprehensive Summary JSON

Usage:
    # Dry-run (print commands only)
    python scripts/run_d82_5_threshold_sweep.py --dry-run

    # Actual execution (9 combinations × 6 min = 54 min)
    python scripts/run_d82_5_threshold_sweep.py

    # Custom parameters
    python scripts/run_d82_5_threshold_sweep.py \
        --entry-bps-list "0.3,0.5,0.7" \
        --tp-bps-list "1.0,1.5,2.0" \
        --run-duration-seconds 360 \
        --topn-size 20
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="D82-5: Threshold Sweep Runner (Grid Search)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--entry-bps-list",
        type=str,
        default="0.3,0.5,0.7",
        help="Comma-separated Entry threshold values (bps), default: 0.3,0.5,0.7",
    )
    parser.add_argument(
        "--tp-bps-list",
        type=str,
        default="1.0,1.5,2.0",
        help="Comma-separated TP threshold values (bps), default: 1.0,1.5,2.0",
    )
    parser.add_argument(
        "--run-duration-seconds",
        type=int,
        default=360,
        help="Duration per run in seconds, default: 360 (6 minutes)",
    )
    parser.add_argument(
        "--topn-size",
        type=int,
        default=20,
        help="TopN size (20|50), default: 20",
    )
    parser.add_argument(
        "--validation-profile",
        type=str,
        default="topn_research",
        help="Validation profile (none|fill_model|topn_research), default: topn_research",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: print commands without execution",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="logs/d82-5",
        help="Output directory for KPI/Trade Logs/Summary, default: logs/d82-5",
    )
    return parser.parse_args()


def generate_run_id(entry_bps: float, tp_bps: float, timestamp: str) -> str:
    """
    Generate unique run_id for a threshold combination.
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        timestamp: Timestamp string (YYYYMMDDHHmmss)
    
    Returns:
        run_id string (e.g., "d82-5-E0.3_TP1.0-20251205103000")
    """
    entry_str = f"E{entry_bps:.1f}".replace(".", "p")
    tp_str = f"TP{tp_bps:.1f}".replace(".", "p")
    return f"d82-5-{entry_str}_{tp_str}-{timestamp}"


def build_command(
    entry_bps: float,
    tp_bps: float,
    run_id: str,
    args: argparse.Namespace,
    kpi_path: Path,
) -> List[str]:
    """
    Build PowerShell command for a single threshold combination.
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        run_id: Unique run ID
        args: Command-line arguments
        kpi_path: Path to KPI output file
    
    Returns:
        Command as list of strings (for subprocess.run)
    """
    project_root = Path(__file__).parent.parent
    runner_script = project_root / "scripts" / "run_d77_0_topn_arbitrage_paper.py"
    
    # PowerShell 환경변수 설정 + Python 실행
    cmd = [
        "powershell",
        "-Command",
        f"$env:ARBITRAGE_ENV='paper'; "
        f"$env:TOPN_ENTRY_MIN_SPREAD_BPS='{entry_bps}'; "
        f"$env:TOPN_EXIT_TP_SPREAD_BPS='{tp_bps}'; "
        f"python {runner_script} "
        f"--data-source real "
        f"--topn-size {args.topn_size} "
        f"--run-duration-seconds {args.run_duration_seconds} "
        f"--validation-profile {args.validation_profile} "
        f"--kpi-output-path {kpi_path} "
        f"--session-id {run_id}"
    ]
    
    return cmd


def load_kpi_json(kpi_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load KPI JSON file.
    
    Args:
        kpi_path: Path to KPI JSON file
    
    Returns:
        KPI dict or None if failed
    """
    if not kpi_path.exists():
        logger.warning(f"KPI file not found: {kpi_path}")
        return None
    
    try:
        with open(kpi_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load KPI JSON: {e}")
        return None


def parse_trade_log(trade_log_path: Path) -> Optional[Dict[str, float]]:
    """
    Parse Trade Log JSONL to extract average spread/slippage.
    
    Args:
        trade_log_path: Path to Trade Log JSONL file
    
    Returns:
        Dict with avg_entry_spread_bps, avg_exit_spread_bps, or None
    """
    if not trade_log_path.exists():
        logger.warning(f"Trade Log not found: {trade_log_path}")
        return None
    
    try:
        entry_spreads = []
        exit_spreads = []
        
        with open(trade_log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                
                # Entry spread (있으면)
                if "entry_spread_bps" in entry:
                    entry_spreads.append(entry["entry_spread_bps"])
                
                # Exit spread (있으면)
                if "exit_spread_bps" in entry:
                    exit_spreads.append(entry["exit_spread_bps"])
        
        avg_entry_spread = sum(entry_spreads) / len(entry_spreads) if entry_spreads else 0.0
        avg_exit_spread = sum(exit_spreads) / len(exit_spreads) if exit_spreads else 0.0
        
        return {
            "avg_entry_spread_bps": avg_entry_spread,
            "avg_exit_spread_bps": avg_exit_spread,
        }
    except Exception as e:
        logger.error(f"Failed to parse Trade Log: {e}")
        return None


def execute_single_run(
    entry_bps: float,
    tp_bps: float,
    run_id: str,
    args: argparse.Namespace,
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Execute a single threshold combination run.
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        run_id: Unique run ID
        args: Command-line arguments
        output_dir: Output directory
    
    Returns:
        Result dict with KPI + Trade Log metrics
    """
    # Paths
    kpi_path = output_dir / "runs" / f"{run_id}_kpi.json"
    trade_log_path = output_dir / "trades" / run_id / "top20_trade_log.jsonl"
    
    # Ensure directories exist
    kpi_path.parent.mkdir(parents=True, exist_ok=True)
    trade_log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build command
    cmd = build_command(entry_bps, tp_bps, run_id, args, kpi_path)
    
    logger.info(f"[Run {run_id}] Entry={entry_bps} bps, TP={tp_bps} bps")
    
    if args.dry_run:
        logger.info(f"[DRY-RUN] Would execute: {' '.join(cmd)}")
        # Dry-run: return dummy result
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "duration_sec": args.run_duration_seconds,
            "entries": 0,
            "round_trips": 0,
            "win_rate_pct": 0.0,
            "avg_spread_bps": 0.0,
            "avg_buy_slippage_bps": 0.0,
            "avg_sell_slippage_bps": 0.0,
            "pnl_usd": 0.0,
            "loop_latency_avg_ms": 0.0,
            "kpi_path": str(kpi_path),
            "trade_log_path": str(trade_log_path),
            "status": "dry_run",
        }
    
    # Execute
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"[Run {run_id}] Execution completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"[Run {run_id}] Execution failed: {e}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "status": "failed",
            "error": str(e),
        }
    
    # Load KPI
    kpi = load_kpi_json(kpi_path)
    if not kpi:
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "status": "kpi_missing",
        }
    
    # Parse Trade Log
    trade_metrics = parse_trade_log(trade_log_path)
    
    # Combine results
    result_dict = {
        "entry_bps": entry_bps,
        "tp_bps": tp_bps,
        "run_id": run_id,
        "duration_sec": kpi.get("actual_duration_seconds", args.run_duration_seconds),
        "entries": kpi.get("entry_trades", 0),
        "round_trips": kpi.get("round_trips_completed", 0),
        "win_rate_pct": kpi.get("win_rate_pct", 0.0),
        "avg_buy_slippage_bps": kpi.get("avg_buy_slippage_bps", 0.0),
        "avg_sell_slippage_bps": kpi.get("avg_sell_slippage_bps", 0.0),
        "pnl_usd": kpi.get("total_pnl_usd", 0.0),
        "loop_latency_avg_ms": kpi.get("loop_latency_avg_ms", 0.0),
        "kpi_path": str(kpi_path),
        "trade_log_path": str(trade_log_path),
        "status": "success",
    }
    
    # Add trade log metrics
    if trade_metrics:
        result_dict["avg_entry_spread_bps"] = trade_metrics["avg_entry_spread_bps"]
        result_dict["avg_exit_spread_bps"] = trade_metrics["avg_exit_spread_bps"]
    
    return result_dict


def main():
    """Main execution."""
    args = parse_args()
    
    # Parse threshold lists
    entry_bps_list = [float(x.strip()) for x in args.entry_bps_list.split(",")]
    tp_bps_list = [float(x.strip()) for x in args.tp_bps_list.split(",")]
    
    total_combinations = len(entry_bps_list) * len(tp_bps_list)
    estimated_time_min = total_combinations * args.run_duration_seconds / 60
    
    logger.info("=" * 80)
    logger.info("[D82-5] Threshold Sweep Configuration")
    logger.info(f"  Entry BPS: {entry_bps_list}")
    logger.info(f"  TP BPS: {tp_bps_list}")
    logger.info(f"  Total Combinations: {total_combinations}")
    logger.info(f"  Duration per run: {args.run_duration_seconds}s ({args.run_duration_seconds / 60:.1f} minutes)")
    logger.info(f"  Total estimated time: {estimated_time_min:.0f} minutes")
    logger.info(f"  Dry-run: {args.dry_run}")
    logger.info("=" * 80)
    
    # Output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sweep metadata
    sweep_metadata = {
        "start_time": datetime.now().isoformat(),
        "total_runs": total_combinations,
        "duration_per_run_sec": args.run_duration_seconds,
        "entry_bps_list": entry_bps_list,
        "tp_bps_list": tp_bps_list,
        "topn_size": args.topn_size,
        "validation_profile": args.validation_profile,
        "dry_run": args.dry_run,
    }
    
    # Execute all combinations
    results = []
    run_count = 0
    
    for entry_bps in entry_bps_list:
        for tp_bps in tp_bps_list:
            run_count += 1
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            run_id = generate_run_id(entry_bps, tp_bps, timestamp)
            
            logger.info(f"\n[Run {run_count}/{total_combinations}] Starting...")
            
            result = execute_single_run(entry_bps, tp_bps, run_id, args, output_dir)
            results.append(result)
            
            logger.info(f"[Run {run_count}/{total_combinations}] Completed: {result.get('status', 'unknown')}")
    
    # Finalize metadata
    sweep_metadata["end_time"] = datetime.now().isoformat()
    
    # Save summary JSON
    summary = {
        "sweep_metadata": sweep_metadata,
        "results": results,
    }
    
    summary_path = output_dir / "threshold_sweep_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info("\n" + "=" * 80)
    logger.info(f"[D82-5] Threshold Sweep Completed")
    logger.info(f"  Total Runs: {run_count}")
    logger.info(f"  Summary saved to: {summary_path}")
    logger.info("=" * 80)
    
    # Print result table
    logger.info("\nResults Summary:")
    logger.info(f"{'Entry':<8} {'TP':<8} {'Entries':<8} {'RT':<6} {'WinRate':<8} {'PnL(USD)':<12} {'Status':<10}")
    logger.info("-" * 80)
    for r in results:
        logger.info(
            f"{r.get('entry_bps', 0.0):<8.1f} "
            f"{r.get('tp_bps', 0.0):<8.1f} "
            f"{r.get('entries', 0):<8} "
            f"{r.get('round_trips', 0):<6} "
            f"{r.get('win_rate_pct', 0.0):<8.1f} "
            f"{r.get('pnl_usd', 0.0):<12.2f} "
            f"{r.get('status', 'unknown'):<10}"
        )


if __name__ == "__main__":
    main()
