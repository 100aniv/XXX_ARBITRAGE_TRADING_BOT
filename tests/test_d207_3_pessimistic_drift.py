"""
D207-3: Pessimistic Drift Validation

Goal: verify pessimistic drift bps applied to filled price
SSOT: D_ROADMAP.md -> D207-3
"""

import pytest

from arbitrage.v2.adapters.paper_execution_adapter import PaperExecutionAdapter


class TestPessimisticDrift:
    """D207-3: drift applied to filled_price"""

    def test_buy_drift_applied(self):
        adapter = PaperExecutionAdapter(
            enable_slippage=False,
            slippage_bps_min=0.0,
            slippage_bps_max=0.0,
            latency_base_ms=0.0,
            latency_jitter_ms=0.0,
            partial_fill_probability=0.0,
            pessimistic_drift_bps_min=10.0,
            pessimistic_drift_bps_max=10.0,
        )

        payload = {
            "exchange": "mock",
            "symbol": "BTC/KRW",
            "side": "BUY",
            "order_type": "MARKET",
            "quote_amount": 100000.0,
            "ref_price": 100.0,
        }

        response = adapter.submit_order(payload)
        expected_price = 100.0 * (1 + 10.0 / 10000.0)
        assert response["filled_price"] == pytest.approx(expected_price)
        assert response["pessimistic_drift_bps"] == pytest.approx(10.0)

    def test_sell_drift_applied(self):
        adapter = PaperExecutionAdapter(
            enable_slippage=False,
            slippage_bps_min=0.0,
            slippage_bps_max=0.0,
            latency_base_ms=0.0,
            latency_jitter_ms=0.0,
            partial_fill_probability=0.0,
            pessimistic_drift_bps_min=10.0,
            pessimistic_drift_bps_max=10.0,
        )

        payload = {
            "exchange": "mock",
            "symbol": "BTC/KRW",
            "side": "SELL",
            "order_type": "MARKET",
            "base_qty": 1.0,
            "ref_price": 100.0,
        }

        response = adapter.submit_order(payload)
        expected_price = 100.0 * (1 - 10.0 / 10000.0)
        assert response["filled_price"] == pytest.approx(expected_price)
        assert response["pessimistic_drift_bps"] == pytest.approx(10.0)
