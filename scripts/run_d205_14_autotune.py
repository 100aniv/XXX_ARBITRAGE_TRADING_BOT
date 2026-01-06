#!/usr/bin/env python3
"""
D205-14: Auto Tuning CLI

Config SSOT 기반 파라미터 자동 튜닝

Usage:
    python scripts/run_d205_14_autotune.py --config config/v2/config.yml --input logs/evidence/.../market.ndjson
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.execution_quality.autotune import AutoTuner
from arbitrage.v2.core.config import load_config

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="D205-14: Auto Tuning")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/v2/config.yml"),
        help="Config file path (default: config/v2/config.yml)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input market.ndjson file path (Replay data)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output evidence directory (default: auto-generated)",
    )
    
    args = parser.parse_args()
    
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Load config
    logger.info(f"[D205-14_CLI] Loading config: {args.config}")
    config = load_config(args.config)
    
    # Validate tuning enabled
    if not config.tuning.enabled:
        logger.warning("[D205-14_CLI] tuning.enabled=false in config - proceeding anyway (dry-run mode)")
    
    # Output directory
    output_dir = args.output_dir or Path(f"logs/evidence/d205_14_autotune_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    logger.info(f"[D205-14_CLI] Input: {args.input}")
    logger.info(f"[D205-14_CLI] Output: {output_dir}")
    
    # Run AutoTuner
    tuner = AutoTuner(
        config=config,
        input_path=args.input,
        output_dir=output_dir,
    )
    
    result = tuner.run()
    
    # Summary
    logger.info("[D205-14_CLI] ===== AUTO TUNING SUMMARY =====")
    logger.info(f"Total combinations: {len(result['leaderboard'])}")
    logger.info(f"Best params: {result['best_params']}")
    logger.info(f"Output dir: {result['output_dir']}")
    logger.info("[D205-14_CLI] Done.")


if __name__ == "__main__":
    main()
