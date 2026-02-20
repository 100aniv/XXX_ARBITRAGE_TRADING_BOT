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
    
    D82-2: Hybrid Mode
    - Selection: uses selection_data_source (mock or real, cached with long TTL)
    - Entry/Exit: uses entry_exit_data_source (real-time spread checks)
    """
    
    def __init__(
        self,
        mode: TopNMode = TopNMode.TOP_20,
        selection_data_source: str = "mock",  # D82-2: "mock" | "real" for TopN selection
        entry_exit_data_source: str = "real",  # D82-2: "mock" | "real" for Entry/Exit
        cache_ttl_seconds: int = 600,  # D82-2: Reduced to 10 minutes (from 1h)
        max_symbols: int = 50,  # D82-2: Max symbols for selection
        upbit_api_base: str = "https://api.upbit.com/v1",
        binance_api_base: str = "https://api.binance.com/api/v3",
        min_volume_usd: float = 1_000_000.0,  # $1M
        min_liquidity_usd: float = 50_000.0,  # $50K
        max_spread_bps: float = 50.0,  # 0.5%
        # D82-3: Real Selection Rate Limit 옵션
        selection_rate_limit_enabled: bool = True,
        selection_batch_size: int = 10,
        selection_batch_delay_sec: float = 1.5,
        clean_room: bool = False,
    ):
        """
        D82-2: Hybrid Mode initialization.
        
        Args:
            mode: TopN mode
            selection_data_source: "mock" | "real" for TopN selection
            entry_exit_data_source: "mock" | "real" for Entry/Exit spread checks
            cache_ttl_seconds: Cache TTL (seconds)
            max_symbols: Maximum symbols to select
            upbit_api_base: Upbit API base URL
            binance_api_base: Binance API base URL
            min_volume_usd: Minimum volume (USD)
            min_liquidity_usd: Minimum liquidity (USD)
            max_spread_bps: Maximum spread (bps)
        """
        self.mode = mode
        self.selection_data_source = selection_data_source
        self.entry_exit_data_source = entry_exit_data_source
        self.clean_room = bool(clean_room)
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_symbols = max_symbols
        self.upbit_api_base = upbit_api_base
        self.binance_api_base = binance_api_base
        self.min_volume_usd = min_volume_usd
        self.min_liquidity_usd = min_liquidity_usd
        self.max_spread_bps = max_spread_bps
        
        # D82-3: Real Selection Rate Limit 옵션
        self.selection_rate_limit_enabled = selection_rate_limit_enabled
        self.selection_batch_size = selection_batch_size
        self.selection_batch_delay_sec = selection_batch_delay_sec
        
        # D82-2: Selection cache (long TTL, 10+ minutes)
        self._selection_cache: Optional[TopNResult] = None
        self._selection_cache_ts: float = 0.0
        self._selection_cache_mono_ts: float = 0.0
        
        # Previous result (for churn calculation)
        self._previous_symbols: List[Tuple[str, str]] = []
        
        # D77-0-RM: Public Data Clients (lazy init)
        self._upbit_client = None
        self._binance_client = None
        
        # D82-3: Rate Limiter (lazy init)
        self._rate_limiter = None

        if self.clean_room:
            if self.selection_data_source != "mock" or self.entry_exit_data_source != "mock":
                raise RuntimeError(
                    "[CLEAN_ROOM] TopNProvider real data source is forbidden "
                    f"(selection={self.selection_data_source}, entry_exit={self.entry_exit_data_source})"
                )
        
        logger.info(
            f"[TOPN_PROVIDER] D82-2/D82-3 Hybrid Mode: "
            f"mode={mode.name}, selection={selection_data_source}, "
            f"entry_exit={entry_exit_data_source}, cache_ttl={cache_ttl_seconds}s, "
            f"rate_limit={'ON' if selection_rate_limit_enabled else 'OFF'}, batch_size={selection_batch_size}"
        )
    
    def get_topn_symbols(
        self,
        force_refresh: bool = False,
        selection_limit: Optional[int] = None,
    ) -> TopNResult:
        """
        D82-2: TopN selection with hybrid mode and cache.
        
        Uses `selection_data_source` for selecting symbols.
        Cache is checked first (10-minute TTL by default).
        
        Args:
            force_refresh: Ignore cache and force refresh
        
        Returns:
            TopNResult
        """
        if self.clean_room:
            raise RuntimeError("[CLEAN_ROOM] TopNProvider.get_topn_symbols is forbidden")
        # D82-2: Check selection cache first
        now = time.time()
        now_mono = time.monotonic()
        use_cache = selection_limit is None
        if use_cache and not force_refresh and self._selection_cache is not None:
            cache_age = now_mono - self._selection_cache_mono_ts
            if cache_age < self.cache_ttl_seconds:
                logger.info(
                    f"[TOPN_PROVIDER] Using cached TopN selection (age: {cache_age:.1f}s / {self.cache_ttl_seconds}s)"
                )
                return self._selection_cache
        
        # D82-2: Fetch new selection (uses selection_data_source)
        # D_ALPHA-1U-FIX-1: selection_limit 전달하여 확장된 후보군 조회
        logger.info(f"[TOPN_PROVIDER] Refreshing TopN selection (source: {self.selection_data_source})")
        metrics = self._fetch_selection_metrics(selection_limit=selection_limit)
        
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
        
        # Select TopN (or expanded selection_limit)
        limit = self.mode.value
        if isinstance(selection_limit, int) and selection_limit > 0:
            limit = selection_limit
        topn_metrics = sorted_metrics[:min(limit, len(sorted_metrics))]
        
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
        
        # D82-2: Update selection cache (default selection only)
        if use_cache:
            self._selection_cache = result
            self._selection_cache_ts = now
            self._selection_cache_mono_ts = now_mono
            self._previous_symbols = symbols
        
        logger.info(
            f"[TOPN_PROVIDER] TopN selection refreshed: {len(symbols)} symbols, "
            f"churn_rate={churn_rate:.2%}, source={self.selection_data_source}"
        )
        
        return result
    
    def _fetch_selection_metrics(self, selection_limit: Optional[int] = None) -> Dict[str, SymbolMetrics]:
        """
        D82-2/D82-3: Fetch metrics for TopN selection.
        
        Uses `selection_data_source` to determine data source.
        
        D_ALPHA-1U-FIX-1: selection_limit 파라미터 전달 체인 추가
        
        Returns:
            {symbol: SymbolMetrics}
        """
        if self.clean_room:
            raise RuntimeError("[CLEAN_ROOM] TopNProvider selection metrics fetch is forbidden")
        if self.selection_data_source == "mock":
            logger.info("[TOPN_PROVIDER] Using MOCK data for TopN selection")
            return self._fetch_mock_metrics()
        elif self.selection_data_source == "real":
            logger.info("[TOPN_PROVIDER] Using REAL data for TopN selection (Rate-Limited)")
            return self._fetch_real_metrics_safe(selection_limit=selection_limit)
        else:
            logger.warning(
                f"[TOPN_PROVIDER] Unknown selection_data_source: {self.selection_data_source}, using mock"
            )
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
            
            # D82-2: Increased base liquidity to pass relaxed mock threshold (10K)
            metrics[f"{symbol}/KRW"] = SymbolMetrics(
                symbol=f"{symbol}/KRW",
                volume_24h=10_000_000 * volume_multiplier,  # $10M ~ $333K
                liquidity_depth=300_000 * volume_multiplier,  # $300K ~ $10K (all pass 10K threshold)
                spread_bps=10.0 + (i * 1.0),  # 10 bps ~ 40 bps
            )
        
        return metrics
    
    def _fetch_real_metrics(self, selection_limit: Optional[int] = None) -> Dict[str, SymbolMetrics]:
        """
        D77-0-RM: Real market metrics from Upbit/Binance Public APIs.
        
        D_ALPHA-1U-FIX-1: selection_limit 지원 추가
        - selection_limit이 제공되면 더 많은 후보군 조회 (100+)
        - 기본값 150으로 충분한 후보군 확보
        """
        # Lazy init clients
        if self._upbit_client is None:
            from arbitrage.exchanges.upbit_public_data import UpbitPublicDataClient
            self._upbit_client = UpbitPublicDataClient()
        
        if self._binance_client is None:
            from arbitrage.exchanges.binance_public_data import BinancePublicDataClient
            self._binance_client = BinancePublicDataClient()
        
        # D_ALPHA-1U-FIX-1: 확장된 후보군 조회 (selection_limit 기반)
        fetch_limit = selection_limit if selection_limit is not None else 150
        
        # Fetch top symbols from Upbit (KRW market)
        upbit_symbols = self._upbit_client.fetch_top_symbols(
            market="KRW",
            limit=fetch_limit,
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
    
    def _fetch_real_metrics_safe(self, selection_limit: Optional[int] = None) -> Dict[str, SymbolMetrics]:
        """
        D82-3: Rate-Limit-Safe Real TopN Selection.
        
        Upbit Public API Rate Limits:
        - public_ticker: 10 req/sec
        - public_orderbook: 10 req/sec
        - global: 600 req/min
        
        Strategy:
        - Batch processing: Process N symbols at a time
        - Delay between batches to avoid rate limits
        - Use RateLimiter to enforce limits
        - Fallback to mock if all symbols fail
        
        D_ALPHA-1U-FIX-1: selection_limit 지원 추가
        
        Returns:
            {symbol: SymbolMetrics}
        """
        # Lazy init clients
        if self._upbit_client is None:
            from arbitrage.exchanges.upbit_public_data import UpbitPublicDataClient
            self._upbit_client = UpbitPublicDataClient()
        
        # D82-3: Lazy init rate limiter
        if self._rate_limiter is None and self.selection_rate_limit_enabled:
            from arbitrage.infrastructure.rate_limiter import UPBIT_PROFILE, RateLimitPolicy
            self._rate_limiter = UPBIT_PROFILE.get_rest_limiter(
                "public_ticker",  # Use ticker endpoint (same limit as orderbook: 10 req/sec)
                policy=RateLimitPolicy.TOKEN_BUCKET,
            )
            logger.info("[TOPN_PROVIDER] RateLimiter initialized for Real Selection")
        
        # D_ALPHA-1U-FIX-1: 확장된 후보군 조회
        fetch_limit = selection_limit if selection_limit is not None else max(self.max_symbols * 2, 150)
        fetch_limit = min(fetch_limit, 500)  # 상한 500
        
        # 1) 후보 심볼 리스트 가져오기 (이미 Upbit API 1회 호출)
        try:
            candidate_symbols = self._upbit_client.fetch_top_symbols(
                market="KRW",
                limit=fetch_limit,
                sort_by="acc_trade_price_24h",
            )
            logger.info(f"[TOPN_PROVIDER] Real Selection: {len(candidate_symbols)} candidate symbols")
        except Exception as e:
            logger.error(f"[TOPN_PROVIDER] Failed to fetch candidate symbols: {e}")
            logger.warning("[TOPN_PROVIDER] Falling back to MOCK selection")
            return self._fetch_mock_metrics()
        
        if not candidate_symbols:
            logger.warning("[TOPN_PROVIDER] No candidate symbols, falling back to MOCK")
            return self._fetch_mock_metrics()
        
        # 2) 배치 단위로 metrics 수집
        metrics: Dict[str, SymbolMetrics] = {}
        batch_size = self.selection_batch_size
        batch_delay = self.selection_batch_delay_sec
        
        for batch_idx in range(0, len(candidate_symbols), batch_size):
            batch = candidate_symbols[batch_idx:batch_idx + batch_size]
            batch_num = batch_idx // batch_size + 1
            total_batches = (len(candidate_symbols) + batch_size - 1) // batch_size
            
            logger.info(
                f"[TOPN_PROVIDER] Real Selection Batch {batch_num}/{total_batches}: "
                f"Processing {len(batch)} symbols"
            )
            
            # 배치 처리
            for upbit_symbol in batch:
                try:
                    # D82-3: Rate Limiter 체크 (ticker 호출 전)
                    if self._rate_limiter is not None:
                        while not self._rate_limiter.consume():
                            wait_time = self._rate_limiter.wait_time()
                            if wait_time > 0:
                                time.sleep(wait_time)
                    
                    # Upbit ticker
                    ticker = self._upbit_client.fetch_ticker(upbit_symbol)
                    if ticker is None:
                        continue
                    
                    # D82-3: Rate Limiter 체크 (orderbook 호출 전)
                    if self._rate_limiter is not None:
                        while not self._rate_limiter.consume():
                            wait_time = self._rate_limiter.wait_time()
                            if wait_time > 0:
                                time.sleep(wait_time)
                    
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
            
            # 3) 배치 간 지연 (마지막 배치가 아닌 경우)
            if batch_idx + batch_size < len(candidate_symbols):
                logger.info(f"[TOPN_PROVIDER] Batch delay: {batch_delay}s")
                time.sleep(batch_delay)
        
        # 4) 결과 검증
        if not metrics:
            logger.error("[TOPN_PROVIDER] Real Selection failed: no valid metrics")
            logger.warning("[TOPN_PROVIDER] Falling back to MOCK selection")
            return self._fetch_mock_metrics()
        
        logger.info(
            f"[TOPN_PROVIDER] Real Selection completed: {len(metrics)} symbols "
            f"(processed {len(candidate_symbols)} candidates in {total_batches} batches)"
        )
        return metrics
    
    def _filter_by_thresholds(
        self,
        metrics: Dict[str, SymbolMetrics],
    ) -> Dict[str, SymbolMetrics]:
        """
        Threshold 필터링.
        
        D82-2: Mock mode uses relaxed thresholds
        
        Args:
            metrics: {symbol: SymbolMetrics}
        
        Returns:
            Filtered metrics
        """
        # D82-2: Relax thresholds for mock mode (to allow testing with full symbol list)
        if self.selection_data_source == "mock":
            min_volume = 100_000.0  # $100K (relaxed from $1M)
            min_liquidity = 10_000.0  # $10K (relaxed from $50K)
            max_spread = 100.0  # 100 bps (relaxed from 50 bps)
        else:
            min_volume = self.min_volume_usd
            min_liquidity = self.min_liquidity_usd
            max_spread = self.max_spread_bps
        
        filtered: Dict[str, SymbolMetrics] = {}
        
        for symbol, m in metrics.items():
            if m.volume_24h < min_volume:
                continue
            if m.liquidity_depth < min_liquidity:
                continue
            if m.spread_bps > max_spread:
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
        D82-2: Real-time spread for Entry/Exit decisions.
        
        Uses `entry_exit_data_source` (NOT selection_data_source).
        
        Args:
            symbol: Symbol in "BTC/KRW" format
            cross_exchange: True = cross-exchange arbitrage (Upbit-Binance)
                           False = single exchange spread (Upbit only)
        
        Returns:
            SpreadSnapshot or None (data unavailable)
        
        Note:
            - D82-2: Uses entry_exit_data_source for real-time spread checks
            - This is independent of TopN selection data source
        """
        if self.entry_exit_data_source == "mock":
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
    
    def _is_selection_cache_valid(self) -> bool:
        """D82-2: Check if selection cache is still valid"""
        if self._selection_cache is None:
            return False
        
        cache_age = time.monotonic() - self._selection_cache_mono_ts
        return cache_age < self.cache_ttl_seconds
    
    def _get_mock_spread(self, symbol: str) -> SpreadSnapshot:
        """D82-2: Mock spread data (for testing)"""
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
