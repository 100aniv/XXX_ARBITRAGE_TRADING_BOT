#!/usr/bin/env python3
"""
D205-5: Record/Replay SSOT CLI

모드:
- record: 실시간 데이터 수집 → market.ndjson 저장
- replay: market.ndjson 입력 → 재실행 검증
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider
from arbitrage.v2.replay.schemas import MarketTick
from arbitrage.v2.replay.recorder import MarketRecorder
from arbitrage.v2.replay.replay_runner import ReplayRunner
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logger = logging.getLogger(__name__)


class RecordReplayRunner:
    """
    Record/Replay 통합 Runner
    """
    
    def __init__(
        self,
        mode: str,
        symbols: List[str],
        duration_sec: int = 30,
        sample_interval_sec: float = 2.0,
        output_dir: Path = None,
        input_file: Path = None,
        fx_krw_per_usdt: float = 1450.0,
    ):
        self.mode = mode
        self.symbols = symbols
        self.duration_sec = duration_sec
        self.sample_interval_sec = sample_interval_sec
        self.output_dir = Path(output_dir) if output_dir else Path(f"logs/evidence/d205_5_record_replay_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.input_file = input_file
        self.fx_krw_per_usdt = fx_krw_per_usdt
        
        # Providers (record 모드용)
        self.upbit_rest = UpbitRestProvider()
        self.binance_rest = BinanceRestProvider()
        
        # Break-even params
        fee_a = FeeStructure("upbit", maker_fee_bps=5.0, taker_fee_bps=25.0)
        fee_b = FeeStructure("binance", maker_fee_bps=10.0, taker_fee_bps=25.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        self.break_even_params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        logger.info(f"[D205-5] Mode: {mode}")
        logger.info(f"[D205-5] Output: {self.output_dir}")
    
    async def run(self):
        """메인 실행"""
        if self.mode == "record":
            await self._run_record()
        elif self.mode == "replay":
            self._run_replay()
        else:
            raise ValueError(f"Invalid mode: {self.mode}")
    
    async def _run_record(self):
        """Record 모드: 실시간 데이터 수집"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        market_file = self.output_dir / "market.ndjson"
        
        recorder = MarketRecorder(market_file)
        
        start_time = time.time()
        logger.info(f"[D205-5_RECORD] Starting record... (duration={self.duration_sec}s)")
        
        try:
            tick_count = 0
            while (time.time() - start_time) < self.duration_sec:
                for symbol in self.symbols:
                    try:
                        # Upbit tick
                        upbit_ticker = self.upbit_rest.get_ticker(symbol)
                        if not upbit_ticker:
                            continue
                        
                        # Binance tick (symbol 매핑)
                        binance_symbol = symbol.replace("/KRW", "/USDT")
                        binance_ticker = self.binance_rest.get_ticker(binance_symbol)
                        if not binance_ticker:
                            continue
                        
                        # MarketTick 생성
                        tick = MarketTick(
                            timestamp=datetime.now().isoformat(),
                            symbol=symbol,
                            upbit_bid=upbit_ticker.bid,
                            upbit_ask=upbit_ticker.ask,
                            binance_bid=binance_ticker.bid,
                            binance_ask=binance_ticker.ask,
                        )
                        
                        recorder.record_tick(tick)
                        tick_count += 1
                        
                        if tick_count % 5 == 0:
                            logger.info(f"[D205-5_RECORD] Recorded {tick_count} ticks")
                    
                    except Exception as e:
                        logger.error(f"[D205-5_RECORD] Error: {e}")
                
                await asyncio.sleep(self.sample_interval_sec)
        
        finally:
            recorder.close()
            
            # Manifest 저장 (git_sha 포함)
            recorder.save_manifest(self.symbols, time.time() - start_time)
            
            # KPI 저장
            self._save_record_kpi(tick_count, time.time() - start_time)
            
            logger.info(f"[D205-5_RECORD] Completed: {tick_count} ticks recorded")
            
            # 성공 조건 검증
            if tick_count == 0:
                logger.error("[D205-5_RECORD] FAIL: evaluated_ticks_total = 0")
                sys.exit(1)
    
    def _run_replay(self):
        """Replay 모드: 재실행 검증"""
        if not self.input_file:
            logger.error("[D205-5_REPLAY] Input file required for replay mode")
            sys.exit(1)
        
        if not self.input_file.exists():
            logger.error(f"[D205-5_REPLAY] Input file not found: {self.input_file}")
            sys.exit(1)
        
        logger.info(f"[D205-5_REPLAY] Starting replay... (input={self.input_file})")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        replay_runner = ReplayRunner(
            input_path=self.input_file,
            output_dir=self.output_dir,
            break_even_params=self.break_even_params,
            fx_krw_per_usdt=self.fx_krw_per_usdt,
        )
        
        result = replay_runner.run()
        
        logger.info(f"[D205-5_REPLAY] Result: {result}")
        
        if result["status"] == "FAIL":
            logger.error(f"[D205-5_REPLAY] FAIL: {result.get('reason', 'Unknown')}")
            sys.exit(1)
    
    def _save_record_kpi(self, tick_count: int, duration: float):
        """Record 모드 KPI 저장 (manifest는 recorder.save_manifest()로 이미 저장됨)"""
        kpi = {
            "mode": "record",
            "ticks_recorded": tick_count,
            "duration_sec": round(duration, 2),
            "ticks_per_sec": round(tick_count / duration, 2) if duration > 0 else 0,
        }
        
        with open(self.output_dir / "kpi.json", "w", encoding="utf-8") as f:
            json.dump(kpi, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="D205-5: Record/Replay SSOT")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["record", "replay"],
        help="Mode: record or replay",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/KRW"],
        help="Symbols to record (default: BTC/KRW)",
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
    
    args = parser.parse_args()
    
    # Logging setup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Run
    runner = RecordReplayRunner(
        mode=args.mode,
        symbols=args.symbols,
        duration_sec=args.duration_sec,
        sample_interval_sec=args.sample_interval_sec,
        output_dir=args.out_evidence_dir,
        input_file=args.input_file,
    )
    
    asyncio.run(runner.run())
    
    logger.info("[D205-5] Completed successfully")


if __name__ == "__main__":
    main()
