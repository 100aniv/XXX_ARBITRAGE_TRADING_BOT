# -*- coding: utf-8 -*-
"""
D77-0-RM: Upbit Public Data Client

API key 없이 public endpoints만 사용하여 시세 정보를 조회하는 클라이언트.
PAPER 모드 Real Market Validation용.

Features:
- 호가 조회 (orderbook)
- 티커 조회 (ticker)
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
class TickerInfo:
    """티커 정보"""
    symbol: str  # "KRW-BTC"
    trade_price: float  # 현재가
    trade_volume_24h: float  # 24시간 거래량
    acc_trade_volume_24h: float  # 24시간 누적 거래량
    acc_trade_price_24h: float  # 24시간 누적 거래대금 (KRW)
    change_rate: float  # 전일 대비 변화율


@dataclass
class OrderbookLevel:
    """호가 레벨"""
    price: float
    size: float  # 수량


@dataclass
class OrderbookData:
    """호가 데이터"""
    symbol: str
    timestamp: float
    bids: List[OrderbookLevel]  # 매수 호가 (높은 가격순)
    asks: List[OrderbookLevel]  # 매도 호가 (낮은 가격순)


class UpbitPublicDataClient:
    """
    Upbit Public Data Client (No Authentication)
    
    Public endpoints만 사용하여 시세 데이터를 조회한다.
    주문 전송 기능은 없음 (PAPER 모드용).
    """
    
    BASE_URL = "https://api.upbit.com/v1"
    
    def __init__(self, timeout: int = 10):
        """
        Args:
            timeout: HTTP 요청 타임아웃 (초)
        """
        self.timeout = timeout
        self.session = requests.Session()
        logger.info("[UPBIT_PUBLIC] Client initialized (public endpoints only)")
    
    def fetch_ticker(self, symbol: str) -> Optional[TickerInfo]:
        """
        현재가(티커) 정보 조회
        
        Args:
            symbol: 거래 쌍 (예: "KRW-BTC")
        
        Returns:
            TickerInfo 또는 None (오류 시)
        """
        try:
            url = f"{self.BASE_URL}/ticker"
            params = {"markets": symbol}
            
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            
            data = resp.json()
            if not data or len(data) == 0:
                logger.warning(f"[UPBIT_PUBLIC] No ticker data for {symbol}")
                return None
            
            item = data[0]
            return TickerInfo(
                symbol=symbol,
                trade_price=item.get("trade_price", 0.0),
                trade_volume_24h=item.get("trade_volume", 0.0),
                acc_trade_volume_24h=item.get("acc_trade_volume_24h", 0.0),
                acc_trade_price_24h=item.get("acc_trade_price_24h", 0.0),
                change_rate=item.get("signed_change_rate", 0.0),
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[UPBIT_PUBLIC] Failed to fetch ticker for {symbol}: {e}")
            return None
    
    def fetch_orderbook(self, symbol: str) -> Optional[OrderbookData]:
        """
        호가 정보 조회
        
        Args:
            symbol: 거래 쌍 (예: "KRW-BTC")
        
        Returns:
            OrderbookData 또는 None (오류 시)
        """
        try:
            url = f"{self.BASE_URL}/orderbook"
            params = {"markets": symbol}
            
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            
            data = resp.json()
            if not data or len(data) == 0:
                logger.warning(f"[UPBIT_PUBLIC] No orderbook data for {symbol}")
                return None
            
            item = data[0]
            orderbook_units = item.get("orderbook_units", [])
            
            bids = []
            asks = []
            for unit in orderbook_units:
                # Upbit: bid_price/ask_price, bid_size/ask_size
                bids.append(OrderbookLevel(
                    price=unit.get("bid_price", 0.0),
                    size=unit.get("bid_size", 0.0),
                ))
                asks.append(OrderbookLevel(
                    price=unit.get("ask_price", 0.0),
                    size=unit.get("ask_size", 0.0),
                ))
            
            # Upbit는 이미 정렬되어 옴 (bids: 높은 가격순, asks: 낮은 가격순)
            return OrderbookData(
                symbol=symbol,
                timestamp=item.get("timestamp", time.time() * 1000) / 1000.0,
                bids=bids,
                asks=asks,
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[UPBIT_PUBLIC] Failed to fetch orderbook for {symbol}: {e}")
            return None
    
    def fetch_top_symbols(
        self,
        market: str = "KRW",
        limit: int = 50,
        sort_by: str = "acc_trade_price_24h",
    ) -> List[str]:
        """
        거래량 기준 상위 심볼 조회
        
        Args:
            market: 마켓 (예: "KRW")
            limit: 개수
            sort_by: 정렬 기준 ("acc_trade_price_24h": 거래대금, "trade_volume": 거래량)
        
        Returns:
            심볼 리스트 (예: ["KRW-BTC", "KRW-ETH", ...])
        """
        try:
            # 1. Get all market codes
            url = f"{self.BASE_URL}/market/all"
            resp = self.session.get(url, params={"isDetails": "false"}, timeout=self.timeout)
            resp.raise_for_status()
            
            markets = resp.json()
            # Filter by market (e.g., "KRW-*")
            symbols = [m["market"] for m in markets if m["market"].startswith(f"{market}-")]
            
            if not symbols:
                logger.warning(f"[UPBIT_PUBLIC] No symbols found for market {market}")
                return []
            
            # 2. Get tickers for all symbols
            ticker_url = f"{self.BASE_URL}/ticker"
            ticker_params = {"markets": ",".join(symbols)}
            ticker_resp = self.session.get(ticker_url, params=ticker_params, timeout=self.timeout)
            ticker_resp.raise_for_status()
            
            tickers = ticker_resp.json()
            
            # 3. Sort by specified field
            sorted_tickers = sorted(
                tickers,
                key=lambda x: x.get(sort_by, 0.0),
                reverse=True,
            )
            
            # 4. Return top N
            top_symbols = [t["market"] for t in sorted_tickers[:limit]]
            logger.info(f"[UPBIT_PUBLIC] Fetched Top{limit} symbols: {top_symbols[:5]}...")
            
            return top_symbols
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[UPBIT_PUBLIC] Failed to fetch top symbols: {e}")
            return []
    
    def close(self):
        """세션 종료"""
        self.session.close()
        logger.info("[UPBIT_PUBLIC] Client closed")
