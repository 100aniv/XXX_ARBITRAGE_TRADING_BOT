#!/usr/bin/env python3
"""
D205-10-1: 20m Smoke Test (Best Buffer)

목적:
- sweep 결과에서 선정된 Best buffer로 20m smoke test 실행
- AC-5 검증: opportunities > 0, intents > 0, closed_trades > 0

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
from arbitrage.v2.opportunity import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_best_buffer(sweep_summary_path: Path) -> float:
    """
    sweep_summary.json에서 Best buffer 로드
    
    Returns:
        best_buffer_bps: float
    """
    with open(sweep_summary_path, "r") as f:
        summary = json.load(f)
    
    best_buffer_bps = summary.get("best_selection", {}).get("best_buffer_bps")
    
    if best_buffer_bps is None:
        raise ValueError(f"No best_buffer_bps found in {sweep_summary_path}")
    
    return best_buffer_bps


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
    
    # FeeModel
    fee_a = FeeStructure(
        exchange_name="upbit",
        maker_fee_bps=5.0,
        taker_fee_bps=25.0,
    )
    fee_b = FeeStructure(
        exchange_name="binance",
        maker_fee_bps=10.0,
        taker_fee_bps=25.0,
    )
    fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
    
    # BreakEvenParams (Best buffer)
    break_even_params = BreakEvenParams(
        fee_model=fee_model,
        slippage_bps=15.0,
        latency_bps=10.0,
        buffer_bps=best_buffer_bps,
    )
    
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
    
    # Load KPI
    kpi_path = evidence_dir / "kpi_smoke_best.json"
    if not kpi_path.exists():
        logger.error(f"[D205-10-1] KPI file not found: {kpi_path}")
        return 1
    
    with open(kpi_path, "r") as f:
        kpi = json.load(f)
    
    # Validation (AC-5)
    opportunities = kpi.get("opportunities_generated", 0)
    intents = kpi.get("intents_created", 0)
    closed_trades = kpi.get("closed_trades", 0)
    error_count = kpi.get("error_count", 0)
    
    passed = opportunities > 0 and intents > 0 and closed_trades > 0 and error_count == 0
    
    # Save result
    result = {
        "best_buffer_bps": best_buffer_bps,
        "duration_minutes": 20,
        "kpi": kpi,
        "ac_5_validation": {
            "opportunities_gt_0": opportunities > 0,
            "intents_gt_0": intents > 0,
            "closed_trades_gt_0": closed_trades > 0,
            "error_count_eq_0": error_count == 0,
            "passed": passed,
        },
    }
    
    result_path = evidence_dir / "result.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    
    logger.info(f"[D205-10-1] Result saved to {result_path}")
    
    if passed:
        logger.info(f"[D205-10-1] ✅ AC-5 PASS")
        return 0
    else:
        logger.error(f"[D205-10-1] ❌ AC-5 FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
