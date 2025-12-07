# -*- coding: utf-8 -*-
"""
D85-0: L2-based available_volume Integration - Unit Tests

Tests:
1. Single L2 (OrderBookSnapshot) volume extraction
2. Multi L2 (MultiExchangeL2Snapshot) volume extraction  
3. Stale source handling
4. Empty orderbook handling
5. Fallback scenarios
6. Unknown snapshot type handling
"""

import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from enum import Enum

from arbitrage.execution.executor import PaperExecutor
from arbitrage.types import OrderSide, PortfolioState
from arbitrage.live_runner import RiskGuard, RiskLimits


# Mock OrderBookSnapshot
@dataclass
class MockOrderBookSnapshot:
    """Mock OrderBookSnapshot (Single L2)"""
    bids: List[Tuple[float, float]]  # [(price, volume), ...]
    asks: List[Tuple[float, float]]
    timestamp: float = 0.0
    
    def best_bid(self) -> Optional[float]:
        return self.bids[0][0] if self.bids else None
    
    def best_ask(self) -> Optional[float]:
        return self.asks[0][0] if self.asks else None


# Mock ExchangeId Enum
class MockExchangeId(Enum):
    UPBIT = "upbit"
    BINANCE = "binance"


# Mock MultiExchangeL2Snapshot
@dataclass
class MockMultiExchangeL2Snapshot:
    """Mock MultiExchangeL2Snapshot (Multi L2)"""
    per_exchange: Dict  # {ExchangeId: OrderBookSnapshot}
    best_bid: Optional[float]
    best_ask: Optional[float]
    best_bid_exchange: Optional[MockExchangeId]
    best_ask_exchange: Optional[MockExchangeId]
    timestamp: float = 0.0
    source_status: Dict = None


class TestAvailableVolumeExtraction:
    """D85-0: available_volume extraction tests"""
    
    @pytest.fixture
    def executor(self):
        """PaperExecutor fixture"""
        portfolio_state = PortfolioState(
            total_balance=10000.0,
            available_balance=10000.0,
            positions={},
        )
        risk_limits = RiskLimits(
            max_notional_per_trade=10000.0,
            max_daily_loss=1000.0,
            max_open_trades=10,
        )
        risk_guard = RiskGuard(risk_limits=risk_limits)
        
        executor = PaperExecutor(
            symbol="BTC",
            portfolio_state=portfolio_state,
            risk_guard=risk_guard,
            enable_fill_model=True,
            default_available_volume_factor=2.0,
        )
        
        return executor
    
    def test_single_l2_buy_volume(self, executor):
        """
        Test 1: Single L2 (OrderBookSnapshot) - BUY volume extraction
        """
        # Mock Single L2 snapshot
        snapshot = MockOrderBookSnapshot(
            bids=[(50000.0, 1.5), (49900.0, 2.0)],
            asks=[(50100.0, 0.8), (50200.0, 1.2)],
        )
        
        # Extract volume
        volume = executor._extract_volume_from_single_l2(
            snapshot=snapshot,
            symbol="BTC",
            side=OrderSide.BUY,
            fallback_quantity=0.001,
        )
        
        # BUY uses asks (best ask volume = 0.8)
        assert volume == 0.8
    
    def test_single_l2_sell_volume(self, executor):
        """
        Test 2: Single L2 (OrderBookSnapshot) - SELL volume extraction
        """
        # Mock Single L2 snapshot
        snapshot = MockOrderBookSnapshot(
            bids=[(50000.0, 1.5), (49900.0, 2.0)],
            asks=[(50100.0, 0.8), (50200.0, 1.2)],
        )
        
        # Extract volume
        volume = executor._extract_volume_from_single_l2(
            snapshot=snapshot,
            symbol="BTC",
            side=OrderSide.SELL,
            fallback_quantity=0.001,
        )
        
        # SELL uses bids (best bid volume = 1.5)
        assert volume == 1.5
    
    def test_single_l2_empty_levels(self, executor):
        """
        Test 3: Single L2 - Empty orderbook levels (fallback)
        """
        # Mock snapshot with empty asks
        snapshot = MockOrderBookSnapshot(
            bids=[(50000.0, 1.5)],
            asks=[],  # Empty!
        )
        
        # Extract volume (BUY side, empty asks)
        volume = executor._extract_volume_from_single_l2(
            snapshot=snapshot,
            symbol="BTC",
            side=OrderSide.BUY,
            fallback_quantity=0.001,
        )
        
        # Fallback: 0.001 * 2.0 = 0.002
        assert volume == 0.002
    
    def test_multi_l2_buy_volume(self, executor):
        """
        Test 4: Multi L2 (MultiExchangeL2Snapshot) - BUY volume extraction
        """
        # Mock per-exchange snapshots
        upbit_snapshot = MockOrderBookSnapshot(
            bids=[(100000000.0, 2.0)],  # KRW
            asks=[(100100000.0, 1.2)],
        )
        binance_snapshot = MockOrderBookSnapshot(
            bids=[(50000.0, 1.5)],  # USD
            asks=[(50100.0, 0.8)],  # <- Best ask (lowest)
        )
        
        # Mock Multi L2 snapshot
        multi_snapshot = MockMultiExchangeL2Snapshot(
            per_exchange={
                MockExchangeId.UPBIT: upbit_snapshot,
                MockExchangeId.BINANCE: binance_snapshot,
            },
            best_bid=100000000.0,
            best_ask=50100.0,  # Binance has best ask
            best_bid_exchange=MockExchangeId.UPBIT,
            best_ask_exchange=MockExchangeId.BINANCE,
        )
        
        # Extract volume (BUY side → use best_ask_exchange = BINANCE)
        volume = executor._extract_volume_from_multi_l2(
            snapshot=multi_snapshot,
            symbol="BTC",
            side=OrderSide.BUY,
            fallback_quantity=0.001,
        )
        
        # Binance best ask volume = 0.8
        assert volume == 0.8
    
    def test_multi_l2_sell_volume(self, executor):
        """
        Test 5: Multi L2 (MultiExchangeL2Snapshot) - SELL volume extraction
        """
        # Mock per-exchange snapshots
        upbit_snapshot = MockOrderBookSnapshot(
            bids=[(100000000.0, 2.0)],  # <- Best bid (highest)
            asks=[(100100000.0, 1.2)],
        )
        binance_snapshot = MockOrderBookSnapshot(
            bids=[(50000.0, 1.5)],
            asks=[(50100.0, 0.8)],
        )
        
        # Mock Multi L2 snapshot
        multi_snapshot = MockMultiExchangeL2Snapshot(
            per_exchange={
                MockExchangeId.UPBIT: upbit_snapshot,
                MockExchangeId.BINANCE: binance_snapshot,
            },
            best_bid=100000000.0,
            best_ask=50100.0,
            best_bid_exchange=MockExchangeId.UPBIT,  # Best bid
            best_ask_exchange=MockExchangeId.BINANCE,
        )
        
        # Extract volume (SELL side → use best_bid_exchange = UPBIT)
        volume = executor._extract_volume_from_multi_l2(
            snapshot=multi_snapshot,
            symbol="BTC",
            side=OrderSide.SELL,
            fallback_quantity=0.001,
        )
        
        # Upbit best bid volume = 2.0
        assert volume == 2.0
    
    def test_multi_l2_no_best_exchange(self, executor):
        """
        Test 6: Multi L2 - No best exchange (fallback)
        """
        # Mock Multi L2 snapshot with no best exchange
        multi_snapshot = MockMultiExchangeL2Snapshot(
            per_exchange={},
            best_bid=None,
            best_ask=None,
            best_bid_exchange=None,  # No best exchange!
            best_ask_exchange=None,
        )
        
        # Extract volume (BUY side, no best_ask_exchange)
        volume = executor._extract_volume_from_multi_l2(
            snapshot=multi_snapshot,
            symbol="BTC",
            side=OrderSide.BUY,
            fallback_quantity=0.001,
        )
        
        # Fallback: 0.001 * 2.0 = 0.002
        assert volume == 0.002
    
    def test_multi_l2_missing_exchange_snapshot(self, executor):
        """
        Test 7: Multi L2 - Best exchange exists but snapshot missing (fallback)
        """
        # Mock Multi L2 snapshot
        multi_snapshot = MockMultiExchangeL2Snapshot(
            per_exchange={
                # BINANCE snapshot missing!
            },
            best_bid=None,
            best_ask=50100.0,
            best_bid_exchange=None,
            best_ask_exchange=MockExchangeId.BINANCE,  # Points to missing snapshot
        )
        
        # Extract volume (BUY side, best_ask_exchange exists but snapshot missing)
        volume = executor._extract_volume_from_multi_l2(
            snapshot=multi_snapshot,
            symbol="BTC",
            side=OrderSide.BUY,
            fallback_quantity=0.001,
        )
        
        # Fallback: 0.001 * 2.0 = 0.002
        assert volume == 0.002
    
    def test_get_available_volume_no_provider(self, executor):
        """
        Test 8: No market_data_provider → fallback
        """
        # No provider
        executor.market_data_provider = None
        
        # Get volume
        volume = executor._get_available_volume_from_orderbook(
            symbol="BTC",
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        
        # Fallback: 0.001 * 2.0 = 0.002
        assert volume == 0.002
    
    def test_get_available_volume_no_snapshot(self, executor):
        """
        Test 9: Provider exists but returns None snapshot → fallback
        """
        # Mock provider that returns None
        mock_provider = Mock()
        mock_provider.get_latest_snapshot = Mock(return_value=None)
        executor.market_data_provider = mock_provider
        
        # Get volume
        volume = executor._get_available_volume_from_orderbook(
            symbol="BTC",
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        
        # Fallback: 0.001 * 2.0 = 0.002
        assert volume == 0.002
    
    def test_get_available_volume_single_l2(self, executor):
        """
        Test 10: get_available_volume with Single L2 (OrderBookSnapshot)
        """
        # Mock Single L2 provider
        snapshot = MockOrderBookSnapshot(
            bids=[(50000.0, 1.5)],
            asks=[(50100.0, 0.8)],
        )
        mock_provider = Mock()
        mock_provider.get_latest_snapshot = Mock(return_value=snapshot)
        executor.market_data_provider = mock_provider
        
        # Get volume (BUY side)
        volume = executor._get_available_volume_from_orderbook(
            symbol="BTC",
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        
        # Best ask volume = 0.8
        assert volume == 0.8
    
    def test_get_available_volume_multi_l2(self, executor):
        """
        Test 11: get_available_volume with Multi L2 (MultiExchangeL2Snapshot)
        """
        # Mock per-exchange snapshots
        upbit_snapshot = MockOrderBookSnapshot(
            bids=[(100000000.0, 2.0)],
            asks=[(100100000.0, 1.2)],
        )
        binance_snapshot = MockOrderBookSnapshot(
            bids=[(50000.0, 1.5)],
            asks=[(50100.0, 0.8)],
        )
        
        # Mock Multi L2 snapshot
        multi_snapshot = MockMultiExchangeL2Snapshot(
            per_exchange={
                MockExchangeId.UPBIT: upbit_snapshot,
                MockExchangeId.BINANCE: binance_snapshot,
            },
            best_bid=100000000.0,
            best_ask=50100.0,
            best_bid_exchange=MockExchangeId.UPBIT,
            best_ask_exchange=MockExchangeId.BINANCE,
        )
        
        # Mock Multi L2 provider
        mock_provider = Mock()
        mock_provider.get_latest_snapshot = Mock(return_value=multi_snapshot)
        executor.market_data_provider = mock_provider
        
        # Get volume (BUY side → use BINANCE)
        volume = executor._get_available_volume_from_orderbook(
            symbol="BTC",
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        
        # Binance best ask volume = 0.8
        assert volume == 0.8
    
    def test_get_available_volume_unknown_type(self, executor):
        """
        Test 12: Unknown snapshot type → fallback
        """
        # Mock unknown snapshot type
        class UnknownSnapshot:
            pass
        
        unknown_snapshot = UnknownSnapshot()
        
        # Mock provider
        mock_provider = Mock()
        mock_provider.get_latest_snapshot = Mock(return_value=unknown_snapshot)
        executor.market_data_provider = mock_provider
        
        # Get volume
        volume = executor._get_available_volume_from_orderbook(
            symbol="BTC",
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        
        # Fallback: 0.001 * 2.0 = 0.002
        assert volume == 0.002
