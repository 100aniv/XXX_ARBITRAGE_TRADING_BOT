#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arbitrage Signal Engine (PHASE D7)
===================================

실시간 차익 신호 계산 및 거래 기회 판단.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ArbitrageSignal:
    """차익 신호"""
    
    def __init__(
        self,
        opportunity_type: str,  # "upbit_buy_binance_sell" | "binance_buy_upbit_sell"
        spread_pct: float,  # 차익률 (%)
        buy_exchange: str,  # 매수 거래소
        buy_price: float,  # 매수가
        sell_exchange: str,  # 매도 거래소
        sell_price: float,  # 매도가
        profit_krw: float,  # 예상 수익 (KRW)
        profit_pct: float,  # 수익률 (%)
        confidence: float,  # 신뢰도 (0-1)
        timestamp: datetime = None
    ):
        self.opportunity_type = opportunity_type
        self.spread_pct = spread_pct
        self.buy_exchange = buy_exchange
        self.buy_price = buy_price
        self.sell_exchange = sell_exchange
        self.sell_price = sell_price
        self.profit_krw = profit_krw
        self.profit_pct = profit_pct
        self.confidence = confidence
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "opportunity_type": self.opportunity_type,
            "spread_pct": self.spread_pct,
            "buy_exchange": self.buy_exchange,
            "buy_price": self.buy_price,
            "sell_exchange": self.sell_exchange,
            "sell_price": self.sell_price,
            "profit_krw": self.profit_krw,
            "profit_pct": self.profit_pct,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }


class ArbitrageSignalEngine:
    """차익 신호 엔진"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: 설정 딕셔너리
        """
        self.config = config or {}
        
        # 최소 차익 조건
        self.min_spread_pct = self.config.get("min_spread_pct", 0.1)  # 0.1%
        
        # 수수료 (%)
        self.upbit_fee = self.config.get("upbit_fee", 0.25)  # 0.25%
        self.binance_fee = self.config.get("binance_fee", 0.1)  # 0.1%
        
        # 슬리피지 (%)
        self.slippage_pct = self.config.get("slippage_pct", 0.1)  # 0.1%
        
        # 최소 거래량
        self.min_trade_amount_krw = self.config.get("min_trade_amount_krw", 10000)
        
        self.last_signal: Optional[ArbitrageSignal] = None
    
    def compute_signal(self, ticker: Dict[str, float]) -> Optional[ArbitrageSignal]:
        """
        차익 신호 계산
        
        Args:
            ticker: {
                "upbit_bid": float,
                "upbit_ask": float,
                "binance_bid": float,
                "binance_ask": float,
                "btc_krw_rate": float (optional)
            }
        
        Returns:
            ArbitrageSignal 또는 None
        """
        try:
            upbit_bid = ticker.get("upbit_bid", 0)
            upbit_ask = ticker.get("upbit_ask", 0)
            binance_bid = ticker.get("binance_bid", 0)
            binance_ask = ticker.get("binance_ask", 0)
            
            if not all([upbit_bid, upbit_ask, binance_bid, binance_ask]):
                return None
            
            # 시나리오 1: Upbit에서 사서 Binance에서 팔기
            signal1 = self._check_opportunity(
                buy_exchange="upbit",
                buy_price=upbit_ask,
                sell_exchange="binance",
                sell_price=binance_bid,
                opportunity_type="upbit_buy_binance_sell"
            )
            
            # 시나리오 2: Binance에서 사서 Upbit에서 팔기
            signal2 = self._check_opportunity(
                buy_exchange="binance",
                buy_price=binance_ask,
                sell_exchange="upbit",
                sell_price=upbit_bid,
                opportunity_type="binance_buy_upbit_sell"
            )
            
            # 더 나은 신호 선택
            best_signal = None
            if signal1 and signal2:
                best_signal = signal1 if signal1.profit_pct > signal2.profit_pct else signal2
            elif signal1:
                best_signal = signal1
            elif signal2:
                best_signal = signal2
            
            if best_signal:
                self.last_signal = best_signal
                logger.info(
                    f"[SIGNAL] {best_signal.opportunity_type}: "
                    f"spread={best_signal.spread_pct:.2f}%, "
                    f"profit={best_signal.profit_pct:.2f}%"
                )
            
            return best_signal
        except Exception as e:
            logger.error(f"[SignalEngine] Compute error: {e}")
            return None
    
    def _check_opportunity(
        self,
        buy_exchange: str,
        buy_price: float,
        sell_exchange: str,
        sell_price: float,
        opportunity_type: str
    ) -> Optional[ArbitrageSignal]:
        """
        거래 기회 판단
        
        Args:
            buy_exchange: 매수 거래소
            buy_price: 매수가
            sell_exchange: 매도 거래소
            sell_price: 매도가
            opportunity_type: 기회 유형
        
        Returns:
            ArbitrageSignal 또는 None
        """
        if buy_price <= 0 or sell_price <= 0:
            return None
        
        # 기본 스프레드
        spread_pct = ((sell_price - buy_price) / buy_price) * 100
        
        # 수수료 계산
        buy_fee = self._get_fee(buy_exchange)
        sell_fee = self._get_fee(sell_exchange)
        total_fee_pct = buy_fee + sell_fee
        
        # 슬리피지 반영
        net_spread_pct = spread_pct - total_fee_pct - self.slippage_pct
        
        # 최소 차익 조건 확인
        if net_spread_pct < self.min_spread_pct:
            return None
        
        # 거래량 확인
        if buy_price < self.min_trade_amount_krw:
            return None
        
        # 신뢰도 계산 (spread가 클수록 높음)
        confidence = min(1.0, net_spread_pct / 2.0)
        
        # 수익 계산 (1 BTC 기준)
        profit_krw = sell_price - buy_price - (buy_price * total_fee_pct / 100)
        profit_pct = net_spread_pct
        
        return ArbitrageSignal(
            opportunity_type=opportunity_type,
            spread_pct=spread_pct,
            buy_exchange=buy_exchange,
            buy_price=buy_price,
            sell_exchange=sell_exchange,
            sell_price=sell_price,
            profit_krw=profit_krw,
            profit_pct=profit_pct,
            confidence=confidence
        )
    
    def _get_fee(self, exchange: str) -> float:
        """거래소 수수료 조회"""
        if exchange == "upbit":
            return self.upbit_fee
        elif exchange == "binance":
            return self.binance_fee
        return 0.0
