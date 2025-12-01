# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Layer - Binance Futures Exchange

Binance USDT-M Futures REST API를 통한 선물 거래 어댑터.

D46: Read-Only 모드 추가
- get_orderbook: 실제 Binance API 호출
- get_balance: 실제 Binance API 호출
- create_order/cancel_order: live_enabled=True일 때만 실행
"""

import logging
import time
import os
from typing import Dict, List, Optional, Any
import requests
import hmac
import hashlib
import json
from urllib.parse import urlencode

from arbitrage.exchanges.base import (
    BaseExchange,
    OrderSide,
    OrderType,
    TimeInForce,
    OrderStatus,
    OrderResult,
    Balance,
    Position,
    PositionSide,
    OrderBookSnapshot,
)
from arbitrage.common.currency import Currency
from arbitrage.exchanges.exceptions import (
    NetworkError,
    AuthenticationError,
    InsufficientBalanceError,
    OrderNotFoundError,
)
from arbitrage.exchanges.http_client import HTTPClient, RateLimitConfig

logger = logging.getLogger(__name__)


class BinanceFuturesExchange(BaseExchange):
    """
    Binance USDT-M Futures 거래 어댑터.
    
    Binance Futures REST API를 사용하여 선물 거래를 수행.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 설정 dict
                - api_key: Binance API 키
                - api_secret: Binance API 시크릿
                - base_url: API 엔드포인트 (기본: https://fapi.binance.com)
                - timeout: 요청 타임아웃 (초)
                - leverage: 레버리지 (기본: 1)
                - rate_limit: RateLimitConfig dict (D48)
        """
        super().__init__("binance_futures", config)
        
        self.api_key = self.config.get("api_key", "")
        self.api_secret = self.config.get("api_secret", "")
        self.base_url = self.config.get("base_url", "https://fapi.binance.com")
        self.timeout = self.config.get("timeout", 10)
        self.leverage = self.config.get("leverage", 1)
        
        # 실제 거래 활성화 여부
        self.live_enabled = self.config.get("live_enabled", False)
        
        # D48: HTTP 클라이언트 (레이트리밋/재시도)
        rate_limit_config = self.config.get("rate_limit", {})
        if isinstance(rate_limit_config, dict):
            self.http_client = HTTPClient(
                RateLimitConfig(
                    max_requests_per_sec=rate_limit_config.get("max_requests_per_sec", 5.0),
                    max_retry=rate_limit_config.get("max_retry", 3),
                    base_backoff_seconds=rate_limit_config.get("base_backoff_seconds", 0.5),
                )
            )
        else:
            self.http_client = HTTPClient()
        
        if not self.live_enabled:
            logger.warning("[D42_BINANCE] Live trading is DISABLED. Use Paper mode or enable live_enabled=True")
        
        logger.info(
            f"[D42_BINANCE] BinanceFuturesExchange initialized: "
            f"base_url={self.base_url}, leverage={self.leverage}, base_currency={self.base_currency.value}"
        )
    
    def _infer_base_currency(self) -> Currency:
        """
        D80-2: Binance Futures는 USDT 마켓
        
        Returns:
            Currency.USDT
        """
        return self.config.get("base_currency", Currency.USDT)
    
    def get_orderbook(self, symbol: str) -> OrderBookSnapshot:
        """
        호가 정보 조회 (D46: 실제 API 호출).
        
        Args:
            symbol: 거래 쌍 (예: "BTCUSDT")
        
        Returns:
            OrderBookSnapshot
        
        Raises:
            NetworkError: API 호출 실패
        """
        logger.debug(f"[D46_BINANCE] Getting orderbook for {symbol}")
        
        try:
            url = f"{self.base_url}/fapi/v1/depth"
            params = {"symbol": symbol, "limit": 5}
            
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Binance API 응답 파싱
            # {
            #   "bids": [["40000", "1.0"], ["39999", "2.0"], ...],
            #   "asks": [["40100", "1.0"], ["40101", "2.0"], ...],
            #   "E": 1234567890000,
            #   "T": 1234567890000
            # }
            
            bids = []
            asks = []
            
            for bid in data.get("bids", []):
                price = float(bid[0])
                size = float(bid[1])
                if price > 0 and size > 0:
                    bids.append((price, size))
            
            for ask in data.get("asks", []):
                price = float(ask[0])
                size = float(ask[1])
                if price > 0 and size > 0:
                    asks.append((price, size))
            
            # 최상단 호가만 유지
            bids = sorted(bids, key=lambda x: x[0], reverse=True)[:1]
            asks = sorted(asks, key=lambda x: x[0])[:1]
            
            # 타임스탐프 (밀리초 → 초)
            timestamp = data.get("E", int(time.time() * 1000)) / 1000.0
            
            logger.debug(
                f"[D46_BINANCE] Orderbook: {symbol} bids={bids} asks={asks}"
            )
            
            return OrderBookSnapshot(
                symbol=symbol,
                timestamp=timestamp,
                bids=bids if bids else [(0, 0)],
                asks=asks if asks else [(0, 0)],
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[D46_BINANCE] Network error getting orderbook: {e}")
            raise NetworkError(f"Failed to get orderbook: {e}")
        except (KeyError, ValueError, IndexError) as e:
            logger.error(f"[D46_BINANCE] Parse error getting orderbook: {e}")
            raise NetworkError(f"Failed to parse orderbook: {e}")
    
    def get_balance(self) -> Dict[str, Balance]:
        """
        자산 잔고 조회 (D46: 실제 API 호출).
        
        Returns:
            {asset: Balance, ...}
        
        Raises:
            AuthenticationError: API 키 부족
            NetworkError: API 호출 실패
        """
        logger.debug("[D46_BINANCE] Getting balance")
        
        # API 키 확인
        if not self.api_key or not self.api_secret:
            logger.warning("[D46_BINANCE] API key/secret not configured, returning empty balance")
            raise AuthenticationError("Binance API key/secret not configured")
        
        try:
            # Binance API 서명 생성
            timestamp = int(time.time() * 1000)
            params = {"timestamp": timestamp}
            query_string = urlencode(params)
            
            signature = hmac.new(
                self.api_secret.encode(),
                query_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            params["signature"] = signature
            
            headers = {
                "X-MBX-APIKEY": self.api_key,
            }
            
            url = f"{self.base_url}/fapi/v2/account"
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Binance API 응답 파싱
            # {
            #   "assets": [
            #     {"asset": "USDT", "walletBalance": "10000", "unrealizedProfit": "0", ...},
            #     {"asset": "BTC", "walletBalance": "1.5", "unrealizedProfit": "0", ...},
            #     ...
            #   ],
            #   "positions": [...],
            #   ...
            # }
            
            balances = {}
            for asset in data.get("assets", []):
                currency = asset.get("asset", "").upper()
                free = float(asset.get("walletBalance", 0))
                locked = float(asset.get("marginBalance", 0)) - free
                
                if currency and (free > 0 or locked > 0):
                    balances[currency] = Balance(
                        asset=currency,
                        free=max(0, free),
                        locked=max(0, locked),
                    )
            
            logger.debug(f"[D46_BINANCE] Balance: {list(balances.keys())}")
            return balances
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[D46_BINANCE] Network error getting balance: {e}")
            raise NetworkError(f"Failed to get balance: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"[D46_BINANCE] Parse error getting balance: {e}")
            raise NetworkError(f"Failed to parse balance: {e}")
    
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> OrderResult:
        """
        주문 생성 (D48: 실제 REST API 호출).
        
        Args:
            symbol: 거래 쌍 (예: "BTCUSDT")
            side: 주문 방향 (BUY/SELL)
            qty: 주문 수량
            price: 주문 가격
            order_type: 주문 유형
            time_in_force: 주문 유효 기간
        
        Returns:
            OrderResult
        
        Raises:
            RuntimeError: live_enabled=False
            AuthenticationError: API 키 부족
            NetworkError: API 호출 실패
        """
        if not self.live_enabled:
            logger.warning(
                f"[D48_BINANCE] Live trading is disabled. Order NOT sent: "
                f"{side} {qty} {symbol} @ {price}"
            )
            raise RuntimeError(
                "[D48_BINANCE] Live trading is disabled. "
                "Set live_enabled=True in config to enable real trading."
            )
        
        # API 키 확인
        if not self.api_key or not self.api_secret:
            logger.error("[D48_BINANCE] API key or secret not configured")
            raise AuthenticationError("Binance API key or secret not configured")
        
        logger.info(
            f"[D48_BINANCE] Creating order: {side} {qty} {symbol} @ {price} "
            f"(type={order_type}, tif={time_in_force}, leverage={self.leverage})"
        )
        
        try:
            # Binance API 요청 구성
            url = f"{self.base_url}/fapi/v1/order"
            
            # 주문 파라미터
            side_str = "BUY" if side == OrderSide.BUY else "SELL"
            type_str = "LIMIT" if order_type == OrderType.LIMIT else "MARKET"
            tif_str = "GTC" if time_in_force == TimeInForce.GTC else "IOC"
            
            timestamp = int(time.time() * 1000)
            recv_window = 5000
            
            params = {
                "symbol": symbol,
                "side": side_str,
                "type": type_str,
                "quantity": str(qty),
                "timeInForce": tif_str,
                "timestamp": timestamp,
                "recvWindow": recv_window,
            }
            
            if price is not None:
                params["price"] = str(price)
            
            # 서명 생성
            query_string = urlencode(params)
            signature = hmac.new(
                self.api_secret.encode(),
                query_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            params["signature"] = signature
            
            headers = {
                "X-MBX-APIKEY": self.api_key,
            }
            
            # HTTP 요청 (레이트리밋/재시도 포함)
            response = self.http_client.post(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            data = response.json()
            
            # 응답 파싱
            order_id = str(data.get("orderId", ""))
            status_str = data.get("status", "").upper()
            
            # 상태 매핑
            if status_str == "NEW":
                status = OrderStatus.OPEN
            elif status_str == "FILLED":
                status = OrderStatus.FILLED
            elif status_str == "CANCELED":
                status = OrderStatus.CANCELLED
            else:
                status = OrderStatus.OPEN
            
            filled_qty = float(data.get("executedQty", 0))
            
            logger.info(
                f"[D48_BINANCE] Order created: {order_id} "
                f"{side} {qty} {symbol} @ {price} (status={status})"
            )
            
            return OrderResult(
                order_id=order_id,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                order_type=order_type,
                status=status,
                filled_qty=filled_qty,
            )
        
        except requests.RequestException as e:
            logger.error(f"[D48_BINANCE] Network error: {e}")
            raise NetworkError(f"Binance API request failed: {e}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"[D48_BINANCE] Parse error: {e}")
            raise NetworkError(f"Binance API response parse failed: {e}")
    
    def cancel_order(self, order_id: str, symbol: Optional[str] = None) -> bool:
        """
        주문 취소 (D48: 실제 REST API 호출).
        
        Args:
            order_id: 주문 ID
            symbol: 거래 쌍 (Binance는 symbol 필요)
        
        Returns:
            성공 여부
        
        Raises:
            RuntimeError: live_enabled=False
            AuthenticationError: API 키 부족
            NetworkError: API 호출 실패
        """
        if not self.live_enabled:
            logger.warning(f"[D48_BINANCE] Live trading is disabled. Order NOT cancelled: {order_id}")
            raise RuntimeError(
                "[D48_BINANCE] Live trading is disabled. "
                "Set live_enabled=True in config to enable real trading."
            )
        
        # API 키 확인
        if not self.api_key or not self.api_secret:
            logger.error("[D48_BINANCE] API key or secret not configured")
            raise AuthenticationError("Binance API key or secret not configured")
        
        logger.info(f"[D48_BINANCE] Canceling order: {order_id}")
        
        try:
            # Binance API 요청 구성
            url = f"{self.base_url}/fapi/v1/order"
            
            timestamp = int(time.time() * 1000)
            recv_window = 5000
            
            params = {
                "orderId": order_id,
                "timestamp": timestamp,
                "recvWindow": recv_window,
            }
            
            if symbol:
                params["symbol"] = symbol
            
            # 서명 생성
            query_string = urlencode(params)
            signature = hmac.new(
                self.api_secret.encode(),
                query_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            params["signature"] = signature
            
            headers = {
                "X-MBX-APIKEY": self.api_key,
            }
            
            # HTTP 요청 (레이트리밋/재시도 포함)
            response = self.http_client.delete(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            
            logger.info(f"[D48_BINANCE] Order cancelled: {order_id}")
            return True
        
        except requests.RequestException as e:
            logger.error(f"[D48_BINANCE] Network error: {e}")
            raise NetworkError(f"Binance API request failed: {e}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"[D48_BINANCE] Parse error: {e}")
            raise NetworkError(f"Binance API response parse failed: {e}")
    
    def get_open_positions(self) -> List[Position]:
        """
        미결제 포지션 조회.
        
        Returns:
            포지션 리스트
        """
        # 실제 구현: requests를 사용하여 Binance API 호출
        # GET /fapi/v2/positionRisk (인증 필요)
        
        logger.debug("[D42_BINANCE] Getting open positions")
        
        # 기본값 반환 (빈 리스트)
        return []
    
    def get_order_status(self, order_id: str) -> OrderResult:
        """
        주문 상태 조회.
        
        Args:
            order_id: 주문 ID
        
        Returns:
            OrderResult
        """
        # 실제 구현: requests를 사용하여 Binance API 호출
        # GET /fapi/v1/orders (인증 필요)
        
        logger.debug(f"[D42_BINANCE] Getting order status: {order_id}")
        
        # 기본값 반환
        return OrderResult(
            order_id=order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            qty=1.0,
            price=40000.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            filled_qty=1.0,
        )
