#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-8: Intermediate Threshold Long-run Real PAPER Runner

목적:
    D82-6 (Entry 0.3-0.7, TP 1.0-2.0 bps) → 구조적 마이너스 Zone
    D82-7 (Entry 14-18, TP 19-25 bps) → 구조적 플러스 but 거래 없음
    
    **Intermediate Zone (Entry 10-14, TP 12-20 bps)**에서 Long-run을 실행하여:
    - 구조적으로 플러스 Zone +
    - 실제 거래량 및 수익성까지 확보한
    → "운영 가능한 Threshold 후보"를 선정.

핵심 설계:
    - 3-4개 핵심 조합만 선택 (Entry 10/12/14 × TP 15/18/20)
    - 조합당 최소 20분 이상 실행 (RoundTrip ≥ 10개 목표)
    - Runtime Edge Monitor 활성화
    - D82-5 Sweep 인프라 재사용
    
선택된 조합 (근거 포함):
    1. Entry 10, TP 15: 가장 낮은 threshold, 거래 기회 최대화
    2. Entry 12, TP 18: 중간 균형점, D82-6/7 중간 지점
    3. Entry 14, TP 20: Intermediate Zone 최상단, D82-7과 비교 가능
    
    → 총 3조합 × 20분 = 60분

Usage:
    # Dry-run
    python scripts/run_d82_8_intermediate_threshold_longrun.py --dry-run
    
    # 실제 실행 (60분)
    python scripts/run_d82_8_intermediate_threshold_longrun.py

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

# Intermediate Threshold 조합 (근거: D82-6/7 분석 결과)
DEFAULT_COMBINATIONS = [
    {
        "entry_bps": 10.0,
        "tp_bps": 15.0,
        "rationale": "가장 낮은 threshold, 거래 기회 최대화. D82-6(0.7/2.0) 대비 14.3배, D82-7(14/19) 대비 71%"
    },
    {
        "entry_bps": 12.0,
        "tp_bps": 18.0,
        "rationale": "중간 균형점. Slippage(2.14) + Fee(9.0) + Margin(0.86) 커버. Trade-off 최적화 목표"
    },
    {
        "entry_bps": 14.0,
        "tp_bps": 20.0,
        "rationale": "Intermediate Zone 최상단. D82-7 하한(14/19)과 유사, 구조적 안전성 + 거래량 확보 검증"
    }
]

DEFAULT_RUN_DURATION_SEC = 1200  # 20분 (조합당)
DEFAULT_TOPN_SIZE = 20
DEFAULT_OUTPUT_DIR = "logs/d82-8"


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="D82-8: Intermediate Threshold Long-run Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--run-duration-seconds",
        type=int,
        default=DEFAULT_RUN_DURATION_SEC,
        help=f"Duration per run in seconds, default: {DEFAULT_RUN_DURATION_SEC} (20 minutes)",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=3,
        help="Maximum number of combinations to run, default: 3",
    )
    parser.add_argument(
        "--topn-size",
        type=int,
        default=DEFAULT_TOPN_SIZE,
        help=f"TopN size, default: {DEFAULT_TOPN_SIZE}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode: print commands without execution",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory, default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--enable-edge-monitor",
        action="store_true",
        default=True,
        help="Enable Runtime Edge Monitor (default: True)",
    )
    return parser.parse_args()


def generate_run_id(entry_bps: float, tp_bps: float, timestamp: str) -> str:
    """
    Generate unique run_id for D82-8.
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        timestamp: Timestamp string
    
    Returns:
        run_id (e.g., "d82-8-E10p0_TP15p0-20251205170000")
    """
    entry_str = f"E{entry_bps:.1f}".replace(".", "p")
    tp_str = f"TP{tp_bps:.1f}".replace(".", "p")
    return f"d82-8-{entry_str}_{tp_str}-{timestamp}"


def build_command(
    entry_bps: float,
    tp_bps: float,
    run_id: str,
    args: argparse.Namespace,
    kpi_path: Path,
    edge_monitor_path: Optional[Path],
) -> tuple[List[str], Dict[str, str]]:
    """
    Build command for a single threshold combination.
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        run_id: Unique run ID
        args: Command-line arguments
        kpi_path: KPI output path
        edge_monitor_path: Edge Monitor log path (optional)
    
    Returns:
        (command list, environment variables dict)
    """
    project_root = Path(__file__).parent.parent
    runner_script = project_root / "scripts" / "run_d77_0_topn_arbitrage_paper.py"
    
    cmd = [
        "python",
        str(runner_script),
        "--data-source", "real",
        "--topn-size", str(args.topn_size),
        "--run-duration-seconds", str(args.run_duration_seconds),
        "--validation-profile", "none",  # Long-run에서는 validation overhead 제거
        "--kpi-output-path", str(kpi_path),
    ]
    
    # 환경 변수
    env_vars = os.environ.copy()
    env_vars["ARBITRAGE_ENV"] = "paper"
    env_vars["TOPN_ENTRY_MIN_SPREAD_BPS"] = str(entry_bps)
    env_vars["TOPN_EXIT_TP_SPREAD_BPS"] = str(tp_bps)
    
    # Edge Monitor 활성화 (optional)
    if edge_monitor_path:
        env_vars["TOPN_EDGE_MONITOR_ENABLED"] = "true"
        env_vars["TOPN_EDGE_MONITOR_PATH"] = str(edge_monitor_path)
        env_vars["TOPN_EDGE_MONITOR_WINDOW"] = "50"  # Rolling window size
    
    return cmd, env_vars


def load_kpi_json(kpi_path: Path) -> Optional[Dict[str, Any]]:
    """Load KPI JSON file."""
    if not kpi_path.exists():
        logger.warning(f"KPI file not found: {kpi_path}")
        return None
    
    try:
        with open(kpi_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load KPI JSON: {e}")
        return None


def execute_single_run(
    entry_bps: float,
    tp_bps: float,
    run_id: str,
    rationale: str,
    args: argparse.Namespace,
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Execute a single threshold combination run.
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        run_id: Unique run ID
        rationale: Combination rationale
        args: Command-line arguments
        output_dir: Output directory
    
    Returns:
        Result dict with KPI + metadata
    """
    # Paths
    kpi_path = output_dir / "runs" / f"{run_id}_kpi.json"
    kpi_path.parent.mkdir(parents=True, exist_ok=True)
    
    edge_monitor_path = None
    if args.enable_edge_monitor:
        edge_monitor_path = output_dir / "edge_monitor" / f"{run_id}_edge.jsonl"
        edge_monitor_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build command
    cmd, env_vars = build_command(
        entry_bps, tp_bps, run_id, args, kpi_path, edge_monitor_path
    )
    
    logger.info(f"[Run {run_id}] Entry={entry_bps} bps, TP={tp_bps} bps")
    logger.info(f"[Run {run_id}] Rationale: {rationale}")
    logger.info(f"[Run {run_id}] Duration: {args.run_duration_seconds}s")
    logger.info(f"[Run {run_id}] KPI: {kpi_path}")
    if edge_monitor_path:
        logger.info(f"[Run {run_id}] Edge Monitor: {edge_monitor_path}")
    
    if args.dry_run:
        logger.info(f"[Run {run_id}] [DRY-RUN] Command: {' '.join(cmd)}")
        logger.info(f"[Run {run_id}] [DRY-RUN] Env: {env_vars.get('TOPN_ENTRY_MIN_SPREAD_BPS')}, {env_vars.get('TOPN_EXIT_TP_SPREAD_BPS')}")
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "rationale": rationale,
            "status": "dry_run",
        }
    
    # Execute
    try:
        result = subprocess.run(
            cmd,
            env=env_vars,
            capture_output=True,
            text=True,
            timeout=args.run_duration_seconds + 300,  # 5분 여유
        )
        
        if result.returncode != 0:
            logger.error(f"[Run {run_id}] Execution failed: {result.stderr[:500]}")
            return {
                "entry_bps": entry_bps,
                "tp_bps": tp_bps,
                "run_id": run_id,
                "rationale": rationale,
                "status": "failed",
                "error": result.stderr[:500],
            }
        
        logger.info(f"[Run {run_id}] Execution completed successfully")
        
        # Load KPI
        kpi_data = load_kpi_json(kpi_path)
        if not kpi_data:
            logger.warning(f"[Run {run_id}] KPI data not found")
            return {
                "entry_bps": entry_bps,
                "tp_bps": tp_bps,
                "run_id": run_id,
                "rationale": rationale,
                "status": "success_no_kpi",
            }
        
        # Extract key metrics
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "rationale": rationale,
            "duration_sec": kpi_data.get("duration_minutes", 0) * 60,
            "entries": kpi_data.get("total_entry_trades", 0),
            "round_trips": kpi_data.get("round_trips_completed", 0),
            "win_rate_pct": kpi_data.get("round_trip_win_rate", 0.0) * 100,
            "avg_buy_slippage_bps": kpi_data.get("avg_buy_slippage_bps", 0.0),
            "avg_sell_slippage_bps": kpi_data.get("avg_sell_slippage_bps", 0.0),
            "pnl_usd": kpi_data.get("total_pnl_usd", 0.0),
            "loop_latency_avg_ms": kpi_data.get("avg_loop_latency_ms", 0.0),
            "kpi_path": str(kpi_path),
            "edge_monitor_path": str(edge_monitor_path) if edge_monitor_path else None,
            "status": "success",
        }
    
    except subprocess.TimeoutExpired:
        logger.error(f"[Run {run_id}] Timeout after {args.run_duration_seconds + 300}s")
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "rationale": rationale,
            "status": "timeout",
        }
    except Exception as e:
        logger.error(f"[Run {run_id}] Unexpected error: {e}")
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "rationale": rationale,
            "status": "error",
            "error": str(e),
        }


def main():
    """Main execution."""
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("[D82-8] Intermediate Threshold Long-run PAPER")
    logger.info("=" * 80)
    logger.info(f"Duration per run: {args.run_duration_seconds}s ({args.run_duration_seconds/60:.1f} min)")
    logger.info(f"Max runs: {args.max_runs}")
    logger.info(f"TopN size: {args.topn_size}")
    logger.info(f"Edge Monitor: {'Enabled' if args.enable_edge_monitor else 'Disabled'}")
    logger.info(f"Output dir: {output_dir}")
    logger.info(f"Dry-run: {args.dry_run}")
    
    # Select combinations
    combinations = DEFAULT_COMBINATIONS[:args.max_runs]
    logger.info(f"\nSelected {len(combinations)} combinations:")
    for i, combo in enumerate(combinations, 1):
        logger.info(f"  {i}. Entry={combo['entry_bps']} bps, TP={combo['tp_bps']} bps")
        logger.info(f"     → {combo['rationale']}")
    
    # Execute sweep
    start_time = datetime.now()
    results = []
    
    for i, combo in enumerate(combinations, 1):
        logger.info("")
        logger.info(f"[Run {i}/{len(combinations)}] Starting...")
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        run_id = generate_run_id(combo["entry_bps"], combo["tp_bps"], timestamp)
        
        result = execute_single_run(
            entry_bps=combo["entry_bps"],
            tp_bps=combo["tp_bps"],
            run_id=run_id,
            rationale=combo["rationale"],
            args=args,
            output_dir=output_dir,
        )
        
        results.append(result)
        logger.info(f"[Run {i}/{len(combinations)}] Completed: {result.get('status')}")
    
    end_time = datetime.now()
    
    # Save summary
    summary = {
        "sweep_metadata": {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_duration_sec": (end_time - start_time).total_seconds(),
            "total_runs": len(results),
            "duration_per_run_sec": args.run_duration_seconds,
            "topn_size": args.topn_size,
            "edge_monitor_enabled": args.enable_edge_monitor,
            "dry_run": args.dry_run,
        },
        "results": results,
    }
    
    summary_path = output_dir / "intermediate_threshold_longrun_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D82-8] Sweep Completed")
    logger.info(f"  Total Runs: {len(results)}")
    logger.info(f"  Summary saved to: {summary_path}")
    logger.info("=" * 80)
    
    # Print summary table
    logger.info("")
    logger.info("Results Summary:")
    logger.info("Entry    TP       Entries  RT     WinRate  PnL(USD)     Status")
    logger.info("-" * 80)
    for r in results:
        entry = r.get("entry_bps", 0)
        tp = r.get("tp_bps", 0)
        entries = r.get("entries", 0)
        rt = r.get("round_trips", 0)
        win_rate = r.get("win_rate_pct", 0.0)
        pnl = r.get("pnl_usd", 0.0)
        status = r.get("status", "unknown")
        logger.info(f"{entry:<8.1f} {tp:<8.1f} {entries:<8} {rt:<6} {win_rate:<8.1f} {pnl:<12.2f} {status}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
