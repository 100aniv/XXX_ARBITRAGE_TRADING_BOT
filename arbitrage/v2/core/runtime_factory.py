"""Runtime Factory - Core 컴포넌트 조립 (의존성 주입)"""
from typing import Optional
import logging

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
from arbitrage.v2.marketdata.fx_provider import FXProvider
from arbitrage.v2.marketdata.rate_limiter import RateLimiter
from arbitrage.v2.storage.ledger import V2LedgerStorage

logger = logging.getLogger(__name__)


def build_paper_runtime(config, admin_control=None) -> PaperOrchestrator:
    """Paper Runtime 조립 (Factory Pattern)
    
    Args:
        config: PaperRunnerConfig
        admin_control: Optional AdminControl
    
    Returns:
        PaperOrchestrator (모든 의존성 주입 완료)
    """
    logger.info(f"[D205-18-2D] Building Paper Runtime...")
    
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
            upbit_provider = UpbitRestProvider(timeout=10.0)
            binance_provider = BinanceRestProvider(timeout=10.0)
            rate_limiter_upbit = RateLimiter(requests_per_second=9, burst=2)
            rate_limiter_binance = RateLimiter(requests_per_second=20, burst=5)
            logger.info(f"[D205-18-2D] Real MarketData Providers initialized")
        except Exception as e:
            logger.error(f"[D205-18-2D] Provider init failed: {e}", exc_info=True)
            raise RuntimeError(f"Provider initialization failed: {e}")
    
    # 3. FX Provider
    fx_provider = FXProvider(default_krw_per_usdt=config.fx_krw_per_usdt)
    
    # 4. OpportunitySource (Real/Mock 전략)
    if config.use_real_data:
        opportunity_source = RealOpportunitySource(
            upbit_provider=upbit_provider,
            binance_provider=binance_provider,
            rate_limiter_upbit=rate_limiter_upbit,
            rate_limiter_binance=rate_limiter_binance,
            fx_provider=fx_provider,
            break_even_params=config.break_even_params,
            kpi=kpi,
        )
    else:
        opportunity_source = MockOpportunitySource(
            fx_provider=fx_provider,
            break_even_params=config.break_even_params,
            kpi=kpi,
        )
    
    # 5. PaperExecutor (주문 실행 + Balance)
    executor = PaperExecutor()
    
    # 6. LedgerWriter (DB 기록)
    storage = None
    if config.db_mode != "off":
        if config.db_connection_string:
            storage = V2LedgerStorage(
                connection_string=config.db_connection_string,
                ensure_schema=config.ensure_schema,
            )
    
    ledger_writer = LedgerWriter(storage=storage, config=config)
    
    # 7. Orchestrator 조립
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
    
    logger.info(f"[D205-18-2D] Paper Runtime built successfully")
    return orchestrator
