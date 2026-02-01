#!/usr/bin/env python3
"""
D205-10-1: 20m Smoke Test (Best Buffer)

목적:
- sweep 결과에서 선정된 Best buffer로 20m smoke test 실행
- 코어 로직에 위임 (Thin Wrapper)

Usage:
    python scripts/run_d205_10_1_smoke_best_buffer.py --sweep-summary logs/evidence/d205_10_1_sweep_*/sweep_summary.json --use-real-data --db-mode off
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.paper_runner import PaperRunner, PaperRunnerConfig
from arbitrage.v2.core.d205_10_1_sweep import _with_buffer_params
from arbitrage.v2.core.runtime_factory import build_break_even_params_from_config_path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_best_buffer(sweep_summary_path: Path) -> float:
    with open(sweep_summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    best_buffer_bps = summary.get("best_selection", {}).get("best_buffer_bps")
    if best_buffer_bps is None:
        raise ValueError(f"No best_buffer_bps found in {sweep_summary_path}")
    return float(best_buffer_bps)


def main():
    parser = argparse.ArgumentParser(description="D205-10-1: 20m Smoke (Best Buffer)")
    parser.add_argument("--sweep-summary", required=True, help="Path to sweep_summary.json")
    parser.add_argument("--use-real-data", action="store_true", help="Use Real MarketData")
    parser.add_argument("--db-mode", default="off", choices=["strict", "optional", "off"])
    parser.add_argument("--fx-krw-per-usdt", type=float, default=1450.0, help="FX rate (KRW/USDT)")
    parser.add_argument("--out-evidence-dir", default=None, help="Evidence output directory")
    
    args = parser.parse_args()
    
    # Load Best buffer
    sweep_summary_path = Path(args.sweep_summary)
    best_buffer_bps = load_best_buffer(sweep_summary_path)
    
    logger.info(f"[D205-10-1] Best buffer: {best_buffer_bps} bps")
    
    # Evidence directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out_evidence_dir:
        evidence_dir = Path(args.out_evidence_dir)
    else:
        evidence_dir = Path(f"logs/evidence/d205_10_1_smoke_best_{int(best_buffer_bps)}_{timestamp}")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    base_params = build_break_even_params_from_config_path()
    break_even_params = _with_buffer_params(base_params, best_buffer_bps)
    
    # Config
    config = PaperRunnerConfig(
        duration_minutes=20,
        phase="smoke_best",
        run_id=f"d205_10_1_smoke_best_{int(best_buffer_bps)}_{timestamp}",
        output_dir=str(evidence_dir),
        symbols_top=10,
        db_mode=args.db_mode,
        use_real_data=args.use_real_data,
        fx_krw_per_usdt=args.fx_krw_per_usdt,
        break_even_params=break_even_params,
    )
    
    logger.info(f"[D205-10-1] Starting 20m smoke (best_buffer={best_buffer_bps} bps)")
    logger.info(f"[D205-10-1] Evidence: {evidence_dir}")
    
    # Run
    runner = PaperRunner(config)
    exit_code = runner.run()
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
