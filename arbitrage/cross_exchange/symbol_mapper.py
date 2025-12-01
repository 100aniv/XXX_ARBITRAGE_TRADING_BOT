# -*- coding: utf-8 -*-
"""
D79: Symbol Mapper

Upbit ↔ Binance 심볼 매핑 엔진.

Features:
- 자동 매핑 (BTC/KRW ↔ BTCUSDT)
- 매핑 실패 리포트
- 200+ 주요 심볼 지원
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Exchange(str, Enum):
    """거래소 식별자"""
    UPBIT = "upbit"
    BINANCE = "binance"


@dataclass
class SymbolMapping:
    """
    심볼 매핑 정보
    
    Upbit: "KRW-BTC" → Binance: "BTCUSDT"
    """
    upbit_symbol: str  # "KRW-BTC"
    binance_symbol: str  # "BTCUSDT"
    base_asset: str  # "BTC"
    upbit_quote: str  # "KRW"
    binance_quote: str  # "USDT"
    confidence: float  # 매핑 신뢰도 (0.0 ~ 1.0)


class SymbolMapper:
    """
    Upbit ↔ Binance 심볼 자동 매핑 엔진
    
    주요 기능:
    1. 자동 매핑 (base asset 기반)
    2. 수동 예외 처리 (USDT → USDC 등)
    3. 매핑 통계 및 실패 리포트
    
    Example:
        mapper = SymbolMapper()
        mapping = mapper.map_upbit_to_binance("KRW-BTC")
        # SymbolMapping(upbit_symbol="KRW-BTC", binance_symbol="BTCUSDT", ...)
    """
    
    # 수동 예외 매핑 (특수 케이스)
    MANUAL_OVERRIDES: Dict[str, str] = {
        # Upbit symbol → Binance symbol
        "KRW-USDT": "USDTUSDC",  # USDT/KRW → USDT/USDC (proxy)
        "KRW-USDC": "USDCUSDT",  # USDC/KRW → USDC/USDT
        # ... 필요시 추가
    }
    
    def __init__(self):
        """Initialize SymbolMapper"""
        self.mapping_cache: Dict[str, SymbolMapping] = {}
        self.failed_mappings: List[str] = []
        logger.info("[SYMBOL_MAPPER] Initialized")
    
    def map_upbit_to_binance(self, upbit_symbol: str) -> Optional[SymbolMapping]:
        """
        Upbit 심볼을 Binance 심볼로 매핑
        
        Args:
            upbit_symbol: Upbit 심볼 (예: "KRW-BTC", "BTC-ETH")
        
        Returns:
            SymbolMapping 또는 None (매핑 실패 시)
        
        Logic:
            1. 캐시 확인
            2. 수동 예외 처리
            3. 자동 매핑 (base asset 기반)
            4. 검증 (Binance에서 실제 존재 여부는 외부에서 확인)
        """
        # 1. 캐시 확인
        if upbit_symbol in self.mapping_cache:
            return self.mapping_cache[upbit_symbol]
        
        # 2. 수동 예외 처리
        if upbit_symbol in self.MANUAL_OVERRIDES:
            binance_symbol = self.MANUAL_OVERRIDES[upbit_symbol]
            mapping = self._create_mapping_from_manual(upbit_symbol, binance_symbol)
            self.mapping_cache[upbit_symbol] = mapping
            return mapping
        
        # 3. 자동 매핑
        mapping = self._auto_map_upbit_to_binance(upbit_symbol)
        
        if mapping:
            self.mapping_cache[upbit_symbol] = mapping
            return mapping
        else:
            self.failed_mappings.append(upbit_symbol)
            logger.warning(f"[SYMBOL_MAPPER] Failed to map: {upbit_symbol}")
            return None
    
    def map_binance_to_upbit(self, binance_symbol: str) -> Optional[SymbolMapping]:
        """
        Binance 심볼을 Upbit 심볼로 매핑
        
        Args:
            binance_symbol: Binance 심볼 (예: "BTCUSDT")
        
        Returns:
            SymbolMapping 또는 None (매핑 실패 시)
        
        Note:
            Binance → Upbit 매핑은 reverse lookup을 통해 수행.
            대부분의 경우 Upbit → Binance 방향이 primary.
        """
        # Reverse lookup in cache
        for mapping in self.mapping_cache.values():
            if mapping.binance_symbol == binance_symbol:
                return mapping
        
        # Auto reverse mapping
        mapping = self._auto_map_binance_to_upbit(binance_symbol)
        
        if mapping:
            self.mapping_cache[mapping.upbit_symbol] = mapping
            return mapping
        else:
            logger.warning(f"[SYMBOL_MAPPER] Failed to reverse map: {binance_symbol}")
            return None
    
    def _auto_map_upbit_to_binance(self, upbit_symbol: str) -> Optional[SymbolMapping]:
        """
        Upbit → Binance 자동 매핑 로직
        
        Upbit format: "QUOTE-BASE" (예: "KRW-BTC", "BTC-ETH")
        Binance format: "BASEQUOTE" (예: "BTCUSDT", "ETHBTC")
        
        Logic:
            - Upbit KRW market → Binance USDT market
            - Upbit BTC market → Binance BTC market
            - ...
        """
        try:
            # Parse Upbit symbol
            parts = upbit_symbol.split("-")
            if len(parts) != 2:
                logger.error(f"[SYMBOL_MAPPER] Invalid Upbit symbol format: {upbit_symbol}")
                return None
            
            upbit_quote, base_asset = parts  # e.g., "KRW", "BTC"
            
            # Map Upbit quote to Binance quote
            binance_quote = self._map_quote_asset(upbit_quote)
            
            if not binance_quote:
                logger.warning(f"[SYMBOL_MAPPER] Unsupported Upbit quote: {upbit_quote}")
                return None
            
            # Construct Binance symbol
            binance_symbol = f"{base_asset}{binance_quote}"
            
            # Create mapping
            mapping = SymbolMapping(
                upbit_symbol=upbit_symbol,
                binance_symbol=binance_symbol,
                base_asset=base_asset,
                upbit_quote=upbit_quote,
                binance_quote=binance_quote,
                confidence=1.0,  # Auto-mapped with high confidence
            )
            
            logger.debug(f"[SYMBOL_MAPPER] Auto-mapped: {upbit_symbol} → {binance_symbol}")
            return mapping
        
        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] Auto-mapping failed for {upbit_symbol}: {e}")
            return None
    
    def _auto_map_binance_to_upbit(self, binance_symbol: str) -> Optional[SymbolMapping]:
        """
        Binance → Upbit 자동 매핑 로직 (reverse)
        
        Binance format: "BASEQUOTE" (예: "BTCUSDT")
        Upbit format: "QUOTE-BASE" (예: "KRW-BTC")
        
        Note:
            Binance는 quote asset가 명확하지 않으므로 heuristic 사용.
            USDT, BTC, ETH, BNB 등을 quote로 간주.
        """
        try:
            # Detect quote asset (heuristic)
            quote_candidates = ["USDT", "BUSD", "BTC", "ETH", "BNB", "USDC"]
            
            base_asset = None
            binance_quote = None
            
            for quote in quote_candidates:
                if binance_symbol.endswith(quote):
                    base_asset = binance_symbol[:-len(quote)]
                    binance_quote = quote
                    break
            
            if not base_asset or not binance_quote:
                logger.warning(f"[SYMBOL_MAPPER] Cannot detect quote asset for {binance_symbol}")
                return None
            
            # Reverse map Binance quote to Upbit quote
            upbit_quote = self._reverse_map_quote_asset(binance_quote)
            
            if not upbit_quote:
                logger.warning(f"[SYMBOL_MAPPER] Unsupported Binance quote: {binance_quote}")
                return None
            
            # Construct Upbit symbol
            upbit_symbol = f"{upbit_quote}-{base_asset}"
            
            # Create mapping
            mapping = SymbolMapping(
                upbit_symbol=upbit_symbol,
                binance_symbol=binance_symbol,
                base_asset=base_asset,
                upbit_quote=upbit_quote,
                binance_quote=binance_quote,
                confidence=0.8,  # Reverse-mapped with medium confidence
            )
            
            logger.debug(f"[SYMBOL_MAPPER] Reverse-mapped: {binance_symbol} → {upbit_symbol}")
            return mapping
        
        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] Reverse mapping failed for {binance_symbol}: {e}")
            return None
    
    def _map_quote_asset(self, upbit_quote: str) -> Optional[str]:
        """
        Upbit quote asset을 Binance quote asset로 매핑
        
        Args:
            upbit_quote: Upbit quote (예: "KRW", "BTC", "USDT")
        
        Returns:
            Binance quote (예: "USDT", "BTC") 또는 None
        """
        mapping = {
            "KRW": "USDT",  # KRW 마켓 → USDT 마켓 (proxy)
            "BTC": "BTC",   # BTC 마켓 → BTC 마켓
            "USDT": "USDT",  # USDT 마켓 → USDT 마켓
            "ETH": "ETH",   # ETH 마켓 → ETH 마켓
            # ... 필요시 추가
        }
        return mapping.get(upbit_quote)
    
    def _reverse_map_quote_asset(self, binance_quote: str) -> Optional[str]:
        """
        Binance quote asset을 Upbit quote asset로 매핑 (reverse)
        
        Args:
            binance_quote: Binance quote (예: "USDT", "BTC")
        
        Returns:
            Upbit quote (예: "KRW", "BTC") 또는 None
        """
        mapping = {
            "USDT": "KRW",  # USDT 마켓 → KRW 마켓 (primary for cross-exchange)
            "BTC": "BTC",
            "ETH": "ETH",
            "BNB": None,  # Upbit에 BNB 마켓 없음
            "BUSD": "KRW",  # BUSD → KRW (proxy)
            "USDC": "KRW",  # USDC → KRW (proxy)
            # ... 필요시 추가
        }
        return mapping.get(binance_quote)
    
    def _create_mapping_from_manual(self, upbit_symbol: str, binance_symbol: str) -> SymbolMapping:
        """
        수동 예외 매핑에서 SymbolMapping 생성
        """
        # Parse Upbit
        upbit_parts = upbit_symbol.split("-")
        upbit_quote = upbit_parts[0] if len(upbit_parts) == 2 else "KRW"
        base_asset = upbit_parts[1] if len(upbit_parts) == 2 else upbit_parts[0]
        
        # Parse Binance (heuristic)
        binance_quote = "USDT"  # Default
        for quote in ["USDT", "BUSD", "BTC", "ETH", "BNB", "USDC"]:
            if binance_symbol.endswith(quote):
                binance_quote = quote
                break
        
        return SymbolMapping(
            upbit_symbol=upbit_symbol,
            binance_symbol=binance_symbol,
            base_asset=base_asset,
            upbit_quote=upbit_quote,
            binance_quote=binance_quote,
            confidence=1.0,  # Manual mapping (highest confidence)
        )
    
    def get_mapping_stats(self) -> Dict[str, any]:
        """
        매핑 통계 반환
        
        Returns:
            {
                "total_mapped": int,
                "failed_count": int,
                "success_rate": float,
                "failed_symbols": List[str],
            }
        """
        total_mapped = len(self.mapping_cache)
        failed_count = len(self.failed_mappings)
        total_attempts = total_mapped + failed_count
        
        success_rate = (
            (total_mapped / total_attempts * 100) if total_attempts > 0 else 0.0
        )
        
        return {
            "total_mapped": total_mapped,
            "failed_count": failed_count,
            "total_attempts": total_attempts,
            "success_rate": success_rate,
            "failed_symbols": self.failed_mappings.copy(),
        }
    
    def clear_cache(self):
        """캐시 초기화"""
        self.mapping_cache.clear()
        self.failed_mappings.clear()
        logger.info("[SYMBOL_MAPPER] Cache cleared")
