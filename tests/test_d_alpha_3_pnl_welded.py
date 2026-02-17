"""
D_ALPHA-3: PnL Welding with 5 friction components (including spread)

Goal:
- calculate_net_pnl_full_welded includes fee/slippage/latency/partial/spread costs
- spread cost computed from bid/ask mid vs executed side
"""

from decimal import Decimal

from arbitrage.v2.core.adapter import OrderResult
from arbitrage.v2.domain.pnl_calculator import (
    calculate_execution_friction_from_results,
    calculate_net_pnl_full_welded,
)


def test_pnl_welded_includes_spread_cost():
    result = calculate_net_pnl_full_welded(
        entry_side="BUY",
        exit_side="SELL",
        entry_price=101.0,
        exit_price=103.0,
        entry_qty=1.0,
        exit_qty=1.0,
        total_fee=1.0,
        slippage_cost=2.0,
        latency_cost=3.0,
        partial_penalty=4.0,
        entry_bid=100.0,
        entry_ask=102.0,
        exit_bid=102.0,
        exit_ask=104.0,
        return_decimal=True,
    )

    assert result["gross_pnl"] == Decimal("2")
    assert result["fee_total"] == Decimal("1")
    assert result["slippage_cost"] == Decimal("2")
    assert result["latency_cost"] == Decimal("3")
    assert result["partial_fill_penalty"] == Decimal("4")
    assert result["spread_cost"] == Decimal("2")
    assert result["exec_cost_total"] == Decimal("12")
    assert result["net_pnl_full"] == Decimal("-10")


def test_pnl_welded_zero_spread_when_missing_bid_ask():
    result = calculate_net_pnl_full_welded(
        entry_side="BUY",
        exit_side="SELL",
        entry_price=101.0,
        exit_price=103.0,
        entry_qty=1.0,
        exit_qty=1.0,
        total_fee=1.0,
        slippage_cost=2.0,
        latency_cost=3.0,
        partial_penalty=4.0,
        entry_bid=None,
        entry_ask=None,
        exit_bid=None,
        exit_ask=None,
        return_decimal=True,
    )

    assert result["spread_cost"] == Decimal("0")
    assert result["exec_cost_total"] == Decimal("10")
    assert result["net_pnl_full"] == Decimal("-8")


def test_execution_friction_from_results_truth_api():
    entry = OrderResult(
        success=True,
        filled_qty=2.0,
        filled_price=101.0,
        ref_price=100.0,
        fee=1.5,
        slippage_bps=10.0,
        pessimistic_drift_bps=5.0,
        latency_ms=20.0,
        reject_flag=False,
    )
    exit = OrderResult(
        success=True,
        filled_qty=1.5,
        filled_price=99.0,
        ref_price=100.0,
        fee=1.0,
        slippage_bps=10.0,
        pessimistic_drift_bps=5.0,
        latency_ms=30.0,
        reject_flag=True,
    )

    friction = calculate_execution_friction_from_results(
        entry_result=entry,
        exit_result=exit,
        return_decimal=True,
    )

    assert friction["total_fee"] == Decimal("2.50000000")
    assert friction["latency_total_ms"] == 50.0
    assert friction["reject_count"] == 1.0
    assert friction["slippage_cost"] > Decimal("0")
    assert friction["latency_cost"] > Decimal("0")
    assert friction["partial_fill_penalty"] > Decimal("0")
