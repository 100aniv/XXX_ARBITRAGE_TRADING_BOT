# -*- coding: utf-8 -*-
"""
OKX WebSocket FX Client (D80-5)

OKX Mark Price Stream을 통한 실시간 FX 환율 수신.
"""

import json
import logging
import threading
import time
from decimal import Decimal
from typing import Callable, Optional, Any, Dict

logger = logging.getLogger(__name__)


class OkxFxWebSocketClient:
    """
    OKX WebSocket FX Client.
    
    Features:
    - OKX Mark Price Stream (BTC-USDT)
    - Auto-reconnect with exponential backoff
    - Thread-based (non-blocking)
    - Callback-based rate update
    
    WebSocket API:
    - Endpoint: wss://ws.okx.com:8443/ws/v5/public
    - Subscribe: {"op":"subscribe", "args":[{"channel":"mark-price", "instId":"BTC-USDT"}]}
    - Message: {"arg":{"channel":"mark-price","instId":"BTC-USDT"},"data":[{"instId":"BTC-USDT","markPx":"97000.00","ts":"1701449123450"}]}
    """
    
    WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
    MAX_RECONNECT_ATTEMPTS = 10
    MAX_BACKOFF_SECONDS = 60
    
    def __init__(
        self,
        inst_id: str = "BTC-USDT",
        on_rate_update: Optional[Callable[[Decimal, float], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Args:
            inst_id: OKX instrument ID (e.g., "BTC-USDT")
            on_rate_update: Callback(rate, timestamp)
            on_error: Callback(error)
        """
        self.inst_id = inst_id
        self.on_rate_update = on_rate_update
        self.on_error = on_error
        
        # WebSocket state
        self._ws = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._connected = False
        
        # Reconnect state
        self._reconnect_count = 0
        self._backoff_seconds = 1
        
        # Stats
        self._message_count = 0
        self._error_count = 0
        self._last_message_time = 0.0
    
    def start(self) -> None:
        """Start WebSocket client (background thread)."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("[OKX_FX_WS] Already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="OkxFxWebSocketThread"
        )
        self._thread.start()
        logger.info(f"[OKX_FX_WS] Started (inst_id={self.inst_id})")
    
    def stop(self) -> None:
        """Stop WebSocket client."""
        if self._thread is None:
            return
        
        self._stop_event.set()
        
        if self._ws:
            try:
                self._ws.close()
            except Exception as e:
                logger.warning(f"[OKX_FX_WS] Error closing WebSocket: {e}")
        
        self._thread.join(timeout=5.0)
        logger.info("[OKX_FX_WS] Stopped")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket statistics.
        
        Returns:
            {
                "connected": bool,
                "reconnect_count": int,
                "message_count": int,
                "error_count": int,
                "last_message_age": float,
            }
        """
        last_message_age = time.time() - self._last_message_time if self._last_message_time > 0 else float("inf")
        
        return {
            "connected": self._connected,
            "reconnect_count": self._reconnect_count,
            "message_count": self._message_count,
            "error_count": self._error_count,
            "last_message_age": last_message_age,
        }
    
    def _run(self) -> None:
        """Main WebSocket loop (runs in background thread)."""
        try:
            import websocket
        except ImportError:
            logger.error("[OKX_FX_WS] websocket-client not installed")
            return
        
        while not self._stop_event.is_set():
            try:
                logger.info(f"[OKX_FX_WS] Connecting... (attempt={self._reconnect_count + 1})")
                
                self._ws = websocket.WebSocketApp(
                    self.WS_URL,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )
                
                self._ws.run_forever()
                
                # Connection closed
                if self._stop_event.is_set():
                    break
                
                # Reconnect logic
                if self._reconnect_count >= self.MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        f"[OKX_FX_WS] Max reconnect attempts ({self.MAX_RECONNECT_ATTEMPTS}) reached, giving up"
                    )
                    break
                
                self._reconnect_count += 1
                wait_time = min(self._backoff_seconds, self.MAX_BACKOFF_SECONDS)
                logger.warning(
                    f"[OKX_FX_WS] Reconnecting in {wait_time}s (attempt={self._reconnect_count})"
                )
                self._stop_event.wait(wait_time)
                self._backoff_seconds *= 2
                
            except Exception as e:
                logger.error(f"[OKX_FX_WS] Unexpected error: {e}", exc_info=True)
                self._error_count += 1
                if self.on_error:
                    self.on_error(e)
                break
    
    def _on_ws_open(self, ws) -> None:
        """WebSocket opened."""
        self._connected = True
        self._reconnect_count = 0
        self._backoff_seconds = 1
        
        logger.info(f"[OKX_FX_WS] Connected (inst_id={self.inst_id})")
        
        # Subscribe to mark price
        subscribe_msg = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "mark-price",
                    "instId": self.inst_id
                }
            ]
        }
        
        try:
            ws.send(json.dumps(subscribe_msg))
            logger.info(f"[OKX_FX_WS] Subscribed to mark-price: {self.inst_id}")
        except Exception as e:
            logger.error(f"[OKX_FX_WS] Failed to subscribe: {e}")
            self._error_count += 1
            if self.on_error:
                self.on_error(e)
    
    def _on_ws_message(self, ws, message: str) -> None:
        """WebSocket message received."""
        try:
            data = json.loads(message)
            
            # Check if it's a mark price update
            if "arg" in data and data["arg"].get("channel") == "mark-price":
                if "data" in data and len(data["data"]) > 0:
                    mark_px = data["data"][0].get("markPx")
                    
                    if mark_px:
                        # USDT ≈ USD (근사)
                        rate = Decimal("1.0")
                        timestamp = time.time()
                        
                        self._message_count += 1
                        self._last_message_time = timestamp
                        
                        if self.on_rate_update:
                            self.on_rate_update(rate, timestamp)
                        
                        logger.debug(
                            f"[OKX_FX_WS] Mark price: {mark_px}, rate={rate}, "
                            f"messages={self._message_count}"
                        )
            
            # Ping/pong
            elif data.get("event") == "ping":
                ws.send(json.dumps({"op": "pong"}))
            
        except json.JSONDecodeError as e:
            logger.warning(f"[OKX_FX_WS] Invalid JSON: {message[:100]}")
            self._error_count += 1
        except Exception as e:
            logger.error(f"[OKX_FX_WS] Error processing message: {e}", exc_info=True)
            self._error_count += 1
            if self.on_error:
                self.on_error(e)
    
    def _on_ws_error(self, ws, error: Exception) -> None:
        """WebSocket error."""
        logger.error(f"[OKX_FX_WS] WebSocket error: {error}")
        self._error_count += 1
        if self.on_error:
            self.on_error(error)
    
    def _on_ws_close(self, ws, close_status_code, close_msg) -> None:
        """WebSocket closed."""
        self._connected = False
        logger.warning(
            f"[OKX_FX_WS] Connection closed (code={close_status_code}, msg={close_msg})"
        )
