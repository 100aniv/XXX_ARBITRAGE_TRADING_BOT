#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D16 Live Trading — Upbit Exchange Adapter
==========================================

Upbit REST API + WebSocket 연동.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import aiohttp
import websockets
import json

from arbitrage.types import (
    Price, Order, OrderSide, OrderStatus, ExchangeType, Position
)

logger = logging.getLogger(__name__)


class UpbitExchange:
    """
    Upbit 거래소 어댑터
    
    REST API: 주문, 포지션 조회
    WebSocket: 실시간 가격 스트림
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str = "https://api.upbit.com/v1",
        ws_url: str = "wss://api.upbit.com/websocket/v1"
    ):
        """
        Args:
            api_key: Upbit API 키
            secret_key: Upbit 시크릿 키
            base_url: REST API 기본 URL
            ws_url: WebSocket URL
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.ws_url = ws_url
        self.exchange_type = ExchangeType.UPBIT
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connection = None
        self._price_callbacks: List[callable] = []
    
    async def connect(self) -> None:
        """세션 연결"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        logger.info("Upbit exchange connected")
    
    async def disconnect(self) -> None:
        """세션 종료"""
        if self._session:
            await self._session.close()
            self._session = None
        if self._ws_connection:
            await self._ws_connection.close()
        logger.info("Upbit exchange disconnected")
    
    async def get_balance(self) -> Dict[str, float]:
        """
        계좌 잔액 조회
        
        Returns:
            {symbol: balance} 딕셔너리
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        headers = self._get_headers()
        url = f"{self.base_url}/accounts"
        
        try:
            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {item["currency"]: float(item["balance"]) for item in data}
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
            symbol: 심볼 (예: "KRW-BTC")
        
        Returns:
            Price 객체 또는 None
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        url = f"{self.base_url}/ticker"
        params = {"markets": symbol}
        
        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        item = data[0]
                        return Price(
                            exchange=self.exchange_type,
                            symbol=symbol,
                            bid=float(item.get("bid_price", 0)),
                            ask=float(item.get("ask_price", 0)),
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
        
        headers = self._get_headers()
        url = f"{self.base_url}/orders"
        
        data = {
            "market": symbol,
            "side": side.value,
            "volume": str(quantity),
            "price": str(int(price)),
            "ord_type": "limit"
        }
        
        try:
            async with self._session.post(url, json=data, headers=headers) as resp:
                if resp.status == 201:
                    result = await resp.json()
                    return Order(
                        order_id=result["uuid"],
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
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        주문 취소
        
        Args:
            order_id: 주문 ID
        
        Returns:
            성공 여부
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        headers = self._get_headers()
        url = f"{self.base_url}/order/{order_id}"
        
        try:
            async with self._session.delete(url, headers=headers) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """
        주문 상태 조회
        
        Args:
            order_id: 주문 ID
        
        Returns:
            Order 객체 또는 None
        """
        if not self._session:
            raise RuntimeError("Session not connected")
        
        headers = self._get_headers()
        url = f"{self.base_url}/order/{order_id}"
        
        try:
            async with self._session.get(url, headers=headers) as resp:
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
            symbols: 심볼 목록
            callback: 가격 수신 콜백
        """
        self._price_callbacks.append(callback)
        
        try:
            async with websockets.connect(self.ws_url) as ws:
                self._ws_connection = ws
                
                # 구독 메시지
                subscribe_msg = {
                    "type": "ticker",
                    "codes": symbols
                }
                await ws.send(json.dumps(subscribe_msg))
                
                # 메시지 수신 루프
                async for message in ws:
                    try:
                        data = json.loads(message)
                        price = Price(
                            exchange=self.exchange_type,
                            symbol=data.get("code", ""),
                            bid=float(data.get("bid_price", 0)),
                            ask=float(data.get("ask_price", 0)),
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
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _parse_order(self, data: dict) -> Order:
        """주문 데이터 파싱"""
        status_map = {
            "wait": OrderStatus.PENDING,
            "watch": OrderStatus.PENDING,
            "done": OrderStatus.FILLED,
            "cancel": OrderStatus.CANCELLED
        }
        
        return Order(
            order_id=data["uuid"],
            exchange=self.exchange_type,
            symbol=data["market"],
            side=OrderSide(data["side"]),
            quantity=float(data["volume"]),
            price=float(data["price"]),
            status=status_map.get(data["state"], OrderStatus.PENDING),
            filled_quantity=float(data.get("executed_volume", 0)),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        )
