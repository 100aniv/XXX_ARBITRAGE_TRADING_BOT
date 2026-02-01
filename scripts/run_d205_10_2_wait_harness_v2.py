"""
D205-10-2: Wait Harness v2 CLI 스크립트

사용법:
python scripts/run_d205_10_2_wait_harness_v2.py \
  --phase-hours 3 5 \
  --poll-seconds 30 \
  --trigger-min-edge-bps 0.0 \
  --fx-krw-per-usdt 1450 \
  --infeasible-margin-bps 30 \
  --db-mode off
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.wait_harness_v2 import WaitHarnessV2, WaitHarnessV2Config

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="D205-10-2: Wait Harness v2 (Wallclock Verified, 3h→5h Phased, Early-Stop)"
    )
    
    parser.add_argument(
        "--phase-hours",
        type=int,
        nargs=2,
        default=[3, 5],
        help="Phase hours (checkpoint, total) [default: 3 5]",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=30,
        help="Polling interval (seconds) [default: 30]",
    )
    parser.add_argument(
        "--trigger-min-edge-bps",
        type=float,
        default=0.0,
        help="Trigger minimum edge (bps) [default: 0.0]",
    )
    parser.add_argument(
        "--fx-krw-per-usdt",
        type=float,
        default=1450.0,
        help="FX rate (KRW/USDT) [default: 1450.0]",
    )
    parser.add_argument(
        "--infeasible-margin-bps",
        type=float,
        default=30.0,
        help="Infeasible margin (bps) for early-stop [default: 30.0]",
    )
    parser.add_argument(
        "--heartbeat-interval-sec",
        type=int,
        default=60,
        help="Heartbeat update interval (seconds) [default: 60]",
    )
    parser.add_argument(
        "--sweep-duration-minutes",
        type=int,
        default=2,
        help="Sweep duration (minutes) [default: 2]",
    )
    parser.add_argument(
        "--db-mode",
        type=str,
        default="off",
        choices=["off", "optional", "strict"],
        help="DB mode [default: off]",
    )
    parser.add_argument(
        "--evidence-dir",
        type=str,
        default="",
        help="Evidence directory (auto-generated if empty)",
    )
    
    args = parser.parse_args()
    
    # Config 생성
    config = WaitHarnessV2Config(
        phase_hours=list(args.phase_hours),
        poll_seconds=args.poll_seconds,
        trigger_min_edge_bps=args.trigger_min_edge_bps,
        fx_rate=args.fx_krw_per_usdt,
        infeasible_margin_bps=args.infeasible_margin_bps,
        heartbeat_interval_sec=args.heartbeat_interval_sec,
        sweep_duration_minutes=args.sweep_duration_minutes,
        db_mode=args.db_mode,
        evidence_dir=args.evidence_dir,
    )
    
    # Harness 실행
    try:
        harness = WaitHarnessV2(config)
        exit_code = harness.run_watch_loop()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"[D205-10-2] Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
