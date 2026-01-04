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
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.paper_runner import PaperRunner, PaperRunnerConfig
from arbitrage.v2.opportunity import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_single_sweep(
    buffer_bps: float,
    duration_minutes: int,
    use_real_data: bool,
    db_mode: str,
    evidence_base_dir: Path,
    fx_rate: float = 1450.0,
) -> Dict:
    """
    단일 buffer_bps 값으로 PaperRunner 실행
    
    Returns:
        {
            "buffer_bps": float,
            "kpi": dict,
            "evidence_path": str,
            "exit_code": int,
        }
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"d205_10_1_buffer_{int(buffer_bps)}_{timestamp}"
    evidence_dir = evidence_base_dir / run_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    # FeeModel 생성 (Upbit/Binance 기본값)
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
    
    # BreakEvenParams 생성 (buffer_bps만 변경)
    break_even_params = BreakEvenParams(
        fee_model=fee_model,
        slippage_bps=15.0,
        latency_bps=10.0,
        buffer_bps=buffer_bps,
    )
    
    # Config
    config = PaperRunnerConfig(
        duration_minutes=duration_minutes,
        phase="sweep",
        run_id=run_id,
        output_dir=str(evidence_dir),
        symbols_top=10,
        db_mode=db_mode,
        use_real_data=use_real_data,
        fx_krw_per_usdt=fx_rate,
        break_even_params=break_even_params,
    )
    
    logger.info(f"[D205-10-1] Sweep {buffer_bps} bps (duration={duration_minutes}m)")
    
    # Run
    runner = PaperRunner(config)
    exit_code = runner.run()
    
    # Load KPI
    kpi_path = evidence_dir / "kpi_sweep.json"
    if not kpi_path.exists():
        logger.error(f"[D205-10-1] KPI file not found: {kpi_path}")
        return {
            "buffer_bps": buffer_bps,
            "kpi": {},
            "evidence_path": str(evidence_dir),
            "exit_code": exit_code,
            "error": "KPI file not found",
        }
    
    with open(kpi_path, "r") as f:
        kpi = json.load(f)
    
    return {
        "buffer_bps": buffer_bps,
        "kpi": kpi,
        "evidence_path": str(evidence_dir),
        "exit_code": exit_code,
    }


def select_best_buffer(sweep_results: List[Dict]) -> Dict:
    """
    Best buffer 선정
    
    기준:
    1. closed_trades > 0
    2. error_count == 0
    3. net_pnl 최대
    
    Returns:
        {
            "best_buffer_bps": float,
            "reason": str,
            "candidates": list,
            "rejected": list,
        }
    """
    candidates = []
    rejected = []
    
    for result in sweep_results:
        buffer_bps = result["buffer_bps"]
        kpi = result.get("kpi", {})
        
        closed_trades = kpi.get("closed_trades", 0)
        error_count = kpi.get("error_count", 0)
        net_pnl = kpi.get("net_pnl_krw", 0.0)
        
        # 조건 1: closed_trades > 0
        if closed_trades <= 0:
            rejected.append({
                "buffer_bps": buffer_bps,
                "reason": f"closed_trades={closed_trades} (expected > 0)",
                "kpi": kpi,
            })
            continue
        
        # 조건 2: error_count == 0
        if error_count != 0:
            rejected.append({
                "buffer_bps": buffer_bps,
                "reason": f"error_count={error_count} (expected 0)",
                "kpi": kpi,
            })
            continue
        
        # 후보 추가
        candidates.append({
            "buffer_bps": buffer_bps,
            "closed_trades": closed_trades,
            "error_count": error_count,
            "net_pnl_krw": net_pnl,
            "gross_pnl_krw": kpi.get("gross_pnl_krw", 0.0),
            "total_fees_krw": kpi.get("total_fees_krw", 0.0),
            "winrate_pct": kpi.get("winrate_pct", 0.0),
            "opportunities": kpi.get("opportunities_generated", 0),
            "intents": kpi.get("intents_created", 0),
        })
    
    if not candidates:
        return {
            "best_buffer_bps": None,
            "reason": "No valid candidates (all failed AC-1 or AC-2)",
            "candidates": [],
            "rejected": rejected,
        }
    
    # 조건 3: net_pnl 최대
    best = max(candidates, key=lambda x: x["net_pnl_krw"])
    
    return {
        "best_buffer_bps": best["buffer_bps"],
        "reason": f"Highest net_pnl_krw={best['net_pnl_krw']:.2f} KRW",
        "candidates": candidates,
        "rejected": rejected,
        "best_candidate": best,
    }


def run_negative_control(
    duration_minutes: int,
    use_real_data: bool,
    db_mode: str,
    evidence_base_dir: Path,
    fx_rate: float = 1450.0,
) -> Dict:
    """
    Negative-control run (buffer=999, 매우 큰 값으로 모든 기회 거절 예상)
    
    목적: reject_reasons.profitable_false > 0 검증
    
    Returns:
        {
            "buffer_bps": 999.0,
            "duration_minutes": int,
            "kpi": dict,
            "evidence_dir": str,
            "reject_reasons": dict,
            "passed": bool,
            "reason": str,
        }
    """
    logger.info(f"[D205-10-1] Running negative-control (buffer=999, duration={duration_minutes}m)")
    
    # buffer=999로 run
    result = run_single_sweep(
        buffer_bps=999.0,
        duration_minutes=duration_minutes,
        use_real_data=use_real_data,
        db_mode=db_mode,
        evidence_base_dir=evidence_base_dir,
        fx_rate=fx_rate,
    )
    
    kpi = result.get("kpi", {})
    reject_reasons = kpi.get("reject_reasons", {})
    profitable_false_count = reject_reasons.get("profitable_false", 0)
    
    # PASS 조건: profitable_false > 0
    passed = profitable_false_count > 0
    
    reason = (
        f"profitable_false={profitable_false_count} (expected > 0)"
        if passed
        else f"profitable_false={profitable_false_count} (FAIL: expected > 0, got 0)"
    )
    
    return {
        "buffer_bps": 999.0,
        "duration_minutes": duration_minutes,
        "kpi": kpi,
        "evidence_dir": result.get("evidence_path", ""),
        "reject_reasons": reject_reasons,
        "passed": passed,
        "reason": reason,
    }


def main():
    parser = argparse.ArgumentParser(description="D205-10-1: Threshold Sensitivity Sweep")
    parser.add_argument("--duration-minutes", type=int, default=2, help="Duration per sweep (minutes)")
    parser.add_argument("--use-real-data", action="store_true", help="Use Real MarketData")
    parser.add_argument("--db-mode", default="off", choices=["strict", "optional", "off"])
    parser.add_argument("--fx-krw-per-usdt", type=float, default=1450.0, help="FX rate (KRW/USDT)")
    parser.add_argument("--out-evidence-dir", default=None, help="Evidence output directory")
    
    args = parser.parse_args()
    
    # Evidence base directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out_evidence_dir:
        evidence_base_dir = Path(args.out_evidence_dir)
    else:
        evidence_base_dir = Path(f"logs/evidence/d205_10_1_sweep_{timestamp}")
    evidence_base_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[D205-10-1] Starting Threshold Sensitivity Sweep")
    logger.info(f"[D205-10-1] Duration per sweep: {args.duration_minutes}m")
    logger.info(f"[D205-10-1] Evidence: {evidence_base_dir}")
    
    # Sweep buffer_bps [0, 2, 5, 8, 10]
    buffer_values = [0.0, 2.0, 5.0, 8.0, 10.0]
    sweep_results = []
    
    for buffer_bps in buffer_values:
        result = run_single_sweep(
            buffer_bps=buffer_bps,
            duration_minutes=args.duration_minutes,
            use_real_data=args.use_real_data,
            db_mode=args.db_mode,
            evidence_base_dir=evidence_base_dir,
            fx_rate=args.fx_krw_per_usdt,
        )
        sweep_results.append(result)
        
        # 짧은 sleep (로그 분리)
        time.sleep(2)
    
    # Best buffer 선정
    best_selection = select_best_buffer(sweep_results)
    
    # Negative-control run (buffer=999, 1m)
    logger.info(f"[D205-10-1] Starting negative-control run (buffer=999)")
    negative_control = run_negative_control(
        duration_minutes=1,  # 짧게 1분
        use_real_data=args.use_real_data,
        db_mode=args.db_mode,
        evidence_base_dir=evidence_base_dir,
        fx_rate=args.fx_krw_per_usdt,
    )
    
    # Summary 생성
    summary = {
        "sweep_timestamp": timestamp,
        "duration_minutes_per_sweep": args.duration_minutes,
        "buffer_values": buffer_values,
        "sweep_results": sweep_results,
        "best_selection": best_selection,
        "negative_control": negative_control,
        "passed": best_selection["best_buffer_bps"] is not None and negative_control["passed"],
    }
    
    # Save summary
    summary_path = evidence_base_dir / "sweep_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"[D205-10-1] Summary saved to {summary_path}")
    
    # 결과 출력
    if best_selection["best_buffer_bps"] is not None:
        logger.info(f"[D205-10-1] ✅ Best buffer: {best_selection['best_buffer_bps']} bps")
        logger.info(f"[D205-10-1] Reason: {best_selection['reason']}")
    else:
        logger.error(f"[D205-10-1] ❌ No valid candidates: {best_selection['reason']}")
    
    logger.info(f"[D205-10-1] Negative-control: {'✅ PASS' if negative_control['passed'] else '❌ FAIL'}")
    
    if summary["passed"]:
        logger.info(f"[D205-10-1] ✅ Sweep PASS")
        return 0
    else:
        logger.error(f"[D205-10-1] ❌ Sweep FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
