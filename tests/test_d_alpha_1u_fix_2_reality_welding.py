"""
D_ALPHA-1U-FIX-2-1 Reality Welding Tests.

AC-1: adverse slippage can create a loss.
AC-2: execution reject increments reject counter and skips trades.
AC-3: allow_unprofitable permits intent creation for negative edge.
"""
import pytest

from arbitrage.v2.adapters.paper_execution_adapter import PaperExecutionAdapter
from arbitrage.v2.core.order_intent import OrderIntent, OrderSide, OrderType
from arbitrage.v2.core.paper_executor import PaperExecutor
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector
from arbitrage.v2.core.orchestrator import PaperOrchestrator
from arbitrage.v2.core.opportunity_source import OpportunitySource
from arbitrage.v2.core.profit_core import ProfitCore
from arbitrage.v2.core.config import ProfitCoreConfig
from arbitrage.v2.domain.pnl_calculator import calculate_pnl_summary
from arbitrage.v2.opportunity.detector import OpportunityCandidate, OpportunityDirection
from arbitrage.v2.opportunity.intent_builder import candidate_to_order_intents
from arbitrage.v2.harness.paper_runner import PaperRunnerConfig


class OneShotSource(OpportunitySource):
    def __init__(self, candidate):
        self._candidate = candidate
        self._used = False

    def generate(self, iteration):
        if self._used:
            return None
        self._used = True
        return self._candidate


class DummyLedgerWriter:
    def get_counts(self):
        return {"orders": 0, "fills": 0, "trades": 0}

    def record_order_and_fill(self, *args, **kwargs):
        return None

    def record_trade_complete(self, *args, **kwargs):
        return None


def _adverse_adapter_config(seed=42):
    return {
        "mock_adapter": {
            "enable_slippage": True,
            "slippage_bps_min": 0.0,
            "slippage_bps_max": 0.0,
            "pessimistic_drift_bps_min": 0.0,
            "pessimistic_drift_bps_max": 0.0,
            "latency_base_ms": 0.0,
            "latency_jitter_ms": 0.0,
            "partial_fill_probability": 0.0,
            "adverse_slippage_probability": 1.0,
            "adverse_slippage_bps_min": 20.0,
            "adverse_slippage_bps_max": 20.0,
            "fill_reject_probability": 0.0,
            "random_seed": seed,
        }
    }


def test_ac1_adverse_slippage_can_create_loss():
    adapter = PaperExecutionAdapter(exchange_name="upbit", config=_adverse_adapter_config())

    buy_intent = OrderIntent(
        exchange="upbit",
        symbol="BTC/KRW",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quote_amount=100000.0,
    )
    buy_payload = adapter.translate_intent(buy_intent)
    buy_payload["ref_price"] = 100000.0
    buy_response = adapter.submit_order(buy_payload)
    buy_result = adapter.parse_response(buy_response)

    sell_intent = OrderIntent(
        exchange="upbit",
        symbol="BTC/KRW",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        base_qty=buy_result.filled_qty,
    )
    sell_payload = adapter.translate_intent(sell_intent)
    sell_payload["ref_price"] = 100000.0
    sell_response = adapter.submit_order(sell_payload)
    sell_result = adapter.parse_response(sell_response)

    total_fee = (buy_result.fee or 0.0) + (sell_result.fee or 0.0)
    gross_pnl, realized_pnl, is_win = calculate_pnl_summary(
        entry_side=OrderSide.BUY.value,
        exit_side=OrderSide.SELL.value,
        entry_price=buy_result.filled_price,
        exit_price=sell_result.filled_price,
        quantity=buy_result.filled_qty,
        total_fee=total_fee,
    )

    assert buy_response["adverse_slippage_bps"] > 0
    assert sell_response["adverse_slippage_bps"] > 0
    assert gross_pnl < 0
    assert realized_pnl < 0
    assert is_win is False


def test_ac2_execution_reject_records_reject_and_skips_trade(tmp_path):
    profit_core = ProfitCore(
        ProfitCoreConfig(default_price_krw=100000.0, default_price_usdt=100.0)
    )
    adapter_config = {
        "mock_adapter": {
            "enable_slippage": True,
            "slippage_bps_min": 0.0,
            "slippage_bps_max": 0.0,
            "pessimistic_drift_bps_min": 0.0,
            "pessimistic_drift_bps_max": 0.0,
            "latency_base_ms": 0.0,
            "latency_jitter_ms": 0.0,
            "partial_fill_probability": 0.0,
            "fill_reject_probability": 1.0,
            "random_seed": 7,
        }
    }
    executor = PaperExecutor(profit_core, adapter_config=adapter_config)

    candidate = OpportunityCandidate(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=100000.0,
        price_b=101000.0,
        spread_bps=99.0099,
        break_even_bps=10.0,
        edge_bps=89.0099,
        direction=OpportunityDirection.BUY_A_SELL_B,
        profitable=True,
        deterministic_drift_bps=0.0,
        net_edge_bps=89.0099,
    )
    source = OneShotSource(candidate)

    config = PaperRunnerConfig(
        duration_minutes=0.001,
        phase="smoke",
        output_dir=str(tmp_path),
        db_mode="off",
    )
    config.symbols = [("BTC/KRW", "BTC/USDT")]
    config.cycle_interval_seconds = 0.0

    kpi = PaperMetrics()
    collector = EvidenceCollector(output_dir=str(tmp_path), run_id=config.run_id)

    orch = PaperOrchestrator(
        config=config,
        opportunity_source=source,
        executor=executor,
        ledger_writer=DummyLedgerWriter(),
        kpi=kpi,
        evidence_collector=collector,
        run_id=config.run_id,
    )

    exit_code = orch.run()
    assert exit_code == 0
    assert kpi.closed_trades == 0
    assert kpi.reject_reasons["execution_reject"] > 0


def test_ac3_allow_unprofitable_creates_intents():
    candidate = OpportunityCandidate(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=100000.0,
        price_b=101000.0,
        spread_bps=99.0099,
        break_even_bps=150.0,
        edge_bps=-50.9901,
        direction=OpportunityDirection.BUY_A_SELL_B,
        profitable=False,
        deterministic_drift_bps=0.0,
        net_edge_bps=-50.9901,
        allow_unprofitable=True,
    )

    intents = candidate_to_order_intents(candidate, quote_amount=100000.0)
    assert len(intents) == 2

    candidate.allow_unprofitable = False
    blocked = candidate_to_order_intents(candidate, quote_amount=100000.0)
    assert blocked == []
