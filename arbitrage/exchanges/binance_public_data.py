"""
D77-0-RM + D82-1: Binance Public Data Client with Retry Logic

Features:
- Orderbook/depth fetch
- Ticker fetch
- Top symbols fetch by volume
- Rate limit (429) retry with exponential backoff
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

# D82-1: Rate Limit constants
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.5
DEFAULT_BACKOFF_MAX = 4.0


@dataclass
class BinanceTickerInfo:
    """Binance ticker info"""
    symbol: str
    last_price: float
    volume_24h: float
    quote_volume_24h: float
    price_change_percent: float


@dataclass
class BinanceOrderbookLevel:
    """Binance orderbook level"""
    price: float
    quantity: float


@dataclass
class BinanceOrderbookData:
    """Binance orderbook data"""
    symbol: str
    timestamp: float
    bids: List[BinanceOrderbookLevel]
    asks: List[BinanceOrderbookLevel]


class BinancePublicDataClient:
    """
    Binance Public Data Client (No Authentication Required)
    """
    
    BASE_URL = "https://api.binance.com/api/v3"
    
    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_max: float = DEFAULT_BACKOFF_MAX,
    ):
        """D82-1: Init with retry params"""
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.session = requests.Session()
        self.rate_limit_hits = 0
        logger.info("[BINANCE_PUBLIC] Client initialized")
    
    def _request_with_retry(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        operation_name: str = "request",
    ) -> Optional[requests.Response]:
        """D82-1: HTTP GET with 429 retry"""
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                
                if resp.status_code == 429:
                    self.rate_limit_hits += 1
                    if attempt < self.max_retries:
                        backoff_time = min(self.backoff_base * (2 ** attempt), self.backoff_max)
                        logger.warning(
                            f"[BINANCE_PUBLIC] Rate limit (429) for {operation_name}. "
                            f"Retry {attempt + 1}/{self.max_retries} after {backoff_time:.1f}s"
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        logger.error(f"[BINANCE_PUBLIC] Rate limit persists for {operation_name}")
                        return None
                
                return resp
            
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries:
                    backoff_time = min(self.backoff_base * (2 ** attempt), self.backoff_max)
                    logger.warning(
                        f"[BINANCE_PUBLIC] Request exception for {operation_name}: {e}. "
                        f"Retry {attempt + 1}/{self.max_retries} after {backoff_time:.1f}s"
                    )
                    time.sleep(backoff_time)
                else:
                    logger.error(f"[BINANCE_PUBLIC] Request failed for {operation_name}: {e}")
                    return None
        
        return None
    
    def fetch_ticker(self, symbol: str) -> Optional[BinanceTickerInfo]:
        """Fetch 24hr ticker"""
        try:
            url = f"{self.BASE_URL}/ticker/24hr"
            params = {"symbol": symbol}
            
            resp = self._request_with_retry(url, params, operation_name=f"fetch_ticker({symbol})")
            if resp is None:
                return None
            
            resp.raise_for_status()
            data = resp.json()
            
            return BinanceTickerInfo(
                symbol=symbol,
                last_price=float(data.get("lastPrice", 0.0)),
                volume_24h=float(data.get("volume", 0.0)),
                quote_volume_24h=float(data.get("quoteVolume", 0.0)),
                price_change_percent=float(data.get("priceChangePercent", 0.0)),
            )
        
        except Exception as e:
            logger.error(f"[BINANCE_PUBLIC] Failed to fetch ticker for {symbol}: {e}")
            return None
    
    def fetch_orderbook(self, symbol: str, limit: int = 20) -> Optional[BinanceOrderbookData]:
        """Fetch orderbook"""
        try:
            url = f"{self.BASE_URL}/depth"
            params = {"symbol": symbol, "limit": limit}
            
            resp = self._request_with_retry(url, params, operation_name=f"fetch_orderbook({symbol})")
            if resp is None:
                return None
            
            resp.raise_for_status()
            data = resp.json()
            
            bids = [
                BinanceOrderbookLevel(price=float(b[0]), quantity=float(b[1]))
                for b in data.get("bids", [])
            ]
            asks = [
                BinanceOrderbookLevel(price=float(a[0]), quantity=float(a[1]))
                for a in data.get("asks", [])
            ]
            
            return BinanceOrderbookData(
                symbol=symbol,
                timestamp=time.time(),
                bids=bids,
                asks=asks,
            )
        
        except Exception as e:
            logger.error(f"[BINANCE_PUBLIC] Failed to fetch orderbook for {symbol}: {e}")
            return None
    
    def fetch_top_symbols(
        self,
        quote_asset: str = "USDT",
        limit: int = 50,
        sort_by: str = "quoteVolume",
    ) -> List[str]:
        """Fetch top symbols by volume"""
        try:
            url = f"{self.BASE_URL}/ticker/24hr"
            resp = self._request_with_retry(url, operation_name="fetch_top_symbols")
            if resp is None:
                return []
            
            resp.raise_for_status()
            tickers = resp.json()
            
            filtered_tickers = [
                t for t in tickers
                if t["symbol"].endswith(quote_asset)
            ]
            
            if not filtered_tickers:
                logger.warning(f"[BINANCE_PUBLIC] No symbols found for quote asset {quote_asset}")
                return []
            
            sorted_tickers = sorted(
                filtered_tickers,
                key=lambda x: float(x.get(sort_by, 0.0)),
                reverse=True,
            )
            
            top_symbols = [t["symbol"] for t in sorted_tickers[:limit]]
            logger.info(f"[BINANCE_PUBLIC] Fetched Top{limit} {quote_asset} symbols")
            
            return top_symbols
        
        except Exception as e:
            logger.error(f"[BINANCE_PUBLIC] Failed to fetch top symbols: {e}")
            return []
    
    def close(self):
        """Close session"""
        self.session.close()
        logger.info("[BINANCE_PUBLIC] Client closed")
