#!/usr/bin/env python3
"""
D205-10-1: Threshold Sensitivity Sweep

목적:
- buffer_bps [0, 2, 5, 8, 10] sweep
- Best buffer 선정 (closed_trades > 0, error_count == 0, net_pnl 최대)
- Negative-control 검증 (reject_reasons 분석)

Usage:
    python scripts/run_d205_10_1_sweep.py --duration-minutes 2 --use-real-data --db-mode off
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.tools.d205_10_1_sweep import run_threshold_sweep

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="D205-10-1: Threshold Sensitivity Sweep")
    parser.add_argument("--duration-minutes", type=int, default=2, help="Duration per sweep (minutes)")
    parser.add_argument("--use-real-data", action="store_true", help="Use Real MarketData")
    parser.add_argument("--db-mode", default="off", choices=["strict", "optional", "off"])
    parser.add_argument("--fx-krw-per-usdt", type=float, default=1450.0, help="FX rate (KRW/USDT)")
    parser.add_argument("--out-evidence-dir", default=None, help="Evidence output directory")
    
    args = parser.parse_args()
    
    exit_code = run_threshold_sweep(
        duration_minutes=args.duration_minutes,
        use_real_data=args.use_real_data,
        db_mode=args.db_mode,
        fx_rate=args.fx_krw_per_usdt,
        out_evidence_dir=args.out_evidence_dir,
    )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
