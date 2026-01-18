"""
D207-1-1: PnL Sign Audit Test (Economic Truth Verification)

Purpose:
- Verify realized_pnl sign matches candidate_edge sign
- Prevent negative PnL when candidate_edge is positive
- Audit PnL calculation correctness for both directions

Test Cases:
1. UPBIT_TO_BINANCE (Upbit SELL → Binance BUY): entry_price > exit_price → positive PnL
2. BINANCE_TO_UPBIT (Binance SELL → Upbit BUY): exit_price > entry_price → positive PnL
3. Zero edge → near-zero PnL (fees only)
4. Negative edge → negative PnL (expected loss)

Author: D207-1-1 RECOVERY
Date: 2026-01-19
"""

import pytest
from arbitrage.v2.domain.pnl_calculator import calculate_pnl_summary


class TestPnLSignAudit:
    """PnL 부호 정확성 검증 (Economic Truth)"""
    
    def test_upbit_to_binance_positive_edge(self):
        """
        UPBIT_TO_BINANCE (Upbit SELL → Binance BUY)
        Entry: SELL at 100.0 (Upbit)
        Exit: BUY at 95.0 (Binance)
        Expected: Positive PnL (bought back cheaper)
        """
        gross_pnl, realized_pnl, is_win = calculate_pnl_summary(
            entry_side="SELL",
            exit_side="BUY",
            entry_price=100.0,
            exit_price=95.0,
            quantity=1.0,
            total_fee=0.5
        )
        
        # SELL at 100, BUY at 95 → profit = 5.0 - 0.5 = 4.5
        assert gross_pnl == 5.0, f"Expected gross_pnl=5.0, got {gross_pnl}"
        assert realized_pnl == 4.5, f"Expected realized_pnl=4.5, got {realized_pnl}"
        assert is_win is True, "Expected is_win=True (positive edge)"
    
    def test_binance_to_upbit_positive_edge(self):
        """
        BINANCE_TO_UPBIT (Binance SELL → Upbit BUY)
        Entry: BUY at 95.0 (Binance)
        Exit: SELL at 100.0 (Upbit)
        Expected: Positive PnL (sold higher)
        """
        gross_pnl, realized_pnl, is_win = calculate_pnl_summary(
            entry_side="BUY",
            exit_side="SELL",
            entry_price=95.0,
            exit_price=100.0,
            quantity=1.0,
            total_fee=0.5
        )
        
        # BUY at 95, SELL at 100 → profit = 5.0 - 0.5 = 4.5
        assert gross_pnl == 5.0, f"Expected gross_pnl=5.0, got {gross_pnl}"
        assert realized_pnl == 4.5, f"Expected realized_pnl=4.5, got {realized_pnl}"
        assert is_win is True, "Expected is_win=True (positive edge)"
    
    def test_zero_edge_near_zero_pnl(self):
        """
        Zero edge (same price entry/exit)
        Expected: Negative PnL (fees only)
        """
        gross_pnl, realized_pnl, is_win = calculate_pnl_summary(
            entry_side="BUY",
            exit_side="SELL",
            entry_price=100.0,
            exit_price=100.0,
            quantity=1.0,
            total_fee=0.5
        )
        
        # BUY at 100, SELL at 100 → profit = 0 - 0.5 = -0.5
        assert gross_pnl == 0.0, f"Expected gross_pnl=0.0, got {gross_pnl}"
        assert realized_pnl == -0.5, f"Expected realized_pnl=-0.5, got {realized_pnl}"
        assert is_win is False, "Expected is_win=False (zero edge)"
    
    def test_negative_edge_negative_pnl(self):
        """
        Negative edge (entry_price < exit_price for BUY-SELL)
        Expected: Negative PnL (loss)
        """
        gross_pnl, realized_pnl, is_win = calculate_pnl_summary(
            entry_side="BUY",
            exit_side="SELL",
            entry_price=100.0,
            exit_price=95.0,
            quantity=1.0,
            total_fee=0.5
        )
        
        # BUY at 100, SELL at 95 → profit = -5.0 - 0.5 = -5.5
        assert gross_pnl == -5.0, f"Expected gross_pnl=-5.0, got {gross_pnl}"
        assert realized_pnl == -5.5, f"Expected realized_pnl=-5.5, got {realized_pnl}"
        assert is_win is False, "Expected is_win=False (negative edge)"
    
    def test_realistic_arbitrage_scenario(self):
        """
        Realistic arbitrage with small positive edge
        Simulates actual D207-1 scenario (simplified)
        """
        # Small positive spread after costs
        gross_pnl, realized_pnl, is_win = calculate_pnl_summary(
            entry_side="SELL",
            exit_side="BUY",
            entry_price=1000.0,
            exit_price=986.0,   # 14 KRW spread (1.4% = 140 bps)
            quantity=1.0,
            total_fee=6.3       # 63 bps cost → net edge = 77 bps
        )
        
        # Expected: positive PnL (14 - 6.3 = 7.7)
        assert gross_pnl == 14.0, f"Expected gross_pnl=14.0, got {gross_pnl}"
        assert realized_pnl == 7.7, f"Expected realized_pnl=7.7, got {realized_pnl}"
        assert is_win is True, "Expected is_win=True (positive net edge)"
