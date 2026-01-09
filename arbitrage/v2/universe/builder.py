"""
D205-15-2: Universe Builder (V2 Config-driven Wrapper)

TopNProvider(V1)를 재사용하여 config.yml 기반 Universe 생성.
static/topn 모드 지원.

Design:
- Scan-First 원칙: TopNProvider 재사용 (arbitrage/domain/topn_provider.py)
- Config-driven: config.yml universe 섹션 기반 초기화
- Thin Wrapper: 비즈니스 로직 없음, 초기화 + 호출만
"""

import logging
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UniverseMode(Enum):
    """Universe 생성 모드"""
    STATIC = "static"  # 고정 리스트
    TOPN = "topn"      # Top N (거래량 기반)


@dataclass
class UniverseBuilderConfig:
    """
    Universe Builder 설정
    
    Note: core/config.py의 UniverseConfig와 구분하기 위해 rename (D205-15-5)
    - core/config.py UniverseConfig: V2Config 스키마 일부 (symbols_top_n, allowlist/denylist)
    - universe/builder.py UniverseBuilderConfig: UniverseBuilder 초기화 파라미터
    """
    mode: UniverseMode
    static_symbols: List[Tuple[str, str]] = None  # [(symbol_a, symbol_b), ...]
    topn_count: int = 100
    data_source: str = "mock"  # "mock" | "real"
    cache_ttl_seconds: int = 600
    min_volume_usd: float = 1_000_000.0
    min_liquidity_usd: float = 50_000.0
    max_spread_bps: float = 50.0


class UniverseBuilder:
    """
    Universe Builder (V2 Config-driven).
    
    TopNProvider(V1)를 재사용하여 심볼 Universe 생성.
    
    Usage:
        config = UniverseBuilderConfig(mode=UniverseMode.TOPN, topn_count=100)
        builder = UniverseBuilder(config)
        symbols = builder.get_symbols()
    """
    
    def __init__(self, config: UniverseBuilderConfig):
        """
        Args:
            config: UniverseBuilderConfig
        """
        self.config = config
        self._provider = None  # Lazy init
        
        logger.info(
            f"[UNIVERSE_BUILDER] Initialized: mode={config.mode.value}, "
            f"topn_count={config.topn_count}, data_source={config.data_source}"
        )
    
    def get_symbols(self) -> List[Tuple[str, str]]:
        """
        Universe 심볼 리스트 반환.
        
        Returns:
            [(symbol_a, symbol_b), ...] - 예: [("BTC/KRW", "BTC/USDT"), ...]
        """
        if self.config.mode == UniverseMode.STATIC:
            return self._get_static_symbols()
        elif self.config.mode == UniverseMode.TOPN:
            return self._get_topn_symbols()
        else:
            raise ValueError(f"Unknown universe mode: {self.config.mode}")
    
    def _get_static_symbols(self) -> List[Tuple[str, str]]:
        """Static 모드: 고정 리스트 반환"""
        if not self.config.static_symbols:
            logger.warning("[UNIVERSE_BUILDER] Static mode but no symbols provided, using default")
            # Default: D205-15-1 SYMBOL_UNIVERSE
            return [
                ("BTC/KRW", "BTC/USDT"),
                ("ETH/KRW", "ETH/USDT"),
                ("XRP/KRW", "XRP/USDT"),
                ("SOL/KRW", "SOL/USDT"),
                ("DOGE/KRW", "DOGE/USDT"),
                ("ADA/KRW", "ADA/USDT"),
                ("AVAX/KRW", "AVAX/USDT"),
                ("DOT/KRW", "DOT/USDT"),
                ("MATIC/KRW", "MATIC/USDT"),
                ("LINK/KRW", "LINK/USDT"),
                ("ATOM/KRW", "ATOM/USDT"),
                ("ETC/KRW", "ETC/USDT"),
            ]
        
        logger.info(f"[UNIVERSE_BUILDER] Static mode: {len(self.config.static_symbols)} symbols")
        return self.config.static_symbols
    
    def _get_topn_symbols(self) -> List[Tuple[str, str]]:
        """TopN 모드: TopNProvider 사용"""
        # Lazy init TopNProvider
        if self._provider is None:
            from arbitrage.domain.topn_provider import TopNProvider, TopNMode
            
            # Map topn_count to TopNMode
            if self.config.topn_count <= 10:
                mode = TopNMode.TOP_10
            elif self.config.topn_count <= 20:
                mode = TopNMode.TOP_20
            elif self.config.topn_count <= 50:
                mode = TopNMode.TOP_50
            else:
                mode = TopNMode.TOP_100
            
            self._provider = TopNProvider(
                mode=mode,
                selection_data_source=self.config.data_source,
                entry_exit_data_source=self.config.data_source,
                cache_ttl_seconds=self.config.cache_ttl_seconds,
                max_symbols=self.config.topn_count,
                min_volume_usd=self.config.min_volume_usd,
                min_liquidity_usd=self.config.min_liquidity_usd,
                max_spread_bps=self.config.max_spread_bps,
            )
            
            logger.info(
                f"[UNIVERSE_BUILDER] TopNProvider initialized: mode={mode.name}, "
                f"data_source={self.config.data_source}"
            )
        
        # Get TopN symbols
        result = self._provider.get_topn_symbols()
        
        logger.info(
            f"[UNIVERSE_BUILDER] TopN mode: {len(result.symbols)} symbols, "
            f"churn_rate={result.churn_rate:.2%}"
        )
        
        return result.symbols
    
    def get_snapshot(self) -> Dict[str, Any]:
        """
        Universe snapshot (재현/감사용).
        
        Returns:
            {
                "mode": "static" | "topn",
                "symbols": [...],
                "config": {...},
                "timestamp": <float>,
            }
        """
        import time
        
        symbols = self.get_symbols()
        
        return {
            "mode": self.config.mode.value,
            "symbols": symbols,
            "config": {
                "topn_count": self.config.topn_count,
                "data_source": self.config.data_source,
                "cache_ttl_seconds": self.config.cache_ttl_seconds,
                "min_volume_usd": self.config.min_volume_usd,
                "min_liquidity_usd": self.config.min_liquidity_usd,
                "max_spread_bps": self.config.max_spread_bps,
            },
            "timestamp": time.time(),
        }


def from_config_dict(config_dict: Dict[str, Any]) -> UniverseBuilder:
    """
    config.yml universe 섹션에서 UniverseBuilder 생성.
    
    Args:
        config_dict: config.yml의 universe 섹션
    
    Returns:
        UniverseBuilder
    
    Example config.yml:
        universe:
          mode: "topn"  # or "static"
          topn_count: 100
          data_source: "mock"  # or "real"
          cache_ttl_seconds: 600
          min_volume_usd: 1000000.0
          min_liquidity_usd: 50000.0
          max_spread_bps: 50.0
          static_symbols:  # optional, for static mode
            - ["BTC/KRW", "BTC/USDT"]
            - ["ETH/KRW", "ETH/USDT"]
    """
    mode_str = config_dict.get("mode", "static")
    mode = UniverseMode(mode_str)
    
    # Parse static_symbols (if exists)
    static_symbols = None
    if "static_symbols" in config_dict:
        static_symbols = [
            (pair[0], pair[1])
            for pair in config_dict["static_symbols"]
        ]
    
    config = UniverseBuilderConfig(
        mode=mode,
        static_symbols=static_symbols,
        topn_count=config_dict.get("topn_count", 100),
        data_source=config_dict.get("data_source", "mock"),
        cache_ttl_seconds=config_dict.get("cache_ttl_seconds", 600),
        min_volume_usd=config_dict.get("min_volume_usd", 1_000_000.0),
        min_liquidity_usd=config_dict.get("min_liquidity_usd", 50_000.0),
        max_spread_bps=config_dict.get("max_spread_bps", 50.0),
    )
    
    return UniverseBuilder(config)
