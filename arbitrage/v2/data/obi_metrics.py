"""OBI (Order Book Imbalance) metrics — thin Decimal wrapper.

Reuses the core OBI formula from arbitrage.v2.core.opportunity_source
(_compute_orderbook_obi) but accepts raw (price, qty) tuples and
returns Decimal-precision results matching the test contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Sequence, Tuple, Union

PriceQty = Tuple[Union[float, int, Decimal], Union[float, int, Decimal]]


@dataclass(frozen=True)
class OBIMetrics:
    """Immutable container for OBI calculation results."""

    obi_score: Decimal
    depth_imbalance: Decimal


def calculate_obi_metrics(
    bids: Sequence[PriceQty],
    asks: Sequence[PriceQty],
    depth: int = 5,
) -> OBIMetrics:
    """Calculate OBI score and depth imbalance from raw orderbook levels.

    Args:
        bids: [(price, qty), ...] sorted best-first (descending price).
        asks: [(price, qty), ...] sorted best-first (ascending price).
        depth: Number of top levels to consider.

    Returns:
        OBIMetrics with obi_score and depth_imbalance as Decimal.

    Raises:
        ValueError: If both sides have zero depth after slicing.
    """
    top_bids = bids[:depth]
    top_asks = asks[:depth]

    bid_depth = sum(Decimal(str(qty)) for _, qty in top_bids)
    ask_depth = sum(Decimal(str(qty)) for _, qty in top_asks)

    if bid_depth <= 0 or ask_depth <= 0:
        raise ValueError(
            f"Non-positive depth: bid_depth={bid_depth}, ask_depth={ask_depth}"
        )

    obi_score = (bid_depth - ask_depth) / (bid_depth + ask_depth)
    depth_imbalance = bid_depth / ask_depth

    return OBIMetrics(obi_score=obi_score, depth_imbalance=depth_imbalance)
