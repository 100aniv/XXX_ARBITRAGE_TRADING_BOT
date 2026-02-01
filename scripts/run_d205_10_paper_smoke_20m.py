#!/usr/bin/env python3
"""
D205-10: Paper Smoke 20m (Watchdog + Real-time Monitoring)

목적:
- Real MarketData 20m smoke test
- Watchdog 실시간 모니터링 (intents=0 stall 감지)
- 조기 종료 조건: intents=0 2분 지속, winrate 100%, FX 위반

Usage:
    python scripts/run_d205_10_paper_smoke_20m.py --use-real-data --db-mode off
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.paper_runner import PaperRunner, PaperRunnerConfig

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="D205-10: Paper Smoke 20m")
    parser.add_argument("--use-real-data", action="store_true", help="Use Real MarketData")
    parser.add_argument("--db-mode", default="off", choices=["strict", "optional", "off"])
    parser.add_argument("--out-evidence-dir", default=None, help="Evidence output directory")
    
    args = parser.parse_args()
    
    # Evidence directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out_evidence_dir:
        evidence_dir = Path(args.out_evidence_dir)
    else:
        evidence_dir = Path(f"logs/evidence/d205_10_smoke_20m_{timestamp}")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Config
    config = PaperRunnerConfig(
        duration_minutes=20,
        phase="smoke",
        run_id=f"d205_10_smoke_20m_{timestamp}",
        output_dir=str(evidence_dir),
        symbols_top=10,
        db_mode=args.db_mode,
        use_real_data=args.use_real_data,
        fx_krw_per_usdt=1450.0,
    )
    
    logger.info(f"[D205-10] Starting 20m smoke (real_data={args.use_real_data})")
    logger.info(f"[D205-10] Evidence: {evidence_dir}")
    
    # Run
    runner = PaperRunner(config)
    exit_code = runner.run()
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
