#!/usr/bin/env python3
"""
D205-7: Parameter Sweep CLI

ExecutionQuality 파라미터 튜닝 (Grid Search)

Usage:
    python scripts/run_d205_7_parameter_sweep.py --input logs/evidence/.../market.ndjson
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.execution_quality.sweep import ParameterSweep
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="D205-7: Parameter Sweep")
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input market.ndjson file path",
    )
    parser.add_argument(
        "--out-evidence-dir",
        type=Path,
        default=None,
        help="Output evidence directory",
    )
    parser.add_argument(
        "--slippage-alpha-range",
        nargs="+",
        type=float,
        default=[5.0, 10.0, 15.0, 20.0],
        help="Slippage alpha range (default: 5 10 15 20)",
    )
    parser.add_argument(
        "--partial-penalty-range",
        nargs="+",
        type=float,
        default=[10.0, 20.0, 30.0],
        help="Partial fill penalty range (default: 10 20 30)",
    )
    parser.add_argument(
        "--max-safe-ratio-range",
        nargs="+",
        type=float,
        default=[0.2, 0.3, 0.4],
        help="Max safe ratio range (default: 0.2 0.3 0.4)",
    )
    
    args = parser.parse_args()
    
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Output directory
    output_dir = args.out_evidence_dir or Path(f"logs/evidence/d205_7_parameter_sweep_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    # Param grid
    param_grid = {
        "slippage_alpha": args.slippage_alpha_range,
        "partial_fill_penalty_bps": args.partial_penalty_range,
        "max_safe_ratio": args.max_safe_ratio_range,
    }
    
    # Break-even params (고정)
    fee_a = FeeStructure("upbit", maker_fee_bps=5.0, taker_fee_bps=25.0)
    fee_b = FeeStructure("binance", maker_fee_bps=10.0, taker_fee_bps=25.0)
    fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
    break_even_params = BreakEvenParams(
        fee_model=fee_model,
        slippage_bps=10.0,
        buffer_bps=5.0,
    )
    
    # Sweep 실행
    sweep = ParameterSweep(
        input_path=args.input,
        output_dir=output_dir,
        param_grid=param_grid,
        break_even_params=break_even_params,
    )
    
    result = sweep.run()
    
    logger.info(f"[D205-7] Sweep completed: {result}")
    
    if result["status"] == "FAIL":
        logger.error("[D205-7] Sweep FAIL")
        sys.exit(1)
    
    logger.info("[D205-7] Completed successfully")


if __name__ == "__main__":
    main()
