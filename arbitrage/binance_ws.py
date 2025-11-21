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
        
        # D71: Reconnect 설정
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 1  # 초기 backoff (초)
        self.max_reconnect_delay = 60  # 최대 backoff (초)
    
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
                
                # D71: 연결 종료 시 자동 재연결
                if self.running and not self.connected:
                    self._attempt_reconnect()
                    
            except Exception as e:
                logger.error(f"[BinanceWS] Run error: {e}")
                if self.running:
                    self._attempt_reconnect()
    
    def _on_open(self, ws):
        """연결 성공"""
        self.connected = True
        self.reconnect_attempts = 0  # D71: 재연결 성공 시 카운터 리셋
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
        
        # D71: 자동 재연결 (running=True인 경우만)
        if self.running:
            logger.info("[BinanceWS] Will attempt reconnect...")
    
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
    
    def _attempt_reconnect(self):
        """D71: 재연결 시도 (exponential backoff)"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"[BinanceWS] Max reconnect attempts ({self.max_reconnect_attempts}) reached")
            self.running = False
            return
        
        self.reconnect_attempts += 1
        
        # Exponential backoff: 1, 2, 4, 8, 16, 32, 60, 60, ...
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), self.max_reconnect_delay)
        
        logger.info(f"[BinanceWS] Reconnect attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay}s")
        time.sleep(delay)
    
    def force_reconnect(self):
        """D71: 강제 재연결 (테스트용)"""
        logger.info("[BinanceWS] Force reconnect requested")
        if self.ws:
            self.connected = False
            self.ws.close()
        # _run() 루프가 자동으로 재연결 시도
