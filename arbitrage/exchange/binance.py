#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — Binance Exchange Adapter
============================================

Binance REST API + WebSocket 연동.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
import aiohttp
import websockets
import json
import hmac
import hashlib
from urllib.parse import urlencode

from arbitrage.types import (
    Price, Order, OrderSide, OrderStatus, ExchangeType
)

logger = logging.getLogger(__name__)


class BinanceExchange:
    """
    Binance 거래소 어댑터
    
    REST API: 주문, 포지션 조회
    WebSocket: 실시간 가격 스트림
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://api.binance.com/api/v3",
        ws_url: str = "wss://stream.binance.com:9443/ws"
    ):
        """
        Args:
            api_key: Binance API 키
            secret_key: Binance 시크릿 키
            base_url: REST API 기본 URL
            ws_url: WebSocket URL
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.ws_url = ws_url
        self.exchange_type = ExchangeType.BINANCE
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connection = None
        self._price_callbacks: List[callable] = []
    
    async def connect(self) -> None:
        """세션 연결"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        logger.info("Binance exchange connected")
    
    async def disconnect(self) -> None:
        """세션 종료"""
        if self._session:
            await self._session.close()
            self._session = None
        if self._ws_connection:
            await self._ws_connection.close()
        logger.info("Binance exchange disconnected")
    
    async def get_balance(self) -> Dict[str, float]:
        """
        계좌 잔액 조회
        
        Returns:
            {symbol: balance} 딕셔너리
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        url = f"{self.base_url}/account"
        headers = self._get_headers()
        params = {"timestamp": int(datetime.utcnow().timestamp() * 1000)}
        params["signature"] = self._sign_params(params)
        
        try:
            async with self._session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        item["asset"]: float(item["free"])
                        for item in data.get("balances", [])
                    }
                else:
                    logger.error(f"Failed to get balance: {resp.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return {}
    
    async def get_ticker(self, symbol: str) -> Optional[Price]:
        """
        현재 가격 조회
        
        Args:
            symbol: 심볼 (예: "BTCUSDT")
        
        Returns:
            Price 객체 또는 None
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        url = f"{self.base_url}/ticker/bookTicker"
        params = {"symbol": symbol}
        
        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return Price(
                        exchange=self.exchange_type,
                        symbol=symbol,
                        bid=float(data["bidPrice"]),
                        ask=float(data["askPrice"]),
                        timestamp=datetime.utcnow()
                    )
                else:
                    logger.error(f"Failed to get ticker: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting ticker: {e}")
            return None
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float
    ) -> Optional[Order]:
        """
        주문 생성
        
        Args:
            symbol: 심볼
            side: 주문 방향 (BUY/SELL)
            quantity: 수량
            price: 가격
        
        Returns:
            Order 객체 또는 None
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        url = f"{self.base_url}/order"
        headers = self._get_headers()
        
        params = {
            "symbol": symbol,
            "side": side.value.upper(),
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": str(quantity),
            "price": str(price),
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }
        params["signature"] = self._sign_params(params)
        
        try:
            async with self._session.post(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return Order(
                        order_id=str(result["orderId"]),
                        exchange=self.exchange_type,
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        price=price,
                        status=OrderStatus.PENDING,
                        created_at=datetime.utcnow()
                    )
                else:
                    logger.error(f"Failed to place order: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        주문 취소
        
        Args:
            symbol: 심볼
            order_id: 주문 ID
        
        Returns:
            성공 여부
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        url = f"{self.base_url}/order"
        headers = self._get_headers()
        
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }
        params["signature"] = self._sign_params(params)
        
        try:
            async with self._session.delete(url, params=params, headers=headers) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def get_order_status(self, symbol: str, order_id: str) -> Optional[Order]:
        """
        주문 상태 조회
        
        Args:
            symbol: 심볼
            order_id: 주문 ID
        
        Returns:
            Order 객체 또는 None
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        url = f"{self.base_url}/order"
        headers = self._get_headers()
        
        params = {
            "symbol": symbol,
            "orderId": order_id,
            "timestamp": int(datetime.utcnow().timestamp() * 1000)
        }
        params["signature"] = self._sign_params(params)
        
        try:
            async with self._session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return self._parse_order(result)
                else:
                    logger.error(f"Failed to get order status: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return None
    
    async def subscribe_prices(self, symbols: List[str], callback: callable) -> None:
        """
        실시간 가격 구독
        
        Args:
            symbols: 심볼 목록 (소문자)
            callback: 가격 수신 콜백
        """
        self._price_callbacks.append(callback)
        
        try:
            # WebSocket 스트림 구성
            streams = [f"{symbol.lower()}@bookTicker" for symbol in symbols]
            ws_url = f"{self.ws_url}/{'/'.join(streams)}"
            
            async with websockets.connect(ws_url) as ws:
                self._ws_connection = ws
                
                # 메시지 수신 루프
                async for message in ws:
                    try:
                        data = json.loads(message)
                        price = Price(
                            exchange=self.exchange_type,
                            symbol=data.get("s", ""),
                            bid=float(data.get("b", 0)),
                            ask=float(data.get("a", 0)),
                            timestamp=datetime.utcnow()
                        )
                        
                        # 모든 콜백 실행
                        for cb in self._price_callbacks:
                            await cb(price)
                    except Exception as e:
                        logger.error(f"Error processing price message: {e}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        """인증 헤더 생성"""
        return {
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _sign_params(self, params: dict) -> str:
        """파라미터 서명"""
        query_string = urlencode(params)
        return hmac.new(
            self.secret_key.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _parse_order(self, data: dict) -> Order:
        """주문 데이터 파싱"""
        status_map = {
            "NEW": OrderStatus.PENDING,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED
        }
        
        return Order(
            order_id=str(data["orderId"]),
            exchange=self.exchange_type,
            symbol=data["symbol"],
            side=OrderSide(data["side"].lower()),
            quantity=float(data["origQty"]),
            price=float(data["price"]),
            status=status_map.get(data["status"], OrderStatus.PENDING),
            filled_quantity=float(data.get("executedQty", 0)),
            created_at=datetime.fromtimestamp(data["time"] / 1000)
        )
