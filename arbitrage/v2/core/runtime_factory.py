"""Runtime Factory - Core 컴포넌트 조립 (의존성 주입)

D206-1 CLOSEOUT: Preflight/Registry 요구사항 충족
"""
from typing import Optional
import logging
import os
import yaml

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
from arbitrage.v2.core.fx_provider import LiveFxProvider, FixedFxProvider
from arbitrage.v2.marketdata.rate_limiter import RateLimiter
from arbitrage.v2.storage.ledger import V2LedgerStorage
from arbitrage.v2.core.profit_core import ProfitCore
from arbitrage.v2.core.config import load_config
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.redis_client import RedisClient
from arbitrage.v2.universe.builder import from_config_dict

logger = logging.getLogger(__name__)


def build_paper_runtime(config, admin_control=None) -> PaperOrchestrator:
    """Paper Runtime 조립 (Factory Pattern)
    
    Args:
        config: PaperRunnerConfig
        admin_control: Optional AdminControl
    
    Returns:
        PaperOrchestrator (모든 의존성 주입 완료)
    """
    logger.info(f"[D207-1] Building Paper Runtime...")
    
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
            universe_cfg = raw_config.get("universe", {}) or {}

            if not config.use_real_data:
                universe_cfg = dict(universe_cfg)
                universe_cfg["data_source"] = "mock"

            if config.symbols_top:
                universe_cfg["topn_count"] = config.symbols_top
            elif "topn_count" not in universe_cfg:
                universe_cfg["topn_count"] = v2_config.universe.symbols_top_n

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

        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        config.break_even_params = BreakEvenParams.from_threshold_config(
            fee_model=fee_model,
            threshold_config=v2_config.strategy.threshold,
        )
        config.break_even_params_auto = False

    if getattr(config, "fill_probability_params", None) is None:
        config.fill_probability_params = v2_config.fill_probability

    if getattr(config, "min_hold_ms", None) is None:
        config.min_hold_ms = v2_config.safety.min_hold_ms
    if getattr(config, "cooldown_after_loss_seconds", None) is None:
        config.cooldown_after_loss_seconds = v2_config.safety.cooldown_after_loss_seconds
    deterministic_drift_bps = float(getattr(v2_config.strategy, "deterministic_drift_bps", 0.0))
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
    
    if config.use_real_data:
        try:
            rate_limiter_upbit = RateLimiter(requests_per_second=9, burst=2)
            rate_limiter_binance = RateLimiter(requests_per_second=20, burst=5)
            upbit_provider = UpbitRestProvider(timeout=10.0, rate_limiter=rate_limiter_upbit)
            binance_provider = BinanceRestProvider(timeout=10.0)
            logger.info(f"[D207-1] Real MarketData Providers initialized")
        except Exception as e:
            logger.error(f"[D207-1] Provider init failed: {e}", exc_info=True)
            raise RuntimeError(f"Provider initialization failed: {e}")
    
    # 3. FX Provider (D207-1-2: Real data는 Live FX, 테스트/Mock은 Fixed FX)
    fx_mode = getattr(config, "fx_provider_mode", "live" if config.use_real_data else "fixed")

    # D207-3: REAL 모드에서는 fixed FX 금지 (원천 차단)
    if config.use_real_data and fx_mode == "fixed":
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
        )
        logger.info(f"[D207-1] MockOpportunitySource initialized (MOCK MarketData)")
    
    # 5. PaperExecutor (주문 실행 + Balance) - D206-1 FIXPACK: profit_core 주입
    adapter_config = {"mock_adapter": v2_config.mock_adapter} if v2_config.mock_adapter else None
    executor = PaperExecutor(profit_core, adapter_config=adapter_config)  # D206-1 FIXPACK
    
    # 6. LedgerWriter (DB 기록)
    storage = None
    if config.db_mode != "off":
        if config.db_connection_string:
            storage = V2LedgerStorage(
                connection_string=config.db_connection_string,
                ensure_schema=config.ensure_schema,
            )
    
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
            if redis_client.available:
                logger.info(f"[D206-1] Redis initialized: {redis_config['url']}")
            else:
                logger.warning(f"[D206-1] Redis unavailable (graceful fallback)")
        except Exception as e:
            logger.warning(f"[D206-1] Redis init failed: {e}")
    
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
