import pytest

from arbitrage.v2.adapters.paper_execution_adapter import PaperExecutionAdapter


def _buy_payload(quote_amount: float, top_depth: float) -> dict:
    return {
        "exchange": "upbit",
        "symbol": "BTC/KRW",
        "side": "BUY",
        "order_type": "MARKET",
        "quote_amount": quote_amount,
        "ref_price": 100.0,
        "top_depth": top_depth,
    }


def test_paper_deterministic_config_mode_uses_size_ratio_only():
    adapter = PaperExecutionAdapter(
        config={
            "mock_adapter": {
                "enable_slippage": True,
                "slippage_bps_min": 10.0,
                "slippage_bps_max": 30.0,
                "latency_base_ms": 0.0,
                "latency_jitter_ms": 50.0,
                "partial_fill_probability": 0.0,
                "pessimistic_drift_bps_min": 0.0,
                "pessimistic_drift_bps_max": 0.0,
                "max_safe_ratio": 0.3,
                "paper_deterministic": True,
            }
        }
    )

    # size_ratio = (3000 / 100) / 100 = 0.3 (safe boundary)
    filled = adapter.submit_order(_buy_payload(quote_amount=3000.0, top_depth=100.0))
    assert filled["status"] == "filled"
    assert filled["slippage_bps"] == pytest.approx(10.0)
    assert filled["partial_fill_ratio"] == pytest.approx(1.0)
    assert filled["latency_ms"] == pytest.approx(0.0)

    # size_ratio = (6000 / 100) / 100 = 0.6 (unsafe, max slippage + partial fill)
    partial = adapter.submit_order(_buy_payload(quote_amount=6000.0, top_depth=100.0))
    assert partial["status"] == "partial"
    assert partial["slippage_bps"] == pytest.approx(30.0)
    assert partial["partial_fill_ratio"] == pytest.approx(0.5)

    # size_ratio = (12000 / 100) / 100 = 1.2 (> 3 * max_safe_ratio=0.9) => reject
    rejected = adapter.submit_order(_buy_payload(quote_amount=12000.0, top_depth=100.0))
    assert rejected["status"] == "rejected"


def test_paper_deterministic_explicit_argument_path_applies():
    adapter = PaperExecutionAdapter(
        enable_slippage=True,
        slippage_bps_min=11.0,
        slippage_bps_max=21.0,
        latency_base_ms=0.0,
        latency_jitter_ms=50.0,
        partial_fill_probability=0.0,
        pessimistic_drift_bps_min=0.0,
        pessimistic_drift_bps_max=0.0,
        max_safe_ratio=0.3,
        paper_deterministic=True,
    )

    response = adapter.submit_order(_buy_payload(quote_amount=6000.0, top_depth=100.0))

    assert response["paper_deterministic"] is True
    assert response["slippage_bps"] == pytest.approx(21.0)
    assert response["status"] == "partial"
    assert response["latency_ms"] == pytest.approx(0.0)
