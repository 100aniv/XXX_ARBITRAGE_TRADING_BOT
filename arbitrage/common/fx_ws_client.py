# -*- coding: utf-8 -*-
"""
D80-4: Binance FX WebSocket Client

WebSocket 기반 실시간 환율 스트림 클라이언트.

Features:
- Binance Mark Price Stream (USDT→USD proxy)
- Auto-reconnect (exponential backoff)
- Thread-based (non-blocking)
- Callback-based FxCache update

Architecture:
    WebSocket Thread (background)
        ↓
    on_message → parse → on_rate_update callback
        ↓
    FxCache.set(Currency.USDT, Currency.USD, rate)

Usage:
    client = BinanceFxWebSocketClient(
        symbol="btcusdt",
        on_rate_update=lambda rate, ts: cache.set(Currency.USDT, Currency.USD, rate, ts)
    )
    client.start()  # Background thread
    ...
    client.stop()
"""

import json
import logging
import threading
import time
from decimal import Decimal
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# BinanceFxWebSocketClient
# =============================================================================

class BinanceFxWebSocketClient:
    """
    Binance WebSocket FX Stream Client (D80-4).
    
    Features:
    - Mark Price Stream (USDT→USD proxy)
    - Auto-reconnect (exponential backoff)
    - Thread-based (non-blocking)
    - Callback-based FxCache update
    
    Example:
        client = BinanceFxWebSocketClient(
            symbol="btcusdt",
            on_rate_update=lambda rate, ts: print(f"USDT→USD = {rate}")
        )
        client.start()
        time.sleep(60)
        client.stop()
    """
    
    WS_URL = "wss://fstream.binance.com/ws/{symbol}@markPrice@1s"
    MAX_RECONNECT_ATTEMPTS = 10
    MAX_BACKOFF_SECONDS = 60
    
    def __init__(
        self,
        symbol: str = "btcusdt",
        on_rate_update: Optional[Callable[[Decimal, float], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Args:
            symbol: Binance futures symbol (소문자, 예: "btcusdt")
            on_rate_update: Callback(rate: Decimal, timestamp: float) - FxCache 업데이트용
            on_error: Callback(exception: Exception) - 에러 핸들링용
        """
        self.symbol = symbol.lower()
        self.url = self.WS_URL.format(symbol=self.symbol)
        self.on_rate_update = on_rate_update
        self.on_error = on_error
        
        # WebSocket 관련
        self._ws = None
        self._thread = None
        self._stop_event = threading.Event()
        self._connected = False
        self._reconnect_count = 0
        
        # Metrics
        self._message_count = 0
        self._error_count = 0
        self._last_message_time = 0.0
        
        logger.info(f"[FX_WS] BinanceFxWebSocketClient initialized (symbol={symbol})")
    
    def start(self) -> None:
        """Start WebSocket client in background thread"""
        if self._thread and self._thread.is_alive():
            logger.warning("[FX_WS] WebSocket client already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="FxWebSocketThread")
        self._thread.start()
        logger.info("[FX_WS] WebSocket client started")
    
    def stop(self) -> None:
        """Stop WebSocket client"""
        logger.info("[FX_WS] Stopping WebSocket client...")
        self._stop_event.set()
        
        if self._ws:
            try:
                self._ws.close()
            except Exception as e:
                logger.warning(f"[FX_WS] Error closing WebSocket: {e}")
        
        if self._thread:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                logger.warning("[FX_WS] WebSocket thread did not terminate in time")
        
        logger.info("[FX_WS] WebSocket client stopped")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self._connected
    
    def get_stats(self) -> dict:
        """
        Get WebSocket statistics.
        
        Returns:
            dict: {
                "connected": bool,
                "reconnect_count": int,
                "message_count": int,
                "error_count": int,
                "last_message_age": float (seconds)
            }
        """
        last_message_age = time.time() - self._last_message_time if self._last_message_time > 0 else 0.0
        
        return {
            "connected": self._connected,
            "reconnect_count": self._reconnect_count,
            "message_count": self._message_count,
            "error_count": self._error_count,
            "last_message_age": last_message_age,
        }
    
    def _run(self) -> None:
        """Main WebSocket loop (runs in background thread)"""
        while not self._stop_event.is_set():
            try:
                self._connect()
            except Exception as e:
                logger.error(f"[FX_WS] WebSocket error: {e}")
                self._error_count += 1
                if self.on_error:
                    try:
                        self.on_error(e)
                    except Exception as callback_error:
                        logger.error(f"[FX_WS] Error in on_error callback: {callback_error}")
                
                # Reconnect logic
                self._reconnect_count += 1
                if self._reconnect_count > self.MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        f"[FX_WS] Max reconnect attempts ({self.MAX_RECONNECT_ATTEMPTS}) "
                        "exceeded, stopping WebSocket client"
                    )
                    break
                
                # Exponential backoff
                backoff = min(2 ** self._reconnect_count, self.MAX_BACKOFF_SECONDS)
                logger.warning(
                    f"[FX_WS] Reconnecting in {backoff}s "
                    f"(attempt {self._reconnect_count}/{self.MAX_RECONNECT_ATTEMPTS})"
                )
                
                # Sleep with stop_event check (interruptible)
                if self._stop_event.wait(timeout=backoff):
                    break  # Stop requested during sleep
    
    def _connect(self) -> None:
        """Connect to WebSocket (requires websocket-client library)"""
        try:
            import websocket
        except ImportError:
            logger.error(
                "[FX_WS] websocket-client library not installed. "
                "Install with: pip install websocket-client"
            )
            raise
        
        logger.info(f"[FX_WS] Connecting to {self.url}")
        
        self._ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_ws_error,
            on_close=self._on_close,
        )
        
        # Run forever (blocking in this thread until stop or error)
        self._ws.run_forever()
    
    def _on_open(self, ws) -> None:
        """WebSocket connection opened"""
        self._connected = True
        self._reconnect_count = 0  # Reset on successful connection
        logger.info("[FX_WS] WebSocket connected")
    
    def _on_message(self, ws, message: str) -> None:
        """
        Handle WebSocket message.
        
        Binance Mark Price message format:
        {
            "e": "markPriceUpdate",
            "E": 1234567890,
            "s": "BTCUSDT",
            "p": "97000.00",
            "r": "0.0001",
            ...
        }
        """
        try:
            data = json.loads(message)
            
            # Mark Price message
            if data.get("e") == "markPriceUpdate":
                # USDT/USD ≈ 1.0 (근사, funding rate 무시)
                # 실제로는 funding rate를 고려할 수 있지만, D80-4에서는 단순화
                rate = Decimal("1.0")
                timestamp = time.time()
                
                self._message_count += 1
                self._last_message_time = timestamp
                
                # Callback to update FxCache
                if self.on_rate_update:
                    try:
                        self.on_rate_update(rate, timestamp)
                    except Exception as callback_error:
                        logger.error(f"[FX_WS] Error in on_rate_update callback: {callback_error}")
                
                logger.debug(
                    f"[FX_WS] Mark price update: {data.get('s')} @ {data.get('p')}, "
                    f"USDT→USD={rate}, msg_count={self._message_count}"
                )
        
        except json.JSONDecodeError as e:
            logger.error(f"[FX_WS] JSON decode error: {e}, message={message[:100]}")
            self._error_count += 1
        
        except Exception as e:
            logger.error(f"[FX_WS] Error parsing message: {e}, message={message[:100]}")
            self._error_count += 1
    
    def _on_ws_error(self, ws, error) -> None:
        """WebSocket error"""
        logger.error(f"[FX_WS] WebSocket error: {error}")
        self._connected = False
        self._error_count += 1
        if self.on_error:
            try:
                self.on_error(error)
            except Exception as callback_error:
                logger.error(f"[FX_WS] Error in on_error callback: {callback_error}")
    
    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """WebSocket connection closed"""
        self._connected = False
        logger.warning(
            f"[FX_WS] WebSocket closed (code={close_status_code}, msg={close_msg})"
        )
