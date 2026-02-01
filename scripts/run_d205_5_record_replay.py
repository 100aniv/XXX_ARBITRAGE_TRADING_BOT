#!/usr/bin/env python3
"""
D205-5: Record/Replay SSOT CLI

모드:
- record: 실시간 데이터 수집 → market.ndjson 저장
- replay: market.ndjson 입력 → 재실행 검증
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.replay.replay_runner import ReplayRunner
from arbitrage.v2.scan.scanner import MultiSymbolScanner, ScanConfig
from arbitrage.v2.core.runtime_factory import build_break_even_params_from_config_path

logger = logging.getLogger(__name__)


def main(argv=None):
    """
    Main entry point
    
    Args:
        argv: Command line arguments (None = sys.argv, for testing)
    """
    parser = argparse.ArgumentParser(description="D205-5: Record/Replay SSOT")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["record", "replay"],
        help="Mode: record or replay",
    )
    parser.add_argument(
        "--symbol",
        default="BTC/KRW",
        help="Symbol to record (default: BTC/KRW)",
    )
    parser.add_argument(
        "--duration-sec",
        type=int,
        default=30,
        help="Record duration in seconds (default: 30)",
    )
    parser.add_argument(
        "--sample-interval-sec",
        type=float,
        default=2.0,
        help="Sample interval in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--out-evidence-dir",
        type=str,
        default=None,
        help="Output evidence directory (default: logs/evidence/d205_5_<mode>_<timestamp>)",
    )
    parser.add_argument(
        "--fx-krw-per-usdt",
        type=float,
        default=1450.0,
        help="FX rate USDT → KRW (D205-8, default: 1450.0)",
    )
    parser.add_argument(
        "--input-file",
        type=Path,
        default=None,
        help="Input market.ndjson file for replay mode",
    )
    
    args = parser.parse_args(argv)
    
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    output_dir = Path(args.out_evidence_dir) if args.out_evidence_dir else Path(
        f"logs/evidence/d205_5_record_replay_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    break_even_params = build_break_even_params_from_config_path()
    fee_model = break_even_params.fee_model

    if args.mode == "record":
        scan_config = ScanConfig(
            fx_krw_per_usdt=args.fx_krw_per_usdt,
            upbit_fee_bps=fee_model.fee_a.taker_fee_bps,
            binance_fee_bps=fee_model.fee_b.taker_fee_bps,
            slippage_bps=break_even_params.slippage_bps,
            fx_conversion_bps=0.0,
            buffer_bps=break_even_params.buffer_bps,
        )
        scanner = MultiSymbolScanner(scan_config=scan_config, output_dir=output_dir)
        result = scanner.record_symbol(
            symbol=args.symbol,
            duration_seconds=args.duration_sec,
            polling_interval=args.sample_interval_sec,
        )
        status = result.get("status")
        if status != "completed":
            logger.error(f"[D205-5_RECORD] FAIL: {result}")
            return 1
        logger.info(f"[D205-5_RECORD] Completed: {result}")
        return 0

    if not args.input_file:
        logger.error("[D205-5_REPLAY] Input file required for replay mode")
        return 1
    if not args.input_file.exists():
        logger.error(f"[D205-5_REPLAY] Input file not found: {args.input_file}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)
    replay_runner = ReplayRunner(
        input_path=args.input_file,
        output_dir=output_dir,
        break_even_params=break_even_params,
        fx_krw_per_usdt=args.fx_krw_per_usdt,
    )
    result = replay_runner.run()
    if result.get("status") == "FAIL":
        logger.error(f"[D205-5_REPLAY] FAIL: {result.get('reason', 'Unknown')}")
        return 1

    logger.info(f"[D205-5_REPLAY] Completed: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
