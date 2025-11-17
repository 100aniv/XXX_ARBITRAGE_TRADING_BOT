#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket Manager (PHASE D6)
=============================

여러 WebSocket 클라이언트 관리 및 price aggregation.
"""

import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

try:
    from arbitrage.upbit_ws import UpbitWebSocket
    from arbitrage.binance_ws import BinanceWebSocket
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False


class PriceAggregator:
    """실시간 시세 집계"""
    
    def __init__(self):
        """초기화"""
        self.latest_prices: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.callbacks: list = []
    
    def on_price_update(self, data: Dict[str, Any]):
        """시세 업데이트"""
        symbol = data.get("symbol", "")
        exchange = data.get("exchange", "")
        
        key = f"{exchange}:{symbol}"
        self.latest_prices[key] = data
        
        # 콜백 호출
        for callback in self.callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.debug(f"[Aggregator] Callback error: {e}")
    
    def register_callback(self, callback: Callable):
        """콜백 등록"""
        self.callbacks.append(callback)
    
    def get_latest(self, exchange: str, symbol: str) -> Optional[Dict[str, Any]]:
        """최신 시세 조회"""
        key = f"{exchange}:{symbol}"
        return self.latest_prices.get(key)


class WebSocketManager:
    """WebSocket 매니저"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 설정 딕셔너리
        """
        self.config = config
        self.upbit_ws: Optional[UpbitWebSocket] = None
        self.binance_ws: Optional[BinanceWebSocket] = None
        self.aggregator = PriceAggregator()
        self.enabled = config.get("ws_enabled", False)
    
    def start(self) -> bool:
        """WebSocket 시작"""
        if not self.enabled or not WS_AVAILABLE:
            logger.info("[WSManager] WebSocket disabled or not available")
            return False
        
        try:
            # Upbit WebSocket
            upbit_symbols = self.config.get("upbit_symbols", ["BTC-KRW", "ETH-KRW"])
            self.upbit_ws = UpbitWebSocket(upbit_symbols, self.aggregator.on_price_update)
            if not self.upbit_ws.connect():
                logger.warning("[WSManager] Upbit WS connection failed")
            
            # Binance WebSocket
            binance_symbols = self.config.get("binance_symbols", ["BTCUSDT", "ETHUSDT"])
            self.binance_ws = BinanceWebSocket(binance_symbols, self.aggregator.on_price_update)
            if not self.binance_ws.connect():
                logger.warning("[WSManager] Binance WS connection failed")
            
            logger.info("[WSManager] WebSocket manager started")
            return True
        except Exception as e:
            logger.error(f"[WSManager] Start failed: {e}")
            return False
    
    def stop(self):
        """WebSocket 중지"""
        if self.upbit_ws:
            self.upbit_ws.disconnect()
        if self.binance_ws:
            self.binance_ws.disconnect()
        logger.info("[WSManager] WebSocket manager stopped")
    
    def is_healthy(self) -> bool:
        """헬스 체크"""
        if not self.enabled:
            return True
        
        upbit_ok = self.upbit_ws and self.upbit_ws.is_healthy()
        binance_ok = self.binance_ws and self.binance_ws.is_healthy()
        
        return upbit_ok or binance_ok  # 하나라도 정상이면 OK
    
    def register_callback(self, callback: Callable):
        """콜백 등록"""
        self.aggregator.register_callback(callback)


# 글로벌 인스턴스
_ws_manager: Optional[WebSocketManager] = None


def get_ws_manager(config: Dict[str, Any]) -> WebSocketManager:
    """WebSocket 매니저 싱글톤"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager(config)
    return _ws_manager
