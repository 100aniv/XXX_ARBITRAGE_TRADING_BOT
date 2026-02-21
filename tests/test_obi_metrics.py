from decimal import Decimal

from arbitrage.v2.data.obi_metrics import calculate_obi_metrics


def test_calculate_obi_metrics_balanced():
    bids = [(100.0, 5), (99.5, 5), (99.0, 5)]
    asks = [(100.5, 5), (101.0, 5), (101.5, 5)]
    metrics = calculate_obi_metrics(bids, asks, depth=2)
    # Σ bid_qty = 10, Σ ask_qty = 10  → obi_score = 0, imbalance = 1
    assert metrics.obi_score == Decimal("0")
    assert metrics.depth_imbalance == Decimal("1")


def test_calculate_obi_metrics_bid_heavy():
    bids = [(100.0, 8), (99.5, 7)]
    asks = [(100.5, 5), (101.0, 5)]
    metrics = calculate_obi_metrics(bids, asks, depth=2)
    # Σ bid_qty = 15, Σ ask_qty = 10
    expected_obi = (Decimal("15") - Decimal("10")) / (Decimal("25"))
    expected_imbalance = Decimal("15") / Decimal("10")
    assert metrics.obi_score == expected_obi
    assert metrics.depth_imbalance == expected_imbalance
