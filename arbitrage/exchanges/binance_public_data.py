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
    
    def __init__(self, timeout: int = 10):
        """
        Args:
            timeout: HTTP 요청 타임아웃 (초)
        """
        self.timeout = timeout
        self.session = requests.Session()
        logger.info("[BINANCE_PUBLIC] Client initialized (public endpoints only)")
    
    def fetch_ticker(self, symbol: str) -> Optional[BinanceTickerInfo]:
        """
        24시간 티커 정보 조회
        
        Args:
            symbol: 거래 쌍 (예: "BTCUSDT")
        
        Returns:
            BinanceTickerInfo 또는 None (오류 시)
        """
        try:
            url = f"{self.BASE_URL}/ticker/24hr"
            params = {"symbol": symbol}
            
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            
            data = resp.json()
            
            return BinanceTickerInfo(
                symbol=symbol,
                last_price=float(data.get("lastPrice", 0.0)),
                volume_24h=float(data.get("volume", 0.0)),
                quote_volume_24h=float(data.get("quoteVolume", 0.0)),
                price_change_percent=float(data.get("priceChangePercent", 0.0)),
            )
        
        except requests.exceptions.RequestException as e:
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
        """
        try:
            url = f"{self.BASE_URL}/depth"
            params = {"symbol": symbol, "limit": limit}
            
            resp = self.session.get(url, params=params, timeout=self.timeout)
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
        
        except requests.exceptions.RequestException as e:
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
            # Get all 24hr tickers
            url = f"{self.BASE_URL}/ticker/24hr"
            resp = self.session.get(url, timeout=self.timeout)
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
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[BINANCE_PUBLIC] Failed to fetch top symbols: {e}")
            return []
    
    def close(self):
        """세션 종료"""
        self.session.close()
        logger.info("[BINANCE_PUBLIC] Client closed")
