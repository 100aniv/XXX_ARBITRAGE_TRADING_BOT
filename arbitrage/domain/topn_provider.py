"""
D77-0: TopN Universe Provider

실제 거래량/유동성/스프레드 기반 TopN 심볼 선정:
- Upbit/Binance API 호출
- 24h Volume, Liquidity Depth, Spread Quality 기준
- Composite Score 계산 (40% volume + 30% liquidity + 30% spread)
- Top10/Top20/Top50/Top100 지원
- 1h TTL 캐싱

D77-0-RM:
- data_source: "mock" | "real" 지원
- Real Market 모드에서 Public Data Clients 사용
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


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


@dataclass
class SpreadSnapshot:
    """D82-1: 실시간 스프레드 스냅샷"""
    symbol: str  # "BTC/KRW" format
    upbit_symbol: str  # "KRW-BTC" format
    binance_symbol: Optional[str]  # "BTCUSDT" format (optional for cross-exchange)
    upbit_bid: float
    upbit_ask: float
    binance_bid: Optional[float] = None
    binance_ask: Optional[float] = None
    spread_bps: float = 0.0  # Upbit 내부 스프레드 또는 cross-exchange 스프레드
    timestamp: float = 0.0
    
    def calculate_spread_bps(self) -> float:
        """스프레드(bps) 계산"""
        if self.binance_bid and self.binance_ask:
            # Cross-exchange: Upbit sell, Binance buy
            # Spread = (Upbit_bid - Binance_ask) / mid
            mid = (self.upbit_bid + self.binance_ask) / 2.0
            if mid > 0:
                self.spread_bps = ((self.upbit_bid - self.binance_ask) / mid) * 10000.0
        else:
            # Single exchange (Upbit)
            mid = (self.upbit_bid + self.upbit_ask) / 2.0
            if mid > 0:
                self.spread_bps = ((self.upbit_ask - self.upbit_bid) / mid) * 10000.0
        
        return self.spread_bps


class TopNProvider:
    """
    TopN Universe Provider.
    
    실제 거래량/유동성/스프레드 기반으로 TopN 심볼 선정.
    """
    
    def __init__(
        self,
        mode: TopNMode = TopNMode.TOP_20,
        data_source: str = "mock",  # D77-0-RM: "mock" | "real"
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
            data_source: "mock" | "real" (D77-0-RM)
            cache_ttl_seconds: 캐시 TTL (초)
            upbit_api_base: Upbit API base URL
            binance_api_base: Binance API base URL
            min_volume_usd: 최소 거래량 (USD)
            min_liquidity_usd: 최소 유동성 (USD)
            max_spread_bps: 최대 스프레드 (bps)
        """
        self.mode = mode
        self.data_source = data_source
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
        
        # D77-0-RM: Public Data Clients (lazy init)
        self._upbit_client = None
        self._binance_client = None
        
        logger.info(f"[TOPN_PROVIDER] Initialized: mode={mode.name}, data_source={data_source}")
    
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
        
        D77-0-RM: data_source에 따라 mock 또는 real 사용
        
        Returns:
            {symbol: SymbolMetrics}
        """
        if self.data_source == "mock":
            logger.info("[TOPN_PROVIDER] Using MOCK data source")
            return self._fetch_mock_metrics()
        elif self.data_source == "real":
            logger.info("[TOPN_PROVIDER] Using REAL data source (Public APIs)")
            return self._fetch_real_metrics()
        else:
            logger.warning(f"[TOPN_PROVIDER] Unknown data_source: {self.data_source}, using mock")
            return self._fetch_mock_metrics()
    
    def _fetch_mock_metrics(self) -> Dict[str, SymbolMetrics]:
        """
        Mock metrics (for testing/development).
        """
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
    
    def _fetch_real_metrics(self) -> Dict[str, SymbolMetrics]:
        """
        D77-0-RM: Real market metrics from Upbit/Binance Public APIs.
        """
        # Lazy init clients
        if self._upbit_client is None:
            from arbitrage.exchanges.upbit_public_data import UpbitPublicDataClient
            self._upbit_client = UpbitPublicDataClient()
        
        if self._binance_client is None:
            from arbitrage.exchanges.binance_public_data import BinancePublicDataClient
            self._binance_client = BinancePublicDataClient()
        
        # Fetch top symbols from Upbit (KRW market)
        upbit_symbols = self._upbit_client.fetch_top_symbols(
            market="KRW",
            limit=50,  # Fetch top 50, we'll filter later
            sort_by="acc_trade_price_24h",
        )
        
        logger.info(f"[TOPN_PROVIDER] Fetched {len(upbit_symbols)} Upbit symbols")
        
        metrics: Dict[str, SymbolMetrics] = {}
        
        # Fetch metrics for each symbol
        for upbit_symbol in upbit_symbols:
            try:
                # Upbit ticker
                ticker = self._upbit_client.fetch_ticker(upbit_symbol)
                if ticker is None:
                    continue
                
                # Upbit orderbook
                orderbook = self._upbit_client.fetch_orderbook(upbit_symbol)
                if orderbook is None or not orderbook.bids or not orderbook.asks:
                    continue
                
                # Calculate metrics
                volume_krw = ticker.acc_trade_price_24h
                volume_usd = volume_krw / 1300.0  # Approx KRW/USD conversion
                
                # Liquidity: sum of top 5 bid/ask levels
                liquidity_krw = sum(b.price * b.size for b in orderbook.bids[:5])
                liquidity_krw += sum(a.price * a.size for a in orderbook.asks[:5])
                liquidity_usd = liquidity_krw / 1300.0
                
                # Spread
                best_bid = orderbook.bids[0].price if orderbook.bids else 0.0
                best_ask = orderbook.asks[0].price if orderbook.asks else 0.0
                mid = (best_bid + best_ask) / 2.0 if (best_bid and best_ask) else 0.0
                spread_bps = ((best_ask - best_bid) / mid * 10000.0) if mid > 0 else 999.0
                
                # Convert symbol format: "KRW-BTC" → "BTC/KRW"
                parts = upbit_symbol.split("-")
                if len(parts) == 2:
                    symbol_formatted = f"{parts[1]}/{parts[0]}"
                else:
                    symbol_formatted = upbit_symbol
                
                metrics[symbol_formatted] = SymbolMetrics(
                    symbol=symbol_formatted,
                    volume_24h=volume_usd,
                    liquidity_depth=liquidity_usd,
                    spread_bps=spread_bps,
                )
            
            except Exception as e:
                logger.warning(f"[TOPN_PROVIDER] Failed to fetch metrics for {upbit_symbol}: {e}")
                continue
        
        logger.info(f"[TOPN_PROVIDER] Successfully fetched {len(metrics)} symbol metrics")
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
    
    def get_current_spread(
        self,
        symbol: str,
        cross_exchange: bool = False,
    ) -> Optional[SpreadSnapshot]:
        """
        D82-1: 특정 심볼의 실시간 스프레드 조회.
        
        Args:
            symbol: Symbol in "BTC/KRW" format
            cross_exchange: True = cross-exchange arbitrage (Upbit-Binance)
                           False = single exchange spread (Upbit only)
        
        Returns:
            SpreadSnapshot 또는 None (data unavailable)
        
        Note:
            - data_source="real"일 때만 실제 API 호출
            - data_source="mock"일 때는 mock 데이터 반환
        """
        if self.data_source == "mock":
            return self._get_mock_spread(symbol)
        
        # Lazy init clients
        if self._upbit_client is None:
            from arbitrage.exchanges.upbit_public_data import UpbitPublicDataClient
            self._upbit_client = UpbitPublicDataClient()
        
        # Convert "BTC/KRW" → "KRW-BTC"
        parts = symbol.split("/")
        if len(parts) != 2:
            logger.error(f"[TOPN_PROVIDER] Invalid symbol format: {symbol}")
            return None
        
        base, quote = parts[0], parts[1]
        upbit_symbol = f"{quote}-{base}"  # "KRW-BTC"
        
        try:
            # Fetch Upbit orderbook
            upbit_ob = self._upbit_client.fetch_orderbook(upbit_symbol)
            if upbit_ob is None or not upbit_ob.bids or not upbit_ob.asks:
                logger.warning(f"[TOPN_PROVIDER] No Upbit orderbook for {upbit_symbol}")
                return None
            
            upbit_bid = upbit_ob.bids[0].price
            upbit_ask = upbit_ob.asks[0].price
            
            snapshot = SpreadSnapshot(
                symbol=symbol,
                upbit_symbol=upbit_symbol,
                binance_symbol=None,
                upbit_bid=upbit_bid,
                upbit_ask=upbit_ask,
                timestamp=time.time(),
            )
            
            # Cross-exchange: fetch Binance data
            if cross_exchange:
                if self._binance_client is None:
                    from arbitrage.exchanges.binance_public_data import BinancePublicDataClient
                    self._binance_client = BinancePublicDataClient()
                
                # Convert to Binance format: "BTC/KRW" → "BTCUSDT" (assume USD pair)
                # TODO: Better symbol mapping (KRW pairs are not on Binance)
                binance_symbol = f"{base}USDT"
                binance_ob = self._binance_client.fetch_orderbook(binance_symbol, limit=20)
                
                if binance_ob and binance_ob.bids and binance_ob.asks:
                    snapshot.binance_symbol = binance_symbol
                    snapshot.binance_bid = binance_ob.bids[0].price
                    snapshot.binance_ask = binance_ob.asks[0].price
            
            snapshot.calculate_spread_bps()
            return snapshot
        
        except Exception as e:
            logger.error(f"[TOPN_PROVIDER] Failed to get current spread for {symbol}: {e}")
            return None
    
    def _get_mock_spread(self, symbol: str) -> SpreadSnapshot:
        """D82-1: Mock spread data (for testing)"""
        # Mock prices based on symbol name hash
        base_price = 50000.0 + (hash(symbol) % 10000)
        spread_pct = 0.001  # 0.1%
        
        return SpreadSnapshot(
            symbol=symbol,
            upbit_symbol=f"KRW-{symbol.split('/')[0]}",
            binance_symbol=None,
            upbit_bid=base_price * (1 - spread_pct / 2),
            upbit_ask=base_price * (1 + spread_pct / 2),
            spread_bps=spread_pct * 10000.0,
            timestamp=time.time(),
        )
