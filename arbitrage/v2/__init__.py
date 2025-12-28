"""
V2 Arbitrage Engine - Engine-Centric Architecture

This package contains the V2 implementation of the arbitrage trading system,
redesigned with a clean separation between semantic intent (OrderIntent) and
exchange-specific implementation (Adapters).

Key Components:
- core: OrderIntent, ExchangeAdapter, ArbitrageEngine
- adapters: Exchange-specific implementations (Upbit, Binance, Mock)
- harness: Smoke test runners
"""

__version__ = "2.0.0-alpha"
