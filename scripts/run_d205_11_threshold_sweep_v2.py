#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D205-11: Threshold Sensitivity Sweep (In-Process Version)

Direct PaperRunner import로 subprocess 우회.
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.paper_runner import PaperRunner
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="D205-11: Threshold Sweep (In-Process)")
    parser.add_argument("--buffer-bps-list", type=str, default="0,1,2,3,5", help="Comma-separated buffer_bps values")
    parser.add_argument("--run-duration-minutes", type=float, default=2.0, help="Duration per run in minutes")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    return parser.parse_args()


def run_single_sweep(buffer_bps: float, run_duration_minutes: float, output_dir: Path) -> Optional[Dict[str, Any]]:
    """Run a single sweep with given buffer_bps (in-process)."""
    logger.info(f"[D205-11 SWEEP] buffer_bps={buffer_bps:.1f} | duration={run_duration_minutes:.2f}m")
    
    try:
        # FeeModel 생성
        fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=25.0)
        fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=25.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        # BreakEvenParams (buffer_bps 주입)
        break_even_params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=15.0,
            latency_bps=10.0,
            buffer_bps=buffer_bps,
        )
        
        # PaperRunner 생성 및 실행
        run_id = f"d205_11_sweep_buffer_{buffer_bps:.1f}_{int(time.time())}"
        
        runner = PaperRunner(
            run_id=run_id,
            duration_minutes=run_duration_minutes,
            use_real_data=False,
            db_mode="off",
            output_dir=str(output_dir),
            break_even_params=break_even_params,
        )
        
        runner.run()
        
        # KPI 수집
        kpi_files = list(output_dir.glob("**/kpi_smoke.json"))
        if kpi_files:
            kpi_path = kpi_files[-1]
            with open(kpi_path, "r", encoding="utf-8") as f:
                kpi = json.load(f)
            
            logger.info(f"[D205-11 PASS] buffer_bps={buffer_bps:.1f}")
            
            return {
                "buffer_bps": buffer_bps,
                "status": "pass",
                "opportunities": kpi.get("opportunities_generated", 0),
                "intents": kpi.get("intents_created", 0),
                "closed_trades": kpi.get("closed_trades", 0),
                "net_pnl": kpi.get("net_pnl", 0.0),
                "error_count": kpi.get("error_count", 0),
                "kpi_file": str(kpi_path),
            }
        else:
            logger.warning(f"[D205-11] No KPI file found for buffer_bps={buffer_bps:.1f}")
            return {"buffer_bps": buffer_bps, "status": "no-kpi"}
    
    except Exception as e:
        logger.error(f"[D205-11 ERROR] buffer_bps={buffer_bps:.1f} | {e}", exc_info=True)
        return {"buffer_bps": buffer_bps, "status": "error", "error": str(e)}


def select_best_buffer(results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Select best buffer_bps."""
    candidates = [
        r for r in results
        if r.get("status") == "pass"
        and r.get("closed_trades", 0) > 0
        and r.get("error_count", 0) == 0
    ]
    
    if not candidates:
        logger.warning("[D205-11] No valid candidates")
        return None
    
    candidates.sort(key=lambda x: x.get("net_pnl", -999999), reverse=True)
    best = candidates[0]
    
    logger.info(f"[D205-11 BEST] buffer_bps={best['buffer_bps']:.1f} | net_pnl={best['net_pnl']:.2f} | closed_trades={best['closed_trades']}")
    
    return best


def main():
    args = parse_args()
    
    buffer_bps_list = [float(x.strip()) for x in args.buffer_bps_list.split(",")]
    
    logger.info(f"[D205-11 START] buffer_bps candidates: {buffer_bps_list}")
    logger.info(f"[D205-11] Duration per run: {args.run_duration_minutes:.2f}m")
    logger.info(f"[D205-11] Total estimated time: {len(buffer_bps_list) * args.run_duration_minutes:.1f}m")
    
    # Output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"logs/evidence/d205_11_sweep_{timestamp}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[D205-11] Evidence dir: {output_dir}")
    
    # Run sweep
    results = []
    for buffer_bps in buffer_bps_list:
        result = run_single_sweep(
            buffer_bps=buffer_bps,
            run_duration_minutes=args.run_duration_minutes,
            output_dir=output_dir,
        )
        
        if result:
            results.append(result)
        
        time.sleep(1.0)
    
    # Select best
    best = select_best_buffer(results)
    
    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "buffer_bps_list": buffer_bps_list,
        "run_duration_minutes": args.run_duration_minutes,
        "results": results,
        "best": best,
    }
    
    summary_path = output_dir / "sweep_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[D205-11 DONE] Summary saved: {summary_path}")
    
    if best:
        logger.info(f"[D205-11 ✅ BEST] buffer_bps={best['buffer_bps']:.1f}")
    else:
        logger.error("[D205-11 ❌ FAIL] No valid buffer_bps found")
        sys.exit(1)


if __name__ == "__main__":
    main()
