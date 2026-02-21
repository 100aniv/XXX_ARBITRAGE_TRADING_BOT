"""
OBI Snapshot collector.

This module converts raw order-book (bids, asks) data into an immutable
OBISnapshot record that includes OBI metrics (obi_score, depth_imbalance)
so that higher-level components can persist or further process them.

It is intentionally self-contained and has **no** side-effects such as
I/O or logging; callers decide how/where to store the returned snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence, Tuple, Union

from arbitrage.v2.data.obi_metrics import OBIMetrics, PriceQty, calculate_obi_metrics


@dataclass(frozen=True, slots=True)
class OBISnapshot:
    """
    Immutable snapshot containing OBI metrics for a single exchange/symbol.
    """

    ts: datetime
    exchange: str
    symbol: str
    depth: int
    obi_score: Decimal
    depth_imbalance: Decimal

    def as_dict(self) -> dict[str, Union[str, int, float]]:
        """
        Serialize the snapshot to a plain-Python dict, coercing Decimals to str
        so that downstream JSON serialization keeps full precision.
        """
        return {
            "ts": self.ts.isoformat(timespec="milliseconds"),
            "exchange": self.exchange,
            "symbol": self.symbol,
            "depth": self.depth,
            "obi_score": str(self.obi_score),
            "depth_imbalance": str(self.depth_imbalance),
        }


def build_obi_snapshot(
    exchange: str,
    symbol: str,
    bids: Sequence[PriceQty],
    asks: Sequence[PriceQty],
    depth: int = 5,
    ts: datetime | None = None,
) -> OBISnapshot:
    """
    Convenience helper that calculates OBI metrics and packages them into an
    OBISnapshot dataclass.

    Args:
        exchange: Exchange identifier (e.g. "binance", "bybit").
        symbol: Trading pair symbol (e.g. "BTCUSDT").
        bids: [(price, qty), ...] sorted best-first (descending).
        asks: [(price, qty), ...] sorted best-first (ascending).
        depth: Number of top levels to consider.
        ts: Optional timestamp. If omitted, `datetime.now(timezone.utc)`.

    Returns:
        OBISnapshot with calculated metrics.

    Raises:
        ValueError: Propagated from `calculate_obi_metrics` if depth invalid.
    """
    ts = ts or datetime.now(timezone.utc)

    metrics: OBIMetrics = calculate_obi_metrics(bids=bids, asks=asks, depth=depth)

    return OBISnapshot(
        ts=ts,
        exchange=exchange,
        symbol=symbol,
        depth=depth,
        obi_score=metrics.obi_score,
        depth_imbalance=metrics.depth_imbalance,
    )
