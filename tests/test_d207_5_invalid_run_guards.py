"""
D207-5: Invalid Run Guard Tests

- symbols empty -> Exit 1
- REAL mode with real_ticks_ok_count == 0 -> Exit 1
"""

from arbitrage.v2.core.orchestrator import PaperOrchestrator
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector
from arbitrage.v2.harness.paper_runner import PaperRunnerConfig
from arbitrage.v2.core.opportunity_source import OpportunitySource, RealOpportunitySource
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure


class DummySource(OpportunitySource):
    def generate(self, iteration):
        return None


class RealNoTickSource(RealOpportunitySource):
    def __init__(self, kpi):
        fee_model = FeeModel(
            fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0),
            fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=4.0, taker_fee_bps=4.0),
        )
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=5.0,
            latency_bps=2.0,
            buffer_bps=3.0,
        )
        super().__init__(
            upbit_provider=None,
            binance_provider=None,
            rate_limiter_upbit=None,
            rate_limiter_binance=None,
            fx_provider=None,
            break_even_params=params,
            kpi=kpi,
            profit_core=None,
            deterministic_drift_bps=0.0,
        )

    def generate(self, iteration):
        return None


class DummyExecutor:
    def execute(self, *args, **kwargs):
        raise RuntimeError("should not execute")


class DummyLedgerWriter:
    def get_counts(self):
        return {"orders": 0, "fills": 0, "trades": 0}

    def record_order_and_fill(self, *args, **kwargs):
        return None

    def record_trade_complete(self, *args, **kwargs):
        return None


def test_invalid_run_symbols_empty(tmp_path):
    config = PaperRunnerConfig(duration_minutes=0, phase="smoke", output_dir=str(tmp_path))
    config.symbols = []

    kpi = PaperMetrics()
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id=config.run_id)

    orch = PaperOrchestrator(
        config=config,
        opportunity_source=DummySource(),
        executor=DummyExecutor(),
        ledger_writer=DummyLedgerWriter(),
        kpi=kpi,
        evidence_collector=collector,
        run_id=config.run_id,
    )

    exit_code = orch.run()
    assert exit_code == 1
    assert kpi.stop_reason == "INVALID_RUN_SYMBOLS_EMPTY"


def test_invalid_run_real_ticks_zero(tmp_path):
    config = PaperRunnerConfig(duration_minutes=0, phase="smoke", output_dir=str(tmp_path))
    config.symbols = [("BTC/KRW", "BTC/USDT")]

    kpi = PaperMetrics()
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id=config.run_id)

    orch = PaperOrchestrator(
        config=config,
        opportunity_source=RealNoTickSource(kpi=kpi),
        executor=DummyExecutor(),
        ledger_writer=DummyLedgerWriter(),
        kpi=kpi,
        evidence_collector=collector,
        run_id=config.run_id,
    )

    exit_code = orch.run()
    assert exit_code == 1
    assert kpi.stop_reason == "INVALID_RUN_REAL_TICKS_ZERO"


def test_invalid_run_symbols_invalid_format(tmp_path):
    config = PaperRunnerConfig(duration_minutes=0, phase="smoke", output_dir=str(tmp_path))
    config.symbols = [("BTC/KRW",)]

    kpi = PaperMetrics()
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id=config.run_id)

    orch = PaperOrchestrator(
        config=config,
        opportunity_source=DummySource(),
        executor=DummyExecutor(),
        ledger_writer=DummyLedgerWriter(),
        kpi=kpi,
        evidence_collector=collector,
        run_id=config.run_id,
    )

    exit_code = orch.run()
    assert exit_code == 1
    assert kpi.stop_reason == "INVALID_RUN_SYMBOLS_INVALID"
