# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Layer - Upbit Spot Exchange

Upbit REST API를 통한 현물 거래 어댑터.

D46: Read-Only 모드 추가
- get_orderbook: 실제 Upbit API 호출
- get_balance: 실제 Upbit API 호출
- create_order/cancel_order: live_enabled=True일 때만 실행
"""

import logging
import time
import os
from typing import Dict, List, Optional, Any
import requests
import hmac
import hashlib
import uuid
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
from arbitrage.config.readonly_guard import enforce_readonly

logger = logging.getLogger(__name__)


class UpbitSpotExchange(BaseExchange):
    """
    Upbit 현물 거래 어댑터.
    
    Upbit REST API를 사용하여 현물 거래를 수행.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Args:
            config: 설정 dict
                - api_key: Upbit API 키
                - api_secret: Upbit API 시크릿
                - base_url: API 엔드포인트 (기본: https://api.upbit.com)
                - timeout: 요청 타임아웃 (초)
                - rate_limit: RateLimitConfig dict (D48)
        """
        super().__init__("upbit", config)
        
        self.api_key = self.config.get("api_key", "")
        self.api_secret = self.config.get("api_secret", "")
        self.base_url = self.config.get("base_url", "https://api.upbit.com")
        self.timeout = self.config.get("timeout", 10)
        
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
            logger.warning("[D42_UPBIT] Live trading is DISABLED. Use Paper mode or enable live_enabled=True")
        
        logger.info(f"[D42_UPBIT] UpbitSpotExchange initialized: base_url={self.base_url}, base_currency={self.base_currency.value}")
    
    def _infer_base_currency(self) -> Currency:
        """
        D80-2: Upbit은 KRW 마켓
        
        Returns:
            Currency.KRW
        """
        return self.config.get("base_currency", Currency.KRW)
    
    def get_orderbook(self, symbol: str) -> OrderBookSnapshot:
        """
        호가 정보 조회 (D46: 실제 API 호출).
        
        Args:
            symbol: 거래 쌍 (예: "BTC-KRW")
        
        Returns:
            OrderBookSnapshot
        
        Raises:
            NetworkError: API 호출 실패
        """
        logger.debug(f"[D46_UPBIT] Getting orderbook for {symbol}")
        
        try:
            url = f"{self.base_url}/v1/orderbook"
            params = {"markets": symbol}
            
            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Upbit API 응답 파싱
            # {
            #   "market": "BTC-KRW",
            #   "timestamp": 1234567890,
            #   "orderbook_units": [
            #     {"ask_price": 101000, "ask_size": 1.0, "bid_price": 100000, "bid_size": 1.0},
            #     ...
            #   ]
            # }
            
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            orderbook_units = data.get("orderbook_units", [])
            
            # 최상단 호가만 추출
            bids = []
            asks = []
            
            for unit in orderbook_units:
                bid_price = float(unit.get("bid_price", 0))
                bid_size = float(unit.get("bid_size", 0))
                ask_price = float(unit.get("ask_price", 0))
                ask_size = float(unit.get("ask_size", 0))
                
                if bid_price > 0 and bid_size > 0:
                    bids.append((bid_price, bid_size))
                if ask_price > 0 and ask_size > 0:
                    asks.append((ask_price, ask_size))
            
            # 최상단 호가만 유지
            bids = sorted(bids, key=lambda x: x[0], reverse=True)[:1]
            asks = sorted(asks, key=lambda x: x[0])[:1]
            
            timestamp = data.get("timestamp", time.time())
            if isinstance(timestamp, int) and timestamp > 1000000000:
                # 밀리초 단위 타임스탐프를 초 단위로 변환
                timestamp = timestamp / 1000.0
            
            logger.debug(
                f"[D46_UPBIT] Orderbook: {symbol} bids={bids} asks={asks}"
            )
            
            return OrderBookSnapshot(
                symbol=symbol,
                timestamp=timestamp,
                bids=bids if bids else [(0, 0)],
                asks=asks if asks else [(0, 0)],
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[D46_UPBIT] Network error getting orderbook: {e}")
            raise NetworkError(f"Failed to get orderbook: {e}")
        except (KeyError, ValueError, IndexError) as e:
            logger.error(f"[D46_UPBIT] Parse error getting orderbook: {e}")
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
        logger.debug("[D46_UPBIT] Getting balance")
        
        # API 키 확인
        if not self.api_key or not self.api_secret:
            logger.warning("[D46_UPBIT] API key/secret not configured, returning empty balance")
            raise AuthenticationError("Upbit API key/secret not configured")
        
        try:
            # Upbit API 인증 헤더 생성
            nonce = str(uuid.uuid4())
            timestamp = str(int(time.time() * 1000))
            
            # 요청 서명
            message = f"{nonce}{timestamp}"
            signature = hmac.new(
                self.api_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-Nonce": nonce,
                "X-Timestamp": timestamp,
                "X-Signature": signature,
            }
            
            url = f"{self.base_url}/v1/accounts"
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Upbit API 응답 파싱
            # [
            #   {"currency": "KRW", "balance": "1000000", "locked": "0", "avg_buy_price": "0", ...},
            #   {"currency": "BTC", "balance": "1.5", "locked": "0", ...},
            #   ...
            # ]
            
            balances = {}
            if isinstance(data, list):
                for account in data:
                    currency = account.get("currency", "").upper()
                    balance = float(account.get("balance", 0))
                    locked = float(account.get("locked", 0))
                    
                    if currency and (balance > 0 or locked > 0):
                        balances[currency] = Balance(
                            asset=currency,
                            free=balance,
                            locked=locked,
                        )
            
            logger.debug(f"[D46_UPBIT] Balance: {list(balances.keys())}")
            return balances
        
        except requests.exceptions.RequestException as e:
            logger.error(f"[D46_UPBIT] Network error getting balance: {e}")
            raise NetworkError(f"Failed to get balance: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"[D46_UPBIT] Parse error getting balance: {e}")
            raise NetworkError(f"Failed to parse balance: {e}")
    
    @enforce_readonly
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
        
        D98-2: @enforce_readonly 데코레이터 적용
        READ_ONLY_ENFORCED=true 시 차단됨
        
        Args:
            symbol: 거래 쌍 (예: "BTC-KRW")
            side: 주문 방향 (BUY/SELL)
            qty: 주문 수량
            price: 주문 가격
            order_type: 주문 유형
            time_in_force: 주문 유효 기간
        
        Returns:
            OrderResult
        
        Raises:
            ReadOnlyError: READ_ONLY_ENFORCED=true (D98-2)
            RuntimeError: live_enabled=False
            AuthenticationError: API 키 부족
            NetworkError: API 호출 실패
        """
        if not self.live_enabled:
            logger.warning(
                f"[D48_UPBIT] Live trading is disabled. Order NOT sent: "
                f"{side} {qty} {symbol} @ {price}"
            )
            raise RuntimeError(
                "[D48_UPBIT] Live trading is disabled. "
                "Set live_enabled=True in config to enable real trading."
            )
        
        # API 키 확인
        if not self.api_key or not self.api_secret:
            logger.error("[D48_UPBIT] API key or secret not configured")
            raise AuthenticationError("Upbit API key or secret not configured")
        
        logger.info(
            f"[D48_UPBIT] Creating order: {side} {qty} {symbol} @ {price} "
            f"(type={order_type}, tif={time_in_force})"
        )
        
        try:
            # Upbit API 요청 구성
            url = f"{self.base_url}/v1/orders"
            
            # 주문 파라미터
            ord_type_str = "limit" if order_type == OrderType.LIMIT else "market"
            side_str = "bid" if side == OrderSide.BUY else "ask"
            
            params = {
                "market": symbol,
                "side": side_str,
                "volume": str(qty),
                "price": str(int(price)) if price else None,
                "ord_type": ord_type_str,
            }
            
            # None 값 제거
            params = {k: v for k, v in params.items() if v is not None}
            
            # 인증 헤더 생성
            nonce = str(uuid.uuid4())
            timestamp = str(int(time.time() * 1000))
            query_string = urlencode(params)
            message = f"{nonce}{timestamp}{query_string}"
            
            signature = hmac.new(
                self.api_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-Nonce": nonce,
                "X-Timestamp": timestamp,
                "X-Signature": signature,
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
            order_id = data.get("uuid", "")
            status_str = data.get("state", "").lower()
            
            # 상태 매핑
            if status_str == "wait":
                status = OrderStatus.OPEN
            elif status_str == "done":
                status = OrderStatus.FILLED
            elif status_str == "cancel":
                status = OrderStatus.CANCELLED
            else:
                status = OrderStatus.OPEN
            
            filled_qty = float(data.get("executed_volume", 0))
            
            logger.info(
                f"[D48_UPBIT] Order created: {order_id} "
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
            logger.error(f"[D48_UPBIT] Network error: {e}")
            raise NetworkError(f"Upbit API request failed: {e}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"[D48_UPBIT] Parse error: {e}")
            raise NetworkError(f"Upbit API response parse failed: {e}")
    
    @enforce_readonly
    def cancel_order(self, order_id: str) -> bool:
        """
        주문 취소 (D48: 실제 REST API 호출).
        
        D98-2: @enforce_readonly 데코레이터 적용
        READ_ONLY_ENFORCED=true 시 차단됨
        
        Args:
            order_id: 주문 ID
        
        Returns:
            성공 여부
        
        Raises:
            ReadOnlyError: READ_ONLY_ENFORCED=true (D98-2)
            RuntimeError: live_enabled=False
            AuthenticationError: API 키 부족
            NetworkError: API 호출 실패
        """
        if not self.live_enabled:
            logger.warning(f"[D48_UPBIT] Live trading is disabled. Order NOT cancelled: {order_id}")
            raise RuntimeError(
                "[D48_UPBIT] Live trading is disabled. "
                "Set live_enabled=True in config to enable real trading."
            )
        
        # API 키 확인
        if not self.api_key or not self.api_secret:
            logger.error("[D48_UPBIT] API key or secret not configured")
            raise AuthenticationError("Upbit API key or secret not configured")
        
        logger.info(f"[D48_UPBIT] Canceling order: {order_id}")
        
        try:
            # Upbit API 요청 구성
            url = f"{self.base_url}/v1/orders/{order_id}"
            
            # 인증 헤더 생성
            nonce = str(uuid.uuid4())
            timestamp = str(int(time.time() * 1000))
            message = f"{nonce}{timestamp}"
            
            signature = hmac.new(
                self.api_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "X-Nonce": nonce,
                "X-Timestamp": timestamp,
                "X-Signature": signature,
            }
            
            # HTTP 요청 (레이트리밋/재시도 포함)
            response = self.http_client.delete(
                url,
                headers=headers,
                timeout=self.timeout,
            )
            
            response.raise_for_status()
            
            logger.info(f"[D48_UPBIT] Order cancelled: {order_id}")
            return True
        
        except requests.RequestException as e:
            logger.error(f"[D48_UPBIT] Network error: {e}")
            raise NetworkError(f"Upbit API request failed: {e}")
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"[D48_UPBIT] Parse error: {e}")
            raise NetworkError(f"Upbit API response parse failed: {e}")
    
    def get_open_positions(self) -> List[Position]:
        """
        미결제 포지션 조회 (현물은 포지션 없음).
        
        Returns:
            빈 리스트
        """
        return []
    
    def get_order_status(self, order_id: str) -> OrderResult:
        """
        주문 상태 조회.
        
        Args:
            order_id: 주문 ID
        
        Returns:
            OrderResult
        """
        # 실제 구현: requests를 사용하여 Upbit API 호출
        # GET /v1/orders/{uuid} (인증 필요)
        
        logger.debug(f"[D42_UPBIT] Getting order status: {order_id}")
        
        # 기본값 반환
        return OrderResult(
            order_id=order_id,
            symbol="BTC-KRW",
            side=OrderSide.BUY,
            qty=1.0,
            price=100000.0,
            order_type=OrderType.LIMIT,
            status=OrderStatus.FILLED,
            filled_qty=1.0,
        )
