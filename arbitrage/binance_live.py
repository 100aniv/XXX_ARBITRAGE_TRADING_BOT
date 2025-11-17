#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance Live API Module (PHASE D4)
===================================

Binance REST/WebSocket 통합.

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

logger = logging.getLogger(__name__)

# requests 선택적 import
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class BinanceLiveAPI(LiveAPIBase):
    """Binance Live API"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: Binance API 설정
        """
        api_key = config.get("api_key", "")
        mock_mode = not api_key
        super().__init__(config, mock_mode=mock_mode)
        
        self.api_key = api_key
        self.api_secret = config.get("api_secret", "")
        self.rest_url = config.get("rest_url", "https://api.binance.com")
        self.ws_url = config.get("ws_url", "wss://stream.binance.com:9443")
        
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
    
    def _get_auth_headers(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Binance API 인증 헤더 생성
        
        Args:
            params: 요청 파라미터
        
        Returns:
            인증 헤더 딕셔너리
        """
        if not self.api_key or not self.api_secret:
            return {}
        
        # Binance HMAC-SHA256 서명 생성
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }
    
    def connect(self) -> bool:
        """API 연결
        
        Returns:
            연결 성공 여부
        """
        if self.mock_mode:
            self.connected = True
            self.logger.info("[BinanceLiveAPI] Connected (mock mode)")
            return True
        
        if not REQUESTS_AVAILABLE:
            self.logger.error("[BinanceLiveAPI] requests library not available")
            return False
        
        try:
            # Binance API 연결 테스트
            response = requests.get(
                f"{self.rest_url}/api/v3/ping",
                timeout=5
            )
            if response.status_code == 200:
                self.connected = True
                self.logger.info("[BinanceLiveAPI] Connected to Binance API")
                return True
            else:
                self.logger.warning(f"[BinanceLiveAPI] Connection failed: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"[BinanceLiveAPI] Connection failed: {e}")
            return False
    
    def disconnect(self) -> None:
        """API 연결 해제"""
        self.connected = False
        self.logger.info("[BinanceLiveAPI] Disconnected")
    
    def get_ticker(self, symbol: str) -> Optional[TickerData]:
        """시세 조회
        
        Args:
            symbol: 심볼 (예: BTCUSDT)
        
        Returns:
            TickerData 또는 None
        """
        if self.mock_mode:
            return TickerData(
                symbol=symbol,
                bid=50000.0,
                ask=50010.0,
                last=50005.0,
                timestamp=datetime.now()
            )
        
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            self._rate_limit()
            # Binance REST API 호출
            response = requests.get(
                f"{self.rest_url}/api/v3/depth",
                params={"symbol": symbol, "limit": 5},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                bids = data.get("bids", [])
                asks = data.get("asks", [])
                
                bid_price = float(bids[0][0]) if bids else 0.0
                ask_price = float(asks[0][0]) if asks else 0.0
                
                # 최근 거래가 조회
                ticker_response = requests.get(
                    f"{self.rest_url}/api/v3/ticker/price",
                    params={"symbol": symbol},
                    timeout=5
                )
                last_price = 0.0
                if ticker_response.status_code == 200:
                    last_price = float(ticker_response.json().get("price", 0))
                
                return TickerData(
                    symbol=symbol,
                    bid=bid_price,
                    ask=ask_price,
                    last=last_price,
                    timestamp=datetime.now()
                )
            return None
        except Exception as e:
            self.logger.error(f"[BinanceLiveAPI] Ticker fetch failed: {e}")
            return None
    
    def place_order(self, order: OrderRequest) -> Optional[OrderResponse]:
        """주문 실행
        
        Args:
            order: OrderRequest 객체
        
        Returns:
            OrderResponse 또는 None
        """
        if self.mock_mode:
            return OrderResponse(
                order_id=f"binance_mock_{int(time.time())}",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price or 50000.0,
                status="FILLED",
                timestamp=datetime.now()
            )
        
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            self._rate_limit()
            # Binance 주문 API 호출
            params = {
                "symbol": order.symbol,
                "side": order.side.upper(),
                "type": order.order_type.upper(),
                "quantity": str(order.quantity),
                "timestamp": str(int(time.time() * 1000))
            }
            if order.order_type.upper() == "LIMIT":
                params["price"] = str(order.price)
                params["timeInForce"] = "GTC"
            
            # HMAC 서명 추가
            query_string = urlencode(params)
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature
            
            response = requests.post(
                f"{self.rest_url}/api/v3/order",
                headers=self._get_auth_headers(params),
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return OrderResponse(
                    order_id=str(data.get("orderId", "")),
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=order.price or 0.0,
                    status="PENDING",
                    timestamp=datetime.now()
                )
            else:
                self.logger.warning(f"[BinanceLiveAPI] Order placement failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"[BinanceLiveAPI] Order placement failed: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소
        
        Args:
            order_id: 주문 ID
        
        Returns:
            취소 성공 여부
        """
        if self.mock_mode:
            self.logger.info(f"[BinanceLiveAPI] Order cancelled (mock): {order_id}")
            return True
        
        if not REQUESTS_AVAILABLE:
            return False
        
        try:
            self._rate_limit()
            # Binance 주문 취소 API 호출
            params = {
                "orderId": order_id,
                "timestamp": str(int(time.time() * 1000))
            }
            
            # HMAC 서명 추가
            query_string = urlencode(params)
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature
            
            response = requests.delete(
                f"{self.rest_url}/api/v3/order",
                headers=self._get_auth_headers(params),
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                self.logger.info(f"[BinanceLiveAPI] Order cancelled: {order_id}")
                return True
            else:
                self.logger.warning(f"[BinanceLiveAPI] Order cancellation failed: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"[BinanceLiveAPI] Order cancellation failed: {e}")
            return False
    
    def get_balance(self) -> Optional[Dict[str, float]]:
        """잔액 조회
        
        Returns:
            {통화: 잔액} 딕셔너리 또는 None
        """
        if self.mock_mode:
            return {"USDT": 10000.0, "BTC": 0.1, "ETH": 1.0}
        
        if not REQUESTS_AVAILABLE:
            return None
        
        try:
            self._rate_limit()
            # Binance 잔액 조회 API 호출
            params = {"timestamp": str(int(time.time() * 1000))}
            
            # HMAC 서명 추가
            query_string = urlencode(params)
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature
            
            response = requests.get(
                f"{self.rest_url}/api/v3/account",
                headers=self._get_auth_headers(params),
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                balance = {}
                for balance_data in data.get("balances", []):
                    currency = balance_data.get("asset", "")
                    balance_amount = float(balance_data.get("free", 0))
                    if balance_amount > 0:
                        balance[currency] = balance_amount
                return balance
            else:
                self.logger.warning(f"[BinanceLiveAPI] Balance fetch failed: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"[BinanceLiveAPI] Balance fetch failed: {e}")
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
            # Binance 열린 주문 조회 API 호출
            params = {"timestamp": str(int(time.time() * 1000))}
            if symbol:
                params["symbol"] = symbol
            
            # HMAC 서명 추가
            query_string = urlencode(params)
            signature = hmac.new(
                self.api_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            params["signature"] = signature
            
            response = requests.get(
                f"{self.rest_url}/api/v3/openOrders",
                headers=self._get_auth_headers(params),
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                orders = []
                for order_data in data:
                    orders.append(OrderResponse(
                        order_id=str(order_data.get("orderId", "")),
                        symbol=order_data.get("symbol", ""),
                        side=order_data.get("side", "").upper(),
                        quantity=float(order_data.get("origQty", 0)),
                        price=float(order_data.get("price", 0)),
                        status="PENDING",
                        timestamp=datetime.now()
                    ))
                return orders
            else:
                self.logger.warning(f"[BinanceLiveAPI] Open orders fetch failed: {response.status_code}")
                return []
        except Exception as e:
            self.logger.error(f"[BinanceLiveAPI] Open orders fetch failed: {e}")
            return []
