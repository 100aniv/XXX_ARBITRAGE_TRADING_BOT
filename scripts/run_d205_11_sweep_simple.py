#!/usr/bin/env python3
"""D205-11: Simple Threshold Sweep (3 candidates, 2m each)"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.paper_runner import PaperRunner
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    buffer_bps_list = [0.0, 2.0, 5.0]  # 3개 후보
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"logs/evidence/d205_11_sweep_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[D205-11] START | candidates: {buffer_bps_list} | output: {output_dir}")
    
    results = []
    
    for buffer_bps in buffer_bps_list:
        logger.info(f"[D205-11 SWEEP] buffer_bps={buffer_bps:.1f} | duration=2.0m")
        
        try:
            fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=25.0)
            fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=25.0)
            fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
            
            break_even_params = BreakEvenParams(
                fee_model=fee_model,
                slippage_bps=15.0,
                latency_bps=10.0,
                buffer_bps=buffer_bps,
            )
            
            run_id = f"d205_11_sweep_buffer_{buffer_bps:.1f}_{int(time.time())}"
            
            runner = PaperRunner(
                run_id=run_id,
                duration_minutes=2.0,
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
                
                result = {
                    "buffer_bps": buffer_bps,
                    "status": "pass",
                    "opportunities": kpi.get("opportunities_generated", 0),
                    "intents": kpi.get("intents_created", 0),
                    "closed_trades": kpi.get("closed_trades", 0),
                    "net_pnl": kpi.get("net_pnl", 0.0),
                    "error_count": kpi.get("error_count", 0),
                }
                
                logger.info(f"[D205-11 PASS] buffer_bps={buffer_bps:.1f} | intents={result['intents']} | net_pnl={result['net_pnl']:.2f}")
                results.append(result)
            else:
                logger.warning(f"[D205-11] No KPI for buffer_bps={buffer_bps:.1f}")
                results.append({"buffer_bps": buffer_bps, "status": "no-kpi"})
        
        except Exception as e:
            logger.error(f"[D205-11 ERROR] buffer_bps={buffer_bps:.1f} | {e}")
            results.append({"buffer_bps": buffer_bps, "status": "error", "error": str(e)})
        
        time.sleep(1.0)
    
    # Select best
    candidates = [r for r in results if r.get("status") == "pass" and r.get("closed_trades", 0) > 0 and r.get("error_count", 0) == 0]
    
    if candidates:
        candidates.sort(key=lambda x: x.get("net_pnl", -999999), reverse=True)
        best = candidates[0]
        logger.info(f"[D205-11 ✅ BEST] buffer_bps={best['buffer_bps']:.1f} | net_pnl={best['net_pnl']:.2f}")
    else:
        best = None
        logger.error("[D205-11 ❌ FAIL] No valid candidates")
    
    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "buffer_bps_list": buffer_bps_list,
        "results": results,
        "best": best,
    }
    
    summary_path = output_dir / "sweep_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[D205-11 DONE] Summary: {summary_path}")
    
    if not best:
        sys.exit(1)


if __name__ == "__main__":
    main()
