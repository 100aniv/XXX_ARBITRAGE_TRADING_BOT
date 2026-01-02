#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D205-11: DecisionTrace Negative-Control Test

Verify reject_reasons actually works by forcing all candidates to be unprofitable.

Purpose:
- Set buffer_bps=999 → all candidates become unprofitable
- Run 30-second test
- Verify reject_reasons["profitable_false"] > 0

Usage:
    python scripts/run_d205_11_negative_control.py
"""

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    logger.info("[D205-11 NEGATIVE-CONTROL] Starting...")
    
    # Output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"logs/evidence/d205_11_negative_control_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[D205-11] Evidence dir: {output_dir}")
    
    # 임시 runner 스크립트 생성 (buffer_bps=999 강제)
    runner_script = output_dir / "tmp_negative_control_runner.py"
    
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

# D205-11 NEGATIVE-CONTROL: buffer_bps=999 (강제 unprofitable)
fee_model = FeeModel(
    upbit=FeeStructure(taker_fee_bps=25.0, maker_fee_bps=25.0),
    binance=FeeStructure(taker_fee_bps=25.0, maker_fee_bps=25.0),
)

break_even_params = BreakEvenParams(
    fee_model=fee_model,
    slippage_bps=15.0,
    latency_bps=10.0,
    buffer_bps=999.0,  # D205-11: 강제 unprofitable
)

runner = PaperRunner(
    run_id=f"d205_11_negative_control_{{int(time.time())}}",
    duration_minutes=0.5,  # 30초
    use_real_data=False,
    db_mode="off",
    output_dir=r"{output_dir}",
    break_even_params=break_even_params,
)

runner.run()
"""
    
    runner_script.write_text(runner_code, encoding="utf-8")
    
    # 실행
    cmd = [sys.executable, str(runner_script)]
    logger.info(f"[D205-11] Executing: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            timeout=90,  # 30s + 60s margin
        )
        
        if result.returncode != 0:
            logger.error(f"[D205-11 FAIL] stderr={result.stderr[:500]}")
            sys.exit(1)
        
        logger.info("[D205-11 PASS] Runner completed")
        
        # KPI 수집
        kpi_files = list(output_dir.glob("**/kpi_smoke.json"))
        if not kpi_files:
            logger.error("[D205-11 FAIL] No KPI file found")
            sys.exit(1)
        
        kpi_path = kpi_files[-1]
        with open(kpi_path, "r", encoding="utf-8") as f:
            kpi = json.load(f)
        
        logger.info(f"[D205-11] KPI loaded: {kpi_path}")
        
        # 검증: reject_reasons["profitable_false"] > 0
        reject_reasons = kpi.get("reject_reasons", {})
        profitable_false = reject_reasons.get("profitable_false", 0)
        intents_created = kpi.get("intents_created", 0)
        
        logger.info(f"[D205-11] intents_created={intents_created}")
        logger.info(f"[D205-11] reject_reasons={reject_reasons}")
        
        # 판정
        if intents_created == 0 and profitable_false > 0:
            logger.info(f"[D205-11 ✅ PASS] DecisionTrace works! profitable_false={profitable_false}")
            
            # Summary 저장
            summary = {
                "timestamp": datetime.now().isoformat(),
                "test": "negative-control",
                "buffer_bps": 999.0,
                "result": "PASS",
                "intents_created": intents_created,
                "reject_reasons": reject_reasons,
                "kpi_file": str(kpi_path),
            }
            
            summary_path = output_dir / "negative_control_summary.json"
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[D205-11] Summary saved: {summary_path}")
            
        else:
            logger.error(f"[D205-11 ❌ FAIL] Expected intents=0 and profitable_false>0, got intents={intents_created}, profitable_false={profitable_false}")
            sys.exit(1)
    
    except subprocess.TimeoutExpired:
        logger.error("[D205-11 TIMEOUT]")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[D205-11 ERROR] {e}", exc_info=True)
        sys.exit(1)
    finally:
        # 임시 스크립트 삭제
        if runner_script.exists():
            runner_script.unlink()


if __name__ == "__main__":
    main()
