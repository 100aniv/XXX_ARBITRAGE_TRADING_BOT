#!/usr/bin/env python3
"""
D205-10-1: Wait and Execute (10h Market Watch + Trigger)

목적:
- 10시간 동안 시장 조건 감시
- edge_bps >= trigger_min_edge_bps 조건 충족 시 자동 sweep/smoke 실행

Usage:
    # 기본 (10h, 30s poll, trigger_min_edge_bps=0)
    python scripts/run_d205_10_1_wait_and_execute.py
    
    # 커스텀 설정
    python scripts/run_d205_10_1_wait_and_execute.py --duration-hours 2 --poll-seconds 60 --trigger-min-edge-bps 10.0
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.d205_10_1_wait_harness import (
    WaitHarness,
    WaitHarnessConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="D205-10-1: Wait and Execute")
    parser.add_argument(
        "--duration-hours",
        type=int,
        default=10,
        help="Maximum wait duration (hours, default: 10)"
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=30,
        help="Polling interval (seconds, default: 30)"
    )
    parser.add_argument(
        "--trigger-min-edge-bps",
        type=float,
        default=0.0,
        help="Minimum edge_bps to trigger sweep/smoke (default: 0.0)"
    )
    parser.add_argument(
        "--fx-krw-per-usdt",
        type=float,
        default=1450.0,
        help="FX rate (KRW/USDT, default: 1450.0)"
    )
    parser.add_argument(
        "--sweep-duration-minutes",
        type=int,
        default=2,
        help="Sweep duration per buffer (minutes, default: 2)"
    )
    parser.add_argument(
        "--db-mode",
        default="off",
        choices=["strict", "optional", "off"],
        help="DB mode (default: off)"
    )
    parser.add_argument(
        "--out-evidence-dir",
        default=None,
        help="Evidence output directory (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Config
    config = WaitHarnessConfig(
        duration_hours=args.duration_hours,
        poll_seconds=args.poll_seconds,
        trigger_min_edge_bps=args.trigger_min_edge_bps,
        fx_rate=args.fx_krw_per_usdt,
        evidence_dir=args.out_evidence_dir or "",
        sweep_duration_minutes=args.sweep_duration_minutes,
        db_mode=args.db_mode,
    )
    
    logger.info(f"[D205-10-1 WAIT] ========================================")
    logger.info(f"[D205-10-1 WAIT] D205-10-1: Wait and Execute")
    logger.info(f"[D205-10-1 WAIT] ========================================")
    logger.info(f"[D205-10-1 WAIT] Config:")
    logger.info(f"[D205-10-1 WAIT]   duration_hours: {config.duration_hours}")
    logger.info(f"[D205-10-1 WAIT]   poll_seconds: {config.poll_seconds}")
    logger.info(f"[D205-10-1 WAIT]   trigger_min_edge_bps: {config.trigger_min_edge_bps}")
    logger.info(f"[D205-10-1 WAIT]   fx_rate: {config.fx_rate}")
    logger.info(f"[D205-10-1 WAIT]   evidence_dir: {config.evidence_dir}")
    logger.info(f"[D205-10-1 WAIT] ========================================")
    
    # Run
    harness = WaitHarness(config)
    exit_code = harness.run_watch_loop()
    
    if exit_code == 0:
        logger.info(f"[D205-10-1 WAIT] ✅ SUCCESS: Trigger executed and sweep/smoke completed")
    else:
        logger.error(f"[D205-10-1 WAIT] ❌ FAIL: Trigger not met or execution failed")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
