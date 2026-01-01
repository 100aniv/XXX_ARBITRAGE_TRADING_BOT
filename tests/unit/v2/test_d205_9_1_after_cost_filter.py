"""
D205-9-1: After-Cost Candidate Filtering 단위 테스트

검증:
1. break_even_bps에 latency_bps가 포함되는지
2. raw_spread < break_even → candidate.profitable = False
3. raw_spread > break_even → candidate.profitable = True
"""

import pytest

from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.v2.domain.break_even import (
    BreakEvenParams,
    compute_break_even_bps,
    compute_edge_bps,
)
from arbitrage.v2.opportunity.detector import detect_candidates


class TestAfterCostFiltering:
    """After-Cost Candidate Filtering 테스트"""
    
    @pytest.fixture
    def fee_model(self):
        """Fee model fixture"""
        fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=25.0)
        fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=25.0)
        return FeeModel(fee_a=fee_a, fee_b=fee_b)
    
    def test_break_even_excludes_slippage_latency(self, fee_model):
        """D205-9-2 FIX: slippage/latency는 break_even에 round-trip으로 포함"""
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=15.0,
            latency_bps=10.0,
            buffer_bps=5.0,
        )
        
        break_even_bps = compute_break_even_bps(params)
        
        # D205-9-2 FIX: slippage/latency round-trip으로 포함
        # fee_entry = 25 (upbit taker) + 25 (binance taker) = 50
        # fee_exit = 50 (round-trip)
        # exec_risk_round_trip = 2 * (15 + 10) = 50
        # buffer = 5
        # total = 50 + 50 + 50 + 5 = 155 bps
        assert break_even_bps == 155.0, f"Expected 155, got {break_even_bps}"
    
    def test_candidate_reject_when_spread_below_break_even(self, fee_model):
        """raw_spread < break_even → candidate.profitable = False"""
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=15.0,
            latency_bps=10.0,
            buffer_bps=5.0,
        )
        
        # D205-9-2 FIX: break_even = 155 bps
        # spread = 100 bps (< 155) → unprofitable
        price_a = 100_000_000.0  # 1억
        price_b = 100_100_000.0  # 1억 10만 (0.1% = 100 bps spread)
        
        candidate = detect_candidates(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=price_a,
            price_b=price_b,
            params=params,
        )
        
        assert candidate is not None
        assert candidate.profitable is False, "Expected unprofitable (spread 100 < break_even 155)"
        assert candidate.edge_bps < 0, f"Expected negative edge, got {candidate.edge_bps}"
    
    def test_candidate_accept_when_spread_above_break_even(self, fee_model):
        """raw_spread > break_even → candidate.profitable = True"""
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=15.0,
            latency_bps=10.0,
            buffer_bps=5.0,
        )
        
        # D205-9-2 FIX: break_even = 155 bps
        # spread = 200 bps (> 155) → profitable
        price_a = 100_000_000.0  # 1억
        price_b = 102_000_000.0  # 1억 200만 (2.0% = 200 bps spread)
        
        candidate = detect_candidates(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=price_a,
            price_b=price_b,
            params=params,
        )
        
        assert candidate is not None
        assert candidate.profitable is True, "Expected profitable (spread 200 > break_even 155)"
        assert candidate.edge_bps > 0, f"Expected positive edge, got {candidate.edge_bps}"
        # D205-9-2 FIX: edge = spread - break_even (부동소수점 오차 허용)
        # 실제 spread ~196, edge ~41 (196 - 155)
        assert candidate.edge_bps == pytest.approx(41.0, abs=5.0), f"Expected edge ~41, got {candidate.edge_bps}"
