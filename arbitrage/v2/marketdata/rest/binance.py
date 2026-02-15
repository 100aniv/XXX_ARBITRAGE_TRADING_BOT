"""
D202-1: Binance REST Provider

V2 계약:
- ticker/orderbook/trades 조회
- Rate limit 준수 (1200 req/min = 20 req/s)
- 에러 핸들링
"""

import logging
import requests
from typing import List, Optional
from datetime import datetime

from arbitrage.v2.core.tick_context import (
    record_rest_call,
    is_rest_forbidden_in_tick,
    RestCallInTickError,
)
from arbitrage.v2.marketdata.interfaces import (
    RestProvider,
    Ticker,
    Orderbook,
    OrderbookLevel,
    Trade,
)
from arbitrage.v2.marketdata.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class BinanceRestProvider(RestProvider):
    """
    Binance REST API Provider
    
    V2 기본: Futures (USDT-M) API
    Control-only: Spot API (파이프라인 검증용)
    
    API 문서:
    - Futures: https://binance-docs.github.io/apidocs/futures/en/
    - Spot: https://binance-docs.github.io/apidocs/spot/en/
    Rate limit: 1200 req/min (= 20 req/s)
    
    네이밍 규칙 (D205-15):
    - 프로젝트 시즌: v1/v2 (예: arbitrage/v2/, V2 기본)
    - Binance API Release Channel: R1/R3 (예: /fapi/v1=R1, /api/v3=R3)
    - 혼동 방지: "V2"는 우리 프로젝트 시즌, "R1/R3"는 Binance API 버전
    """
    
    def __init__(
        self,
        market_type: str = "futures",
        timeout: float = 5.0,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        """
        Args:
            market_type: "spot" or "futures" (default: "futures")
            timeout: HTTP 요청 타임아웃 (초)
        """
        if market_type == "futures":
            self.base_url = "https://fapi.binance.com/fapi/v1"
        elif market_type == "spot":
            self.base_url = "https://api.binance.com/api/v3"
        else:
            raise ValueError(f"Invalid market_type: {market_type}")
        
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
        Ticker 조회
        
        Args:
            symbol: "BTC/USDT" 형식
        
        Returns:
            Ticker 또는 None (에러 시)
        """
        try:
            record_rest_call()
            if is_rest_forbidden_in_tick():
                raise RestCallInTickError(f"REST ticker called in tick: symbol={symbol}")
            # BTC/USDT → BTCUSDT
            market = symbol.replace("/", "")
            
            url = f"{self.base_url}/ticker/bookTicker"
            params = {"symbol": market}
            
            self._acquire_rate_limit()
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            
            data = resp.json()
            self._clear_last_error()
            
            return Ticker(
                exchange="binance",
                symbol=symbol,
                timestamp=datetime.now(),
                bid=float(data["bidPrice"]),
                ask=float(data["askPrice"]),
                last=float(data["bidPrice"]),  # bookTicker는 last 없음
                volume=0.0,  # bookTicker는 volume 없음
                bid_size=float(data["bidQty"]),  # D205-14-5
                ask_size=float(data["askQty"]),  # D205-14-5
            )
        
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, "status_code", None)
            self._set_last_error(status_code, "ticker")
            if status_code == 429:
                logger.info("[D202-1_BINANCE_REST] Ticker rate limited (429)")
                return None
            logger.error(f"[D202-1_BINANCE_REST] Ticker error: {e}", exc_info=True)
            return None
        except Exception as e:
            self._set_last_error(None, "ticker")
            logger.error(f"[D202-1_BINANCE_REST] Ticker error: {e}", exc_info=True)
            return None
    
    def get_orderbook(self, symbol: str, depth: int = 20) -> Optional[Orderbook]:
        """
        Orderbook 조회 (L2)
        
        Args:
            symbol: "BTC/USDT" 형식
            depth: 호가 깊이 (기본값: 20)
        
        Returns:
            Orderbook 또는 None (에러 시)
        """
        try:
            record_rest_call()
            if is_rest_forbidden_in_tick():
                raise RestCallInTickError(f"REST orderbook called in tick: symbol={symbol}")
            # BTC/USDT → BTCUSDT
            market = symbol.replace("/", "")
            
            url = f"{self.base_url}/depth"
            params = {"symbol": market, "limit": depth}

            self._acquire_rate_limit()
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()

            data = resp.json()
            self._clear_last_error()
            
            bids = [
                OrderbookLevel(
                    price=float(item[0]),
                    quantity=float(item[1]),
                )
                for item in data["bids"][:depth]
            ]
            
            asks = [
                OrderbookLevel(
                    price=float(item[0]),
                    quantity=float(item[1]),
                )
                for item in data["asks"][:depth]
            ]
            
            return Orderbook(
                exchange="binance",
                symbol=symbol,
                timestamp=datetime.now(),
                bids=bids,
                asks=asks,
            )
        
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, "status_code", None)
            self._set_last_error(status_code, "orderbook")
            if status_code == 429:
                logger.info("[D202-1_BINANCE_REST] Orderbook rate limited (429)")
                return None
            logger.error(f"[D202-1_BINANCE_REST] Orderbook error: {e}", exc_info=True)
            return None
        except Exception as e:
            self._set_last_error(None, "orderbook")
            logger.error(f"[D202-1_BINANCE_REST] Orderbook error: {e}")
            return None
    
    def get_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """
        최근 체결 조회
        
        Args:
            symbol: "BTC/USDT" 형식
            limit: 최대 개수 (기본값: 100)
        
        Returns:
            Trade 리스트
        """
        try:
            record_rest_call()
            if is_rest_forbidden_in_tick():
                raise RestCallInTickError(f"REST trades called in tick: symbol={symbol}")
            # BTC/USDT → BTCUSDT
            market = symbol.replace("/", "")
            
            url = f"{self.base_url}/trades"
            params = {"symbol": market, "limit": min(limit, 1000)}

            self._acquire_rate_limit()
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()

            data = resp.json()
            self._clear_last_error()
            
            return [
                Trade(
                    exchange="binance",
                    symbol=symbol,
                    timestamp=datetime.fromtimestamp(item["time"] / 1000.0),
                    price=float(item["price"]),
                    quantity=float(item["qty"]),
                    side="sell" if item["isBuyerMaker"] else "buy",  # isBuyerMaker=True → sell (buyer=maker, seller=taker)
                )
                for item in data[:limit]
            ]
        
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, "status_code", None)
            self._set_last_error(status_code, "trades")
            if status_code == 429:
                logger.info("[D202-1_BINANCE_REST] Trades rate limited (429)")
                return []
            logger.error(f"[D202-1_BINANCE_REST] Trades error: {e}", exc_info=True)
            return []
        except Exception as e:
            self._set_last_error(None, "trades")
            logger.error(f"[D202-1_BINANCE_REST] Trades error: {e}")
            return []
