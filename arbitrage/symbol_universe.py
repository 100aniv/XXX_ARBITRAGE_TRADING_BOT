# -*- coding: utf-8 -*-
"""
D73-1: Symbol Universe Provider

멀티심볼 엔진의 심볼 선택/필터링 레이어.
4가지 모드를 지원하며, 엔진-비즈니스 로직과 분리된 유니버스 계층.

Design Philosophy:
─────────────────
1. Symbol Selection Layer
   - Engine과 Symbol 선택 로직을 완전히 분리
   - Mode-based strategy: SINGLE → FIXED_LIST → TOP_N → FULL_MARKET
   - Pluggable SymbolSource 인터페이스로 거래소 어댑터 확장

2. 4가지 Universe Mode
   ┌────────────────┬──────────────────────────────────────────────┐
   │ SINGLE         │ 단일 심볼 (기존 방식, 100% 하위 호환)          │
   │ FIXED_LIST     │ 고정 심볼 리스트 (whitelist 기반)             │
   │ TOP_N          │ 거래량 기준 상위 N개 (동적 선택)              │
   │ FULL_MARKET    │ 필터링 후 전체 시장 (거래소 전체 심볼)        │
   └────────────────┴──────────────────────────────────────────────┘

3. Filtering Pipeline
   - Base/Quote asset filtering (예: USDT만)
   - Volume threshold filtering
   - Blacklist/Whitelist filtering
   - Sorting by 24h quote volume (for TOP_N)

4. Future Expansion (D73-2+)
   - Real exchange adapter integration (Binance, Upbit API)
   - Symbol metadata caching & TTL refresh
   - Dynamic universe rebalancing (runtime symbol add/remove)
   - Portfolio manager integration

Architecture:
─────────────
    ┌──────────────────────────────────────────────┐
    │         SymbolUniverse                       │
    │  ┌──────────────────────────────────────┐   │
    │  │ get_symbols() -> List[str]           │   │
    │  │  ├─ SINGLE: return [single_symbol]   │   │
    │  │  ├─ FIXED_LIST: return whitelist     │   │
    │  │  ├─ TOP_N: filter → sort → top N     │   │
    │  │  └─ FULL_MARKET: filter → all        │   │
    │  └──────────────────────────────────────┘   │
    │               ↓                              │
    │  ┌──────────────────────────────────────┐   │
    │  │    AbstractSymbolSource              │   │
    │  │  get_all_symbols() -> List[SymbolInfo]│  │
    │  └──────────────────────────────────────┘   │
    └──────────────────────────────────────────────┘
                    ↑
        ┌───────────┴────────────┐
        │ DummySymbolSource      │  (D73-1: Test용)
        │ BinanceSymbolSource    │  (D73-2: 실제 API)
        │ UpbitSymbolSource      │  (D73-2: 실제 API)
        └────────────────────────┘

Usage Example:
──────────────
    # SINGLE mode (기존 방식과 동일)
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.SINGLE,
        single_symbol="BTCUSDT"
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()  # ["BTCUSDT"]

    # TOP_N mode (거래량 상위 20개)
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.TOP_N,
        top_n=20,
        base_quote="USDT",
        min_24h_quote_volume=1_000_000.0,
        blacklist=["BUSDUSDT", "USDCUSDT"]
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()  # 상위 20개 (필터링 후)

Author: D73-1 Implementation
Date: 2025-11-21
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Protocol
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# 1. Enums & Data Models
# ============================================================================

class SymbolUniverseMode(Enum):
    """
    Symbol Universe 선택 모드
    
    SINGLE: 단일 심볼 (기존 방식, 하위 호환)
    FIXED_LIST: 고정 심볼 리스트 (whitelist 기반)
    TOP_N: 거래량 기준 상위 N개 (동적 선택)
    FULL_MARKET: 필터링 후 전체 시장
    """
    SINGLE = "SINGLE"
    FIXED_LIST = "FIXED_LIST"
    TOP_N = "TOP_N"
    FULL_MARKET = "FULL_MARKET"


@dataclass
class SymbolInfo:
    """
    심볼 메타데이터
    
    거래소에서 제공하는 심볼 정보를 표준화한 모델.
    """
    symbol: str  # 예: "BTCUSDT", "KRW-BTC"
    base_asset: str  # 예: "BTC", "ETH"
    quote_asset: str  # 예: "USDT", "KRW"
    is_margin: Optional[bool] = None
    is_perpetual: Optional[bool] = None
    volume_24h_quote: Optional[float] = None  # 24시간 거래대금 (quote asset 기준)
    
    def __post_init__(self):
        """Validation"""
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.base_asset:
            raise ValueError("base_asset must not be empty")
        if not self.quote_asset:
            raise ValueError("quote_asset must not be empty")


@dataclass
class SymbolUniverseConfig:
    """
    Symbol Universe 설정
    
    4가지 모드와 필터링 옵션을 포함.
    """
    # Mode
    mode: SymbolUniverseMode = SymbolUniverseMode.SINGLE
    
    # Exchange
    exchange: str = "binance_futures"  # "binance_futures", "upbit_spot", etc.
    
    # SINGLE mode
    single_symbol: Optional[str] = None  # 예: "BTCUSDT"
    
    # FIXED_LIST mode
    whitelist: List[str] = field(default_factory=list)  # 사용할 심볼 리스트
    
    # TOP_N mode
    top_n: Optional[int] = None  # 상위 N개 선택
    
    # Filtering (TOP_N, FULL_MARKET 공통)
    base_quote: str = "USDT"  # Quote asset 필터 (예: "USDT", "KRW")
    blacklist: List[str] = field(default_factory=list)  # 제외할 심볼 리스트
    min_24h_quote_volume: Optional[float] = None  # 최소 24시간 거래대금 (quote asset)
    
    def __post_init__(self):
        """Validation"""
        if self.mode == SymbolUniverseMode.SINGLE:
            if not self.single_symbol:
                raise ValueError("SINGLE mode requires single_symbol")
        
        elif self.mode == SymbolUniverseMode.FIXED_LIST:
            if not self.whitelist:
                raise ValueError("FIXED_LIST mode requires whitelist")
        
        elif self.mode == SymbolUniverseMode.TOP_N:
            if self.top_n is None or self.top_n <= 0:
                raise ValueError("TOP_N mode requires top_n > 0")
        
        elif self.mode == SymbolUniverseMode.FULL_MARKET:
            # FULL_MARKET은 필터만 적용, 추가 제약 없음
            pass
        
        else:
            raise ValueError(f"Unknown mode: {self.mode}")


# ============================================================================
# 2. Symbol Source Interface (Protocol)
# ============================================================================

class AbstractSymbolSource(Protocol):
    """
    Symbol Source 인터페이스
    
    거래소별 심볼 리스트 조회 구현을 위한 프로토콜.
    D73-1에서는 DummySymbolSource만 사용,
    D73-2에서 BinanceSymbolSource, UpbitSymbolSource 구현 예정.
    """
    
    def get_all_symbols(self) -> List[SymbolInfo]:
        """
        거래소의 전체 심볼 리스트 조회
        
        Returns:
            List[SymbolInfo]: 심볼 메타데이터 리스트
        """
        ...


# ============================================================================
# 3. Dummy Symbol Source (테스트용)
# ============================================================================

class DummySymbolSource:
    """
    테스트용 Symbol Source
    
    실제 거래소 API 없이 샘플 심볼 데이터를 반환.
    D73-1 필터링/정렬 로직 검증 용도.
    """
    
    def __init__(self, sample_symbols: Optional[List[SymbolInfo]] = None):
        """
        Args:
            sample_symbols: 샘플 심볼 리스트 (None이면 기본 샘플 사용)
        """
        self.sample_symbols = sample_symbols or self._create_default_samples()
    
    def get_all_symbols(self) -> List[SymbolInfo]:
        """샘플 심볼 리스트 반환"""
        return self.sample_symbols
    
    @staticmethod
    def _create_default_samples() -> List[SymbolInfo]:
        """기본 샘플 심볼 생성 (15개)"""
        return [
            # Top tier (high volume)
            SymbolInfo("BTCUSDT", "BTC", "USDT", volume_24h_quote=50_000_000_000.0),
            SymbolInfo("ETHUSDT", "ETH", "USDT", volume_24h_quote=20_000_000_000.0),
            SymbolInfo("BNBUSDT", "BNB", "USDT", volume_24h_quote=3_000_000_000.0),
            
            # Mid tier (medium volume)
            SymbolInfo("SOLUSDT", "SOL", "USDT", volume_24h_quote=2_500_000_000.0),
            SymbolInfo("XRPUSDT", "XRP", "USDT", volume_24h_quote=2_000_000_000.0),
            SymbolInfo("ADAUSDT", "ADA", "USDT", volume_24h_quote=1_500_000_000.0),
            SymbolInfo("DOGEUSDT", "DOGE", "USDT", volume_24h_quote=1_200_000_000.0),
            SymbolInfo("MATICUSDT", "MATIC", "USDT", volume_24h_quote=1_000_000_000.0),
            
            # Low tier (low volume)
            SymbolInfo("DOTUSDT", "DOT", "USDT", volume_24h_quote=800_000_000.0),
            SymbolInfo("AVAXUSDT", "AVAX", "USDT", volume_24h_quote=700_000_000.0),
            SymbolInfo("ATOMUSDT", "ATOM", "USDT", volume_24h_quote=500_000_000.0),
            SymbolInfo("LINKUSDT", "LINK", "USDT", volume_24h_quote=400_000_000.0),
            
            # Stablecoins (should be filtered out in most cases)
            SymbolInfo("BUSDUSDT", "BUSD", "USDT", volume_24h_quote=10_000_000_000.0),
            SymbolInfo("USDCUSDT", "USDC", "USDT", volume_24h_quote=8_000_000_000.0),
            
            # Leveraged tokens (should be filtered out)
            SymbolInfo("BTCBULL", "BTCBULL", "USDT", volume_24h_quote=100_000_000.0),
        ]


# ============================================================================
# 4. Symbol Universe (핵심 클래스)
# ============================================================================

class SymbolUniverse:
    """
    Symbol Universe Provider
    
    Config + SymbolSource를 조합하여 최종 심볼 리스트를 생성.
    Mode별로 다른 필터링/정렬 전략 적용.
    """
    
    def __init__(
        self,
        config: SymbolUniverseConfig,
        source: AbstractSymbolSource
    ):
        """
        Args:
            config: Universe 설정
            source: Symbol source 구현체
        """
        self.config = config
        self.source = source
        
        # Handle both string and enum mode
        mode_str = config.mode.value if hasattr(config.mode, 'value') else config.mode
        logger.info(
            f"[SYMBOL_UNIVERSE] Initialized: mode={mode_str}, "
            f"exchange={config.exchange}"
        )
    
    def get_symbols(self) -> List[str]:
        """
        최종 심볼 리스트 반환
        
        Mode에 따라 다른 전략 적용:
        - SINGLE: single_symbol 1개 반환
        - FIXED_LIST: whitelist 그대로 반환 (blacklist 제외)
        - TOP_N: 필터 → 정렬 → 상위 N개
        - FULL_MARKET: 필터 → 전체
        
        Returns:
            List[str]: 최종 심볼 리스트
        """
        if self.config.mode == SymbolUniverseMode.SINGLE:
            return self._get_single_symbol()
        
        elif self.config.mode == SymbolUniverseMode.FIXED_LIST:
            return self._get_fixed_list()
        
        elif self.config.mode == SymbolUniverseMode.TOP_N:
            return self._get_top_n()
        
        elif self.config.mode == SymbolUniverseMode.FULL_MARKET:
            return self._get_full_market()
        
        else:
            logger.error(f"[SYMBOL_UNIVERSE] Unknown mode: {self.config.mode}")
            return []

    # ────────────────────────────────────────────────────────────────────────
    # Mode별 구현
    # ────────────────────────────────────────────────────────────────────────
    
    def _get_single_symbol(self) -> List[str]:
        """SINGLE 모드: 단일 심볼 반환"""
        symbol = self.config.single_symbol
        logger.debug(f"[SYMBOL_UNIVERSE] SINGLE mode: {symbol}")
        return [symbol]
    
    def _get_fixed_list(self) -> List[str]:
        """FIXED_LIST 모드: whitelist에서 blacklist 제외"""
        whitelist = self.config.whitelist
        blacklist = set(self.config.blacklist)
        
        result = [s for s in whitelist if s not in blacklist]
        
        logger.info(
            f"[SYMBOL_UNIVERSE] FIXED_LIST mode: "
            f"whitelist={len(whitelist)}, blacklist={len(blacklist)}, "
            f"result={len(result)} symbols"
        )
        
        return result
    
    def _get_top_n(self) -> List[str]:
        """TOP_N 모드: 필터 → 정렬 → 상위 N개"""
        # 1. 전체 심볼 조회
        all_symbols = self.source.get_all_symbols()
        
        # 2. 필터링
        filtered = self._filter_symbols(all_symbols)
        
        # 3. Volume 기준 정렬 (내림차순)
        sorted_symbols = self._sort_by_volume(filtered)
        
        # 4. 상위 N개 선택
        top_n = self.config.top_n
        result = [s.symbol for s in sorted_symbols[:top_n]]
        
        logger.info(
            f"[SYMBOL_UNIVERSE] TOP_N mode: "
            f"all={len(all_symbols)}, filtered={len(filtered)}, "
            f"top_n={top_n}, result={len(result)} symbols"
        )
        logger.debug(f"[SYMBOL_UNIVERSE] TOP_N result: {result}")
        
        return result
    
    def _get_full_market(self) -> List[str]:
        """FULL_MARKET 모드: 필터링 후 전체"""
        # 1. 전체 심볼 조회
        all_symbols = self.source.get_all_symbols()
        
        # 2. 필터링
        filtered = self._filter_symbols(all_symbols)
        
        # 3. Volume 기준 정렬 (참고용, 순서 보장)
        sorted_symbols = self._sort_by_volume(filtered)
        
        result = [s.symbol for s in sorted_symbols]
        
        logger.info(
            f"[SYMBOL_UNIVERSE] FULL_MARKET mode: "
            f"all={len(all_symbols)}, filtered={len(filtered)}, "
            f"result={len(result)} symbols"
        )
        
        return result
    
    # ────────────────────────────────────────────────────────────────────────
    # 필터링/정렬 헬퍼 메서드
    # ────────────────────────────────────────────────────────────────────────
    
    def _filter_symbols(self, symbols: List[SymbolInfo]) -> List[SymbolInfo]:
        """
        심볼 필터링 파이프라인
        
        1. Quote asset 필터
        2. Blacklist 제외
        3. Whitelist 적용 (있는 경우)
        4. Volume threshold 필터
        
        Args:
            symbols: 필터링 대상 심볼 리스트
        
        Returns:
            List[SymbolInfo]: 필터링된 심볼 리스트
        """
        result = symbols
        
        # 1. Quote asset 필터
        if self.config.base_quote:
            result = [s for s in result if s.quote_asset == self.config.base_quote]
        
        # 2. Blacklist 제외
        if self.config.blacklist:
            blacklist_set = set(self.config.blacklist)
            result = [s for s in result if s.symbol not in blacklist_set]
        
        # 3. Whitelist 적용 (있는 경우만)
        if self.config.whitelist:
            whitelist_set = set(self.config.whitelist)
            result = [s for s in result if s.symbol in whitelist_set]
        
        # 4. Volume threshold 필터
        if self.config.min_24h_quote_volume is not None:
            result = [
                s for s in result
                if s.volume_24h_quote is not None
                and s.volume_24h_quote >= self.config.min_24h_quote_volume
            ]
        
        return result
    
    def _sort_by_volume(self, symbols: List[SymbolInfo]) -> List[SymbolInfo]:
        """
        Volume 기준 정렬 (내림차순)
        
        Args:
            symbols: 정렬 대상 심볼 리스트
        
        Returns:
            List[SymbolInfo]: Volume 기준 정렬된 심볼 리스트
        """
        return sorted(
            symbols,
            key=lambda s: s.volume_24h_quote or 0.0,
            reverse=True
        )


# ============================================================================
# 5. Factory Function (D73-2 Integration)
# ============================================================================

def build_symbol_universe(config: SymbolUniverseConfig, source: Optional[AbstractSymbolSource] = None) -> SymbolUniverse:
    """
    Build SymbolUniverse from config.
    
    D73-2 integration helper. Creates SymbolUniverse instance from config,
    with optional source override for testing.
    
    Args:
        config: SymbolUniverseConfig instance
        source: Optional symbol source override (default: DummySymbolSource)
    
    Returns:
        SymbolUniverse instance
    
    Example:
        >>> from config.base import ArbitrageConfig
        >>> config = ArbitrageConfig(...)
        >>> universe = build_symbol_universe(config.universe)
        >>> symbols = universe.get_symbols()
    """
    if source is None:
        # D73-2: Use DummySymbolSource by default
        # D73-2+: Will be replaced with real exchange source (BinanceSymbolSource, UpbitSymbolSource)
        source = DummySymbolSource()
    
    return SymbolUniverse(config, source)


# ============================================================================
# 6. 향후 확장 포인트 (D73-2+)
# ============================================================================

# TODO(D73-2): Binance Symbol Source 구현
# class BinanceSymbolSource:
#     """Binance API 기반 Symbol Source"""
#     async def get_all_symbols(self) -> List[SymbolInfo]:
#         # Binance API /fapi/v1/exchangeInfo 호출
#         # 24h ticker 데이터로 volume 채우기
#         pass

# TODO(D73-2): Upbit Symbol Source 구현
# class UpbitSymbolSource:
#     """Upbit API 기반 Symbol Source"""
#     async def get_all_symbols(self) -> List[SymbolInfo]:
#         # Upbit API /v1/market/all 호출
#         # 24h ticker 데이터로 volume 채우기
#         pass

# TODO(D73-3): Multi-Symbol RiskGuard 통합
# - SymbolUniverse → RiskGuard 연동
# - 심볼별 리스크 한도 자동 분배

# TODO(D73-4): Small-Scale Integration Test
# - Top-10 심볼 PAPER 모드 통합 테스트
# - 5분 캠페인 실행 (Entry/Exit/PnL 검증)
