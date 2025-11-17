#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance WebSocket Module (PHASE D6)
====================================

Binance 실시간 시세 수집 (WebSocket).
"""

import logging
import json
import threading
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import websocket
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False


class BinanceWebSocket:
    """Binance WebSocket 클라이언트"""
    
    def __init__(self, symbols: list, on_message: Callable):
        """
        Args:
            symbols: 구독할 심볼 리스트 (예: ['BTCUSDT', 'ETHUSDT'])
            on_message: 메시지 콜백 함수
        """
        self.symbols = [s.lower() for s in symbols]
        self.on_message = on_message
        self.ws = None
        self.connected = False
        self.running = False
        self.thread = None
        self.last_message_time = time.time()
    
    def connect(self) -> bool:
        """WebSocket 연결"""
        if not WS_AVAILABLE:
            logger.error("[BinanceWS] websocket library not available")
            return False
        
        try:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            logger.info("[BinanceWS] Connection started")
            return True
        except Exception as e:
            logger.error(f"[BinanceWS] Connection failed: {e}")
            return False
    
    def _run(self):
        """WebSocket 루프"""
        while self.running:
            try:
                # 여러 스트림 구독
                streams = [f"{s}@depth@100ms" for s in self.symbols]
                url = f"wss://stream.binance.com:9443/stream?streams={'/'.join(streams)}"
                
                self.ws = websocket.WebSocketApp(
                    url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws.on_open = self._on_open
                self.ws.run_forever()
            except Exception as e:
                logger.error(f"[BinanceWS] Run error: {e}")
                time.sleep(5)  # Backoff
    
    def _on_open(self, ws):
        """연결 성공"""
        self.connected = True
        logger.info("[BinanceWS] Connected")
    
    def _on_message(self, ws, message):
        """메시지 수신"""
        try:
            self.last_message_time = time.time()
            data = json.loads(message)
            
            if "data" in data:
                depth_data = data["data"]
                bids = depth_data.get("bids", [])
                asks = depth_data.get("asks", [])
                
                bid_price = float(bids[0][0]) if bids else 0.0
                ask_price = float(asks[0][0]) if asks else 0.0
                
                # 콜백 호출
                if self.on_message:
                    self.on_message({
                        "exchange": "binance",
                        "symbol": depth_data.get("s", ""),
                        "bid": bid_price,
                        "ask": ask_price,
                        "timestamp": datetime.now()
                    })
        except Exception as e:
            logger.debug(f"[BinanceWS] Message error: {e}")
    
    def _on_error(self, ws, error):
        """에러 처리"""
        logger.error(f"[BinanceWS] Error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """연결 종료"""
        self.connected = False
        logger.warning(f"[BinanceWS] Closed: {close_msg}")
    
    def disconnect(self):
        """연결 해제"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("[BinanceWS] Disconnected")
    
    def is_healthy(self) -> bool:
        """헬스 체크"""
        if not self.connected:
            return False
        elapsed = time.time() - self.last_message_time
        return elapsed < 30  # 30초 이상 메시지 없으면 unhealthy
