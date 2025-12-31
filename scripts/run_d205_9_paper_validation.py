#!/usr/bin/env python3
"""
D205-9: Realistic Paper Validation (20m → 1h → 3h)

현실적 KPI 기준으로 Paper 검증 (가짜 낙관 제거)

Usage:
    # 20m Smoke
    python scripts/run_d205_9_paper_validation.py --duration 20 --phase smoke
    
    # 1h Baseline
    python scripts/run_d205_9_paper_validation.py --duration 60 --phase baseline
    
    # 3h Long Run
    python scripts/run_d205_9_paper_validation.py --duration 180 --phase longrun

AC (Acceptance Criteria):
    - 20m: closed_trades > 10, edge_after_cost > 0
    - 1h: closed_trades > 30, winrate 50~80%
    - 3h: closed_trades > 100, PnL 안정성 (std < mean)
    - 가짜 낙관 FAIL: winrate 100% → 모델 현실 미반영

Evidence Output:
    - logs/evidence/d205_9_paper_{phase}_{timestamp}/
    - manifest.json, kpi.json, paper.log
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.paper_runner import PaperRunner, PaperRunnerConfig

logger = logging.getLogger(__name__)


def validate_kpi(kpi: dict, phase: str) -> dict:
    """
    D205-9 AC 검증
    
    Returns:
        {"passed": bool, "reasons": list, "ac_results": dict}
    """
    results = {
        "passed": True,
        "reasons": [],
        "ac_results": {}
    }
    
    closed_trades = kpi.get("total_closed_trades", 0)
    winrate = kpi.get("winrate", 0.0) * 100  # 0~100%
    edge_after_cost = kpi.get("mean_edge_after_cost_bps", 0.0)
    pnl_mean = kpi.get("pnl_mean", 0.0)
    pnl_std = kpi.get("pnl_std", 0.0)
    
    # 가짜 낙관 체크 (모든 phase 공통)
    if winrate == 100.0 and closed_trades > 5:
        results["passed"] = False
        results["reasons"].append("FAKE_OPTIMISM: winrate 100% (모델 현실 미반영)")
        results["ac_results"]["fake_optimism_check"] = "FAIL"
    else:
        results["ac_results"]["fake_optimism_check"] = "PASS"
    
    if phase == "smoke":  # 20m
        # AC: closed_trades > 10, edge_after_cost > 0
        if closed_trades < 10:
            results["passed"] = False
            results["reasons"].append(f"AC_FAIL: closed_trades={closed_trades} < 10")
            results["ac_results"]["closed_trades_10"] = "FAIL"
        else:
            results["ac_results"]["closed_trades_10"] = "PASS"
        
        if edge_after_cost <= 0:
            results["passed"] = False
            results["reasons"].append(f"AC_FAIL: edge_after_cost={edge_after_cost:.2f} <= 0")
            results["ac_results"]["edge_positive"] = "FAIL"
        else:
            results["ac_results"]["edge_positive"] = "PASS"
    
    elif phase == "baseline":  # 1h
        # AC: closed_trades > 30, winrate 50~80%
        if closed_trades < 30:
            results["passed"] = False
            results["reasons"].append(f"AC_FAIL: closed_trades={closed_trades} < 30")
            results["ac_results"]["closed_trades_30"] = "FAIL"
        else:
            results["ac_results"]["closed_trades_30"] = "PASS"
        
        if not (50 <= winrate <= 80):
            results["passed"] = False
            results["reasons"].append(f"AC_FAIL: winrate={winrate:.1f}% not in [50, 80]")
            results["ac_results"]["winrate_realistic"] = "FAIL"
        else:
            results["ac_results"]["winrate_realistic"] = "PASS"
    
    elif phase == "longrun":  # 3h
        # AC: closed_trades > 100, PnL 안정성 (std < mean)
        if closed_trades < 100:
            results["passed"] = False
            results["reasons"].append(f"AC_FAIL: closed_trades={closed_trades} < 100")
            results["ac_results"]["closed_trades_100"] = "FAIL"
        else:
            results["ac_results"]["closed_trades_100"] = "PASS"
        
        if pnl_mean > 0 and pnl_std >= pnl_mean:
            results["passed"] = False
            results["reasons"].append(f"AC_FAIL: PnL unstable (std={pnl_std:.2f} >= mean={pnl_mean:.2f})")
            results["ac_results"]["pnl_stability"] = "FAIL"
        else:
            results["ac_results"]["pnl_stability"] = "PASS"
    
    return results


def main():
    parser = argparse.ArgumentParser(description="D205-9: Realistic Paper Validation")
    parser.add_argument(
        "--duration",
        type=int,
        required=True,
        help="Duration in minutes (20=smoke, 60=baseline, 180=longrun)",
    )
    parser.add_argument(
        "--phase",
        type=str,
        choices=["smoke", "baseline", "longrun"],
        required=True,
        help="Validation phase",
    )
    parser.add_argument(
        "--out-evidence-dir",
        type=str,
        default=None,
        help="Output evidence directory",
    )
    parser.add_argument(
        "--db-mode",
        type=str,
        default="optional",
        choices=["strict", "optional", "off"],
        help="Database mode (default: optional)",
    )
    parser.add_argument(
        "--symbols-top",
        type=int,
        default=10,
        help="Top N symbols (default: 10)",
    )
    
    args = parser.parse_args()
    
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Output directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.out_evidence_dir or f"logs/evidence/d205_9_paper_{args.phase}_{ts}"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[D205-9] Starting {args.phase} validation ({args.duration} minutes)")
    logger.info(f"[D205-9] Output: {output_dir}")
    
    # Config
    config = PaperRunnerConfig(
        duration_minutes=args.duration,
        phase=args.phase,
        output_dir=str(output_path),
        symbols_top=args.symbols_top,
        db_mode=args.db_mode,
    )
    
    # Run
    try:
        runner = PaperRunner(config)
        result = runner.run()
        
        # KPI 검증
        kpi = result.get("kpi", {})
        validation = validate_kpi(kpi, args.phase)
        
        # 결과 저장
        result["validation"] = validation
        
        result_file = output_path / "result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"[D205-9] Result saved to {result_file}")
        
        # AC 결과 출력
        if validation["passed"]:
            logger.info(f"[D205-9] ✅ PASS: {args.phase} validation")
        else:
            logger.error(f"[D205-9] ❌ FAIL: {validation['reasons']}")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"[D205-9] Error: {e}")
        
        # 에러 저장
        error_file = output_path / "error.log"
        with open(error_file, "w", encoding="utf-8") as f:
            f.write(str(e))
        
        sys.exit(1)
    
    logger.info("[D205-9] Completed successfully")


if __name__ == "__main__":
    main()
