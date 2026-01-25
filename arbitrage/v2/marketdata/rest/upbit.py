"""
D202-1: Upbit REST Provider

V2 계약:
- ticker/orderbook/trades 조회
- Rate limit 준수 (30 req/s)
- 에러 핸들링
"""

import logging
import requests
from typing import List, Optional
from datetime import datetime

from arbitrage.v2.marketdata.interfaces import (
    RestProvider,
    Ticker,
    Orderbook,
    OrderbookLevel,
    Trade,
)
from arbitrage.v2.marketdata.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class UpbitRestProvider(RestProvider):
    """
    Upbit REST API Provider
    
    API 문서: https://docs.upbit.com/reference
    Rate limit: 30 req/s (추정)
    """
    
    BASE_URL = "https://api.upbit.com/v1"
    
    def __init__(self, timeout: float = 5.0, rate_limiter: Optional[RateLimiter] = None):
        """
        Args:
            timeout: HTTP 요청 타임아웃 (초)
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.rate_limiter = rate_limiter
        self.last_error_status: Optional[int] = None
        self.last_error_reason: Optional[str] = None

    def _acquire_rate_limit(self) -> None:
        if self.rate_limiter:
            self.rate_limiter.acquire()

    def _set_last_error(self, status_code: Optional[int], reason: str) -> None:
        self.last_error_status = status_code
        self.last_error_reason = reason

    def _clear_last_error(self) -> None:
        self.last_error_status = None
        self.last_error_reason = None
    
    def get_ticker(self, symbol: str) -> Optional[Ticker]:
        """
        Ticker 조회 (D205-14-4: orderbook에서 best bid/ask 추출)
        
        Args:
            symbol: "BTC/KRW" 형식
        
        Returns:
            Ticker 또는 None (에러 시)
        """
        try:
            # D205-14-4/14-5: orderbook에서 실제 best bid/ask + size 가져오기
            orderbook = self.get_orderbook(symbol, depth=1)
            if not orderbook or not orderbook.bids or not orderbook.asks:
                if self.last_error_status == 429:
                    logger.info(f"[D205-14-5_UPBIT] Orderbook unavailable (429) for {symbol}")
                else:
                    logger.warning(f"[D205-14-5_UPBIT] Orderbook empty for {symbol}")
                return None
            
            best_bid = orderbook.bids[0].price
            best_ask = orderbook.asks[0].price
            best_bid_size = orderbook.bids[0].quantity  # D205-14-5: size 추가
            best_ask_size = orderbook.asks[0].quantity  # D205-14-5: size 추가
            
            # Volume은 ticker API로 가져오기 (orderbook에는 없음)
            base, quote = symbol.split("/")
            market = f"{quote}-{base}"
            
            url = f"{self.BASE_URL}/ticker"
            params = {"markets": market}
            
            self._acquire_rate_limit()
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            
            data = resp.json()[0]
            self._clear_last_error()
            
            return Ticker(
                exchange="upbit",
                symbol=symbol,
                timestamp=datetime.now(),
                bid=best_bid,
                ask=best_ask,
                last=float(data.get("trade_price", 0)),
                volume=float(data.get("acc_trade_volume_24h", 0)),
                bid_size=best_bid_size,  # D205-14-5
                ask_size=best_ask_size,  # D205-14-5
            )
        
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, "status_code", None)
            self._set_last_error(status_code, "ticker")
            if status_code == 429:
                logger.info("[D205-14-4_UPBIT] Ticker rate limited (429)")
                return None
            logger.error(f"[D205-14-4_UPBIT] Ticker error: {e}", exc_info=True)
            return None
        except Exception as e:
            self._set_last_error(None, "ticker")
            logger.error(f"[D205-14-4_UPBIT] Ticker error: {e}", exc_info=True)
            return None
    
    def get_orderbook(self, symbol: str, depth: int = 20) -> Optional[Orderbook]:
        """
        Orderbook 조회 (L2)
        
        Args:
            symbol: "BTC/KRW" 형식
            depth: 호가 깊이 (기본값: 20)
        
        Returns:
            Orderbook 또는 None (에러 시)
        """
        try:
            # BTC/KRW → KRW-BTC (Upbit 마켓 코드 형식)
            base, quote = symbol.split("/")
            market = f"{quote}-{base}"
            
            url = f"{self.BASE_URL}/orderbook"
            params = {"markets": market}

            self._acquire_rate_limit()
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            
            data = resp.json()[0]
            
            bids = [
                OrderbookLevel(
                    price=float(item["bid_price"]),
                    quantity=float(item["bid_size"]),
                )
                for item in data["orderbook_units"][:depth]
            ]
            
            asks = [
                OrderbookLevel(
                    price=float(item["ask_price"]),
                    quantity=float(item["ask_size"]),
                )
                for item in data["orderbook_units"][:depth]
            ]
            
            return Orderbook(
                exchange="upbit",
                symbol=symbol,
                timestamp=datetime.now(),
                bids=bids,
                asks=asks,
            )
        
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, "status_code", None)
            self._set_last_error(status_code, "orderbook")
            if status_code == 429:
                logger.info("[D202-1_UPBIT_REST] Orderbook rate limited (429)")
                return None
            logger.error(f"[D202-1_UPBIT_REST] Orderbook error: {e}", exc_info=True)
            return None
        except Exception as e:
            self._set_last_error(None, "orderbook")
            logger.error(f"[D202-1_UPBIT_REST] Orderbook error: {e}", exc_info=True)
            return None
    
    def get_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """
        최근 체결 조회
        
        Args:
            symbol: "BTC/KRW" 형식
            limit: 최대 개수 (기본값: 100)
        
        Returns:
            Trade 리스트
        """
        try:
            # BTC/KRW → KRW-BTC
            market = symbol.replace("/", "-")
            
            url = f"{self.BASE_URL}/trades/ticks"
            params = {"market": market, "count": min(limit, 500)}

            self._acquire_rate_limit()
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            
            data = resp.json()
            self._clear_last_error()
            
            return [
                Trade(
                    exchange="upbit",
                    symbol=symbol,
                    timestamp=datetime.fromisoformat(item["trade_date_utc"] + "T" + item["trade_time_utc"]),
                    price=float(item["trade_price"]),
                    quantity=float(item["trade_volume"]),
                    side="buy" if item["ask_bid"] == "BID" else "sell",
                )
                for item in data[:limit]
            ]
        
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, "status_code", None)
            self._set_last_error(status_code, "trades")
            if status_code == 429:
                logger.info("[D202-1_UPBIT_REST] Trades rate limited (429)")
                return []
            logger.error(f"[D202-1_UPBIT_REST] Trades error: {e}", exc_info=True)
            return []
        except Exception as e:
            self._set_last_error(None, "trades")
            logger.error(f"[D202-1_UPBIT_REST] Trades error: {e}", exc_info=True)
            return []
