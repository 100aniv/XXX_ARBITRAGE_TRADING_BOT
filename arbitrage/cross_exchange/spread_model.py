# -*- coding: utf-8 -*-
"""
D79: Spread Model

Cross-exchange spread 계산 모델.

Features:
- Upbit KRW → USDT 변환
- Binance USDT 가격과 비교
- Spread 계산 (absolute, percentage)
- Direction (positive/negative)
"""

import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SpreadDirection(str, Enum):
    """Spread 방향"""
    POSITIVE = "positive"  # Upbit > Binance (Upbit에서 sell, Binance에서 buy)
    NEGATIVE = "negative"  # Upbit < Binance (Upbit에서 buy, Binance에서 sell)
    NEUTRAL = "neutral"    # Upbit == Binance (spread ~0)


@dataclass
class CrossSpread:
    """
    Cross-exchange spread 정보
    
    Upbit(KRW) vs Binance(USDT) 가격 차이.
    """
    symbol_mapping: any  # SymbolMapping
    fx_rate: float  # KRW/USDT 환율 (1 USDT = ? KRW)
    
    # Prices
    upbit_price_krw: float  # Upbit 가격 (KRW)
    binance_price_usdt: float  # Binance 가격 (USDT)
    binance_price_krw: float  # Binance 가격을 KRW로 변환한 값
    
    # Spread
    spread_krw: float  # Spread (KRW) = upbit_price_krw - binance_price_krw
    spread_usdt: float  # Spread (USDT) = spread_krw / fx_rate
    spread_percent: float  # Spread (%) = (spread_krw / binance_price_krw) * 100
    
    # Direction
    direction: SpreadDirection
    
    # Timestamp
    timestamp: float
    
    def is_profitable(self, min_spread_percent: float = 0.5) -> bool:
        """
        수익성 판단
        
        Args:
            min_spread_percent: 최소 spread threshold (%)
        
        Returns:
            True if abs(spread_percent) >= min_spread_percent
        """
        return abs(self.spread_percent) >= min_spread_percent
    
    def get_arbitrage_action(self) -> str:
        """
        아비트라지 액션 제안
        
        Returns:
            "upbit_sell_binance_buy" | "upbit_buy_binance_sell" | "none"
        """
        if self.direction == SpreadDirection.POSITIVE:
            return "upbit_sell_binance_buy"
        elif self.direction == SpreadDirection.NEGATIVE:
            return "upbit_buy_binance_sell"
        else:
            return "none"


class SpreadModel:
    """
    Cross-exchange spread 계산 모델
    
    Upbit(KRW) vs Binance(USDT) 가격 차이를 계산하고,
    아비트라지 기회를 판단한다.
    
    Example:
        model = SpreadModel(fx_converter=fx_converter)
        
        spread = model.calculate_spread(
            symbol_mapping=mapping,
            upbit_price_krw=50000000.0,  # Upbit BTC: 50M KRW
            binance_price_usdt=40000.0,  # Binance BTC: 40K USDT
        )
        
        if spread.is_profitable(min_spread_percent=0.5):
            print(f"Arbitrage opportunity: {spread.get_arbitrage_action()}")
    """
    
    NEUTRAL_THRESHOLD_PERCENT = 0.1  # Spread < 0.1%이면 neutral로 간주
    
    def __init__(self, fx_converter):
        """
        Initialize SpreadModel
        
        Args:
            fx_converter: FXConverter instance
        """
        self.fx_converter = fx_converter
        logger.info("[SPREAD_MODEL] Initialized")
    
    def calculate_spread(
        self,
        symbol_mapping: any,
        upbit_price_krw: float,
        binance_price_usdt: float,
        timestamp: float = None,
    ) -> CrossSpread:
        """
        Cross-exchange spread 계산
        
        Args:
            symbol_mapping: SymbolMapping (매핑 정보)
            upbit_price_krw: Upbit 가격 (KRW)
            binance_price_usdt: Binance 가격 (USDT)
            timestamp: Timestamp (기본: 현재 시각)
        
        Returns:
            CrossSpread
        
        Logic:
            1. FX rate 조회 (KRW/USDT)
            2. Binance price를 KRW로 변환
            3. Spread 계산
            4. Direction 판단
        """
        import time
        
        if timestamp is None:
            timestamp = time.time()
        
        # 1. FX rate 조회
        fx_rate_obj = self.fx_converter.get_fx_rate()
        fx_rate = fx_rate_obj.rate
        
        # 2. Binance price를 KRW로 변환
        binance_price_krw = binance_price_usdt * fx_rate
        
        # 3. Spread 계산
        spread_krw = upbit_price_krw - binance_price_krw
        spread_usdt = spread_krw / fx_rate
        
        # Avoid division by zero
        if binance_price_krw > 0:
            spread_percent = (spread_krw / binance_price_krw) * 100.0
        else:
            spread_percent = 0.0
        
        # 4. Direction 판단
        if abs(spread_percent) < self.NEUTRAL_THRESHOLD_PERCENT:
            direction = SpreadDirection.NEUTRAL
        elif spread_krw > 0:
            direction = SpreadDirection.POSITIVE
        else:
            direction = SpreadDirection.NEGATIVE
        
        # Create CrossSpread
        cross_spread = CrossSpread(
            symbol_mapping=symbol_mapping,
            fx_rate=fx_rate,
            upbit_price_krw=upbit_price_krw,
            binance_price_usdt=binance_price_usdt,
            binance_price_krw=binance_price_krw,
            spread_krw=spread_krw,
            spread_usdt=spread_usdt,
            spread_percent=spread_percent,
            direction=direction,
            timestamp=timestamp,
        )
        
        logger.debug(
            f"[SPREAD_MODEL] {symbol_mapping.upbit_symbol}: "
            f"spread={spread_percent:.2f}%, direction={direction}"
        )
        
        return cross_spread
    
    def calculate_spread_from_tickers(
        self,
        symbol_mapping: any,
        upbit_ticker: any,
        binance_ticker: any,
    ) -> Optional[CrossSpread]:
        """
        Ticker 객체에서 직접 spread 계산
        
        Args:
            symbol_mapping: SymbolMapping
            upbit_ticker: Upbit ticker (last_price 필드 필요)
            binance_ticker: Binance ticker (last_price 필드 필요)
        
        Returns:
            CrossSpread 또는 None (ticker가 invalid한 경우)
        """
        if not upbit_ticker or not binance_ticker:
            logger.warning("[SPREAD_MODEL] Invalid tickers")
            return None
        
        upbit_price_krw = upbit_ticker.last_price
        binance_price_usdt = binance_ticker.last_price
        
        if upbit_price_krw <= 0 or binance_price_usdt <= 0:
            logger.warning("[SPREAD_MODEL] Invalid ticker prices")
            return None
        
        return self.calculate_spread(
            symbol_mapping=symbol_mapping,
            upbit_price_krw=upbit_price_krw,
            binance_price_usdt=binance_price_usdt,
        )
