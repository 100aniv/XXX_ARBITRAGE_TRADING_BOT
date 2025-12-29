"""
D203-3: Opportunity → OrderIntent Bridge 테스트

테스트 케이스:
1. Direction BUY_A_SELL_B → BUY intent(exchange_a), SELL intent(exchange_b)
2. Direction BUY_B_SELL_A → BUY intent(exchange_b), SELL intent(exchange_a)
3. Unprofitable (Edge<=0) → 빈 리스트 (intent 생성 금지)
4. Direction NONE → 빈 리스트
5. MARKET order validation
6. LIMIT order validation
7. Invalid price → None candidate → 빈 리스트
8. build_and_convert() 편의 함수
"""

import pytest
from arbitrage.v2.opportunity.intent_builder import (
    build_candidate,
    candidate_to_order_intents,
    build_and_convert,
)
from arbitrage.v2.core.order_intent import OrderSide, OrderType
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure


class TestOpportunityToOrderIntent:
    """Opportunity → OrderIntent 변환 테스트"""
    
    @pytest.fixture
    def params(self):
        """Standard BreakEvenParams fixture"""
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        return BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
    
    def test_case1_buy_a_sell_b_direction(self, params):
        """
        Case 1: Direction BUY_A_SELL_B
        
        Scenario:
            - Upbit (A): 49,000,000 KRW (저렴)
            - Binance (B): 50,000,000 KRW (비싸)
            - Direction: BUY_A_SELL_B
            - Expected: BUY(upbit), SELL(binance)
        """
        candidate = build_candidate(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=49_000_000.0,
            price_b=50_000_000.0,
            params=params,
        )
        
        assert candidate is not None
        assert candidate.profitable is True
        
        # Convert to OrderIntents
        intents = candidate_to_order_intents(
            candidate=candidate,
            base_qty=0.01,
            quote_amount=500_000.0,
        )
        
        assert len(intents) == 2
        
        # BUY intent (exchange A = upbit)
        buy_intent = intents[0]
        assert buy_intent.exchange == "upbit"
        assert buy_intent.symbol == "BTC/KRW"
        assert buy_intent.side == OrderSide.BUY
        assert buy_intent.order_type == OrderType.MARKET
        assert buy_intent.quote_amount == 500_000.0
        
        # SELL intent (exchange B = binance)
        sell_intent = intents[1]
        assert sell_intent.exchange == "binance"
        assert sell_intent.symbol == "BTC/KRW"
        assert sell_intent.side == OrderSide.SELL
        assert sell_intent.order_type == OrderType.MARKET
        assert sell_intent.base_qty == 0.01
    
    def test_case2_buy_b_sell_a_direction(self, params):
        """
        Case 2: Direction BUY_B_SELL_A
        
        Scenario:
            - Upbit (A): 50,000,000 KRW (비싸)
            - Binance (B): 49,000,000 KRW (저렴)
            - Direction: BUY_B_SELL_A
            - Expected: BUY(binance), SELL(upbit)
        """
        candidate = build_candidate(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=50_000_000.0,
            price_b=49_000_000.0,
            params=params,
        )
        
        assert candidate is not None
        assert candidate.profitable is True
        
        # Convert to OrderIntents
        intents = candidate_to_order_intents(
            candidate=candidate,
            base_qty=0.01,
            quote_amount=500_000.0,
        )
        
        assert len(intents) == 2
        
        # BUY intent (exchange B = binance)
        buy_intent = intents[0]
        assert buy_intent.exchange == "binance"
        assert buy_intent.symbol == "BTC/KRW"
        assert buy_intent.side == OrderSide.BUY
        
        # SELL intent (exchange A = upbit)
        sell_intent = intents[1]
        assert sell_intent.exchange == "upbit"
        assert sell_intent.symbol == "BTC/KRW"
        assert sell_intent.side == OrderSide.SELL
    
    def test_case3_unprofitable_no_intents(self, params):
        """
        Case 3: Unprofitable (Edge<=0) → 빈 리스트
        
        Policy (SSOT):
            - unprofitable candidate는 OrderIntent 생성 금지
        
        Scenario:
            - Spread: 30 bps
            - Break-even: 45 bps
            - Edge: -15 bps (unprofitable)
            - Expected: 빈 리스트 []
        """
        candidate = build_candidate(
            symbol="ETH/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=3_000_000.0,
            price_b=3_009_000.0,  # spread ~30 bps
            params=params,
        )
        
        assert candidate is not None
        assert candidate.profitable is False
        assert candidate.edge_bps < 0
        
        # Convert to OrderIntents (should be empty)
        intents = candidate_to_order_intents(
            candidate=candidate,
            base_qty=0.1,
            quote_amount=300_000.0,
        )
        
        assert len(intents) == 0  # ✅ Policy: unprofitable → 빈 리스트
    
    def test_case4_direction_none_no_intents(self, params):
        """
        Case 4: Direction NONE → 빈 리스트
        
        Scenario:
            - price_a == price_b (동일 가격)
            - Direction: NONE
            - Expected: 빈 리스트 []
        """
        candidate = build_candidate(
            symbol="XRP/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=1000.0,
            price_b=1000.0,  # 동일 가격
            params=params,
        )
        
        # Spread = 0, 기회 없음
        # Note: spread=0이면 edge < 0이므로 unprofitable
        if candidate:
            assert candidate.profitable is False
        
        # Convert (should be empty)
        intents = candidate_to_order_intents(
            candidate=candidate,
            base_qty=100.0,
            quote_amount=100_000.0,
        ) if candidate else []
        
        assert len(intents) == 0  # ✅ Policy: direction NONE or unprofitable → 빈 리스트
    
    def test_case5_market_order_validation(self, params):
        """
        Case 5: MARKET order validation
        
        Verify:
            - BUY MARKET: quote_amount 필수
            - SELL MARKET: base_qty 필수
        """
        candidate = build_candidate(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=49_000_000.0,
            price_b=50_000_000.0,
            params=params,
        )
        
        intents = candidate_to_order_intents(
            candidate=candidate,
            base_qty=0.01,
            quote_amount=500_000.0,
            order_type=OrderType.MARKET,
        )
        
        assert len(intents) == 2
        
        buy_intent = intents[0]
        sell_intent = intents[1]
        
        # MARKET order 속성 확인
        assert buy_intent.order_type == OrderType.MARKET
        assert buy_intent.quote_amount == 500_000.0
        assert buy_intent.base_qty is None
        
        assert sell_intent.order_type == OrderType.MARKET
        assert sell_intent.base_qty == 0.01
        assert sell_intent.quote_amount is None
    
    def test_case6_limit_order_validation(self, params):
        """
        Case 6: LIMIT order validation
        
        Verify:
            - LIMIT order: limit_price 필수
            - Fallback to market price if limit_price not provided
        """
        candidate = build_candidate(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=49_000_000.0,
            price_b=50_000_000.0,
            params=params,
        )
        
        intents = candidate_to_order_intents(
            candidate=candidate,
            base_qty=0.01,
            quote_amount=500_000.0,
            order_type=OrderType.LIMIT,
            limit_price_a=49_100_000.0,  # Upbit limit price
            limit_price_b=50_100_000.0,  # Binance limit price
        )
        
        assert len(intents) == 2
        
        buy_intent = intents[0]
        sell_intent = intents[1]
        
        # LIMIT order 속성 확인
        assert buy_intent.order_type == OrderType.LIMIT
        assert buy_intent.limit_price == 49_100_000.0  # Upbit
        assert buy_intent.quote_amount == 500_000.0
        
        assert sell_intent.order_type == OrderType.LIMIT
        assert sell_intent.limit_price == 50_100_000.0  # Binance
        assert sell_intent.base_qty == 0.01
    
    def test_case7_invalid_price_no_intents(self, params):
        """
        Case 7: Invalid price → None candidate → 빈 리스트
        
        Scenario:
            - price_a = 0 (invalid)
            - Expected: None candidate → 빈 리스트
        """
        candidate = build_candidate(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=0.0,  # Invalid price
            price_b=50_000_000.0,
            params=params,
        )
        
        assert candidate is None
        
        # Convert (should be empty)
        intents = candidate_to_order_intents(
            candidate=candidate,
            base_qty=0.01,
            quote_amount=500_000.0,
        ) if candidate else []
        
        assert len(intents) == 0  # ✅ Invalid price → 빈 리스트
    
    def test_case8_build_and_convert_convenience(self, params):
        """
        Case 8: build_and_convert() 편의 함수
        
        Verify:
            - build_candidate() + candidate_to_order_intents() 통합
        """
        intents = build_and_convert(
            symbol="BTC/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=49_000_000.0,
            price_b=50_000_000.0,
            params=params,
            base_qty=0.01,
            quote_amount=500_000.0,
        )
        
        assert len(intents) == 2
        
        # BUY intent
        assert intents[0].exchange == "upbit"
        assert intents[0].side == OrderSide.BUY
        
        # SELL intent
        assert intents[1].exchange == "binance"
        assert intents[1].side == OrderSide.SELL
    
    def test_case9_build_and_convert_unprofitable(self, params):
        """
        Case 9: build_and_convert() with unprofitable candidate
        
        Expected: 빈 리스트
        """
        intents = build_and_convert(
            symbol="ETH/KRW",
            exchange_a="upbit",
            exchange_b="binance",
            price_a=3_000_000.0,
            price_b=3_009_000.0,  # unprofitable
            params=params,
            base_qty=0.1,
            quote_amount=300_000.0,
        )
        
        assert len(intents) == 0  # ✅ Unprofitable → 빈 리스트
