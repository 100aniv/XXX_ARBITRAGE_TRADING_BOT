#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D205-11: Threshold Sensitivity Sweep Runner

Grid search over buffer_bps to evaluate impact on trades, PnL, and reject_reasons.

Purpose:
- Systematically vary buffer_bps [0, 1, 2, 3, 5, 8, 10]
- Execute 2-minute PAPER runs for each combination
- Collect KPI metrics
- Select best buffer_bps (closed_trades > 0, error_count == 0, net_pnl max)

Usage:
    # Dry-run (print commands only)
    python scripts/run_d205_11_threshold_sweep.py --dry-run

    # Actual execution (7 combinations × 2 min = 14 min)
    python scripts/run_d205_11_threshold_sweep.py

    # Custom parameters
    python scripts/run_d205_11_threshold_sweep.py \
        --buffer-bps-list "0,1,2,3,5,8,10" \
        --run-duration-seconds 120
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="D205-11: Threshold Sensitivity Sweep (buffer_bps)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--buffer-bps-list",
        type=str,
        default="0,1,2,3,5,8,10",
        help="Comma-separated buffer_bps values, default: 0,1,2,3,5,8,10",
    )
    parser.add_argument(
        "--run-duration-seconds",
        type=int,
        default=120,
        help="Duration per run in seconds, default: 120 (2 minutes)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for evidence, default: logs/evidence/d205_11_sweep_<timestamp>",
    )
    return parser.parse_args()


def run_single_sweep(
    buffer_bps: float,
    run_duration_seconds: int,
    output_dir: Path,
    dry_run: bool = False,
) -> Optional[Dict[str, Any]]:
    """Run a single sweep with given buffer_bps."""
    logger.info(f"[D205-11 SWEEP] buffer_bps={buffer_bps:.1f} | duration={run_duration_seconds}s")
    
    # 임시 runner 스크립트 생성 (buffer_bps 주입)
    runner_script = output_dir / f"tmp_runner_buffer_{buffer_bps:.1f}.py"
    
    runner_code = f"""#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.harness.paper_runner import PaperRunner
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# D205-11: buffer_bps={buffer_bps:.1f} 주입
fee_model = FeeModel(
    upbit=FeeStructure(taker_fee_bps=25.0, maker_fee_bps=25.0),
    binance=FeeStructure(taker_fee_bps=25.0, maker_fee_bps=25.0),
)

break_even_params = BreakEvenParams(
    fee_model=fee_model,
    slippage_bps=15.0,
    latency_bps=10.0,
    buffer_bps={buffer_bps:.1f},  # D205-11: sweep 파라미터
)

runner = PaperRunner(
    run_id=f"d205_11_sweep_buffer_{{buffer_bps:.1f}}_{{int(time.time())}}",
    duration_minutes={run_duration_seconds / 60.0:.2f},
    use_real_data=False,
    db_mode="off",
    output_dir=r"{output_dir}",
    break_even_params=break_even_params,
)

runner.run()
"""
    
    if dry_run:
        logger.info(f"[DRY-RUN] Would create: {runner_script}")
        logger.info(f"[DRY-RUN] Would run: python {runner_script}")
        return {"buffer_bps": buffer_bps, "status": "dry-run"}
    
    # 스크립트 작성
    runner_script.write_text(runner_code, encoding="utf-8")
    
    # 실행
    cmd = [sys.executable, str(runner_script)]
    logger.info(f"[D205-11] Executing: {{' '.join(cmd)}}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            timeout=run_duration_seconds + 60,  # +60s margin
        )
        
        if result.returncode != 0:
            logger.error(f"[D205-11 FAIL] buffer_bps={buffer_bps:.1f} | stderr={result.stderr[:500]}")
            return {"buffer_bps": buffer_bps, "status": "fail", "error": result.stderr[:500]}
        
        logger.info(f"[D205-11 PASS] buffer_bps={buffer_bps:.1f}")
        
        # KPI 수집 (runner가 kpi_smoke.json 생성)
        kpi_files = list(output_dir.glob("**/kpi_smoke.json"))
        if kpi_files:
            kpi_path = kpi_files[-1]  # 최신 파일
            with open(kpi_path, "r", encoding="utf-8") as f:
                kpi = json.load(f)
            
            return {{
                "buffer_bps": buffer_bps,
                "status": "pass",
                "opportunities": kpi.get("opportunities_generated", 0),
                "intents": kpi.get("intents_created", 0),
                "closed_trades": kpi.get("closed_trades", 0),
                "net_pnl": kpi.get("net_pnl", 0.0),
                "error_count": kpi.get("error_count", 0),
                "kpi_file": str(kpi_path),
            }}
        else:
            logger.warning(f"[D205-11] No KPI file found for buffer_bps={{buffer_bps:.1f}}")
            return {{"buffer_bps": buffer_bps, "status": "no-kpi"}}
    
    except subprocess.TimeoutExpired:
        logger.error(f"[D205-11 TIMEOUT] buffer_bps={{buffer_bps:.1f}}")
        return {{"buffer_bps": buffer_bps, "status": "timeout"}}
    except Exception as e:
        logger.error(f"[D205-11 ERROR] buffer_bps={{buffer_bps:.1f}} | {{e}}")
        return {{"buffer_bps": buffer_bps, "status": "error", "error": str(e)}}
    finally:
        # 임시 스크립트 삭제
        if runner_script.exists():
            runner_script.unlink()


def select_best_buffer(results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Select best buffer_bps based on criteria."""
    # 필터: closed_trades > 0 AND error_count == 0
    candidates = [
        r for r in results
        if r.get("status") == "pass"
        and r.get("closed_trades", 0) > 0
        and r.get("error_count", 0) == 0
    ]
    
    if not candidates:
        logger.warning("[D205-11] No valid candidates (all failed or no trades)")
        return None
    
    # 정렬: net_pnl 최대값 (가능하면 >= 0)
    candidates.sort(key=lambda x: x.get("net_pnl", -999999), reverse=True)
    
    best = candidates[0]
    logger.info(f"[D205-11 BEST] buffer_bps={{best['buffer_bps']:.1f}} | net_pnl={{best['net_pnl']:.2f}} | closed_trades={{best['closed_trades']}}")
    
    return best


def main():
    args = parse_args()
    
    # Parse buffer_bps list
    buffer_bps_list = [float(x.strip()) for x in args.buffer_bps_list.split(",")]
    
    logger.info(f"[D205-11 START] buffer_bps candidates: {{buffer_bps_list}}")
    logger.info(f"[D205-11] Duration per run: {{args.run_duration_seconds}}s")
    logger.info(f"[D205-11] Total estimated time: {{len(buffer_bps_list) * args.run_duration_seconds // 60}}m")
    
    # Output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(f"logs/evidence/d205_11_sweep_{{timestamp}}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[D205-11] Evidence dir: {output_dir}")
    
    # Run sweep
    results = []
    for buffer_bps in buffer_bps_list:
        result = run_single_sweep(
            buffer_bps=buffer_bps,
            run_duration_seconds=args.run_duration_seconds,
            output_dir=output_dir,
            dry_run=args.dry_run,
        )
        
        if result:
            results.append(result)
        
        # 다음 러닝 전 1초 대기 (cleanup)
        time.sleep(1.0)
    
    # Select best
    best = select_best_buffer(results)
    
    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "buffer_bps_list": buffer_bps_list,
        "run_duration_seconds": args.run_duration_seconds,
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
