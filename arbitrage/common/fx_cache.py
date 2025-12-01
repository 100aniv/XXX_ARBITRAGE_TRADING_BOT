# -*- coding: utf-8 -*-
"""
D80-3: FX Rate Cache Layer

TTL 기반 In-memory FX Rate 캐싱.

Features:
- TTL expiration (기본 3초)
- Thread-safe (향후 Lock 추가 가능)
- In-memory (Redis 확장 가능)

Architecture:
    FxCache
        ↓
    _cache: Dict[(Currency, Currency), FxCacheEntry]
        ↓
    FxCacheEntry(rate, updated_at)

Usage:
    cache = FxCache(ttl_seconds=3.0)
    cache.set(Currency.USD, Currency.KRW, Decimal("1420.50"))
    rate = cache.get(Currency.USD, Currency.KRW)  # → Decimal("1420.50")
    
    # 3초 후
    rate = cache.get(Currency.USD, Currency.KRW)  # → None (expired)
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Tuple

from .currency import Currency

logger = logging.getLogger(__name__)


# =============================================================================
# FxCacheEntry
# =============================================================================

@dataclass
class FxCacheEntry:
    """
    FX Cache 엔트리.
    
    Attributes:
        rate: 환율
        updated_at: 업데이트 시각 (Unix timestamp)
    """
    rate: Decimal
    updated_at: float


# =============================================================================
# FxCache
# =============================================================================

class FxCache:
    """
    FX Rate TTL Cache.
    
    Features:
    - TTL 기반 expiration (기본 3초)
    - Thread-safe (향후 Lock 추가 가능)
    - In-memory (Redis 확장 가능)
    
    Example:
        >>> cache = FxCache(ttl_seconds=3.0)
        >>> cache.set(Currency.USD, Currency.KRW, Decimal("1420.50"))
        >>> cache.get(Currency.USD, Currency.KRW)
        Decimal('1420.50')
        >>> 
        >>> # 3초 후
        >>> cache.get(Currency.USD, Currency.KRW)
        None  # expired
    """
    
    def __init__(self, ttl_seconds: float = 3.0):
        """
        Args:
            ttl_seconds: TTL (초 단위)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[Tuple[Currency, Currency], FxCacheEntry] = {}
        
        logger.debug(f"[FX_CACHE] Initialized with TTL={ttl_seconds}s")
    
    def get(self, base: Currency, quote: Currency) -> Optional[Decimal]:
        """
        캐시에서 환율 조회.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            환율 (TTL 유효) 또는 None (캐시 miss/expired)
        
        Example:
            >>> cache.get(Currency.USD, Currency.KRW)
            Decimal('1420.50')  # hit
            >>> cache.get(Currency.BTC, Currency.USD)
            None  # miss
        """
        key = (base, quote)
        entry = self._cache.get(key)
        
        if entry is None:
            logger.debug(f"[FX_CACHE] MISS: {base.value}→{quote.value}")
            return None
        
        # TTL 체크
        age = time.time() - entry.updated_at
        if age > self.ttl_seconds:
            # Expired, 캐시 삭제
            logger.debug(
                f"[FX_CACHE] EXPIRED: {base.value}→{quote.value} "
                f"(age={age:.1f}s > TTL={self.ttl_seconds}s)"
            )
            del self._cache[key]
            return None
        
        logger.debug(
            f"[FX_CACHE] HIT: {base.value}→{quote.value} = {entry.rate} "
            f"(age={age:.1f}s)"
        )
        return entry.rate
    
    def set(
        self,
        base: Currency,
        quote: Currency,
        rate: Decimal,
        updated_at: Optional[float] = None
    ) -> None:
        """
        캐시에 환율 저장.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
            rate: 환율
            updated_at: 업데이트 시각 (None이면 현재 시각)
        
        Example:
            >>> cache.set(Currency.USD, Currency.KRW, Decimal("1420.50"))
            >>> cache.get(Currency.USD, Currency.KRW)
            Decimal('1420.50')
        """
        key = (base, quote)
        timestamp = updated_at or time.time()
        
        self._cache[key] = FxCacheEntry(
            rate=rate,
            updated_at=timestamp
        )
        
        logger.debug(
            f"[FX_CACHE] SET: {base.value}→{quote.value} = {rate} "
            f"(updated_at={timestamp:.0f})"
        )
    
    def get_updated_at(self, base: Currency, quote: Currency) -> Optional[float]:
        """
        환율 업데이트 시각 조회.
        
        Args:
            base: 기준 통화
            quote: 목표 통화
        
        Returns:
            업데이트 시각 (Unix timestamp) 또는 None (캐시에 없음)
        
        Example:
            >>> cache.get_updated_at(Currency.USD, Currency.KRW)
            1701449123.45
        """
        key = (base, quote)
        entry = self._cache.get(key)
        return entry.updated_at if entry else None
    
    def clear(self) -> None:
        """
        캐시 전체 삭제.
        
        Example:
            >>> cache.clear()
            >>> cache.size()
            0
        """
        self._cache.clear()
        logger.debug("[FX_CACHE] Cache cleared")
    
    def size(self) -> int:
        """
        캐시 엔트리 개수.
        
        Returns:
            엔트리 개수
        
        Example:
            >>> cache.set(Currency.USD, Currency.KRW, Decimal("1420"))
            >>> cache.set(Currency.USDT, Currency.KRW, Decimal("1420"))
            >>> cache.size()
            2
        """
        return len(self._cache)
