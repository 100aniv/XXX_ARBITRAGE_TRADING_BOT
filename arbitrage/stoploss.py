#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stop-Loss Engine (PHASE D9)
============================

손절매 자동화 및 위험 관리.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class StopLossEngine:
    """손절매 엔진"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 손절매 설정
        """
        self.config = config or {}
        
        # 손절매 설정
        self.enabled = self.config.get("enabled", True)
        self.mode = self.config.get("mode", "static")  # static | dynamic
        self.static_pct = self.config.get("static_pct", 1.2)  # 1.2%
        self.atr_window = self.config.get("atr_window", 20)
        
        # 통계
        self.stoploss_triggers = 0
        self.price_history: Dict[str, List[float]] = {}
    
    def check_stoploss(
        self,
        position: Any,  # Position 객체
        current_price: float
    ) -> bool:
        """
        손절매 체크
        
        Args:
            position: Position 객체
            current_price: 현재가
        
        Returns:
            손절매 발동 여부
        """
        if not self.enabled:
            return False
        
        try:
            if self.mode == "static":
                return self._check_static_stoploss(position, current_price)
            elif self.mode == "dynamic":
                return self._check_dynamic_stoploss(position, current_price)
            
            return False
        
        except Exception as e:
            logger.error(f"[StopLossEngine] Check error: {e}")
            return False
    
    def _check_static_stoploss(
        self,
        position: Any,
        current_price: float
    ) -> bool:
        """정적 손절매 체크"""
        
        if position.side == "BUY":
            # 매수 포지션: 손절매 = 진입가 * (1 - static_pct%)
            stoploss_price = position.entry_price * (1 - self.static_pct / 100)
            if current_price <= stoploss_price:
                logger.warning(
                    f"[StopLossEngine] Static SL triggered for {position.symbol}: "
                    f"current={current_price:.0f}₩ <= sl={stoploss_price:.0f}₩"
                )
                self.stoploss_triggers += 1
                return True
        
        else:  # SELL
            # 매도 포지션: 손절매 = 진입가 * (1 + static_pct%)
            stoploss_price = position.entry_price * (1 + self.static_pct / 100)
            if current_price >= stoploss_price:
                logger.warning(
                    f"[StopLossEngine] Static SL triggered for {position.symbol}: "
                    f"current={current_price:.0f}₩ >= sl={stoploss_price:.0f}₩"
                )
                self.stoploss_triggers += 1
                return True
        
        return False
    
    def _check_dynamic_stoploss(
        self,
        position: Any,
        current_price: float
    ) -> bool:
        """동적 손절매 체크 (ATR 기반)"""
        
        # 간단한 구현: 최근 가격 변동성 기반
        symbol = position.symbol
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(current_price)
        
        # 윈도우 크기 유지
        if len(self.price_history[symbol]) > self.atr_window:
            self.price_history[symbol].pop(0)
        
        # 최소 데이터 필요
        if len(self.price_history[symbol]) < self.atr_window:
            return False
        
        # 간단한 ATR 계산 (표준편차 기반)
        prices = self.price_history[symbol]
        avg_price = sum(prices) / len(prices)
        variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
        atr = (variance ** 0.5) * 2  # 표준편차 * 2
        
        # 손절매 체크
        if position.side == "BUY":
            stoploss_price = position.entry_price - atr
            if current_price <= stoploss_price:
                logger.warning(
                    f"[StopLossEngine] Dynamic SL triggered for {position.symbol}: "
                    f"current={current_price:.0f}₩ <= sl={stoploss_price:.0f}₩ (atr={atr:.0f})"
                )
                self.stoploss_triggers += 1
                return True
        
        else:  # SELL
            stoploss_price = position.entry_price + atr
            if current_price >= stoploss_price:
                logger.warning(
                    f"[StopLossEngine] Dynamic SL triggered for {position.symbol}: "
                    f"current={current_price:.0f}₩ >= sl={stoploss_price:.0f}₩ (atr={atr:.0f})"
                )
                self.stoploss_triggers += 1
                return True
        
        return False
    
    def get_stoploss_price(
        self,
        position: Any,
        current_price: float = None
    ) -> float:
        """손절매가 조회"""
        
        if self.mode == "static":
            if position.side == "BUY":
                return position.entry_price * (1 - self.static_pct / 100)
            else:
                return position.entry_price * (1 + self.static_pct / 100)
        
        elif self.mode == "dynamic" and current_price:
            # 동적 계산
            symbol = position.symbol
            if symbol in self.price_history and len(self.price_history[symbol]) >= self.atr_window:
                prices = self.price_history[symbol]
                avg_price = sum(prices) / len(prices)
                variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
                atr = (variance ** 0.5) * 2
                
                if position.side == "BUY":
                    return position.entry_price - atr
                else:
                    return position.entry_price + atr
        
        return position.entry_price
    
    def get_stats(self) -> Dict[str, Any]:
        """손절매 통계"""
        return {
            "stoploss_triggers": self.stoploss_triggers,
            "mode": self.mode,
            "enabled": self.enabled
        }
