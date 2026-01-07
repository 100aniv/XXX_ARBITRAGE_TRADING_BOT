"""
D205-15: Multi-Symbol Scanner

멀티심볼 시장 데이터 수집기
- FX 정규화 (Binance USDT → KRW 변환)
- bid_size/ask_size 필드 포함
- size 누락 시 skip_reason 기록
"""

import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider
from arbitrage.v2.replay.recorder import MarketRecorder
from arbitrage.v2.replay.schemas import MarketTick

logger = logging.getLogger(__name__)


@dataclass
class ScanConfig:
    """스캔 설정"""
    fx_krw_per_usdt: float
    upbit_fee_bps: float
    binance_fee_bps: float
    slippage_bps: float
    fx_conversion_bps: float
    buffer_bps: float = 0.0


SYMBOL_UNIVERSE = [
    "BTC/KRW", "ETH/KRW", "XRP/KRW", "SOL/KRW",
    "ADA/KRW", "DOT/KRW", "MATIC/KRW", "AVAX/KRW",
    "LINK/KRW", "UNI/KRW", "ATOM/KRW", "DOGE/KRW",
]

BINANCE_SYMBOL_MAP = {
    "BTC/KRW": "BTC/USDT", "ETH/KRW": "ETH/USDT",
    "XRP/KRW": "XRP/USDT", "SOL/KRW": "SOL/USDT",
    "ADA/KRW": "ADA/USDT", "DOT/KRW": "DOT/USDT",
    "MATIC/KRW": "MATIC/USDT", "AVAX/KRW": "AVAX/USDT",
    "LINK/KRW": "LINK/USDT", "UNI/KRW": "UNI/USDT",
    "ATOM/KRW": "ATOM/USDT", "DOGE/KRW": "DOGE/USDT",
}


class MultiSymbolScanner:
    """
    Multi-Symbol Scanner (D205-15)
    
    FX 정규화 및 size 필드 포함 시장 데이터 수집
    
    Args:
        scan_config: ScanConfig (FX rate, fees 등)
        output_dir: 출력 디렉토리
    """
    
    def __init__(self, scan_config: ScanConfig, output_dir: Path):
        self.scan_config = scan_config
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.upbit = UpbitRestProvider()
        self.binance = BinanceRestProvider(market_type="futures")
        
        logger.info(
            f"[D205-15_SCANNER] Initialized: "
            f"fx_rate={scan_config.fx_krw_per_usdt}, "
            f"fees={scan_config.upbit_fee_bps}+{scan_config.binance_fee_bps}bps"
        )
    
    def record_symbol(
        self,
        symbol: str,
        duration_seconds: int,
        polling_interval: float = 1.0,
    ) -> Dict[str, Any]:
        """
        단일 심볼 Recording (D205-15 Fix-1/Fix-2 적용)
        
        Args:
            symbol: Upbit 심볼 (예: BTC/KRW)
            duration_seconds: 기록 시간 (초)
            polling_interval: 폴링 주기 (초)
        
        Returns:
            Recording 결과 딕셔너리
        """
        binance_symbol = BINANCE_SYMBOL_MAP.get(symbol)
        if not binance_symbol:
            logger.warning(f"[D205-15_SCANNER] No Binance mapping for {symbol}")
            return {
                "symbol": symbol,
                "status": "skipped",
                "skip_reason": "no_binance_mapping",
            }
        
        symbol_safe = symbol.replace("/", "_")
        symbol_dir = self.output_dir / symbol_safe
        symbol_dir.mkdir(parents=True, exist_ok=True)
        
        market_file = symbol_dir / "market.ndjson"
        recorder = MarketRecorder(output_path=market_file)
        
        logger.info(f"[D205-15_SCANNER] Recording {symbol} → {binance_symbol} for {duration_seconds}s")
        
        start_time = time.time()
        tick_count = 0
        error_count = 0
        skip_count = 0
        skip_reasons: Dict[str, int] = {}
        
        while time.time() - start_time < duration_seconds:
            try:
                upbit_ticker = self.upbit.get_ticker(symbol)
                binance_ticker = self.binance.get_ticker(binance_symbol)
                
                if not upbit_ticker or not binance_ticker:
                    error_count += 1
                    logger.warning(f"[D205-15_SCANNER] Failed to fetch ticker for {symbol}")
                    time.sleep(polling_interval)
                    continue
                
                # Fix-2: Check for size fields
                has_upbit_size = (
                    upbit_ticker.bid_size is not None and upbit_ticker.bid_size > 0 and
                    upbit_ticker.ask_size is not None and upbit_ticker.ask_size > 0
                )
                has_binance_size = (
                    binance_ticker.bid_size is not None and binance_ticker.bid_size > 0 and
                    binance_ticker.ask_size is not None and binance_ticker.ask_size > 0
                )
                
                if not has_upbit_size:
                    skip_count += 1
                    reason = "upbit_size_missing"
                    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                    time.sleep(polling_interval)
                    continue
                
                if not has_binance_size:
                    skip_count += 1
                    reason = "binance_size_missing"
                    skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                    time.sleep(polling_interval)
                    continue
                
                # Fix-1: FX Normalization - Binance USDT → KRW
                binance_bid_krw = binance_ticker.bid * self.scan_config.fx_krw_per_usdt
                binance_ask_krw = binance_ticker.ask * self.scan_config.fx_krw_per_usdt
                
                # Create MarketTick with proper schema fields
                tick = MarketTick(
                    timestamp=datetime.now().isoformat(),
                    symbol=symbol,
                    upbit_bid=upbit_ticker.bid,
                    upbit_ask=upbit_ticker.ask,
                    binance_bid=binance_bid_krw,  # FX normalized to KRW
                    binance_ask=binance_ask_krw,  # FX normalized to KRW
                    upbit_bid_size=upbit_ticker.bid_size,
                    upbit_ask_size=upbit_ticker.ask_size,
                    binance_bid_size=binance_ticker.bid_size,
                    binance_ask_size=binance_ticker.ask_size,
                    upbit_quote="KRW",
                    binance_quote="KRW",  # Already converted to KRW
                )
                
                recorder.record_tick(tick)
                tick_count += 1
                
            except Exception as e:
                error_count += 1
                logger.error(f"[D205-15_SCANNER] Error recording {symbol}: {e}")
            
            time.sleep(polling_interval)
        
        elapsed = time.time() - start_time
        recorder.save_manifest(symbols=[symbol], duration_sec=elapsed)
        recorder.close()
        
        logger.info(
            f"[D205-15_SCANNER] Recorded {symbol}: "
            f"{tick_count} ticks, {skip_count} skipped, {error_count} errors"
        )
        
        return {
            "symbol": symbol,
            "binance_symbol": binance_symbol,
            "status": "completed",
            "tick_count": tick_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "skip_reasons": skip_reasons,
            "duration_seconds": elapsed,
            "market_file": str(market_file.relative_to(self.output_dir.parent)),
            "fx_krw_per_usdt": self.scan_config.fx_krw_per_usdt,
        }
    
    def scan_all(
        self,
        symbols: Optional[List[str]] = None,
        duration_seconds: int = 600,
        polling_interval: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        전체 심볼 스캔
        
        Args:
            symbols: 스캔할 심볼 리스트 (None이면 전체)
            duration_seconds: 심볼당 기록 시간 (초)
            polling_interval: 폴링 주기 (초)
        
        Returns:
            Recording 결과 리스트
        """
        target_symbols = symbols or SYMBOL_UNIVERSE
        results = []
        
        for symbol in target_symbols:
            result = self.record_symbol(
                symbol=symbol,
                duration_seconds=duration_seconds,
                polling_interval=polling_interval,
            )
            results.append(result)
        
        return results
