from decimal import Decimal

from arbitrage.v2.data.obi_collector import build_obi_snapshot


def test_build_obi_snapshot_basic():
    bids = [(100.0, 2), (99.5, 3), (99.0, 1)]
    asks = [(100.5, 1), (101.0, 4), (101.5, 2)]

    snapshot = build_obi_snapshot(
        exchange="fakeex",
        symbol="BTCUSDT",
        bids=bids,
        asks=asks,
        depth=3,
    )

    # Simple invariant checks
    assert snapshot.exchange == "fakeex"
    assert snapshot.symbol == "BTCUSDT"
    assert snapshot.depth == 3

    # Numeric sanity ‑ ensure obi_score ∈ [-1, 1] and depth_imbalance > 0
    assert -Decimal("1") <= snapshot.obi_score <= Decimal("1")
    assert snapshot.depth_imbalance > 0

    # Dict serialization keeps same values (as str for Decimal)
    data = snapshot.as_dict()
    assert data["obi_score"] == str(snapshot.obi_score)
    assert data["depth_imbalance"] == str(snapshot.depth_imbalance)
