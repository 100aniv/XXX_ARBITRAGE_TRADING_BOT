"""
D_ALPHA-2-UNBLOCK-2: net_pnl_full SSOT Consistency Test

Formula:
- net_pnl_full = gross - (fees + slippage + latency + partial_fill_penalty)
- tolerance <= 0.01%

SSOT: D_ROADMAP.md → D_ALPHA-2-UNBLOCK-2
"""

from decimal import Decimal, ROUND_HALF_UP

from arbitrage.v2.domain.pnl_calculator import calculate_net_pnl_full


DECIMAL_QUANTIZE = Decimal("0.00000001")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(DECIMAL_QUANTIZE, rounding=ROUND_HALF_UP)


def test_net_pnl_full_formula_consistency():
    """net_pnl_full 공식 정합성 검증 (<=0.01% 오차)"""
    gross = Decimal("1000.12345678")
    fees = Decimal("10.11111111")
    slippage = Decimal("2.22222222")
    latency = Decimal("0.33333333")
    partial = Decimal("1.44444444")

    expected_exec = _quantize(fees + slippage + latency + partial)
    expected_net = _quantize(gross - expected_exec)

    net_pnl_full, exec_cost_total = calculate_net_pnl_full(
        gross_pnl=gross,
        total_fee=fees,
        slippage_cost=slippage,
        latency_cost=latency,
        partial_penalty=partial,
        return_decimal=True,
    )

    assert exec_cost_total == expected_exec

    if expected_net == 0:
        assert net_pnl_full == expected_net
    else:
        tolerance = abs(expected_net) * Decimal("0.0001")
        assert abs(net_pnl_full - expected_net) <= tolerance
