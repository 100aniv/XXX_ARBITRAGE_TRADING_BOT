"""
D75-4: Cross-Exchange Sync Unit Tests

Inventory, InventoryTracker, RebalanceSignal 검증
"""

import pytest
from arbitrage.domain.cross_sync import (
    Inventory,
    InventoryTracker,
    RebalanceSignal,
)


class TestInventory:
    """Inventory 테스트"""
    
    def test_initialization(self):
        """초기화"""
        inv = Inventory(
            exchange_name="UPBIT",
            base_balance=1.0,
            quote_balance=10_000_000.0,
        )
        
        assert inv.exchange_name == "UPBIT"
        assert inv.base_balance == 1.0
        assert inv.quote_balance == 10_000_000.0
    
    def test_total_value_calculation(self):
        """총 자산 가치 계산"""
        inv = Inventory(
            exchange_name="UPBIT",
            base_balance=1.0,  # 1 BTC
            quote_balance=10_000_000.0,  # 10M KRW
        )
        
        # base_price = 100M KRW
        # total_value = 1.0 * 100M + 10M = 110M KRW
        total = inv.total_value_in_quote(100_000_000.0)
        assert total == 110_000_000.0
    
    def test_base_ratio(self):
        """Base asset 비율"""
        inv = Inventory(
            exchange_name="UPBIT",
            base_balance=1.0,
            quote_balance=100_000_000.0,
        )
        
        # base_price = 100M KRW
        # base_value = 100M, quote_value = 100M
        # base_ratio = 100M / 200M = 0.5
        ratio = inv.base_ratio(100_000_000.0)
        assert abs(ratio - 0.5) < 0.01


class TestInventoryTracker:
    """InventoryTracker 테스트"""
    
    @pytest.fixture
    def tracker(self):
        return InventoryTracker(
            imbalance_threshold=0.3,
            exposure_threshold=0.8,
        )
    
    def test_initialization(self, tracker):
        """초기화"""
        assert tracker.imbalance_threshold == 0.3
        assert tracker.exposure_threshold == 0.8
    
    def test_update_inventory(self, tracker):
        """Inventory 업데이트"""
        inv_a = Inventory("UPBIT", base_balance=1.0, quote_balance=10_000_000.0)
        inv_b = Inventory("BINANCE", base_balance=0.5, quote_balance=5_000.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        state = tracker.get_inventory_state()
        assert state[0].exchange_name == "UPBIT"
        assert state[1].exchange_name == "BINANCE"
    
    def test_calculate_imbalance_balanced(self, tracker):
        """Imbalance 계산 (균형 상태)"""
        inv_a = Inventory("UPBIT", base_balance=1.0, quote_balance=0.0)
        inv_b = Inventory("BINANCE", base_balance=1.0, quote_balance=0.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        # Use same normalized price (in USDT)
        # value_a = 1.0 * 73k = 73k USDT
        # value_b = 1.0 * 73k = 73k USDT
        imbalance = tracker.calculate_imbalance(73_000.0, 73_000.0)
        
        # Balanced state
        assert abs(imbalance) < 0.01
    
    def test_calculate_imbalance_a_heavy(self, tracker):
        """Imbalance 계산 (A가 많음)"""
        inv_a = Inventory("UPBIT", base_balance=2.0, quote_balance=0.0)
        inv_b = Inventory("BINANCE", base_balance=1.0, quote_balance=0.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        # Use same normalized price
        imbalance = tracker.calculate_imbalance(73_000.0, 73_000.0)
        
        # A가 더 많으므로 양수
        assert imbalance > 0.2
    
    def test_calculate_imbalance_b_heavy(self, tracker):
        """Imbalance 계산 (B가 많음)"""
        inv_a = Inventory("UPBIT", base_balance=1.0, quote_balance=0.0)
        inv_b = Inventory("BINANCE", base_balance=2.0, quote_balance=0.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        # Use same normalized price
        imbalance = tracker.calculate_imbalance(73_000.0, 73_000.0)
        
        # B가 더 많으므로 음수
        assert imbalance < -0.2
    
    def test_exposure_risk_low(self, tracker):
        """Exposure risk (낮음)"""
        inv_a = Inventory("UPBIT", base_balance=1.0, quote_balance=0.0)
        inv_b = Inventory("BINANCE", base_balance=1.1, quote_balance=0.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        # Use same normalized price
        risk = tracker.calculate_exposure_risk(73_000.0, 73_000.0)
        
        # 균형 상태이므로 risk 낮음
        assert risk < 0.15
    
    def test_exposure_risk_high(self, tracker):
        """Exposure risk (높음)"""
        inv_a = Inventory("UPBIT", base_balance=10.0, quote_balance=0.0)
        inv_b = Inventory("BINANCE", base_balance=1.0, quote_balance=0.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        # Use same normalized price
        risk = tracker.calculate_exposure_risk(73_000.0, 73_000.0)
        
        # 한쪽 집중이므로 risk 높음
        assert risk > 0.9
    
    def test_rebalance_needed_balanced(self, tracker):
        """Rebalance 필요성 (균형)"""
        inv_a = Inventory("UPBIT", base_balance=1.0, quote_balance=0.0)
        inv_b = Inventory("BINANCE", base_balance=1.0, quote_balance=0.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        # Use same normalized price
        signal = tracker.check_rebalance_needed(73_000.0, 73_000.0)
        
        assert signal.needed is False
        assert signal.recommended_action == "NONE"
    
    def test_rebalance_needed_a_heavy(self, tracker):
        """Rebalance 필요성 (A 과다)"""
        inv_a = Inventory("UPBIT", base_balance=5.0, quote_balance=0.0)
        inv_b = Inventory("BINANCE", base_balance=1.0, quote_balance=0.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        # Use same normalized price
        signal = tracker.check_rebalance_needed(73_000.0, 73_000.0)
        
        assert signal.needed is True
        assert signal.recommended_action == "BUY_B_SELL_A"
        assert signal.imbalance_ratio > 0.3
    
    def test_rebalance_needed_b_heavy(self, tracker):
        """Rebalance 필요성 (B 과다)"""
        inv_a = Inventory("UPBIT", base_balance=1.0, quote_balance=0.0)
        inv_b = Inventory("BINANCE", base_balance=5.0, quote_balance=0.0)
        
        tracker.update_inventory(inv_a, inv_b)
        
        # Use same normalized price
        signal = tracker.check_rebalance_needed(73_000.0, 73_000.0)
        
        assert signal.needed is True
        assert signal.recommended_action == "BUY_A_SELL_B"
        assert signal.imbalance_ratio < -0.3
