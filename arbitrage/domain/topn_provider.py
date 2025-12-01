"""
D77-0: TopN Universe Provider

실제 거래량/유동성/스프레드 기반 TopN 심볼 선정:
- Upbit/Binance API 호출
- 24h Volume, Liquidity Depth, Spread Quality 기준
- Composite Score 계산 (40% volume + 30% liquidity + 30% spread)
- Top10/Top20/Top50/Top100 지원
- 1h TTL 캐싱
"""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import requests


class TopNMode(Enum):
    """TopN 모드"""
    TOP_10 = 10
    TOP_20 = 20
    TOP_50 = 50
    TOP_100 = 100


@dataclass
class SymbolMetrics:
    """심볼 metrics"""
    symbol: str
    volume_24h: float  # USD
    liquidity_depth: float  # USD at ±1% price level
    spread_bps: float  # (ask - bid) / mid * 10000
    composite_score: float = 0.0
    
    def calculate_composite_score(
        self,
        volume_rank: float,
        liquidity_rank: float,
        spread_rank: float,
    ) -> float:
        """
        Composite Score 계산.
        
        Args:
            volume_rank: 0.0 ~ 1.0 (1.0 = highest volume)
            liquidity_rank: 0.0 ~ 1.0 (1.0 = highest liquidity)
            spread_rank: 0.0 ~ 1.0 (1.0 = lowest spread)
        
        Returns:
            Composite score (0.0 ~ 1.0)
        """
        self.composite_score = (
            volume_rank * 0.4 +
            liquidity_rank * 0.3 +
            spread_rank * 0.3
        )
        return self.composite_score


@dataclass
class TopNResult:
    """TopN 선정 결과"""
    symbols: List[Tuple[str, str]]  # [(symbol_a, symbol_b), ...]
    metrics: Dict[str, SymbolMetrics]
    timestamp: float
    mode: TopNMode
    churn_rate: float = 0.0  # 이전 대비 변경 비율


class TopNProvider:
    """
    TopN Universe Provider.
    
    실제 거래량/유동성/스프레드 기반으로 TopN 심볼 선정.
    """
    
    def __init__(
        self,
        mode: TopNMode = TopNMode.TOP_20,
        cache_ttl_seconds: int = 3600,  # 1h
        upbit_api_base: str = "https://api.upbit.com/v1",
        binance_api_base: str = "https://api.binance.com/api/v3",
        min_volume_usd: float = 1_000_000.0,  # $1M
        min_liquidity_usd: float = 50_000.0,  # $50K
        max_spread_bps: float = 50.0,  # 0.5%
    ):
        """
        Args:
            mode: TopN 모드
            cache_ttl_seconds: 캐시 TTL (초)
            upbit_api_base: Upbit API base URL
            binance_api_base: Binance API base URL
            min_volume_usd: 최소 거래량 (USD)
            min_liquidity_usd: 최소 유동성 (USD)
            max_spread_bps: 최대 스프레드 (bps)
        """
        self.mode = mode
        self.cache_ttl_seconds = cache_ttl_seconds
        self.upbit_api_base = upbit_api_base
        self.binance_api_base = binance_api_base
        self.min_volume_usd = min_volume_usd
        self.min_liquidity_usd = min_liquidity_usd
        self.max_spread_bps = max_spread_bps
        
        # Cache
        self._cache: Optional[TopNResult] = None
        self._cache_timestamp: float = 0.0
        
        # Previous result (for churn calculation)
        self._previous_symbols: List[Tuple[str, str]] = []
    
    def get_topn_symbols(
        self,
        force_refresh: bool = False,
    ) -> TopNResult:
        """
        TopN 심볼 선정.
        
        Args:
            force_refresh: 캐시 무시하고 강제 refresh
        
        Returns:
            TopNResult
        """
        # Cache hit
        now = time.time()
        if not force_refresh and self._cache is not None:
            if now - self._cache_timestamp < self.cache_ttl_seconds:
                return self._cache
        
        # Fetch metrics from exchanges
        metrics = self._fetch_all_metrics()
        
        # Filter by thresholds
        filtered = self._filter_by_thresholds(metrics)
        
        # Calculate composite scores
        filtered = self._calculate_composite_scores(filtered)
        
        # Sort by composite score (descending)
        sorted_metrics = sorted(
            filtered.values(),
            key=lambda m: m.composite_score,
            reverse=True,
        )
        
        # Select TopN
        topn_metrics = sorted_metrics[:self.mode.value]
        
        # Create symbol pairs (Upbit KRW ↔ Binance USDT)
        symbols: List[Tuple[str, str]] = []
        metrics_dict: Dict[str, SymbolMetrics] = {}
        
        for m in topn_metrics:
            # symbol format: "BTC/KRW" (Upbit), "BTC/USDT" (Binance)
            base = m.symbol.replace("/KRW", "").replace("/USDT", "")
            symbol_a = f"{base}/KRW"
            symbol_b = f"{base}/USDT"
            symbols.append((symbol_a, symbol_b))
            metrics_dict[base] = m
        
        # Calculate churn rate
        churn_rate = self._calculate_churn_rate(symbols)
        
        result = TopNResult(
            symbols=symbols,
            metrics=metrics_dict,
            timestamp=now,
            mode=self.mode,
            churn_rate=churn_rate,
        )
        
        # Update cache
        self._cache = result
        self._cache_timestamp = now
        self._previous_symbols = symbols
        
        return result
    
    def _fetch_all_metrics(self) -> Dict[str, SymbolMetrics]:
        """
        모든 심볼의 metrics 수집.
        
        Returns:
            {symbol: SymbolMetrics}
        """
        # PAPER mode / Mock implementation
        # 실제 운영 시에는 Upbit/Binance API 호출
        
        # Mock data (Top 30 crypto by market cap)
        mock_symbols = [
            "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "MATIC", "DOT", "AVAX",
            "LINK", "UNI", "LTC", "ATOM", "ETC", "XLM", "ALGO", "VET", "ICP", "FIL",
            "NEAR", "APT", "ARB", "OP", "SUI", "INJ", "TIA", "SEI", "STX", "RUNE",
        ]
        
        metrics: Dict[str, SymbolMetrics] = {}
        
        for i, symbol in enumerate(mock_symbols):
            # Mock metrics (realistic values)
            volume_multiplier = 1.0 / (i + 1)  # Higher rank = higher volume
            
            metrics[f"{symbol}/KRW"] = SymbolMetrics(
                symbol=f"{symbol}/KRW",
                volume_24h=10_000_000 * volume_multiplier,  # $10M ~ $333K
                liquidity_depth=100_000 * volume_multiplier,  # $100K ~ $3.3K
                spread_bps=10.0 + (i * 1.0),  # 10 bps ~ 40 bps
            )
        
        return metrics
    
    def _filter_by_thresholds(
        self,
        metrics: Dict[str, SymbolMetrics],
    ) -> Dict[str, SymbolMetrics]:
        """
        Threshold 필터링.
        
        Args:
            metrics: {symbol: SymbolMetrics}
        
        Returns:
            Filtered metrics
        """
        filtered: Dict[str, SymbolMetrics] = {}
        
        for symbol, m in metrics.items():
            if m.volume_24h < self.min_volume_usd:
                continue
            if m.liquidity_depth < self.min_liquidity_usd:
                continue
            if m.spread_bps > self.max_spread_bps:
                continue
            
            filtered[symbol] = m
        
        return filtered
    
    def _calculate_composite_scores(
        self,
        metrics: Dict[str, SymbolMetrics],
    ) -> Dict[str, SymbolMetrics]:
        """
        Composite Score 계산.
        
        Args:
            metrics: {symbol: SymbolMetrics}
        
        Returns:
            Updated metrics with composite scores
        """
        if not metrics:
            return metrics
        
        # Extract values
        volumes = [m.volume_24h for m in metrics.values()]
        liquidities = [m.liquidity_depth for m in metrics.values()]
        spreads = [m.spread_bps for m in metrics.values()]
        
        # Min/Max normalization
        volume_min, volume_max = min(volumes), max(volumes)
        liquidity_min, liquidity_max = min(liquidities), max(liquidities)
        spread_min, spread_max = min(spreads), max(spreads)
        
        for m in metrics.values():
            # Normalize to 0.0 ~ 1.0
            volume_rank = (
                (m.volume_24h - volume_min) / (volume_max - volume_min)
                if volume_max > volume_min else 0.5
            )
            liquidity_rank = (
                (m.liquidity_depth - liquidity_min) / (liquidity_max - liquidity_min)
                if liquidity_max > liquidity_min else 0.5
            )
            # Spread: lower is better (invert)
            spread_rank = (
                1.0 - (m.spread_bps - spread_min) / (spread_max - spread_min)
                if spread_max > spread_min else 0.5
            )
            
            m.calculate_composite_score(volume_rank, liquidity_rank, spread_rank)
        
        return metrics
    
    def _calculate_churn_rate(
        self,
        new_symbols: List[Tuple[str, str]],
    ) -> float:
        """
        Churn rate 계산 (이전 대비 변경 비율).
        
        Args:
            new_symbols: 새로운 symbol 리스트
        
        Returns:
            Churn rate (0.0 ~ 1.0)
        """
        if not self._previous_symbols:
            return 0.0
        
        prev_set = set(self._previous_symbols)
        new_set = set(new_symbols)
        
        # Added + Removed symbols
        added = new_set - prev_set
        removed = prev_set - new_set
        
        churn_count = len(added) + len(removed)
        total = len(prev_set) + len(new_set)
        
        if total == 0:
            return 0.0
        
        return churn_count / total
    
    def _fetch_upbit_metrics(self) -> Dict[str, SymbolMetrics]:
        """
        Upbit API에서 metrics 수집.
        
        Note: PAPER 모드에서는 mock 사용. LIVE 모드에서만 실제 API 호출.
        """
        # TODO: LIVE mode implementation
        # GET /v1/ticker
        # GET /v1/orderbook
        raise NotImplementedError("LIVE mode not implemented yet")
    
    def _fetch_binance_metrics(self) -> Dict[str, SymbolMetrics]:
        """
        Binance API에서 metrics 수집.
        
        Note: PAPER 모드에서는 mock 사용. LIVE 모드에서만 실제 API 호출.
        """
        # TODO: LIVE mode implementation
        # GET /api/v3/ticker/24hr
        # GET /api/v3/depth
        raise NotImplementedError("LIVE mode not implemented yet")
