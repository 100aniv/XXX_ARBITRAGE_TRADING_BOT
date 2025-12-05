#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D82-9: TP Fine-tuning Real PAPER 1h Runner

목적:
    analyze_d82_9_tp_candidates.py에서 선정된 후보 조합을
    Real PAPER 1h로 검증하여 실제 Win Rate와 PnL을 확인.

배경:
    - D82-8: Entry 10-14, TP 15-20 → Win Rate 0% (TP가 너무 높음)
    - D82-9: TP를 13-15로 낮춰 TP 도달 가능성 증가
    - 5개 후보 선정 (Entry [10,12] × TP [13,14,15])

핵심 설계:
    - 후보 JSON 파일 로드 (logs/d82-9/selected_candidates.json)
    - 각 후보를 1h Real PAPER로 검증
    - Runtime Edge Monitor 활성화
    - D82-8 Runner 인프라 재사용

Acceptance Criteria:
    - 최소 1개 조합이라도:
      - RT ≥ 10
      - Win Rate > 0%
      - PnL USD ≥ 0
    - Loop Latency < 25ms
    - CPU < 50%

Usage:
    # Dry-run
    python scripts/run_d82_9_paper_candidates_longrun.py --dry-run
    
    # 실제 실행 (5조합 × 1h = 5시간, 기본 20분으로 설정)
    python scripts/run_d82_9_paper_candidates_longrun.py

    # 1시간 실행 (권장)
    python scripts/run_d82_9_paper_candidates_longrun.py --run-duration-seconds 3600

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

DEFAULT_RUN_DURATION_SEC = 1200  # 20분 (조합당, 기본값)
DEFAULT_TOPN_SIZE = 20
DEFAULT_OUTPUT_DIR = "logs/d82-9"
CANDIDATES_JSON_PATH = "logs/d82-9/selected_candidates.json"


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="D82-9: TP Fine-tuning Real PAPER Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--candidates-json",
        type=str,
        default=CANDIDATES_JSON_PATH,
        help=f"Path to candidates JSON file, default: {CANDIDATES_JSON_PATH}",
    )
    parser.add_argument(
        "--run-duration-seconds",
        type=int,
        default=DEFAULT_RUN_DURATION_SEC,
        help=f"Duration per run in seconds, default: {DEFAULT_RUN_DURATION_SEC} (20 min), recommended: 3600 (1h)",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=5,
        help="Maximum number of candidates to run, default: 5",
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


def load_candidates_json(json_path: Path) -> List[Dict[str, Any]]:
    """
    Load candidates from JSON file.
    
    Args:
        json_path: Path to candidates JSON file
    
    Returns:
        List of candidate dicts
    """
    if not json_path.exists():
        logger.error(f"Candidates JSON not found: {json_path}")
        logger.error("Run analyze_d82_9_tp_candidates.py first!")
        return []
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        candidates = data.get("candidates", [])
        logger.info(f"Loaded {len(candidates)} candidates from {json_path}")
        return candidates
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}")
        return []
    except Exception as e:
        logger.error(f"Failed to load candidates: {e}")
        return []


def generate_run_id(entry_bps: float, tp_bps: float, timestamp: str) -> str:
    """
    Generate unique run_id for D82-9.
    
    Args:
        entry_bps: Entry threshold (bps)
        tp_bps: TP threshold (bps)
        timestamp: Timestamp string
    
    Returns:
        run_id (e.g., "d82-9-E10p0_TP13p0-20251205190000")
    """
    entry_str = f"E{entry_bps:.1f}".replace(".", "p")
    tp_str = f"TP{tp_bps:.1f}".replace(".", "p")
    return f"d82-9-{entry_str}_{tp_str}-{timestamp}"


def build_command(
    entry_bps: float,
    tp_bps: float,
    run_id: str,
    args: argparse.Namespace,
    kpi_path: Path,
) -> tuple[List[str], Dict[str, str]]:
    """
    Build Python command for a single candidate.
    
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
    
    # Python 직접 실행
    cmd = [
        "python",
        str(runner_script),
        "--data-source", "real",
        "--topn-size", str(args.topn_size),
        "--run-duration-seconds", str(args.run_duration_seconds),
        "--validation-profile", "relaxed",
        "--kpi-output-path", str(kpi_path),
    ]
    
    # 환경 변수 dict
    env_vars = os.environ.copy()
    env_vars["ARBITRAGE_ENV"] = "paper"
    env_vars["TOPN_ENTRY_MIN_SPREAD_BPS"] = str(entry_bps)
    env_vars["TOPN_EXIT_TP_SPREAD_BPS"] = str(tp_bps)
    
    # Edge Monitor 활성화
    if args.enable_edge_monitor:
        env_vars["ENABLE_RUNTIME_EDGE_MONITOR"] = "1"
        # Edge Monitor 로그 경로
        edge_monitor_dir = Path(args.output_dir) / "edge_monitor"
        edge_monitor_dir.mkdir(parents=True, exist_ok=True)
        edge_monitor_path = edge_monitor_dir / f"{run_id}_edge.jsonl"
        env_vars["EDGE_MONITOR_LOG_PATH"] = str(edge_monitor_path)
    
    return cmd, env_vars


def execute_single_run(
    candidate: Dict[str, Any],
    run_index: int,
    total_runs: int,
    args: argparse.Namespace,
) -> Dict[str, Any]:
    """
    Execute single candidate run.
    
    Args:
        candidate: Candidate dict from JSON
        run_index: Current run index (1-based)
        total_runs: Total number of runs
        args: Command-line arguments
    
    Returns:
        Result dict with status, paths, etc.
    """
    entry_bps = candidate["entry_bps"]
    tp_bps = candidate["tp_bps"]
    rationale = candidate.get("rationale", "")
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    run_id = generate_run_id(entry_bps, tp_bps, timestamp)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info(f"[Run {run_index}/{total_runs}] Starting...")
    logger.info(f"[Run {run_id}] Entry={entry_bps} bps, TP={tp_bps} bps")
    logger.info(f"[Run {run_id}] Rationale: {rationale}")
    logger.info(f"[Run {run_id}] Duration: {args.run_duration_seconds}s")
    
    # Output paths
    runs_dir = Path(args.output_dir) / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    kpi_path = runs_dir / f"{run_id}_kpi.json"
    
    logger.info(f"[Run {run_id}] KPI: {kpi_path}")
    
    # Edge Monitor path
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
            "run_id": run_id,
            "rationale": rationale,
            "status": "dry_run",
        }
    
    # Execute
    try:
        logger.info(f"[Run {run_id}] Executing...")
        result = subprocess.run(
            cmd,
            env=env_vars,
            capture_output=False,
            text=True,
            check=False,
        )
        
        if result.returncode == 0:
            logger.info(f"[Run {run_id}] Execution completed successfully")
            status = "success"
        else:
            logger.error(f"[Run {run_id}] Execution failed with exit code: {result.returncode}")
            status = "failed"
        
        logger.info(f"[Run {run_index}/{total_runs}] Completed: {status}")
        
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "rationale": rationale,
            "duration_sec": args.run_duration_seconds,
            "kpi_path": str(kpi_path),
            "edge_monitor_path": str(edge_monitor_path) if args.enable_edge_monitor else None,
            "status": status,
        }
    
    except Exception as e:
        logger.exception(f"[Run {run_id}] Exception during execution: {e}")
        return {
            "entry_bps": entry_bps,
            "tp_bps": tp_bps,
            "run_id": run_id,
            "rationale": rationale,
            "status": "error",
            "error": str(e),
        }


def save_summary(
    results: List[Dict[str, Any]],
    args: argparse.Namespace,
    start_time: datetime,
    end_time: datetime,
):
    """
    Save sweep summary to JSON.
    
    Args:
        results: List of result dicts
        args: Command-line arguments
        start_time: Sweep start time
        end_time: Sweep end time
    """
    summary_path = Path(args.output_dir) / "paper_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    summary = {
        "sweep_metadata": {
            "task": "D82-9: TP Fine-tuning Real PAPER 1h Validation",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "total_duration_sec": (end_time - start_time).total_seconds(),
            "total_runs": len(results),
            "duration_per_run_sec": args.run_duration_seconds,
            "topn_size": args.topn_size,
            "edge_monitor_enabled": args.enable_edge_monitor,
            "dry_run": args.dry_run,
        },
        "results": results
    }
    
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Summary saved to: {summary_path}")


# =============================================================================
# Main Runner
# =============================================================================

def main():
    """메인 함수."""
    args = parse_args()
    
    logger.info("=" * 80)
    logger.info("[D82-9] TP Fine-tuning Real PAPER Runner")
    logger.info("=" * 80)
    logger.info(f"Candidates JSON: {args.candidates_json}")
    logger.info(f"Duration per run: {args.run_duration_seconds}s ({args.run_duration_seconds/60:.1f} min)")
    logger.info(f"Max runs: {args.max_runs}")
    logger.info(f"TopN size: {args.topn_size}")
    logger.info(f"Dry-run: {args.dry_run}")
    logger.info(f"Edge Monitor: {args.enable_edge_monitor}")
    logger.info("")
    
    # Load candidates
    candidates_path = Path(args.candidates_json)
    candidates = load_candidates_json(candidates_path)
    
    if not candidates:
        logger.error("No candidates loaded. Exiting.")
        return 1
    
    # Limit to max_runs
    candidates_to_run = candidates[:args.max_runs]
    logger.info(f"Running {len(candidates_to_run)} / {len(candidates)} candidates")
    
    # Execute runs
    start_time = datetime.now()
    results = []
    
    for i, candidate in enumerate(candidates_to_run, 1):
        result = execute_single_run(candidate, i, len(candidates_to_run), args)
        results.append(result)
    
    end_time = datetime.now()
    
    # Save summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D82-9] Sweep Completed")
    logger.info(f"  Total Runs: {len(results)}")
    save_summary(results, args, start_time, end_time)
    logger.info("=" * 80)
    
    # Print results table
    logger.info("")
    logger.info("Results Summary:")
    logger.info("Entry    TP       Status")
    logger.info("-" * 80)
    for r in results:
        logger.info(
            f"{r['entry_bps']:<8.1f} {r['tp_bps']:<8.1f} {r['status']}"
        )
    logger.info("=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
