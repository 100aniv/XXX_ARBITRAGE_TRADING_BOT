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


def validate_kpi(kpi: dict, phase: str) -> dict:
    """
    D205-10 AC 검증
    
    Returns:
        {"passed": bool, "reasons": list, "ac_results": dict}
    """
    results = {
        "passed": True,
        "reasons": [],
        "ac_results": {},
    }
    
    # AC-1: opportunities > 0
    opportunities = kpi.get("opportunities_generated", 0)
    ac1 = opportunities > 0
    results["ac_results"]["AC-1_opportunities_gt_0"] = {
        "passed": ac1,
        "actual": opportunities,
        "expected": "> 0",
    }
    if not ac1:
        results["passed"] = False
        results["reasons"].append(f"AC_FAIL: opportunities={opportunities} (expected > 0)")
    
    # AC-2: intents > 0
    intents = kpi.get("intents_created", 0)
    ac2 = intents > 0
    results["ac_results"]["AC-2_intents_gt_0"] = {
        "passed": ac2,
        "actual": intents,
        "expected": "> 0",
    }
    if not ac2:
        results["passed"] = False
        results["reasons"].append(f"AC_FAIL: intents={intents} (expected > 0)")
    
    # AC-3: closed_trades > 0
    closed_trades = kpi.get("closed_trades", 0)
    ac3 = closed_trades > 0
    results["ac_results"]["AC-3_closed_trades_gt_0"] = {
        "passed": ac3,
        "actual": closed_trades,
        "expected": "> 0",
    }
    if not ac3:
        results["passed"] = False
        results["reasons"].append(f"AC_FAIL: closed_trades={closed_trades} (expected > 0)")
    
    # AC-4: error_count == 0
    error_count = kpi.get("error_count", 0)
    ac4 = error_count == 0
    results["ac_results"]["AC-4_error_count_eq_0"] = {
        "passed": ac4,
        "actual": error_count,
        "expected": "0",
    }
    if not ac4:
        results["passed"] = False
        results["reasons"].append(f"AC_FAIL: error_count={error_count} (expected 0)")
    
    return results


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
    
    # Load KPI
    kpi_path = evidence_dir / "kpi_smoke.json"
    with open(kpi_path, "r") as f:
        kpi = json.load(f)
    
    # Validation
    validation = validate_kpi(kpi, "smoke")
    
    # Save result
    result = {
        "phase": "smoke",
        "duration_minutes": 20,
        "kpi": kpi,
        "validation": validation,
        "passed": validation["passed"],
    }
    
    result_path = evidence_dir / "result.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"[D205-10] Result saved to {result_path}")
    
    if validation["passed"]:
        logger.info(f"[D205-10] ✅ PASS")
        return 0
    else:
        logger.error(f"[D205-10] ❌ FAIL: {validation['reasons']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
