"""
D_ALPHA-2: Dynamic OBI Threshold + Artifact

- warmup -> threshold ready
- zero-pass guard ensures at least one pass
- obi_dynamic_threshold.json artifact saved
"""

from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.v2.core.config import ObiDynamicThresholdConfig, ObiFilterConfig
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.monitor import EvidenceCollector
from arbitrage.v2.core.opportunity_source import (
    RealOpportunitySource,
    _candidate_to_edge_dict,
    _compute_dynamic_threshold,
)
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.opportunity.detector import OpportunityCandidate, OpportunityDirection


def test_dynamic_threshold_warmup_and_artifact(tmp_path):
    values = [-5.0, -3.0, -1.0]
    threshold, pass_rate, fallback_used, reason = _compute_dynamic_threshold(
        values=values,
        percentile=0.9,
        min_pass_rate=0.05,
        min_samples=1,
        min_net_edge_bps=10.0,
    )
    assert threshold == min(values)
    assert pass_rate > 0
    assert fallback_used is True
    assert reason == "zero_pass_guard"

    kpi = PaperMetrics()
    fee_model = FeeModel(
        fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0),
        fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=4.0, taker_fee_bps=4.0),
    )
    params = BreakEvenParams(
        fee_model=fee_model,
        slippage_bps=1.0,
        latency_bps=1.0,
        buffer_bps=0.0,
    )

    dynamic_cfg = ObiDynamicThresholdConfig(
        enabled=True,
        warmup_sec=1,
        percentile=0.5,
        min_pass_rate=0.1,
        min_samples=1,
    )
    obi_filter_cfg = ObiFilterConfig(
        enabled=True,
        levels=5,
        threshold=0.02,
        top_k=0,
    )

    source = RealOpportunitySource(
        upbit_provider=None,
        binance_provider=None,
        rate_limiter_upbit=None,
        rate_limiter_binance=None,
        fx_provider=None,
        break_even_params=params,
        kpi=kpi,
        profit_core=None,
        deterministic_drift_bps=0.0,
        obi_filter=obi_filter_cfg,
        obi_dynamic_threshold=dynamic_cfg,
        min_net_edge_bps=0.0,
    )

    candidate = OpportunityCandidate(
        symbol="BTC/KRW",
        exchange_a="upbit",
        exchange_b="binance",
        price_a=100.0,
        price_b=99.0,
        spread_bps=101.0,
        break_even_bps=1.0,
        edge_bps=100.0,
        direction=OpportunityDirection.BUY_A_SELL_B,
        profitable=True,
        net_edge_bps=10.0,
    )

    warmup_state = source._update_dynamic_threshold_state([candidate], now_ts=0.0)
    assert warmup_state["ready"] is False
    assert warmup_state["status"] == "warming_up"

    ready_state = source._update_dynamic_threshold_state([candidate], now_ts=2.0)
    assert ready_state["ready"] is True
    assert ready_state["threshold"] is not None

    candidate.dynamic_threshold_pass = True
    candidate.dynamic_threshold_reason = None
    candidate.dynamic_threshold_value = ready_state.get("threshold")
    edge_distribution = [
        {
            "iteration": 1,
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "reason": "",
            "candidates": [_candidate_to_edge_dict(candidate)],
        }
    ]

    run_meta = {
        "run_id": "test_dynamic_threshold",
        "git_sha": "dummy",
        "branch": "test",
        "config_path": "config/v2/config.yml",
        "symbols": [("BTC/KRW", "BTC/USDT")],
        "cli_args": {"duration": 1},
        "metrics": kpi.to_dict(),
        "obi_dynamic_threshold_state": ready_state,
    }

    collector = EvidenceCollector(output_dir=str(tmp_path), run_id="test_dynamic_threshold")
    collector.save(
        metrics=kpi,
        trade_history=[],
        edge_distribution=edge_distribution,
        phase="smoke",
        run_meta=run_meta,
    )

    artifact_path = tmp_path / "obi_dynamic_threshold.json"
    assert artifact_path.exists()
    content = artifact_path.read_text(encoding="utf-8")
    assert "threshold_values" in content
    assert "state" in content
