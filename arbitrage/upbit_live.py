#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upbit Live API Module (PHASE D4)
=================================

Upbit REST/WebSocket 통합.

특징:
- REST API 기반 (동기)
- Rate limiting 내장
- 에러 처리 및 재시도
- Mock mode 지원
"""

import logging
import time
import json
import hmac
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
from urllib.parse import urlencode

from arbitrage.live_api import LiveAPIBase, OrderRequest, OrderResponse, TickerData
from arbitrage.config.readonly_guard import enforce_readonly

logger = logging.getLogger(__name__)

# requests 선택적 import
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class UpbitLiveAPI(LiveAPIBase):
    """Upbit Live API"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: Upbit API 설정
        """
        api_key = config.get("api_key", "")
        mock_mode = not api_key
        super().__init__(config, mock_mode=mock_mode)
        
        self.api_key = api_key
        self.api_secret = config.get("api_secret", "")
        self.rest_url = config.get("rest_url", "https://api.upbit.com")
        self.ws_url = config.get("ws_url", "wss://api.upbit.com/websocket/v1")
        
        # Rate limiting
        rate_limit_config = config.get("rate_limit", {})
        self.rate_limit_rps = rate_limit_config.get("requests_per_second", 10)
        self.last_request_time = 0.0
        
        self.connected = False
    
    def _rate_limit(self) -> None:
        """Rate limiting 적용"""
        elapsed = time.time() - self.last_request_time
        min_interval = 1.0 / self.rate_limit_rps
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
    
    def _get_auth_headers(self, query_string: str = "") -> Dict[str, str]:
        """Upbit API 인증 헤더 생성
        
        Args:
            query_string: 쿼리 문자열
        
        Returns:
            인증 헤더 딕셔너리
        """
        if not self.api_key or not self.api_secret:
            return {}
        
        # HMAC-SHA256 서명 생성
        message = query_string.encode('utf-8')
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()
        
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Signature": signature,
            "X-Query-String": query_string,
            "Content-Type": "application/json"
        }
    
    def connect(self) -> bool:
        """API 연결
        
        Returns:
            연결 성공 여부
        """
        if self.mock_mode:
            self.connected = True
            self.logger.info("[UpbitLiveAPI] Connected (mock mode)")
            return True
        
        if not REQUESTS_AVAILABLE:
            self.logger.error("[UpbitLiveAPI] requests library not available")
            return False
        
        try:
            # Upbit API 연결 테스트
            response = requests.get(
                f"{self.rest_url}/v1/status/wallet",
                headers=self._get_auth_headers(),
                timeout=5
            )
            if response.status_code == 200:
                self.connected = True
                self.logger.info("[UpbitLiveAPI] Connected to Upbit API")
                return True
            else:
                self.logger.warning(f"[UpbitLiveAPI] Connection failed: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"[UpbitLiveAPI] Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """API 연결 해제"""
        self.connected = False
        self.logger.info("[UpbitLiveAPI] Disconnected")
    
    def get_ticker(self, symbol: str) -> Optional[TickerData]:
        """시세 조회
        
        Args:
            symbol: 심볼 (예: BTC-KRW)
        
        Returns:
            TickerData 또는 None
        """
        if self.mock_mode:
            return TickerData(
                symbol=symbol,
                bid=50000000.0,
                ask=50001000.0,
                last=50000500.0,
                timestamp=datetime.now()
            )
        
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            self._rate_limit()
            # Upbit REST API 호출
            response = requests.get(
                f"{self.rest_url}/v1/orderbook",
                params={"markets": symbol},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    orderbook = data[0]
                    return TickerData(
                        symbol=symbol,
                        bid=float(orderbook.get("orderbook_units", [{}])[0].get("bid_price", 0)),
                        ask=float(orderbook.get("orderbook_units", [{}])[0].get("ask_price", 0)),
                        last=float(orderbook.get("trade_price", 0)),
                        timestamp=datetime.now()
                    )
            return None
        except Exception as e:
            self.logger.error(f"[UpbitLiveAPI] Ticker fetch failed: {e}")
            return None
    
    @enforce_readonly
    def place_order(self, order: OrderRequest) -> Optional[OrderResponse]:
        """주문 실행 (D98-3: ReadOnlyGuard 추가)
        
        Args:
            order: OrderRequest 객체
        
        Returns:
            OrderResponse 또는 None
        
        Raises:
            ReadOnlyError: READ_ONLY_ENFORCED=true 시 발생
        """
        if self.mock_mode:
            return OrderResponse(
                order_id=f"upbit_mock_{int(time.time())}",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price or 50000000.0,
                status="FILLED",
                timestamp=datetime.now()
            )
        
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            self._rate_limit()
            # Upbit 주문 API 호출
            params = {
                "market": order.symbol,
                "side": order.side.lower(),
                "ord_type": order.order_type.lower(),
                "volume": str(order.quantity)
            }
            if order.order_type.upper() == "LIMIT":
                params["price"] = str(order.price)
            
            query_string = urlencode(params)
            response = requests.post(
                f"{self.rest_url}/v1/orders",
                headers=self._get_auth_headers(query_string),
                params=params,
                timeout=5
            )
            
            if response.status_code == 201:
                data = response.json()
                return OrderResponse(
                    order_id=data.get("uuid", ""),
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=order.price or 0.0,
                    status="PENDING",
                    timestamp=datetime.now()
                )
            else:
                self.logger.warning(f"[UpbitLiveAPI] Order placement failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"[UpbitLiveAPI] Order placement failed: {e}")
            return None
    
    @enforce_readonly
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소 (D98-3: ReadOnlyGuard 추가)
        
        Args:
            order_id: 주문 ID
        
        Returns:
            취소 성공 여부
        
        Raises:
            ReadOnlyError: READ_ONLY_ENFORCED=true 시 발생
        """
        if self.mock_mode:
            self.logger.info(f"[UpbitLiveAPI] Order cancelled (mock): {order_id}")
            return True
        
        if not REQUESTS_AVAILABLE:
            return False
        
        try:
            self._rate_limit()
            # Upbit 주문 취소 API 호출
            query_string = f"uuid={order_id}"
            response = requests.delete(
                f"{self.rest_url}/v1/order",
                headers=self._get_auth_headers(query_string),
                params={"uuid": order_id},
                timeout=5
            )
            
            if response.status_code == 200:
                self.logger.info(f"[UpbitLiveAPI] Order cancelled: {order_id}")
                return True
            else:
                self.logger.warning(f"[UpbitLiveAPI] Order cancellation failed: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"[UpbitLiveAPI] Order cancellation failed: {e}")
            return False
    
    def get_balance(self) -> Optional[Dict[str, float]]:
        """잔액 조회
        
        Returns:
            {통화: 잔액} 딕셔너리 또는 None
        """
        if self.mock_mode:
            return {"KRW": 1000000.0, "BTC": 0.1, "ETH": 1.0}
        
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            self._rate_limit()
            # Upbit 잔액 조회 API 호출
            response = requests.get(
                f"{self.rest_url}/v1/accounts",
                headers=self._get_auth_headers(),
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                balance = {}
                for account in data:
                    currency = account.get("currency", "")
                    balance_amount = float(account.get("balance", 0))
                    if balance_amount > 0:
                        balance[currency] = balance_amount
                return balance
            else:
                self.logger.warning(f"[UpbitLiveAPI] Balance fetch failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"[UpbitLiveAPI] Balance fetch failed: {e}")
            return None
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        """열린 주문 조회
        
        Args:
            symbol: 심볼 (None이면 전체)
        
        Returns:
            OrderResponse 리스트
        """
        if self.mock_mode:
            return []
        
        if not REQUESTS_AVAILABLE:
            return []
        
        try:
            self._rate_limit()
            # Upbit 열린 주문 조회 API 호출
            params = {"state": "wait"}
            if symbol:
                params["market"] = symbol
            
            response = requests.get(
                f"{self.rest_url}/v1/orders",
                headers=self._get_auth_headers(),
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                orders = []
                for order_data in data:
                    orders.append(OrderResponse(
                        order_id=order_data.get("uuid", ""),
                        symbol=order_data.get("market", ""),
                        side=order_data.get("side", "").upper(),
                        quantity=float(order_data.get("volume", 0)),
                        price=float(order_data.get("price", 0)),
                        status="PENDING",
                        timestamp=datetime.now()
                    ))
                return orders
            else:
                self.logger.warning(f"[UpbitLiveAPI] Open orders fetch failed: {response.status_code}")
                return []
        except Exception as e:
            self.logger.error(f"[UpbitLiveAPI] Open orders fetch failed: {e}")
            return []
