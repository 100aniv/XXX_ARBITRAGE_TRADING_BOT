"""Runtime Factory - Core 컴포넌트 조립 (의존성 주입)

D206-1 CLOSEOUT: Preflight/Registry 요구사항 충족
"""
from typing import Optional, List, Tuple, Dict, Any
import logging
import asyncio
import os
import threading
import time
import yaml
from datetime import datetime, timezone

from arbitrage.v2.core.opportunity_source import (
    OpportunitySource,
    RealOpportunitySource,
    MockOpportunitySource,
)
from arbitrage.v2.core.paper_executor import PaperExecutor
from arbitrage.v2.core.ledger_writer import LedgerWriter
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector
from arbitrage.v2.core.orchestrator import PaperOrchestrator
from arbitrage.v2.marketdata.rest.upbit import UpbitRestProvider
from arbitrage.v2.marketdata.rest.binance import BinanceRestProvider
from arbitrage.v2.marketdata.ws import UpbitWsProvider, BinanceWsProvider
from arbitrage.v2.marketdata.interfaces import WsProvider, Orderbook, OrderbookLevel
from arbitrage.v2.core.fx_provider import LiveFxProvider, FixedFxProvider
from arbitrage.v2.marketdata.rate_limiter import RateLimiter
from arbitrage.v2.storage.ledger import V2LedgerStorage
from arbitrage.v2.core.profit_core import ProfitCore
from arbitrage.v2.core.config import load_config
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.redis_client import RedisClient
from arbitrage.v2.universe.builder import from_config_dict
from arbitrage.exchanges.upbit_ws_adapter import UpbitWebSocketAdapter
from arbitrage.exchanges.binance_ws_adapter import BinanceWebSocketAdapter
from arbitrage.exchanges.base import OrderBookSnapshot


logger = logging.getLogger(__name__)


def _upbit_v2_to_ws_symbol(symbol: str) -> str:
    base, quote = symbol.split("/")
    if quote != "KRW":
        raise ValueError(f"Unsupported Upbit symbol quote: {symbol}")
    return f"{quote}-{base}"  # KRW-BTC


def _binance_v2_to_ws_symbol(symbol: str) -> str:
    base, quote = symbol.split("/")
    if quote != "USDT":
        raise ValueError(f"Unsupported Binance symbol quote: {symbol}")
    return f"{base}{quote}".lower()  # btcusdt


def _upbit_ws_to_v2_symbol(symbol: str) -> str:
    # KRW-BTC -> BTC/KRW
    quote, base = symbol.split("-")
    return f"{base}/{quote}"


def _binance_ws_to_v2_symbol(symbol: str) -> str:
    # BTCUSDT -> BTC/USDT
    if not symbol.endswith("USDT"):
        return symbol
    base = symbol[:-4]
    return f"{base}/USDT"


class _AdapterBackedWsProvider(WsProvider):
    def __init__(
        self,
        exchange: str,
        symbols_v2: List[str],
        depth: str = "20",
        interval: str = "100ms",
    ):
        self.exchange = exchange
        self.symbols_v2 = list(symbols_v2)
        self.depth = depth
        self.interval = interval

        self._lock = threading.Lock()
        self._latest: Dict[str, Orderbook] = {}

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._adapter = None

    async def connect(self) -> None:
        self._ensure_started()

    async def disconnect(self) -> None:
        self._stop.set()
        if self._loop is not None:
            loop = self._loop
            adapter = self._adapter

            def _request_shutdown() -> None:
                if adapter is not None:
                    try:
                        asyncio.create_task(adapter.disconnect())
                    except Exception:
                        pass

            try:
                loop.call_soon_threadsafe(_request_shutdown)
            except Exception:
                pass
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    async def subscribe(self, symbols: List[str]) -> None:
        # 브릿지 내부에서 구독 심볼은 생성 시점에 고정한다.
        return

    def get_latest_orderbook(self, symbol: str) -> Optional[Orderbook]:
        with self._lock:
            return self._latest.get(symbol)

    async def health_check(self) -> bool:
        adapter = self._adapter
        if adapter is None:
            return False
        return bool(getattr(adapter, "is_connected", False))

    def _ensure_started(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run())
        finally:
            try:
                loop.stop()
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

    async def _run(self) -> None:
        if self.exchange == "upbit":
            ws_symbols = [_upbit_v2_to_ws_symbol(sym) for sym in self.symbols_v2]
            adapter = UpbitWebSocketAdapter(symbols=ws_symbols, callback=self._on_snapshot)
            channels = ws_symbols
        elif self.exchange == "binance":
            ws_symbols = [_binance_v2_to_ws_symbol(sym) for sym in self.symbols_v2]
            adapter = BinanceWebSocketAdapter(
                symbols=ws_symbols,
                callback=self._on_snapshot,
                depth=self.depth,
                interval=self.interval,
            )
            channels = [f"{sym}@depth{self.depth}@{self.interval}" for sym in ws_symbols]
        else:
            raise ValueError(f"Unsupported exchange for WS bridge: {self.exchange}")

        self._adapter = adapter

        def _resubscribe_on_reconnect() -> None:
            try:
                asyncio.create_task(adapter.subscribe(channels))
            except Exception:
                pass

        adapter.on_reconnect = _resubscribe_on_reconnect

        await adapter.connect()
        await adapter.subscribe(channels)

        receive_task = asyncio.create_task(adapter.receive_loop())
        try:
            while not self._stop.is_set():
                await asyncio.sleep(0.1)
        finally:
            try:
                await adapter.disconnect()
            except Exception:
                pass
            try:
                receive_task.cancel()
            except Exception:
                pass

    def _on_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        try:
            if self.exchange == "upbit":
                v2_symbol = _upbit_ws_to_v2_symbol(snapshot.symbol)
            else:
                v2_symbol = _binance_ws_to_v2_symbol(snapshot.symbol)

            ts = datetime.fromtimestamp(float(snapshot.timestamp), tz=timezone.utc)
            bids = [OrderbookLevel(price=float(p), quantity=float(q)) for p, q in (snapshot.bids or [])]
            asks = [OrderbookLevel(price=float(p), quantity=float(q)) for p, q in (snapshot.asks or [])]
            orderbook = Orderbook(
                exchange=self.exchange,
                symbol=v2_symbol,
                timestamp=ts,
                bids=bids,
                asks=asks,
            )
            with self._lock:
                self._latest[v2_symbol] = orderbook
        except Exception as exc:
            logger.warning(f"[CLEAN_ROOM_WS] Snapshot convert failed: exchange={self.exchange}, err={exc}")


def _build_fee_model_from_v2_config(v2_config) -> FeeModel:
    use_exchange_fees = v2_config.strategy.threshold.use_exchange_fees
    upbit_cfg = v2_config.exchanges.get("upbit")
    binance_cfg = v2_config.exchanges.get("binance")
    if use_exchange_fees and upbit_cfg and binance_cfg:
        fee_a = FeeStructure(
            exchange_name="upbit",
            maker_fee_bps=upbit_cfg.maker_fee_bps,
            taker_fee_bps=upbit_cfg.taker_fee_bps,
        )
        fee_b = FeeStructure(
            exchange_name="binance",
            maker_fee_bps=binance_cfg.maker_fee_bps,
            taker_fee_bps=binance_cfg.taker_fee_bps,
        )
    else:
        fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=0.0, taker_fee_bps=0.0)
        fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=0.0, taker_fee_bps=0.0)
    return FeeModel(fee_a=fee_a, fee_b=fee_b)


def build_break_even_params_from_v2_config(v2_config) -> BreakEvenParams:
    fee_model = _build_fee_model_from_v2_config(v2_config)
    return BreakEvenParams.from_threshold_config(
        fee_model=fee_model,
        threshold_config=v2_config.strategy.threshold,
    )


def build_break_even_params_from_config_path(config_path: str = "config/v2/config.yml") -> BreakEvenParams:
    v2_config = load_config(config_path)
    return build_break_even_params_from_v2_config(v2_config)


def build_paper_runtime(config, admin_control=None) -> PaperOrchestrator:
    """Paper Runtime 조립 (Factory Pattern)
    
    Args:
        config: PaperRunnerConfig
        admin_control: Optional AdminControl
    
    Returns:
        PaperOrchestrator (모든 의존성 주입 완료)
    """
    logger.info(f"[D207-1] Building Paper Runtime...")

    clean_room = bool(getattr(config, "clean_room", False))
    if clean_room and not getattr(config, "use_real_data", False):
        raise RuntimeError("[CLEAN_ROOM] requires use_real_data=True")

    if getattr(config, "db_mode", "") == "strict":
        if not os.getenv("POSTGRES_CONNECTION_STRING"):
            logger.critical("[D_ALPHA-1U] DB strict requires POSTGRES_CONNECTION_STRING")
            raise SystemExit(1)
        if not os.getenv("REDIS_URL"):
            logger.critical("[D_ALPHA-1U] DB strict requires REDIS_URL")
            raise SystemExit(1)
    
    # 0. D206-1 CLOSEOUT: ProfitCore (config.yml 기반)
    v2_config = load_config("config/v2/config.yml")
    profit_core = ProfitCore(v2_config.profit_core)
    logger.info(f"[D206-1] ProfitCore loaded: default_price_krw={v2_config.profit_core.default_price_krw}")

    # D207-5: run_meta defaults (config_path/symbols)
    if getattr(config, "config_path", None) is None:
        config.config_path = "config/v2/config.yml"
    if getattr(config, "symbols", None) in (None, [], ()):  # 실제 사용 심볼 (UniverseBuilder)
        try:
            with open(config.config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}
            universe_cfg = dict(raw_config.get("universe", {}) or {})

            if clean_room:
                universe_cfg["mode"] = "static"
                universe_cfg["data_source"] = "mock"
                universe_cfg["clean_room"] = True
            else:
                universe_mode = getattr(config, "universe_mode", None)
                if universe_mode is not None:
                    universe_cfg["mode"] = universe_mode
                if universe_cfg.get("mode") == "topn":
                    if config.use_real_data:
                        universe_cfg["data_source"] = "real"
                    else:
                        universe_cfg["data_source"] = "mock"

                    requested_topn = v2_config.universe.symbols_top_n
                    symbols_top = getattr(config, "symbols_top", None)
                    if isinstance(symbols_top, int) and symbols_top > 0:
                        requested_topn = symbols_top
                    universe_cfg["topn_count"] = requested_topn

            builder = from_config_dict(universe_cfg)
            symbols = builder.get_symbols()

            allowlist = set(v2_config.universe.allowlist or [])
            denylist = set(v2_config.universe.denylist or [])
            if allowlist:
                symbols = [pair for pair in symbols if pair[0] in allowlist]
            if denylist:
                symbols = [pair for pair in symbols if pair[0] not in denylist]

            config.symbols = symbols
            
            # D_ALPHA-0: Universe metadata 저장
            universe_snapshot = builder.get_snapshot()
            config.universe_metadata = {
                "universe_requested_top_n": universe_snapshot.get("universe_requested_top_n"),
                "universe_loaded_count": len(symbols),  # allowlist/denylist 적용 후 실제 개수
                "mode": universe_snapshot.get("mode"),
            }
            
            logger.info(
                f"[D_ALPHA-0] Universe loaded: requested={config.universe_metadata['universe_requested_top_n']}, "
                f"loaded={config.universe_metadata['universe_loaded_count']}, mode={config.universe_metadata['mode']}"
            )
        except Exception as e:
            logger.warning(f"[D207-6] Universe load failed, fallback to BTC only: {e}")
            config.symbols = [("BTC/KRW", "BTC/USDT")]

    if getattr(config, "order_size_policy_mode", None) is None:
        config.order_size_policy_mode = v2_config.strategy.order_size_policy.mode
    if getattr(config, "fixed_quote", None) is None:
        config.fixed_quote = v2_config.strategy.order_size_policy.fixed_quote

    if getattr(config, "break_even_params", None) is None or getattr(config, "break_even_params_auto", False):
        config.break_even_params = build_break_even_params_from_v2_config(v2_config)
        config.break_even_params_auto = False

    fee_rates = None
    if getattr(config, "break_even_params", None) is not None:
        fee_model = getattr(config.break_even_params, "fee_model", None)
        if fee_model and getattr(fee_model, "fee_a", None) and getattr(fee_model, "fee_b", None):
            fee_rates = {
                str(getattr(fee_model.fee_a, "exchange_name", "upbit")).lower(): fee_model.fee_a.taker_fee_bps,
                str(getattr(fee_model.fee_b, "exchange_name", "binance")).lower(): fee_model.fee_b.taker_fee_bps,
            }

    if getattr(config, "fill_probability_params", None) is None:
        config.fill_probability_params = v2_config.fill_probability

    if getattr(config, "min_hold_ms", None) is None:
        config.min_hold_ms = v2_config.safety.min_hold_ms
    if getattr(config, "cooldown_after_loss_seconds", None) is None:
        config.cooldown_after_loss_seconds = v2_config.safety.cooldown_after_loss_seconds
    deterministic_drift_bps = float(getattr(v2_config.strategy, "deterministic_drift_bps", 0.0))
    negative_edge_execution_probability = float(
        getattr(v2_config.strategy, "negative_edge_execution_probability", 0.0)
    )
    negative_edge_floor_bps = float(
        getattr(v2_config.strategy, "negative_edge_floor_bps", 0.0)
    )
    min_net_edge_bps = float(getattr(v2_config.strategy, "min_net_edge_bps", 0.0))
    obi_filter_cfg = getattr(v2_config.strategy, "obi_filter", None)
    obi_dynamic_cfg = getattr(v2_config.strategy, "obi_dynamic_threshold", None)
    if getattr(config, "deterministic_drift_bps", None) is None:
        config.deterministic_drift_bps = deterministic_drift_bps
    if config.use_real_data and getattr(config, "cycle_interval_seconds", None) is None:
        exec_cfg = getattr(v2_config, "execution", None)
        if exec_cfg is not None and getattr(exec_cfg, "cycle_interval_seconds", None) is not None:
            config.cycle_interval_seconds = exec_cfg.cycle_interval_seconds
        else:
            config.cycle_interval_seconds = v2_config.cycle_interval_seconds

    fx_config = getattr(v2_config, "fx", {}) or {}
    fx_provider_mode = getattr(config, "fx_provider_mode", None)
    if fx_provider_mode is None:
        fx_provider_mode = fx_config.get("provider")
    if fx_provider_mode is None:
        fx_provider_mode = "live" if config.use_real_data else "fixed"
    config.fx_provider_mode = fx_provider_mode
    if config.fx_provider_mode == "fixed":
        fixed_cfg = fx_config.get("fixed", {}) or {}
        config.fx_krw_per_usdt = fixed_cfg.get(
            "krw_per_usdt",
            getattr(config, "fx_krw_per_usdt", 1450.0),
        )
    
    # 1. Metrics & Evidence
    kpi = PaperMetrics()
    evidence_collector = EvidenceCollector(
        output_dir=config.output_dir,
        run_id=config.run_id,
    )
    
    # 2. MarketData Providers (use_real_data에 따라 분기)
    upbit_provider = None
    binance_provider = None
    rate_limiter_upbit = None
    rate_limiter_binance = None
    upbit_ws_provider = None
    binance_ws_provider = None
    
    if config.use_real_data and (not clean_room):
        try:
            rate_limiter_upbit = RateLimiter(requests_per_second=9, burst=2)
            rate_limiter_binance = RateLimiter(requests_per_second=20, burst=5)
            upbit_provider = UpbitRestProvider(timeout=10.0)
            binance_provider = BinanceRestProvider(timeout=10.0)
            logger.info(f"[D207-1] Real MarketData Providers initialized")
        except Exception as e:
            logger.error(f"[D207-1] Provider init failed: {e}", exc_info=True)
            raise RuntimeError(f"Provider initialization failed: {e}")

    cache_cfg = getattr(v2_config, "cache", None)
    if config.use_real_data and clean_room:
        upbit_ws_provider = _AdapterBackedWsProvider(
            exchange="upbit",
            symbols_v2=[pair[0] for pair in getattr(config, "symbols", [])],
        )
        binance_ws_provider = _AdapterBackedWsProvider(
            exchange="binance",
            symbols_v2=[pair[1] for pair in getattr(config, "symbols", [])],
        )
        logger.info("[CLEAN_ROOM] WS providers initialized (adapter-backed)")
    elif config.use_real_data and cache_cfg and getattr(cache_cfg, "redis_enabled", False):
        upbit_ws_provider = UpbitWsProvider()
        binance_ws_provider = BinanceWsProvider()
        logger.info("[D207-1] WS providers initialized (cache.redis_enabled=True)")
    
    # 3. FX Provider (D207-1-2: Real data는 Live FX, 테스트/Mock은 Fixed FX)
    fx_mode = getattr(config, "fx_provider_mode", "live" if config.use_real_data else "fixed")

    # D207-3: REAL 모드에서는 fixed FX 금지 (원천 차단)
    if clean_room and fx_mode != "fixed":
        raise RuntimeError("[CLEAN_ROOM] requires fx_provider_mode=fixed")

    if config.use_real_data and fx_mode == "fixed" and (not clean_room):
        raise RuntimeError("REAL mode requires live FX provider (fixed FX is forbidden)")

    class _FxMarketDataFetcher:
        def __init__(self, upbit, binance):
            self.upbit = upbit
            self.binance = binance

        def get_mid_price(self, exchange: str, symbol: str) -> float:
            provider = self.upbit if exchange == "upbit" else self.binance
            if provider is None:
                raise RuntimeError(f"FX fetcher provider missing: {exchange}")
            ticker = provider.get_ticker(symbol)
            if not ticker:
                raise RuntimeError(f"FX fetcher ticker missing: {exchange}/{symbol}")
            bid = getattr(ticker, "bid", None)
            ask = getattr(ticker, "ask", None)
            if bid and ask:
                return (bid + ask) / 2.0
            last = getattr(ticker, "last", None)
            if last:
                return float(last)
            raise RuntimeError(f"FX fetcher price missing: {exchange}/{symbol}")

    if fx_mode == "fixed":
        fx_provider = FixedFxProvider(fx_krw_per_usdt=getattr(config, "fx_krw_per_usdt", 1450.0))
        logger.info("[D207-1] FixedFxProvider selected for paper/test mode")
    else:
        fx_live_cfg = fx_config.get("live", {}) or {}
        fx_source = fx_live_cfg.get("source", "crypto_implied")
        fx_ttl_seconds = fx_live_cfg.get("ttl_seconds", 60.0)
        fx_http_cfg = fx_live_cfg.get("http", {}) or {}
        market_data_fetcher = _FxMarketDataFetcher(upbit_provider, binance_provider) if config.use_real_data else None
        fx_provider = LiveFxProvider(
            source=fx_source,
            ttl_seconds=fx_ttl_seconds,
            http_base_url=fx_http_cfg.get("base_url"),
            http_timeout=fx_http_cfg.get("timeout_seconds", 5.0),
            market_data_fetcher=market_data_fetcher,
        )
    
    # 4. OpportunitySource (Real/Mock 전략) - D206-1 FIXPACK: profit_core 주입
    # D207-1 Step 2: REAL MarketData 강제 검증 (baseline/longrun phase)
    if config.phase in ["baseline", "longrun"] and not config.use_real_data:
        logger.error(f"[D207-1 REAL GUARD] FAIL: phase={config.phase} requires use_real_data=True")
        logger.error(f"[D207-1 REAL GUARD] Reason: MOCK data is invalid for {config.phase} validation")
        raise RuntimeError(f"phase={config.phase} requires --use-real-data flag")
    
    if config.use_real_data:
        if clean_room:
            # Clean-room은 WS-only 모드이므로 런타임 시작 전에 캐시 프리웜을 강제한다.
            upbit_ws_provider._ensure_started()
            binance_ws_provider._ensure_started()
            required_pairs: List[Tuple[str, str]] = list(getattr(config, "symbols", []) or [])
            deadline = time.time() + 15.0
            while time.time() < deadline:
                ok = True
                for sym_a, sym_b in required_pairs:
                    if upbit_ws_provider.get_latest_orderbook(sym_a) is None:
                        ok = False
                        break
                    if binance_ws_provider.get_latest_orderbook(sym_b) is None:
                        ok = False
                        break
                if ok:
                    break
                time.sleep(0.1)
            if required_pairs:
                for sym_a, sym_b in required_pairs:
                    if upbit_ws_provider.get_latest_orderbook(sym_a) is None:
                        raise RuntimeError(f"[CLEAN_ROOM] WS prewarm failed (upbit): {sym_a}")
                    if binance_ws_provider.get_latest_orderbook(sym_b) is None:
                        raise RuntimeError(f"[CLEAN_ROOM] WS prewarm failed (binance): {sym_b}")

        opportunity_source = RealOpportunitySource(
            upbit_provider=upbit_provider,
            binance_provider=binance_provider,
            rate_limiter_upbit=rate_limiter_upbit,
            rate_limiter_binance=rate_limiter_binance,
            fx_provider=fx_provider,
            break_even_params=config.break_even_params,
            fill_probability_params=getattr(config, "fill_probability_params", None),
            kpi=kpi,
            profit_core=profit_core,  # D206-1 FIXPACK
            deterministic_drift_bps=config.deterministic_drift_bps,
            symbols=getattr(config, "symbols", None),
            max_symbols_per_tick=getattr(config, "max_symbols_per_tick", None),
            survey_mode=getattr(config, "survey_mode", False),
            maker_mode=getattr(config, "maker_mode", False),
            negative_edge_execution_probability=negative_edge_execution_probability,
            negative_edge_floor_bps=negative_edge_floor_bps,
            obi_filter=obi_filter_cfg,
            obi_dynamic_threshold=obi_dynamic_cfg,
            min_net_edge_bps=min_net_edge_bps,
            upbit_ws_provider=upbit_ws_provider,
            binance_ws_provider=binance_ws_provider,
            clean_room=clean_room,
            order_size_policy_mode=getattr(config, "order_size_policy_mode", "fixed_quote"),
            fixed_quote=getattr(config, "fixed_quote", None),
            default_quote_amount=getattr(config, "default_quote_amount", 100000.0),
        )
        logger.info(f"[D207-1] RealOpportunitySource initialized (REAL MarketData, survey_mode={getattr(config, 'survey_mode', False)})")
    else:
        opportunity_source = MockOpportunitySource(
            fx_provider=fx_provider,
            break_even_params=config.break_even_params,
            fill_probability_params=getattr(config, "fill_probability_params", None),
            kpi=kpi,
            profit_core=profit_core,  # D206-1 FIXPACK
            deterministic_drift_bps=config.deterministic_drift_bps,
            maker_mode=getattr(config, "maker_mode", False),
            negative_edge_execution_probability=negative_edge_execution_probability,
            negative_edge_floor_bps=negative_edge_floor_bps,
        )
        logger.info(f"[D207-1] MockOpportunitySource initialized (MOCK MarketData)")
    
    # 5. PaperExecutor (주문 실행 + Balance) - D206-1 FIXPACK: profit_core 주입
    adapter_config = {"mock_adapter": dict(v2_config.mock_adapter)} if v2_config.mock_adapter else {}
    if getattr(config, "break_even_params", None) is not None and "mock_adapter" in adapter_config:
        mock_cfg = adapter_config["mock_adapter"]
        if getattr(config.break_even_params, "slippage_bps", None) is not None:
            mock_cfg["slippage_bps_min"] = float(config.break_even_params.slippage_bps)
            mock_cfg["slippage_bps_max"] = float(config.break_even_params.slippage_bps)
        if getattr(config.break_even_params, "latency_bps", None) is not None:
            mock_cfg["pessimistic_drift_bps_min"] = float(config.break_even_params.latency_bps)
            mock_cfg["pessimistic_drift_bps_max"] = float(config.break_even_params.latency_bps)
    if fee_rates:
        adapter_config["fee_rates"] = fee_rates
    if not adapter_config:
        adapter_config = None
    executor = PaperExecutor(profit_core, adapter_config=adapter_config)  # D206-1 FIXPACK
    
    # 6. LedgerWriter (DB 기록)
    storage = None
    if config.db_mode != "off":
        if config.db_connection_string:
            storage = V2LedgerStorage(
                connection_string=config.db_connection_string,
                ensure_schema=config.ensure_schema,
            )

    if config.db_mode == "strict":
        if not storage:
            raise RuntimeError("DB strict mode requires initialized storage")
        missing_tables = storage.verify_schema(["v2_orders", "v2_fills", "v2_trades"])
        if missing_tables:
            raise RuntimeError(f"DB strict mode missing tables: {missing_tables}")

    ledger_writer = LedgerWriter(storage=storage, config=config)

    # 6-1. Redis (D206-1 CLOSEOUT: OPS Gate 필수)
    redis_client = None
    if config.db_mode != "off":
        try:
            redis_config = {
                "enabled": True,
                "url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                "prefix": "arb",
                "health_ttl_seconds": 60
            }
            redis_client = RedisClient(redis_config)
            redis_available = bool(redis_client.available and redis_client.ping())
            kpi.redis_ok = redis_available
            if redis_available:
                logger.info(f"[D206-1] Redis initialized: {redis_config['url']}")
            else:
                logger.critical("[D_ALPHA-1U] Redis unavailable: fail-fast")
                raise SystemExit(1)
        except SystemExit:
            kpi.redis_ok = False
            raise
        except Exception as e:
            kpi.redis_ok = False
            logger.critical(f"[D_ALPHA-1U] Redis init failed: {e}")
            raise SystemExit(1)
    
    # 7. Orchestrator 조립 (D206-1 CLOSEOUT: redis_client 전달)
    orchestrator = PaperOrchestrator(
        config=config,
        opportunity_source=opportunity_source,
        executor=executor,
        ledger_writer=ledger_writer,
        kpi=kpi,
        evidence_collector=evidence_collector,
        admin_control=admin_control,
        run_id=config.run_id,
    )
    
    # D206-1 CLOSEOUT: Orchestrator에 redis_client 주입 (Preflight 필수)
    orchestrator.redis_client = redis_client
    
    logger.info(f"[D205-18-2D] Paper Runtime built successfully")
    return orchestrator
