# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Layer

거래소 어댑터 (Upbit Spot, Binance Futures, Paper 모드)
"""

from arbitrage.exchanges.base import (
    BaseExchange,
    OrderSide,
    OrderType,
    TimeInForce,
    OrderResult,
    Balance,
    Position,
    OrderBookSnapshot,
)
from arbitrage.exchanges.exceptions import (
    ExchangeError,
    NetworkError,
    AuthenticationError,
    InsufficientBalanceError,
)
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
from arbitrage.exchanges.binance_futures import BinanceFuturesExchange

__all__ = [
    "BaseExchange",
    "OrderSide",
    "OrderType",
    "TimeInForce",
    "OrderResult",
    "Balance",
    "Position",
    "OrderBookSnapshot",
    "ExchangeError",
    "NetworkError",
    "AuthenticationError",
    "InsufficientBalanceError",
    "PaperExchange",
    "UpbitSpotExchange",
    "BinanceFuturesExchange",
]
