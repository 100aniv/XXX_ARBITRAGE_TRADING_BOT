#!/usr/bin/env python3
"""
D205-10: Paper Smoke 2m Precheck (20m 멍때림 방지)

목적:
- 20m smoke 전에 2m 프리체크를 먼저 실행
- opportunities > 50인데 intents == 0이면 즉시 FAIL 종료
- 프리체크 PASS 시에만 20m로 진행

Usage:
    python scripts/run_d205_10_paper_smoke_2m_precheck.py --use-real-data --db-mode off
"""

import argparse
import json
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
    parser = argparse.ArgumentParser(description="D205-10: 2m Precheck")
    parser.add_argument("--use-real-data", action="store_true", help="Use Real MarketData")
    parser.add_argument("--db-mode", default="off", choices=["strict", "optional", "off"])
    parser.add_argument("--out-evidence-dir", default=None, help="Evidence output directory")
    
    args = parser.parse_args()
    
    # Evidence directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out_evidence_dir:
        evidence_dir = Path(args.out_evidence_dir)
    else:
        evidence_dir = Path(f"logs/evidence/d205_10_precheck_2m_{timestamp}")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # Config
    config = PaperRunnerConfig(
        duration_minutes=2,
        phase="precheck",
        run_id=f"d205_10_precheck_2m_{timestamp}",
        output_dir=str(evidence_dir),
        symbols_top=10,
        db_mode=args.db_mode,
        use_real_data=args.use_real_data,
        fx_krw_per_usdt=1450.0,
    )
    
    logger.info(f"[D205-10 PRECHECK] Starting 2m precheck (real_data={args.use_real_data})")
    logger.info(f"[D205-10 PRECHECK] Evidence: {evidence_dir}")
    
    # Run
    runner = PaperRunner(config)
    exit_code = runner.run()
    
    # Load KPI
    kpi_path = evidence_dir / "kpi_precheck.json"
    with open(kpi_path, "r") as f:
        kpi = json.load(f)
    
    # Validation
    opportunities = kpi.get("opportunities_generated", 0)
    intents = kpi.get("intents_created", 0)
    
    logger.info(f"[D205-10 PRECHECK] Opportunities: {opportunities}, Intents: {intents}")
    
    # FAIL 조건: opportunities > 50인데 intents == 0
    if opportunities > 50 and intents == 0:
        logger.error(f"[D205-10 PRECHECK] ❌ FAIL: {opportunities} opp → 0 intents (100% reject)")
        logger.error(f"[D205-10 PRECHECK] Reject reasons: {kpi.get('reject_reasons', {})}")
        logger.error(f"[D205-10 PRECHECK] 20m smoke 진행 금지. Threshold/spread 조정 필요.")
        return 1
    
    # PASS
    logger.info(f"[D205-10 PRECHECK] ✅ PASS: intents > 0 확인. 20m smoke 진행 가능.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
