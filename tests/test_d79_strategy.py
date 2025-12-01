# -*- coding: utf-8 -*-
"""
D79-2: Cross-Exchange Strategy & Position Manager - Tests

25+ unit tests for Entry/Exit strategy and Position management.
"""

import pytest
import time
import json
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from arbitrage.cross_exchange.strategy import (
    CrossExchangeStrategy,
    CrossExchangeSignal,
    CrossExchangeAction,
)
from arbitrage.cross_exchange.position_manager import (
    CrossExchangePositionManager,
    CrossExchangePosition,
    PositionState,
)
from arbitrage.cross_exchange.spread_model import SpreadDirection


class TestCrossExchangeStrategy:
    """CrossExchangeStrategy 테스트"""
    
    def test_strategy_initialization(self):
        """전략 초기화"""
        strategy = CrossExchangeStrategy(
            min_spread_percent=0.5,
            tp_spread_percent=0.2,
            sl_spread_percent=-0.3,
        )
        
        config = strategy.get_config()
        assert config["min_spread_percent"] == 0.5
        assert config["tp_spread_percent"] == 0.2
        assert config["sl_spread_percent"] == -0.3
    
    def test_entry_signal_positive_spread(self):
        """Entry signal - Positive spread"""
        strategy = CrossExchangeStrategy(min_spread_percent=0.5)
        
        # Mock data
        mock_mapping = Mock()
        mock_mapping.upbit_symbol = "KRW-BTC"
        
        mock_spread = Mock()
        mock_spread.spread_percent = 1.0  # 1% positive
        mock_spread.direction = SpreadDirection.POSITIVE
        mock_spread.is_profitable.return_value = True
        
        # Evaluate entry
        signal = strategy.evaluate_entry(
            symbol_mapping=mock_mapping,
            cross_spread=mock_spread,
            fx_confidence=1.0,
            health_ok=True,
            secrets_available=True,
        )
        
        assert signal.action == CrossExchangeAction.ENTRY_POSITIVE
        assert signal.entry_side == "positive"
        assert "Positive spread" in signal.reason
    
    def test_entry_signal_negative_spread(self):
        """Entry signal - Negative spread"""
        strategy = CrossExchangeStrategy(min_spread_percent=0.5)
        
        mock_mapping = Mock()
        mock_spread = Mock()
        mock_spread.spread_percent = -1.0  # 1% negative
        mock_spread.direction = SpreadDirection.NEGATIVE
        mock_spread.is_profitable.return_value = True
        
        signal = strategy.evaluate_entry(
            symbol_mapping=mock_mapping,
            cross_spread=mock_spread,
            fx_confidence=1.0,
            health_ok=True,
            secrets_available=True,
        )
        
        assert signal.action == CrossExchangeAction.ENTRY_NEGATIVE
        assert signal.entry_side == "negative"
    
    def test_entry_blocked_secrets_unavailable(self):
        """Entry 차단 - Secrets 없음"""
        strategy = CrossExchangeStrategy()
        
        mock_mapping = Mock()
        mock_spread = Mock()
        
        signal = strategy.evaluate_entry(
            symbol_mapping=mock_mapping,
            cross_spread=mock_spread,
            fx_confidence=1.0,
            health_ok=True,
            secrets_available=False,  # Blocked
        )
        
        assert signal.action == CrossExchangeAction.NO_ACTION
        assert "Secrets not available" in signal.reason
    
    def test_entry_blocked_health_degraded(self):
        """Entry 차단 - Exchange health 문제"""
        strategy = CrossExchangeStrategy()
        
        mock_mapping = Mock()
        mock_spread = Mock()
        
        signal = strategy.evaluate_entry(
            symbol_mapping=mock_mapping,
            cross_spread=mock_spread,
            fx_confidence=1.0,
            health_ok=False,  # Blocked
            secrets_available=True,
        )
        
        assert signal.action == CrossExchangeAction.NO_ACTION
        assert "health degraded" in signal.reason
    
    def test_entry_blocked_fx_confidence_low(self):
        """Entry 차단 - FX confidence 낮음"""
        strategy = CrossExchangeStrategy(min_fx_confidence=0.8)
        
        mock_mapping = Mock()
        mock_spread = Mock()
        
        signal = strategy.evaluate_entry(
            symbol_mapping=mock_mapping,
            cross_spread=mock_spread,
            fx_confidence=0.5,  # Too low
            health_ok=True,
            secrets_available=True,
        )
        
        assert signal.action == CrossExchangeAction.NO_ACTION
        assert "FX confidence too low" in signal.reason
    
    def test_entry_blocked_low_liquidity(self):
        """Entry 차단 - 유동성 부족"""
        strategy = CrossExchangeStrategy(min_liquidity_krw=100_000_000.0)
        
        mock_mapping = Mock()
        mock_spread = Mock()
        mock_spread.is_profitable.return_value = True
        
        signal = strategy.evaluate_entry(
            symbol_mapping=mock_mapping,
            cross_spread=mock_spread,
            fx_confidence=1.0,
            health_ok=True,
            secrets_available=True,
            liquidity_krw=50_000_000.0,  # Too low
        )
        
        assert signal.action == CrossExchangeAction.NO_ACTION
        assert "Liquidity too low" in signal.reason
    
    def test_entry_blocked_spread_too_low(self):
        """Entry 차단 - Spread 너무 작음"""
        strategy = CrossExchangeStrategy(min_spread_percent=0.5)
        
        mock_mapping = Mock()
        mock_spread = Mock()
        mock_spread.spread_percent = 0.2  # 0.2% (< 0.5%)
        mock_spread.is_profitable.return_value = False
        
        signal = strategy.evaluate_entry(
            symbol_mapping=mock_mapping,
            cross_spread=mock_spread,
            fx_confidence=1.0,
            health_ok=True,
            secrets_available=True,
        )
        
        assert signal.action == CrossExchangeAction.NO_ACTION
        assert "Spread too low" in signal.reason
    
    def test_exit_tp_positive_entry(self):
        """Exit - TP (Positive entry)"""
        strategy = CrossExchangeStrategy(tp_spread_percent=0.2)
        
        # Position (positive entry)
        position = {
            "entry_side": "positive",
            "entry_spread_percent": 1.0,  # Entry at 1.0%
            "entry_timestamp": time.time() - 100,
            "symbol_mapping": Mock(),
        }
        
        # Current spread (decreased to 0.5%)
        mock_spread = Mock()
        mock_spread.spread_percent = 0.5  # Decreased → Profit
        
        signal = strategy.evaluate_exit(
            position=position,
            current_spread=mock_spread,
            health_ok=True,
        )
        
        # Spread decreased by 0.5% → TP condition met
        assert signal.action == CrossExchangeAction.EXIT_TP
        assert "TP" in signal.reason
    
    def test_exit_sl_positive_entry(self):
        """Exit - SL (Positive entry)"""
        strategy = CrossExchangeStrategy(sl_spread_percent=-0.3)
        
        position = {
            "entry_side": "positive",
            "entry_spread_percent": 1.0,  # Entry at 1.0%
            "entry_timestamp": time.time() - 100,
            "symbol_mapping": Mock(),
        }
        
        # Current spread (increased to 1.5%)
        mock_spread = Mock()
        mock_spread.spread_percent = 1.5  # Increased → Loss
        
        signal = strategy.evaluate_exit(
            position=position,
            current_spread=mock_spread,
            health_ok=True,
        )
        
        # Spread increased by 0.5% → SL condition met
        assert signal.action == CrossExchangeAction.EXIT_SL
        assert "SL" in signal.reason
    
    def test_exit_timeout(self):
        """Exit - Timeout"""
        strategy = CrossExchangeStrategy(max_holding_seconds=60.0)
        
        position = {
            "entry_side": "positive",
            "entry_spread_percent": 1.0,
            "entry_timestamp": time.time() - 120,  # 120 seconds ago
            "symbol_mapping": Mock(),
        }
        
        mock_spread = Mock()
        mock_spread.spread_percent = 1.0  # No change
        
        signal = strategy.evaluate_exit(
            position=position,
            current_spread=mock_spread,
            health_ok=True,
        )
        
        assert signal.action == CrossExchangeAction.EXIT_TIMEOUT
        assert "Max holding time" in signal.reason
    
    def test_exit_health_degraded(self):
        """Exit - Exchange health degraded (emergency)"""
        strategy = CrossExchangeStrategy()
        
        position = {
            "entry_side": "positive",
            "entry_spread_percent": 1.0,
            "entry_timestamp": time.time() - 100,
            "symbol_mapping": Mock(),
        }
        
        mock_spread = Mock()
        mock_spread.spread_percent = 1.0
        
        signal = strategy.evaluate_exit(
            position=position,
            current_spread=mock_spread,
            health_ok=False,  # Health degraded
        )
        
        assert signal.action == CrossExchangeAction.EXIT_HEALTH
        assert "health degraded" in signal.reason
    
    def test_exit_reversal_positive_entry(self):
        """Exit - Spread reversal (Positive → Negative)"""
        strategy = CrossExchangeStrategy(
            tp_spread_percent=0.5,  # TP threshold (high to avoid TP trigger)
        )
        
        position = {
            "entry_side": "positive",
            "entry_spread_percent": 0.3,  # Small positive entry
            "entry_timestamp": time.time() - 100,
            "symbol_mapping": Mock(),
        }
        
        # Spread reversed to negative (but not enough for TP)
        # spread_change = -0.1 - 0.3 = -0.4 (> -0.5 TP threshold, no TP)
        mock_spread = Mock()
        mock_spread.spread_percent = -0.1  # Reversed
        
        signal = strategy.evaluate_exit(
            position=position,
            current_spread=mock_spread,
            health_ok=True,
        )
        
        assert signal.action == CrossExchangeAction.EXIT_REVERSAL
        assert "reversal" in signal.reason.lower()
    
    def test_exit_no_action(self):
        """Exit - No exit condition met"""
        strategy = CrossExchangeStrategy(
            tp_spread_percent=0.2,
            sl_spread_percent=-0.3,
            max_holding_seconds=3600,
        )
        
        position = {
            "entry_side": "positive",
            "entry_spread_percent": 1.0,
            "entry_timestamp": time.time() - 100,  # Recent
            "symbol_mapping": Mock(),
        }
        
        # Spread slightly changed (not enough for TP/SL)
        mock_spread = Mock()
        mock_spread.spread_percent = 0.95  # -0.05% change
        
        signal = strategy.evaluate_exit(
            position=position,
            current_spread=mock_spread,
            health_ok=True,
        )
        
        assert signal.action == CrossExchangeAction.NO_ACTION


class TestCrossExchangePositionManager:
    """CrossExchangePositionManager 테스트"""
    
    def test_position_manager_initialization(self):
        """PositionManager 초기화"""
        pm = CrossExchangePositionManager()
        
        assert pm is not None
        assert pm.POSITION_KEY_PREFIX == "cross_position:"
    
    def test_open_position(self):
        """Position 진입"""
        mock_redis = Mock()
        pm = CrossExchangePositionManager(redis_client=mock_redis)
        
        # Mock data
        mock_mapping = Mock()
        mock_mapping.upbit_symbol = "KRW-BTC"
        mock_mapping.binance_symbol = "BTCUSDT"
        mock_mapping.base_asset = "BTC"
        mock_mapping.upbit_quote = "KRW"
        mock_mapping.binance_quote = "USDT"
        mock_mapping.confidence = 1.0
        
        mock_spread = Mock()
        mock_spread.spread_percent = 1.0
        mock_spread.fx_rate = 1300.0
        mock_spread.upbit_price_krw = 52000000.0
        mock_spread.binance_price_usdt = 40000.0
        
        # Open position
        position = pm.open_position(
            symbol_mapping=mock_mapping,
            entry_side="positive",
            entry_spread=mock_spread,
        )
        
        assert position.state == PositionState.OPEN
        assert position.entry_side == "positive"
        assert position.entry_spread_percent == 1.0
        assert position.is_open()
        assert not position.is_closed()
    
    def test_close_position(self):
        """Position 청산"""
        mock_redis = Mock()
        pm = CrossExchangePositionManager(redis_client=mock_redis)
        
        # Mock existing position
        existing_position = CrossExchangePosition(
            symbol_mapping={"upbit_symbol": "KRW-BTC"},
            entry_side="positive",
            entry_spread_percent=1.0,
            entry_fx_rate=1300.0,
            entry_timestamp=time.time() - 100,
            entry_upbit_price_krw=52000000.0,
            entry_binance_price_usdt=40000.0,
            state=PositionState.OPEN,
        )
        
        # Mock Redis get
        mock_redis.get.return_value = json.dumps(existing_position.to_dict())
        
        # Mock exit spread
        mock_exit_spread = Mock()
        mock_exit_spread.spread_percent = 0.5  # Decreased (profit)
        
        # Close position
        closed_position = pm.close_position(
            upbit_symbol="KRW-BTC",
            exit_spread=mock_exit_spread,
            exit_reason="TP",
        )
        
        assert closed_position.state == PositionState.CLOSED
        assert closed_position.exit_reason == "TP"
        assert closed_position.exit_pnl_krw is not None
        assert closed_position.is_closed()
    
    def test_get_position(self):
        """Position 조회"""
        mock_redis = Mock()
        pm = CrossExchangePositionManager(redis_client=mock_redis)
        
        # Mock Redis data
        position_data = {
            "symbol_mapping": {"upbit_symbol": "KRW-BTC"},
            "entry_side": "positive",
            "entry_spread_percent": 1.0,
            "entry_fx_rate": 1300.0,
            "entry_timestamp": time.time(),
            "entry_upbit_price_krw": 52000000.0,
            "entry_binance_price_usdt": 40000.0,
            "state": "open",
            "exit_timestamp": None,
            "exit_spread_percent": None,
            "exit_reason": None,
            "exit_pnl_krw": None,
            "position_id": "KRW-BTC_123456",
        }
        
        mock_redis.get.return_value = json.dumps(position_data)
        
        # Get position
        position = pm.get_position("KRW-BTC")
        
        assert position is not None
        assert position.entry_side == "positive"
        assert position.state == PositionState.OPEN
    
    def test_get_position_not_found(self):
        """Position 조회 - 없음"""
        mock_redis = Mock()
        mock_redis.get.return_value = None
        
        pm = CrossExchangePositionManager(redis_client=mock_redis)
        
        position = pm.get_position("KRW-BTC")
        
        assert position is None
    
    def test_list_open_positions(self):
        """모든 open position 조회"""
        mock_redis = Mock()
        pm = CrossExchangePositionManager(redis_client=mock_redis)
        
        # Mock Redis scan
        keys = ["cross_position:KRW-BTC", "cross_position:KRW-ETH"]
        mock_redis.scan_iter.return_value = iter(keys)
        
        # Mock position data
        position1 = CrossExchangePosition(
            symbol_mapping={"upbit_symbol": "KRW-BTC"},
            entry_side="positive",
            entry_spread_percent=1.0,
            entry_fx_rate=1300.0,
            entry_timestamp=time.time(),
            entry_upbit_price_krw=52000000.0,
            entry_binance_price_usdt=40000.0,
            state=PositionState.OPEN,
        )
        
        position2 = CrossExchangePosition(
            symbol_mapping={"upbit_symbol": "KRW-ETH"},
            entry_side="negative",
            entry_spread_percent=-0.8,
            entry_fx_rate=1300.0,
            entry_timestamp=time.time(),
            entry_upbit_price_krw=3000000.0,
            entry_binance_price_usdt=2350.0,
            state=PositionState.CLOSED,  # Closed (should not be included)
        )
        
        mock_redis.get.side_effect = [
            json.dumps(position1.to_dict()),
            json.dumps(position2.to_dict()),
        ]
        
        # List open positions
        open_positions = pm.list_open_positions()
        
        assert len(open_positions) == 1  # Only OPEN positions
        assert open_positions[0].state == PositionState.OPEN
    
    def test_get_inventory(self):
        """인벤토리 조회"""
        mock_redis = Mock()
        pm = CrossExchangePositionManager(redis_client=mock_redis)
        
        # Mock scan
        keys = ["cross_position:KRW-BTC", "cross_position:KRW-ETH"]
        mock_redis.scan_iter.return_value = iter(keys)
        
        # Mock positions (1 positive, 1 negative)
        pos1 = CrossExchangePosition(
            symbol_mapping={"upbit_symbol": "KRW-BTC"},
            entry_side="positive",
            entry_spread_percent=1.0,
            entry_fx_rate=1300.0,
            entry_timestamp=time.time(),
            entry_upbit_price_krw=52000000.0,
            entry_binance_price_usdt=40000.0,
            state=PositionState.OPEN,
        )
        
        pos2 = CrossExchangePosition(
            symbol_mapping={"upbit_symbol": "KRW-ETH"},
            entry_side="negative",
            entry_spread_percent=-0.8,
            entry_fx_rate=1300.0,
            entry_timestamp=time.time(),
            entry_upbit_price_krw=3000000.0,
            entry_binance_price_usdt=2350.0,
            state=PositionState.OPEN,
        )
        
        mock_redis.get.side_effect = [
            json.dumps(pos1.to_dict()),
            json.dumps(pos2.to_dict()),
        ]
        
        # Get inventory
        inventory = pm.get_inventory()
        
        assert inventory["total_open"] == 2
        assert inventory["positive"] == 1
        assert inventory["negative"] == 1
    
    def test_position_holding_time(self):
        """Position holding time 계산"""
        position = CrossExchangePosition(
            symbol_mapping={"upbit_symbol": "KRW-BTC"},
            entry_side="positive",
            entry_spread_percent=1.0,
            entry_fx_rate=1300.0,
            entry_timestamp=time.time() - 100,  # 100 seconds ago
            entry_upbit_price_krw=52000000.0,
            entry_binance_price_usdt=40000.0,
            state=PositionState.OPEN,
        )
        
        holding_time = position.get_holding_time()
        
        assert holding_time >= 100.0
        assert holding_time < 105.0  # Allow small time difference
    
    def test_position_to_dict_from_dict(self):
        """Position serialization"""
        position = CrossExchangePosition(
            symbol_mapping={"upbit_symbol": "KRW-BTC"},
            entry_side="positive",
            entry_spread_percent=1.0,
            entry_fx_rate=1300.0,
            entry_timestamp=time.time(),
            entry_upbit_price_krw=52000000.0,
            entry_binance_price_usdt=40000.0,
            state=PositionState.OPEN,
        )
        
        # to_dict
        data = position.to_dict()
        assert data["entry_side"] == "positive"
        assert data["state"] == "open"  # Enum → str
        
        # from_dict
        restored = CrossExchangePosition.from_dict(data)
        assert restored.entry_side == "positive"
        assert restored.state == PositionState.OPEN  # str → Enum


# Integration tests
def test_strategy_position_manager_integration():
    """Strategy + PositionManager 통합 테스트"""
    strategy = CrossExchangeStrategy(min_spread_percent=0.5)
    pm = CrossExchangePositionManager()  # No Redis (testing mode)
    
    # Mock data
    mock_mapping = Mock()
    mock_mapping.upbit_symbol = "KRW-BTC"
    mock_mapping.binance_symbol = "BTCUSDT"
    mock_mapping.base_asset = "BTC"
    mock_mapping.upbit_quote = "KRW"
    mock_mapping.binance_quote = "USDT"
    mock_mapping.confidence = 1.0
    
    mock_spread = Mock()
    mock_spread.spread_percent = 1.0
    mock_spread.direction = SpreadDirection.POSITIVE
    mock_spread.is_profitable.return_value = True
    mock_spread.fx_rate = 1300.0
    mock_spread.upbit_price_krw = 52000000.0
    mock_spread.binance_price_usdt = 40000.0
    
    # Entry signal
    entry_signal = strategy.evaluate_entry(
        symbol_mapping=mock_mapping,
        cross_spread=mock_spread,
        fx_confidence=1.0,
        health_ok=True,
        secrets_available=True,
    )
    
    assert entry_signal.action == CrossExchangeAction.ENTRY_POSITIVE
    
    # This test would continue with position opening, but we skip Redis for unit test
    pass
