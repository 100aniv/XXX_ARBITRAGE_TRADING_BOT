#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upbit WebSocket Module (PHASE D6)
==================================

Upbit 실시간 시세 수집 (WebSocket).
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


class UpbitWebSocket:
    """Upbit WebSocket 클라이언트"""
    
    def __init__(self, symbols: list, on_message: Callable):
        """
        Args:
            symbols: 구독할 심볼 리스트 (예: ['BTC-KRW', 'ETH-KRW'])
            on_message: 메시지 콜백 함수
        """
        self.symbols = symbols
        self.on_message = on_message
        self.ws = None
        self.connected = False
        self.running = False
        self.thread = None
        self.url = "wss://api.upbit.com/websocket/v1"
        self.last_message_time = time.time()
    
    def connect(self) -> bool:
        """WebSocket 연결"""
        if not WS_AVAILABLE:
            logger.error("[UpbitWS] websocket library not available")
            return False
        
        try:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            logger.info("[UpbitWS] Connection started")
            return True
        except Exception as e:
            logger.error(f"[UpbitWS] Connection failed: {e}")
            return False
    
    def _run(self):
        """WebSocket 루프"""
        while self.running:
            try:
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self.ws.on_open = self._on_open
                self.ws.run_forever()
            except Exception as e:
                logger.error(f"[UpbitWS] Run error: {e}")
                time.sleep(5)  # Backoff
    
    def _on_open(self, ws):
        """연결 성공"""
        self.connected = True
        logger.info("[UpbitWS] Connected")
        
        # 구독 메시지 전송
        for symbol in self.symbols:
            msg = {
                "type": "orderbook",
                "codes": [symbol]
            }
            ws.send(json.dumps(msg))
    
    def _on_message(self, ws, message):
        """메시지 수신"""
        try:
            self.last_message_time = time.time()
            data = json.loads(message)
            
            # 콜백 호출
            if self.on_message:
                self.on_message({
                    "exchange": "upbit",
                    "symbol": data.get("code", ""),
                    "bid": float(data.get("orderbook_units", [{}])[0].get("bid_price", 0)),
                    "ask": float(data.get("orderbook_units", [{}])[0].get("ask_price", 0)),
                    "timestamp": datetime.now()
                })
        except Exception as e:
            logger.debug(f"[UpbitWS] Message error: {e}")
    
    def _on_error(self, ws, error):
        """에러 처리"""
        logger.error(f"[UpbitWS] Error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """연결 종료"""
        self.connected = False
        logger.warning(f"[UpbitWS] Closed: {close_msg}")
    
    def disconnect(self):
        """연결 해제"""
        self.running = False
        if self.ws:
            self.ws.close()
        logger.info("[UpbitWS] Disconnected")
    
    def is_healthy(self) -> bool:
        """헬스 체크"""
        if not self.connected:
            return False
        elapsed = time.time() - self.last_message_time
        return elapsed < 30  # 30초 이상 메시지 없으면 unhealthy
