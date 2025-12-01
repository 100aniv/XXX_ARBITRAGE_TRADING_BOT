# -*- coding: utf-8 -*-
"""
D79: FX Converter

KRW ↔ USDT 환율 변환 모듈.

Features:
- Upbit/Binance ticker 기반 환율 추정
- Weighted average 환율 계산
- 환율 캐싱 (TTL)
"""

import logging
import time
from typing import Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FXRate:
    """
    환율 정보
    
    KRW/USDT 환율 (1 USDT = ? KRW)
    """
    rate: float  # 환율 (예: 1300.0 → 1 USDT = 1300 KRW)
    source: str  # 환율 출처 (예: "upbit_usdt", "binance_weighted", "fallback")
    timestamp: float  # 환율 조회 시각 (Unix timestamp)
    confidence: float  # 신뢰도 (0.0 ~ 1.0)


class FXConverter:
    """
    KRW ↔ USDT 환율 변환기
    
    환율 추정 방법:
    1. Upbit KRW-USDT ticker 사용 (가장 직접적)
    2. Upbit/Binance BTC price 비율 사용 (fallback)
    3. 고정 환율 사용 (emergency fallback)
    
    Example:
        converter = FXConverter()
        
        # USDT → KRW 변환
        krw_price = converter.usdt_to_krw(100.0)  # 100 USDT → 130,000 KRW
        
        # KRW → USDT 변환
        usdt_price = converter.krw_to_usdt(130000.0)  # 130,000 KRW → 100 USDT
    """
    
    DEFAULT_FALLBACK_RATE = 1300.0  # Emergency fallback (1 USDT = 1300 KRW)
    CACHE_TTL = 60.0  # 환율 캐시 TTL (초)
    
    def __init__(
        self,
        upbit_client=None,
        binance_client=None,
        fallback_rate: float = DEFAULT_FALLBACK_RATE,
    ):
        """
        Initialize FXConverter
        
        Args:
            upbit_client: Upbit data client (optional)
            binance_client: Binance data client (optional)
            fallback_rate: Emergency fallback 환율
        """
        self.upbit_client = upbit_client
        self.binance_client = binance_client
        self.fallback_rate = fallback_rate
        
        # Cache
        self.cached_rate: Optional[FXRate] = None
        self.cache_timestamp: float = 0.0
        
        logger.info(f"[FX_CONVERTER] Initialized (fallback_rate: {fallback_rate})")
    
    def get_fx_rate(self, force_refresh: bool = False) -> FXRate:
        """
        현재 KRW/USDT 환율 조회
        
        Args:
            force_refresh: 캐시 무시하고 재조회
        
        Returns:
            FXRate (1 USDT = ? KRW)
        
        Logic:
            1. 캐시 확인 (TTL 이내이면 캐시 사용)
            2. Upbit KRW-USDT ticker 조회
            3. Fallback: Upbit/Binance BTC price 비율
            4. Emergency fallback: 고정 환율
        """
        # 1. 캐시 확인
        if not force_refresh and self._is_cache_valid():
            logger.debug(f"[FX_CONVERTER] Using cached rate: {self.cached_rate.rate}")
            return self.cached_rate
        
        # 2. Upbit KRW-USDT ticker 조회 (가장 직접적)
        fx_rate = self._fetch_from_upbit_usdt()
        
        if fx_rate:
            self._update_cache(fx_rate)
            return fx_rate
        
        # 3. Fallback: Upbit/Binance BTC price 비율
        fx_rate = self._fetch_from_btc_ratio()
        
        if fx_rate:
            self._update_cache(fx_rate)
            return fx_rate
        
        # 4. Emergency fallback: 고정 환율
        logger.warning(f"[FX_CONVERTER] Using emergency fallback rate: {self.fallback_rate}")
        fx_rate = FXRate(
            rate=self.fallback_rate,
            source="fallback",
            timestamp=time.time(),
            confidence=0.5,  # Low confidence
        )
        self._update_cache(fx_rate)
        return fx_rate
    
    def usdt_to_krw(self, usdt_amount: float, force_refresh: bool = False) -> float:
        """
        USDT → KRW 변환
        
        Args:
            usdt_amount: USDT 금액
            force_refresh: 환율 재조회
        
        Returns:
            KRW 금액
        """
        fx_rate = self.get_fx_rate(force_refresh=force_refresh)
        krw_amount = usdt_amount * fx_rate.rate
        logger.debug(f"[FX_CONVERTER] {usdt_amount} USDT → {krw_amount:.2f} KRW (rate: {fx_rate.rate})")
        return krw_amount
    
    def krw_to_usdt(self, krw_amount: float, force_refresh: bool = False) -> float:
        """
        KRW → USDT 변환
        
        Args:
            krw_amount: KRW 금액
            force_refresh: 환율 재조회
        
        Returns:
            USDT 금액
        """
        fx_rate = self.get_fx_rate(force_refresh=force_refresh)
        usdt_amount = krw_amount / fx_rate.rate
        logger.debug(f"[FX_CONVERTER] {krw_amount} KRW → {usdt_amount:.2f} USDT (rate: {fx_rate.rate})")
        return usdt_amount
    
    def _fetch_from_upbit_usdt(self) -> Optional[FXRate]:
        """
        Upbit KRW-USDT ticker에서 환율 조회
        
        Returns:
            FXRate 또는 None
        """
        if not self.upbit_client:
            return None
        
        try:
            # Upbit KRW-USDT ticker 조회
            ticker = self.upbit_client.fetch_ticker("KRW-USDT")
            
            if not ticker or ticker.last_price <= 0:
                logger.warning("[FX_CONVERTER] Invalid Upbit USDT ticker")
                return None
            
            # 1 USDT = ticker.last_price KRW
            fx_rate = FXRate(
                rate=ticker.last_price,
                source="upbit_usdt",
                timestamp=time.time(),
                confidence=1.0,  # High confidence (direct ticker)
            )
            
            logger.debug(f"[FX_CONVERTER] Fetched from Upbit USDT: {fx_rate.rate}")
            return fx_rate
        
        except Exception as e:
            logger.error(f"[FX_CONVERTER] Failed to fetch from Upbit USDT: {e}")
            return None
    
    def _fetch_from_btc_ratio(self) -> Optional[FXRate]:
        """
        Upbit/Binance BTC price 비율로 환율 추정
        
        Logic:
            - Upbit BTC/KRW price = 50,000,000 KRW
            - Binance BTC/USDT price = 40,000 USDT
            - FX rate = 50,000,000 / 40,000 = 1,250 (1 USDT = 1,250 KRW)
        
        Returns:
            FXRate 또는 None
        """
        if not self.upbit_client or not self.binance_client:
            return None
        
        try:
            # Upbit BTC/KRW
            upbit_btc = self.upbit_client.fetch_ticker("KRW-BTC")
            
            # Binance BTC/USDT
            binance_btc = self.binance_client.fetch_ticker("BTCUSDT")
            
            if not upbit_btc or not binance_btc:
                logger.warning("[FX_CONVERTER] Failed to fetch BTC tickers")
                return None
            
            if upbit_btc.last_price <= 0 or binance_btc.last_price <= 0:
                logger.warning("[FX_CONVERTER] Invalid BTC prices")
                return None
            
            # Calculate FX rate
            # Upbit: 1 BTC = X KRW
            # Binance: 1 BTC = Y USDT
            # → 1 USDT = (X / Y) KRW
            fx_rate_value = upbit_btc.last_price / binance_btc.last_price
            
            fx_rate = FXRate(
                rate=fx_rate_value,
                source="btc_ratio",
                timestamp=time.time(),
                confidence=0.8,  # Medium confidence (indirect)
            )
            
            logger.debug(f"[FX_CONVERTER] Fetched from BTC ratio: {fx_rate.rate}")
            return fx_rate
        
        except Exception as e:
            logger.error(f"[FX_CONVERTER] Failed to fetch from BTC ratio: {e}")
            return None
    
    def _is_cache_valid(self) -> bool:
        """캐시 유효성 확인"""
        if not self.cached_rate:
            return False
        
        elapsed = time.time() - self.cache_timestamp
        return elapsed < self.CACHE_TTL
    
    def _update_cache(self, fx_rate: FXRate):
        """캐시 업데이트"""
        self.cached_rate = fx_rate
        self.cache_timestamp = time.time()
    
    def clear_cache(self):
        """캐시 초기화"""
        self.cached_rate = None
        self.cache_timestamp = 0.0
        logger.info("[FX_CONVERTER] Cache cleared")
    
    def get_cache_info(self) -> Dict[str, any]:
        """
        캐시 정보 반환
        
        Returns:
            {
                "cached_rate": float,
                "source": str,
                "age_seconds": float,
                "is_valid": bool,
            }
        """
        if not self.cached_rate:
            return {
                "cached_rate": None,
                "source": None,
                "age_seconds": 0.0,
                "is_valid": False,
            }
        
        age_seconds = time.time() - self.cache_timestamp
        is_valid = age_seconds < self.CACHE_TTL
        
        return {
            "cached_rate": self.cached_rate.rate,
            "source": self.cached_rate.source,
            "age_seconds": age_seconds,
            "is_valid": is_valid,
        }
