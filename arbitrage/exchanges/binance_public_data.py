# -*- coding: utf-8 -*-
"""
D77-0-RM: Binance Public Data Client

API key 없이 public endpoints만 사용하여 시세 정보를 조회하는 클라이언트.
PAPER 모드 Real Market Validation용.

Features:
- 호가 조회 (orderbook/depth)
- 티커 조회 (ticker/24hr)
- Top symbols 조회 (거래량 기준)
- No authentication required
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

# D82-1: Rate Limit 관련 상수
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.5  # 초기 백오프 시간 (초)
DEFAULT_BACKOFF_MAX = 4.0  # 최대 백오프 시간 (초)


@dataclass
class BinanceTickerInfo:
    """Binance 티커 정보"""
    symbol: str  # "BTCUSDT"
    last_price: float  # 현재가
    volume_24h: float  # 24시간 거래량 (base asset)
    quote_volume_24h: float  # 24시간 거래대금 (quote asset)
    price_change_percent: float  # 24시간 가격 변동률 (%)


@dataclass
class BinanceOrderbookLevel:
    """Binance 호가 레벨"""
    price: float
    quantity: float


@dataclass
class BinanceOrderbookData:
    """Binance 호가 데이터"""
    symbol: str
    timestamp: float
    bids: List[BinanceOrderbookLevel]  # 매수 호가
    asks: List[BinanceOrderbookLevel]  # 매도 호가


class BinancePublicDataClient:
    """
    Binance Public Data Client (No Authentication)
    
    Public endpoints만 사용하여 시세 데이터를 조회한다.
    주문 전송 기능은 없음 (PAPER 모드용).
    """
    
    BASE_URL = "https://api.binance.com/api/v3"
    
    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_max: float = DEFAULT_BACKOFF_MAX,
    ):
        """
        Args:
            timeout: HTTP 요청 타임아웃 (초)
            max_retries: 429 에러 발생 시 최대 재시도 횟수 (D82-1)
            backoff_base: 초기 백오프 시간 (초) (D82-1)
            backoff_max: 최대 백오프 시간 (초) (D82-1)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.session = requests.Session()
        self.rate_limit_hits = 0  # D82-1: Rate limit 히트 횟수 (메트릭용)
        logger.info("[BINANCE_PUBLIC] Client initialized (public endpoints only)")
    
    def _request_with_retry(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        operation_name: str = "request",
    ) -> Optional[requests.Response]:
        """
        D82-1: Rate limit (429) 핸들링이 포함된 HTTP GET 요청.
        
        Args:
            url: 요청 URL
            params: 쿼리 파라미터
            operation_name: 작업 이름 (로깅용)
        
        Returns:
            requests.Response 또는 None (실패 시)
        """
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                
                # 429 (Too Many Requests) 체크
                if resp.status_code == 429:
                    self.rate_limit_hits += 1
                    
                    if attempt < self.max_retries:
                        # Exponential backoff: 0.5s -> 1s -> 2s (최대 4s)
                        backoff_time = min(self.backoff_base * (2 ** attempt), self.backoff_max)
                        logger.warning(
                            f"[BINANCE_PUBLIC] Rate limit (429) hit for {operation_name}. "
                            f"Retry {attempt + 1}/{self.max_retries} after {backoff_time:.1f}s"
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        logger.error(
                            f"[BINANCE_PUBLIC] Rate limit (429) persists after {self.max_retries} retries for {operation_name}. "
                            "Giving up."
                        )
                        return None
                
                # 성공 또는 다른 에러 코드
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
                    logger.error(
                        f"[BINANCE_PUBLIC] Request failed after {self.max_retries} retries for {operation_name}: {e}"
                    )
                    return None
        
        return None
    
    def fetch_ticker(self, symbol: str) -> Optional[BinanceTickerInfo]:
        """
        24시간 티커 정보 조회
        
        Args:
            symbol: 거래 쌍 (예: "BTCUSDT")
        
        Returns:
            BinanceTickerInfo 또는 None (오류 시)
        
        Note:
            D82-1: Rate limit (429) handling with retry.
        """
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
        """
        호가 정보 조회
        
        Args:
            symbol: 거래 쌍 (예: "BTCUSDT")
            limit: 호가 깊이 (5, 10, 20, 50, 100, 500, 1000, 5000)
        
        Returns:
            BinanceOrderbookData 또는 None (오류 시)
        
        Note:
            D82-1: Rate limit (429) handling with retry.
        """
        try:
            url = f"{self.BASE_URL}/depth"
            params = {"symbol": symbol, "limit": limit}
            
            resp = self._request_with_retry(url, params, operation_name=f"fetch_orderbook({symbol})")
            if resp is None:
                return None
            
            resp.raise_for_status()
            
            data = resp.json()
            
            # Binance: bids/asks are [price, quantity] arrays
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
                bids=bids,  # Already sorted (highest first)
                asks=asks,  # Already sorted (lowest first)
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
        """
        거래량 기준 상위 심볼 조회
        
        Args:
            quote_asset: Quote asset (예: "USDT", "BTC")
            limit: 개수
            sort_by: 정렬 기준 ("quoteVolume": 거래대금, "volume": 거래량)
        
        Returns:
            심볼 리스트 (예: ["BTCUSDT", "ETHUSDT", ...])
        """
        try:
            # D82-1: Get all 24hr tickers with retry logic
            url = f"{self.BASE_URL}/ticker/24hr"
            resp = self._request_with_retry(url, operation_name="fetch_top_symbols")
            if resp is None:
                return []
            
            resp.raise_for_status()
            
            tickers = resp.json()
            
            # Filter by quote asset
            filtered_tickers = [
                t for t in tickers
                if t["symbol"].endswith(quote_asset)
            ]
            
            if not filtered_tickers:
                logger.warning(f"[BINANCE_PUBLIC] No symbols found for quote asset {quote_asset}")
                return []
            
            # Sort by specified field
            sorted_tickers = sorted(
                filtered_tickers,
                key=lambda x: float(x.get(sort_by, 0.0)),
                reverse=True,
            )
            
            # Return top N
            top_symbols = [t["symbol"] for t in sorted_tickers[:limit]]
            logger.info(f"[BINANCE_PUBLIC] Fetched Top{limit} {quote_asset} symbols: {top_symbols[:5]}...")
            
            return top_symbols
        
        except Exception as e:
            logger.error(f"[BINANCE_PUBLIC] Failed to fetch top symbols: {e}")
            return []
    
    def close(self):
        """세션 종료"""
        self.session.close()
        logger.info("[BINANCE_PUBLIC] Client closed")
                           