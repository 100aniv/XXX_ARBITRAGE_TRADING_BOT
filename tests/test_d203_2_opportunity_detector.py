"""
D203-2: Opportunity Detector v1 테스트

테스트 케이스:
1. 단일 기회 탐지 (profitable)
2. 단일 기회 탐지 (unprofitable)
3. Direction 판단 (BUY_A_SELL_B vs BUY_B_SELL_A)
4. 여러 기회 중 profitable만 필터링
5. Edge 순서대로 정렬
6. Invalid 가격 (0 또는 음수) 처리
"""

import pytest
from arbitrage.v2.opportunity.detector import (
    OpportunityCandidate,
    OpportunityDirection,
    detect_candidates,
    detect_multi_candidates,
)
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure


class TestOpportunityDetector:
    """Opportunity Detector 테스트"""
    
    def test_case1_single_profitable_opportunity(self):
        """
        Case 1: 단일 기회 탐지 (profitable)
        
        Scenario:
            - Upbit: 50,000,000 KRW
            - Binance (normalized to KRW): 49,500,000 KRW
            - Spread: 1.01% = 101 bps
            - Break-even: 45 bps
            - Edge: 56 bps (profitable)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        candidate = detect_candidates(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=50_000_000.0,
            price_b=49_500_000.0,
            params=params,
        )
        
        assert candidate is not None
        assert candidate.symbol == "BTC/KRW"
        assert candidate.exchange_a == "upbit"
        assert candidate.exchange_b == "binance"
        assert candidate.price_a == 50_000_000.0
        assert candidate.price_b == 49_500_000.0
        
        # Spread: (50M - 49.5M) / 49.5M * 100 = 1.0101% = 101.01 bps
        assert 100.0 <= candidate.spread_bps <= 102.0
        
        # Break-even: 15 + 15 + 10 + 5 = 45 bps
        assert candidate.break_even_bps == 45.0
        
        # Edge: 101 - 45 = 56 bps
        assert 55.0 <= candidate.edge_bps <= 57.0
        
        # Direction: Upbit > Binance → BUY_B_SELL_A
        assert candidate.direction == OpportunityDirection.BUY_B_SELL_A
        
        # Profitable
        assert candidate.profitable is True
    
    def test_case2_single_unprofitable_opportunity(self):
        """
        Case 2: 단일 기회 탐지 (unprofitable)
        
        Scenario:
            - Spread: 30 bps
            - Break-even: 45 bps
            - Edge: -15 bps (unprofitable)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        # Spread ~0.3% = 30 bps
        candidate = detect_candidates(
            symbol="ETH/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=3_000_000.0,
            price_b=3_009_000.0,  # 0.3% higher
            params=params,
        )
        
        assert candidate is not None
        assert 29.0 <= candidate.spread_bps <= 31.0
        assert candidate.break_even_bps == 45.0
        assert candidate.edge_bps < 0  # Unprofitable
        assert candidate.profitable is False
    
    def test_case3_direction_buy_a_sell_b(self):
        """
        Case 3: Direction 판단 (BUY_A_SELL_B)
        
        Scenario:
            - Upbit (A): 49,000,000 KRW (저렴)
            - Binance (B): 50,000,000 KRW (비싸)
            - Direction: BUY_A_SELL_B (A에서 사고 B에서 팔기)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        candidate = detect_candidates(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=49_000_000.0,  # A가 저렴
            price_b=50_000_000.0,  # B가 비싸
            params=params,
        )
        
        assert candidate is not None
        assert candidate.direction == OpportunityDirection.BUY_A_SELL_B
    
    def test_case4_multi_candidates_filter_profitable(self):
        """
        Case 4: 여러 기회 중 profitable만 필터링
        
        Scenario:
            - BTC: profitable (edge = 56 bps)
            - ETH: unprofitable (edge = -15 bps)
            - XRP: profitable (edge = 10 bps)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        opportunities = [
            # BTC: profitable (spread ~101 bps)
            {
                "symbol": "BTC/KRW",
                "exchange_a": "upbit",
                "exchange_b": "binance",
                "price_a": 50_000_000.0,
                "price_b": 49_500_000.0,
            },
            # ETH: unprofitable (spread ~30 bps)
            {
                "symbol": "ETH/KRW",
                "exchange_a": "upbit",
                "exchange_b": "binance",
                "price_a": 3_000_000.0,
                "price_b": 3_009_000.0,
            },
            # XRP: profitable (spread ~60 bps)
            {
                "symbol": "XRP/KRW",
                "exchange_a": "upbit",
                "exchange_b": "binance",
                "price_a": 1000.0,
                "price_b": 994.0,
            },
        ]
        
        candidates = detect_multi_candidates(opportunities, params)
        
        # Only 2 profitable (BTC, XRP)
        assert len(candidates) == 2
        assert all(c.profitable for c in candidates)
        
        # Symbols
        symbols = [c.symbol for c in candidates]
        assert "BTC/KRW" in symbols
        assert "XRP/KRW" in symbols
        assert "ETH/KRW" not in symbols  # Unprofitable excluded
    
    def test_case5_multi_candidates_sorted_by_edge(self):
        """
        Case 5: Edge 순서대로 정렬 (내림차순)
        
        Scenario:
            - BTC: edge ~56 bps
            - XRP: edge ~15 bps
            - Expected order: BTC, XRP
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        opportunities = [
            # XRP: edge ~15 bps (lower)
            {
                "symbol": "XRP/KRW",
                "exchange_a": "upbit",
                "exchange_b": "binance",
                "price_a": 1000.0,
                "price_b": 994.0,
            },
            # BTC: edge ~56 bps (higher)
            {
                "symbol": "BTC/KRW",
                "exchange_a": "upbit",
                "exchange_b": "binance",
                "price_a": 50_000_000.0,
                "price_b": 49_500_000.0,
            },
        ]
        
        candidates = detect_multi_candidates(opportunities, params)
        
        assert len(candidates) == 2
        
        # Sorted by edge_bps (descending)
        assert candidates[0].symbol == "BTC/KRW"  # Higher edge first
        assert candidates[1].symbol == "XRP/KRW"  # Lower edge second
        assert candidates[0].edge_bps > candidates[1].edge_bps
    
    def test_case6_invalid_price_handling(self):
        """
        Case 6: Invalid 가격 (0 또는 음수) 처리
        
        Expected: None 반환
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        # price_a = 0
        candidate1 = detect_candidates(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=0.0,
            price_b=50_000_000.0,
            params=params,
        )
        assert candidate1 is None
        
        # price_b = 0
        candidate2 = detect_candidates(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=50_000_000.0,
            price_b=0.0,
            params=params,
        )
        assert candidate2 is None
        
        # price_a < 0
        candidate3 = detect_candidates(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=-1000.0,
            price_b=50_000_000.0,
            params=params,
        )
        assert candidate3 is None
