"""
D206-1: V2 Domain Models

V1 arbitrage_core.py 타입을 V2에서 재사용.
Engine-centric 아키텍처의 유일한 타입 정의.
"""

from arbitrage.v2.domain.orderbook import OrderBookSnapshot
from arbitrage.v2.domain.opportunity import ArbitrageOpportunity, Side
from arbitrage.v2.domain.trade import ArbitrageTrade
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.domain.fill_model import FillModelConfig
from arbitrage.v2.domain.order_intent import OrderIntent

__all__ = [
    # D206-1: V1 Domain Models (Core)
    "OrderBookSnapshot",
    "ArbitrageOpportunity",
    "ArbitrageTrade",
    "Side",
    
    # V2 Existing
    "BreakEvenParams",
    "FillModelConfig",
    "OrderIntent",
]
