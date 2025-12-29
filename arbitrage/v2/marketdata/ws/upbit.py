"""
D202-1: Upbit WebSocket Provider (reconnect 포함)

V2 계약:
- L2 orderbook 실시간 스트림
- 자동 재연결 (exponential backoff, 최대 3회)
- Health check
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime

from arbitrage.v2.marketdata.interfaces import WsProvider, Orderbook, OrderbookLevel

logger = logging.getLogger(__name__)


class UpbitWsProvider(WsProvider):
    """
    Upbit WebSocket Provider (L2 Orderbook)
    
    API 문서: https://docs.upbit.com/docs/upbit-quotation-websocket
    Reconnect: 최대 3회, exponential backoff
    """
    
    WS_URL = "wss://api.upbit.com/websocket/v1"
    
    def __init__(
        self,
        max_reconnect_attempts: int = 3,
        reconnect_backoff: float = 2.0,
    ):
        """
        Args:
            max_reconnect_attempts: 최대 재연결 시도 횟수
            reconnect_backoff: 재연결 backoff 배수
        """
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_backoff = reconnect_backoff
        
        self.ws = None
        self.latest_orderbooks: Dict[str, Orderbook] = {}
        self._is_connected = False
        self._reconnect_count = 0
    
    async def connect(self) -> None:
        """WebSocket 연결 (mock)"""
        logger.info("[D202-1_UPBIT_WS] Connecting to WebSocket (mock)")
        self._is_connected = True
        self._reconnect_count = 0
    
    async def disconnect(self) -> None:
        """WebSocket 연결 종료"""
        logger.info("[D202-1_UPBIT_WS] Disconnecting WebSocket")
        self._is_connected = False
        if self.ws:
            self.ws = None
    
    async def subscribe(self, symbols: List[str]) -> None:
        """
        심볼 구독
        
        Args:
            symbols: ["BTC/KRW", "ETH/KRW"] 형식
        """
        logger.info(f"[D202-1_UPBIT_WS] Subscribing to symbols: {symbols}")
    
    def get_latest_orderbook(self, symbol: str) -> Optional[Orderbook]:
        """최신 orderbook 스냅샷"""
        return self.latest_orderbooks.get(symbol)
    
    async def health_check(self) -> bool:
        """연결 상태 확인"""
        return self._is_connected
    
    async def _reconnect(self) -> bool:
        """
        재연결 로직 (exponential backoff)
        
        Returns:
            bool: 재연결 성공 여부
        """
        if self._reconnect_count >= self.max_reconnect_attempts:
            logger.error(
                f"[D202-1_UPBIT_WS] Max reconnect attempts reached: "
                f"{self._reconnect_count}/{self.max_reconnect_attempts}"
            )
            return False
        
        self._reconnect_count += 1
        backoff_time = self.reconnect_backoff ** self._reconnect_count
        
        logger.warning(
            f"[D202-1_UPBIT_WS] Reconnecting... "
            f"(attempt {self._reconnect_count}/{self.max_reconnect_attempts}, "
            f"backoff {backoff_time:.2f}s)"
        )
        
        await asyncio.sleep(backoff_time)
        
        try:
            await self.connect()
            logger.info("[D202-1_UPBIT_WS] Reconnect successful")
            return True
        except Exception as e:
            logger.error(f"[D202-1_UPBIT_WS] Reconnect failed: {e}")
            return await self._reconnect()
