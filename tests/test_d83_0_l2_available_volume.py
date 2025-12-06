# -*- coding: utf-8 -*-
"""
D83-0: L2 Orderbook Integration – available_volume 계산 테스트

PaperExecutor의 _get_available_volume_from_orderbook() 메서드와
L2 기반 available_volume 계산 로직을 테스트한다.
"""

import pytest
from unittest.mock import Mock, MagicMock
from arbitrage.execution.executor import PaperExecutor
from arbitrage.types import OrderSide, PortfolioState
from arbitrage.live_runner import RiskGuard
from arbitrage.exchanges.base import OrderBookSnapshot


class TestD83_0_L2AvailableVolume:
    """D83-0: L2 Orderbook 기반 available_volume 계산 테스트"""
    
    def setup_method(self):
        """테스트 환경 초기화"""
        self.symbol = "BTC/USDT"
        self.portfolio_state = Mock(spec=PortfolioState)
        self.risk_guard = Mock(spec=RiskGuard)
        self.market_data_provider = Mock()
    
    def test_available_volume_with_l2_best_level_buy(self):
        """
        TEST 1: L2 Orderbook Best Level (BUY)
        
        BUY 주문 시 asks (매도 호가) best level volume 반환
        """
        # Mock OrderBookSnapshot
        snapshot = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567890.0,
            bids=[(50000.0, 0.5), (49999.0, 1.0)],
            asks=[(50001.0, 0.8), (50002.0, 1.2)],  # Best ask: 0.8 BTC
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot
        
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=self.market_data_provider,
        )
        
        # available_volume 계산
        available_volume = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50001.0,
            fallback_quantity=0.001,
        )
        
        # Best ask level volume (0.8) 반환
        assert available_volume == 0.8
        self.market_data_provider.get_latest_snapshot.assert_called_once_with(self.symbol)
    
    def test_available_volume_with_l2_best_level_sell(self):
        """
        TEST 2: L2 Orderbook Best Level (SELL)
        
        SELL 주문 시 bids (매수 호가) best level volume 반환
        """
        # Mock OrderBookSnapshot
        snapshot = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567890.0,
            bids=[(50000.0, 1.5), (49999.0, 2.0)],  # Best bid: 1.5 BTC
            asks=[(50001.0, 0.8), (50002.0, 1.2)],
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot
        
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=self.market_data_provider,
        )
        
        # available_volume 계산
        available_volume = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.SELL,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        
        # Best bid level volume (1.5) 반환
        assert available_volume == 1.5
        self.market_data_provider.get_latest_snapshot.assert_called_once_with(self.symbol)
    
    def test_fallback_when_provider_is_none(self):
        """
        TEST 3: Fallback (Provider None)
        
        market_data_provider가 None이면 기존 fallback 로직 사용
        """
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=None,  # Provider 없음
            default_available_volume_factor=2.0,
        )
        
        # Fallback 로직: fallback_quantity * factor
        available_volume = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        
        assert available_volume == 0.001 * 2.0
    
    def test_fallback_when_snapshot_is_none(self):
        """
        TEST 4: Fallback (Snapshot None)
        
        Orderbook snapshot이 None이면 fallback 로직 사용
        """
        self.market_data_provider.get_latest_snapshot.return_value = None
        
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=self.market_data_provider,
            default_available_volume_factor=3.0,
        )
        
        available_volume = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=0.005,
        )
        
        assert available_volume == 0.005 * 3.0
    
    def test_fallback_when_levels_empty_buy(self):
        """
        TEST 5: Fallback (Empty asks)
        
        BUY 주문인데 asks가 비어있으면 fallback 사용
        """
        snapshot = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567890.0,
            bids=[(50000.0, 1.0)],
            asks=[],  # Empty asks
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot
        
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=self.market_data_provider,
            default_available_volume_factor=2.5,
        )
        
        available_volume = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=0.002,
        )
        
        assert available_volume == 0.002 * 2.5
    
    def test_fallback_when_levels_empty_sell(self):
        """
        TEST 6: Fallback (Empty bids)
        
        SELL 주문인데 bids가 비어있으면 fallback 사용
        """
        snapshot = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567890.0,
            bids=[],  # Empty bids
            asks=[(50001.0, 0.5)],
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot
        
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=self.market_data_provider,
            default_available_volume_factor=1.5,
        )
        
        available_volume = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.SELL,
            target_price=50000.0,
            fallback_quantity=0.003,
        )
        
        assert available_volume == 0.003 * 1.5
    
    def test_varying_available_volume_over_time(self):
        """
        TEST 7: 시간에 따른 available_volume 변화
        
        여러 snapshot에서 available_volume이 다르게 계산됨
        """
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=self.market_data_provider,
        )
        
        # Snapshot 1: Best ask = 0.5
        snapshot1 = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567890.0,
            bids=[(50000.0, 1.0)],
            asks=[(50001.0, 0.5)],
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot1
        volume1 = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50001.0,
            fallback_quantity=0.001,
        )
        
        # Snapshot 2: Best ask = 1.2
        snapshot2 = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567900.0,
            bids=[(50000.0, 1.0)],
            asks=[(50001.0, 1.2)],
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot2
        volume2 = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50001.0,
            fallback_quantity=0.001,
        )
        
        # Snapshot 3: Best ask = 0.05
        snapshot3 = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567910.0,
            bids=[(50000.0, 1.0)],
            asks=[(50001.0, 0.05)],
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot3
        volume3 = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50001.0,
            fallback_quantity=0.001,
        )
        
        # 모두 다른 값
        assert volume1 == 0.5
        assert volume2 == 1.2
        assert volume3 == 0.05
        assert volume1 != volume2 != volume3
    
    def test_large_available_volume(self):
        """
        TEST 8: 큰 available_volume 값
        
        Best level에 매우 큰 volume이 있을 때 정상 동작
        """
        snapshot = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567890.0,
            bids=[(50000.0, 100.0)],  # 100 BTC
            asks=[(50001.0, 150.0)],  # 150 BTC
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot
        
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=self.market_data_provider,
        )
        
        # BUY
        volume_buy = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50001.0,
            fallback_quantity=0.001,
        )
        assert volume_buy == 150.0
        
        # SELL
        volume_sell = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.SELL,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        assert volume_sell == 100.0
    
    def test_small_available_volume(self):
        """
        TEST 9: 작은 available_volume 값
        
        Best level에 매우 작은 volume이 있을 때 정상 동작
        """
        snapshot = OrderBookSnapshot(
            symbol="BTC/USDT",
            timestamp=1234567890.0,
            bids=[(50000.0, 0.0001)],  # 0.0001 BTC
            asks=[(50001.0, 0.00005)],  # 0.00005 BTC
        )
        self.market_data_provider.get_latest_snapshot.return_value = snapshot
        
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=self.market_data_provider,
        )
        
        # BUY
        volume_buy = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50001.0,
            fallback_quantity=0.001,
        )
        assert volume_buy == 0.00005
        
        # SELL
        volume_sell = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.SELL,
            target_price=50000.0,
            fallback_quantity=0.001,
        )
        assert volume_sell == 0.0001
    
    def test_backwards_compatibility_legacy_executor(self):
        """
        TEST 10: Backwards Compatibility (기존 로직 유지)
        
        market_data_provider=None이면 기존 테스트 모두 PASS
        """
        # Provider 없이 생성
        executor = PaperExecutor(
            symbol=self.symbol,
            portfolio_state=self.portfolio_state,
            risk_guard=self.risk_guard,
            enable_fill_model=True,
            market_data_provider=None,
            default_available_volume_factor=2.0,
        )
        
        # 기존 로직: order_qty * factor
        fallback = 0.001
        expected = fallback * 2.0
        
        volume_buy = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=50000.0,
            fallback_quantity=fallback,
        )
        
        volume_sell = executor._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.SELL,
            target_price=50000.0,
            fallback_quantity=fallback,
        )
        
        assert volume_buy == expected
        assert volume_sell == expected
        # 기존 테스트 호환성 보장


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
