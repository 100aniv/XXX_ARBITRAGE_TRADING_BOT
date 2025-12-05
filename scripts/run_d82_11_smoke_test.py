#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-11: Recalibrated TP/Entry PAPER Smoke Test Runner

목적:
    D82-10에서 Edge 모델 재보정을 통해 선정된 8개 후보를
    실제 PAPER 환경에서 단계적으로 검증하는 Smoke Test 하네스.

배경:
    - D82-9: Entry [10,12] × TP [13,14,15] → 모두 실패 (Edge < 0)
    - D82-10: 비용 구조 재측정 (13.28 bps) → 8개 후보 재선정 (Edge >= 0)
    - D82-11: 10분 → 20분 → 60분 단계적 PAPER Smoke Test

핵심 설계:
    - D82-9 Runner 패턴 재사용 (최소 수정)
    - D82-10 후보 JSON 로드 & Top-N 선택
    - Duration별 Summary JSON 생성
    - KPI 요약 및 집계

Acceptance Criteria (Implementation):
    - Top 3 후보 기준:
      - 각 후보에 대해 duration 지정 PAPER 실행 가능
      - KPI/Summary JSON 정상 생성
      - D82-9/D82-10 테스트 100% PASS 유지

Usage:
    # Dry-run
    python scripts/run_d82_11_smoke_test.py --duration-seconds 600 --top-n 3 --dry-run
    
    # 10분 Smoke (Top 3)
    python scripts/run_d82_11_smoke_test.py --duration-seconds 600 --top-n 3
    
    # 20분 Validation (Top 2)
    python scripts/run_d82_11_smoke_test.py --duration-seconds 1200 --top-n 2
    
    # 60분 Confirmation (Top 1)
    python scripts/run_d82_11_smoke_test.py --duration-seconds 3600 --top-n 1

Author: arbitrage-lite project
Date: 2025-12-05
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


# =============================================================================
# Configuration & Defaults
# =============================================================================

DEFAULT_CANDIDATES_JSON = "logs/d82-10/recalibrated_tp_entry_candidates.json"
DEFAULT_OUTPUT_DIR = "logs/d82-11"
DEFAULT_TOP_N = 3
DEFAULT_TOPN_SIZE = 20


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="D82-11: Recalibrated TP/Entry PAPER Smoke Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        required=True,
        help="Duration per run in seconds (600/1200/3600 recommended)",
    )
    parser.add_argument(
        "--candidates-json",
        type=str,
        default=DEFAULT_CANDIDATES_JSON,
        help=f"Path to D82-10 candidates JSON, default: {DEFAULT_CANDIDATES_JSON}",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"Number of top candidates to run, default: {DEFAULT_TOP_N}",
    )
    parser.add_argument(
        "--summary-output",
        type=str,
        default=None,
        help="Summary JSON output path, default: logs/d82-11/d82_11_summary_{duration}.json",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for KPI files, default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--topn-size",
        type=int,
        default=DEFAULT_TOPN_SIZE,
        help=f"Arbitrage engine TOPN size, default: {DEFAULT_TOPN_SIZE}",
    )
    parser.add_argument(
        "--enable-edge-monitor",
        action="store_true",
        help="Enable Runtime Edge Monitor (logs to edge_monitor/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: print commands without execution",
    )
    
    return parser.parse_args()


# =============================================================================
# Candidate Loading & Selection
# =============================================================================

def load_recalibrated_candidates(path: Path) -> List[Dict[str, Any]]:
    """
    Load D82-10 recalibrated candidates from JSON.
    
    Args:
        path: Path to candidates JSON file
    
    Returns:
        List of candidate dicts
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        candidates = data.get("candidates", [])
        logger.info(f"Loaded {len(candidates)} candidates from {path}")
        return candidates
    
    except FileNotFoundError:
        logger.error(f"Candidates JSON not found: {path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse candidates JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to load candidates: {e}")
        return []


def select_top_n_candidates(
    candidates: List[Dict[str, Any]],
    n: int,
) -> List[Dict[str, Any]]:
    """
    Select top N candidates by sorting.
    
    Sorting criteria (descending):
        1. edge_realistic
        2. edge_conservative
    
    Args:
        candidates: List of candidate dicts
        n: Number of top candidates to select
    
    Returns:
        List of top N candidates
    """
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (
            -c.get("edge_realistic", 0),
            -c.get("edge_conservative", 0),
        )
    )
    
    selected = sorted_candidates[:n]
    logger.info(f"Selected top {len(selected)} candidates:")
    for i, c in enumerate(selected, 1):
        logger.info(
            f"  {i}. Entry {c['entry_bps']} bps, TP {c['tp_bps']} bps, "
            f"Edge (Real) {c['edge_realistic']:.2f} bps"
        )
    
    return selected


# =============================================================================
# Run ID & Command Building (D82-9 패턴 재사용)
# =============================================================================

def generate_run_id(
    duration_sec: int,
    entry_bps: float,
    tp_bps: float,
    timestamp: str,
) -> str:
    """
    Generate unique run_id for D82-11.
    
    Format: d82-11-{duration}-E{entry}_TP{tp}-{timestamp}
    Example: d82-11-600-E16p0_TP18p0-20251205215000
    
    Args:
        duration_sec: Run duration in seconds
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        timestamp: Timestamp string (YYYYMMDDHHmmss)
    
    Returns:
        run_id string
    """
    entry_str = f"E{entry_bps:.1f}".replace(".", "p")
    tp_str = f"TP{tp_bps:.1f}".replace(".", "p")
    return f"d82-11-{duration_sec}-{entry_str}_{tp_str}-{timestamp}"


def build_command(
    entry_bps: float,
    tp_bps: float,
    run_id: str,
    args: argparse.Namespace,
    kpi_path: Path,
) -> tuple[List[str], Dict[str, str]]:
    """
    Build Python command for a single candidate.
    
    Reuses D82-9 pattern: subprocess call to run_d77_0_topn_arbitrage_paper.py
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        run_id: Unique run ID
        args: Command-line arguments
        kpi_path: Path to KPI output file
    
    Returns:
        Tuple of (command as list, environment variables dict)
    """
    project_root = Path(__file__).parent.parent
    runner_script = project_root / "scripts" / "run_d77_0_topn_arbitrage_paper.py"
    
    # Python command
    cmd = [
        "python",
        str(runner_script),
        "--data-source", "real",
        "--topn-size", str(args.topn_size),
        "--run-duration-seconds", str(args.duration_seconds),
        "--validation-profile", "topn_research",
        "--kpi-output-path", str(kpi_path),
    ]
    
    # Environment variables
    env_vars = os.environ.copy()
    env_vars["ARBITRAGE_ENV"] = "paper"
    env_vars["TOPN_ENTRY_MIN_SPREAD_BPS"] = str(entry_bps)
    env_vars["TOPN_EXIT_TP_SPREAD_BPS"] = str(tp_bps)
    
    # Edge Monitor (optional)
    if args.enable_edge_monitor:
        env_vars["ENABLE_RUNTIME_EDGE_MONITOR"] = "1"
        edge_monitor_dir = Path(args.output_dir) / "edge_monitor"
        edge_monitor_dir.mkdir(parents=True, exist_ok=True)
        edge_monitor_path = edge_monitor_dir / f"{run_id}_edge.jsonl"
        env_vars["EDGE_MONITOR_LOG_PATH"] = str(edge_monitor_path)
    
    return cmd, env_vars


# =============================================================================
# KPI Parsing (D82-9 파서 재사용)
# =============================================================================

def parse_kpi_file(kpi_path: Path) -> Dict[str, Any]:
    """
    Parse KPI JSON file and extract summary metrics.
    
    Reuses D82-9 KPI structure.
    
    Args:
        kpi_path: Path to KPI JSON file
    
    Returns:
        Dict of summary metrics
    """
    try:
        with open(kpi_path, "r", encoding="utf-8") as f:
            kpi = json.load(f)
        
        # Calculate exit percentages
        exit_reasons = kpi.get("exit_reasons", {})
        total_exits = sum(exit_reasons.values())
        tp_exits = exit_reasons.get("tp", 0)
        timeout_exits = exit_reasons.get("time_limit", 0)
        
        tp_exit_pct = (tp_exits / total_exits * 100) if total_exits > 0 else 0.0
        timeout_exit_pct = (timeout_exits / total_exits * 100) if total_exits > 0 else 0.0
        
        return {
            "round_trips_completed": kpi.get("round_trips_completed", 0),
            "win_rate_pct": kpi.get("win_rate_pct", 0.0),
            "tp_exit_pct": tp_exit_pct,
            "timeout_exit_pct": timeout_exit_pct,
            "total_pnl_usd": kpi.get("total_pnl_usd", 0.0),
            "avg_pnl_per_rt_usd": kpi.get("avg_pnl_per_rt_usd", 0.0),
            "buy_fill_ratio_avg": kpi.get("buy_fill_ratio_avg", 0.0),
            "sell_fill_ratio_avg": kpi.get("sell_fill_ratio_avg", 0.0),
            "slippage_avg_bps": kpi.get("slippage_avg_bps", 0.0),
            "loop_latency_avg_ms": kpi.get("loop_latency_avg_ms", 0.0),
        }
    
    except FileNotFoundError:
        logger.warning(f"KPI file not found: {kpi_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse KPI JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Failed to parse KPI file: {e}")
        return {}


# =============================================================================
# Single Run Execution
# =============================================================================

def execute_single_run(
    candidate: Dict[str, Any],
    run_index: int,
    total_runs: int,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """
    Execute single candidate PAPER run.
    
    Args:
        candidate: Candidate dict from D82-10 JSON
        run_index: Current run index (1-based)
        total_runs: Total number of runs
        args: Command-line arguments
    
    Returns:
        Result dict with status, paths, KPI summary, etc.
    """
    entry_bps = candidate["entry_bps"]
    tp_bps = candidate["tp_bps"]
    edge_realistic = candidate.get("edge_realistic", 0.0)
    edge_conservative = candidate.get("edge_conservative", 0.0)
    rationale = candidate.get("rationale", "")
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    run_id = generate_run_id(args.duration_seconds, entry_bps, tp_bps, timestamp)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"[Run {run_index}/{total_runs}] Starting...")
    logger.info(f"[Run {run_id}] Entry={entry_bps} bps, TP={tp_bps} bps")
    logger.info(f"[Run {run_id}] Edge (Real)={edge_realistic:.2f} bps, (Cons)={edge_conservative:.2f} bps")
    logger.info(f"[Run {run_id}] Rationale: {rationale}")
    logger.info(f"[Run {run_id}] Duration: {args.duration_seconds}s")
    
    # Output paths
    runs_dir = Path(args.output_dir) / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    kpi_path = runs_dir / f"{run_id}_kpi.json"
    
    logger.info(f"[Run {run_id}] KPI: {kpi_path}")
    
    # Edge Monitor path (optional)
    if args.enable_edge_monitor:
        edge_monitor_dir = Path(args.output_dir) / "edge_monitor"
        edge_monitor_path = edge_monitor_dir / f"{run_id}_edge.jsonl"
        logger.info(f"[Run {run_id}] Edge Monitor: {edge_monitor_path}")
    
    # Build command
    cmd, env_vars = build_command(entry_bps, tp_bps, run_id, args, kpi_path)
    
    if args.dry_run:
        logger.info(f"[DRY-RUN] Command: {' '.join(cmd)}")
        logger.info(f"[DRY-RUN] Env: TOPN_ENTRY_MIN_SPREAD_BPS={entry_bps}, TOPN_EXIT_TP_SPREAD_BPS={tp_bps}")
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "edge_optimistic": candidate.get("edge_optimistic", 0.0),
            "edge_realistic": edge_realistic,
            "edge_conservative": edge_conservative,
            "run_id": run_id,
            "kpi_path": str(kpi_path),
            "kpi_summary": {},
            "status": "dry_run",
        }
    
    # Execute
    try:
        logger.info(f"[Run {run_id}] Executing...")
        
        # Calculate timeout: duration + 60s buffer
        timeout_sec = args.duration_seconds + 60
        
        result = subprocess.run(
            cmd,
            env=env_vars,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
        
        # Log stderr if present
        if result.stderr:
            logger.warning(f"[Run {run_id}] Stderr output:\n{result.stderr[:500]}...")
        
        # Check KPI file existence
        kpi_exists = kpi_path.exists()
        
        if result.returncode == 0:
            if kpi_exists:
                logger.info(f"[Run {run_id}] Execution completed successfully")
                logger.info(f"[Run {run_id}] KPI file verified: {kpi_path}")
                status = "ok"
            else:
                logger.error(f"[Run {run_id}] Execution succeeded but KPI file not found")
                status = "no_kpi"
        else:
            logger.error(f"[Run {run_id}] Execution failed with exit code: {result.returncode}")
            status = "error"
        
        # Parse KPI
        kpi_summary = parse_kpi_file(kpi_path) if kpi_exists else {}
        
        # Determine final status
        if status == "ok" and kpi_summary.get("round_trips_completed", 0) == 0:
            status = "no_trades"
        
        logger.info(f"[Run {run_index}/{total_runs}] Completed: {status}")
        
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "edge_optimistic": candidate.get("edge_optimistic", 0.0),
            "edge_realistic": edge_realistic,
            "edge_conservative": edge_conservative,
            "run_id": run_id,
            "kpi_path": str(kpi_path),
            "kpi_summary": kpi_summary,
            "status": status,
        }
    
    except subprocess.TimeoutExpired:
        logger.error(f"[Run {run_id}] Execution timed out after {timeout_sec}s")
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "edge_optimistic": candidate.get("edge_optimistic", 0.0),
            "edge_realistic": edge_realistic,
            "edge_conservative": edge_conservative,
            "run_id": run_id,
            "kpi_path": str(kpi_path),
            "kpi_summary": {},
            "status": "timeout",
        }
    
    except Exception as e:
        logger.exception(f"[Run {run_id}] Exception during execution: {e}")
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "edge_optimistic": candidate.get("edge_optimistic", 0.0),
            "edge_realistic": edge_realistic,
            "edge_conservative": edge_conservative,
            "run_id": run_id,
            "kpi_path": str(kpi_path),
            "kpi_summary": {},
            "status": "error",
            "error": str(e),
        }


# =============================================================================
# Summary Generation
# =============================================================================

def generate_summary(
    results: List[Dict[str, Any]],
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """
    Generate summary JSON from all run results.
    
    Args:
        results: List of result dicts from execute_single_run()
        args: Command-line arguments
    
    Returns:
        Summary dict
    """
    successful_runs = [r for r in results if r["status"] == "ok"]
    failed_runs = [r for r in results if r["status"] not in ["ok", "dry_run"]]
    
    total_round_trips = sum(r["kpi_summary"].get("round_trips_completed", 0) for r in successful_runs)
    total_pnl_usd = sum(r["kpi_summary"].get("total_pnl_usd", 0.0) for r in successful_runs)
    
    avg_round_trips = total_round_trips / len(successful_runs) if successful_runs else 0.0
    avg_pnl_usd = total_pnl_usd / len(successful_runs) if successful_runs else 0.0
    
    return {
        "metadata": {
            "duration_seconds": args.duration_seconds,
            "top_n": args.top_n,
            "candidates_source": args.candidates_json,
            "created_at": datetime.now().isoformat(),
            "d82_11_implementation_version": "1.0",
        },
        "candidates": results,
        "summary_stats": {
            "total_runs": len(results),
            "successful_runs": len(successful_runs),
            "failed_runs": len(failed_runs),
            "total_round_trips": total_round_trips,
            "avg_round_trips": avg_round_trips,
            "total_pnl_usd": total_pnl_usd,
            "avg_pnl_usd": avg_pnl_usd,
        },
    }


def save_summary(summary: Dict[str, Any], output_path: Path):
    """
    Save summary JSON to file.
    
    Args:
        summary: Summary dict
        output_path: Path to output JSON file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Summary saved to: {output_path}")


# =============================================================================
# Main
# =============================================================================

def main():
    """Main entry point."""
    args = parse_args()
    
    logger.info("=" * 80)
    logger.info("[D82-11] Recalibrated TP/Entry PAPER Smoke Test")
    logger.info("=" * 80)
    logger.info(f"Duration: {args.duration_seconds}s")
    logger.info(f"Top-N: {args.top_n}")
    logger.info(f"Candidates JSON: {args.candidates_json}")
    logger.info(f"Output Dir: {args.output_dir}")
    logger.info(f"Dry-run: {args.dry_run}")
    logger.info("")
    
    # Load candidates
    candidates_path = Path(args.candidates_json)
    candidates = load_recalibrated_candidates(candidates_path)
    
    if not candidates:
        logger.error("No candidates loaded. Exiting.")
        sys.exit(1)
    
    # Select top N
    selected_candidates = select_top_n_candidates(candidates, args.top_n)
    
    if not selected_candidates:
        logger.error("No candidates selected. Exiting.")
        sys.exit(1)
    
    logger.info("")
    logger.info(f"Running {len(selected_candidates)} candidates...")
    logger.info("")
    
    # Execute runs
    results = []
    for i, candidate in enumerate(selected_candidates, 1):
        result = execute_single_run(candidate, i, len(selected_candidates), args)
        results.append(result)
    
    # Generate summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("Generating summary...")
    logger.info("=" * 80)
    
    summary = generate_summary(results, args)
    
    # Determine summary output path
    if args.summary_output:
        summary_path = Path(args.summary_output)
    else:
        summary_path = Path(args.output_dir) / f"d82_11_summary_{args.duration_seconds}.json"
    
    save_summary(summary, summary_path)
    
    # Log summary stats
    stats = summary["summary_stats"]
    logger.info("")
    logger.info(f"Total Runs: {stats['total_runs']}")
    logger.info(f"Successful Runs: {stats['successful_runs']}")
    logger.info(f"Failed Runs: {stats['failed_runs']}")
    logger.info(f"Total Round Trips: {stats['total_round_trips']}")
    logger.info(f"Avg Round Trips: {stats['avg_round_trips']:.1f}")
    logger.info(f"Total PnL USD: ${stats['total_pnl_usd']:.2f}")
    logger.info(f"Avg PnL USD: ${stats['avg_pnl_usd']:.2f}")
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D82-11] Smoke Test Complete")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
