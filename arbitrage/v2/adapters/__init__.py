"""V2 Exchange Adapters"""

from arbitrage.v2.adapters.paper_execution_adapter import PaperExecutionAdapter, MockAdapter
PaperAdapter = PaperExecutionAdapter
from .upbit_adapter import UpbitAdapter
from .binance_adapter import BinanceAdapter

__all__ = [
    "MockAdapter",
    "PaperAdapter",
    "PaperExecutionAdapter",
    "UpbitAdapter",
    "BinanceAdapter",
]
