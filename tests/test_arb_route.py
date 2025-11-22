"""
D75-4: ArbRoute Unit Tests

ArbRoute, RouteScore, RouteDecision 검증
"""

import pytest
from arbitrage.arbitrage_core import OrderBookSnapshot
from arbitrage.domain.arb_route import (
    ArbRoute,
    ArbRouteDecision,
    RouteDirection,
    RouteScore,
)
from arbitrage.domain.fee_model import create_fee_model_upbit_binance
from arbitrage.domain.market_spec import create_market_spec_upbit_binance
from arbitrage.infrastructure.exchange_health import HealthMonitor


class TestRouteScore:
    """RouteScore 테스트"""
    
    def test_total_score_calculation(self):
        """총점 계산"""
        score = RouteScore(
            spread_score=80.0,
            health_score=90.0,
            fee_score=70.0,
            inventory_penalty=100.0,
        )
        
        # 0.4*80 + 0.3*90 + 0.2*70 + 0.1*100 = 32 + 27 + 14 + 10 = 83
        assert abs(score.total_score() - 83.0) < 0.1
    
    def test_penalty_impact(self):
        """Inventory penalty 영향"""
        score_no_penalty = RouteScore(
            spread_score=80.0,
            health_score=80.0,
            fee_score=80.0,
            inventory_penalty=100.0,
        )
        
        score_with_penalty = RouteScore(
            spread_score=80.0,
            health_score=80.0,
            fee_score=80.0,
            inventory_penalty=0.0,  # 100% penalty
        )
        
        # Penalty는 가중치 10%
        expected_diff = 100.0 * 0.1
        actual_diff = score_no_penalty.total_score() - score_with_penalty.total_score()
        assert abs(actual_diff - expected_diff) < 0.1


class TestArbRoute:
    """ArbRoute 테스트"""
    
    @pytest.fixture
    def market_spec(self):
        return create_market_spec_upbit_binance(krw_usd_rate=1370.0)
    
    @pytest.fixture
    def fee_model(self):
        return create_fee_model_upbit_binance()
    
    @pytest.fixture
    def arb_route(self, market_spec, fee_model):
        return ArbRoute(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            market_spec=market_spec,
            fee_model=fee_model,
            min_spread_bps=30.0,
            slippage_bps=5.0,
        )
    
    def test_initialization(self, arb_route):
        """초기화"""
        assert arb_route.symbol_a == "KRW-BTC"
        assert arb_route.symbol_b == "BTCUSDT"
        assert arb_route.min_spread_bps == 30.0
    
    def test_spread_calculation_a_to_b(self, arb_route):
        """A → B spread 계산 (Buy A, Sell B)"""
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=100_000_000.0,  # KRW
            best_ask_a=99_000_000.0,   # KRW
            best_bid_b=73_000.0,  # USDT
            best_ask_b=72_000.0,  # USDT
        )
        
        # ask_a_norm = 99_000_000 / 1370 = 72,262 USDT
        # bid_b = 73,000 USDT
        # spread = (73000 - 72262) / 72262 * 10000 = 102 bps
        # spread - fee - slippage = 102 - 15 - 5 = 82 bps
        spread = arb_route._calculate_spread_a_to_b(snapshot)
        assert 80.0 < spread < 84.0  # Approx 82 bps
    
    def test_spread_calculation_b_to_a(self, arb_route):
        """B → A spread 계산 (Buy B, Sell A)"""
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=101_000_000.0,  # KRW
            best_ask_a=100_000_000.0,  # KRW
            best_bid_b=73_000.0,  # USDT
            best_ask_b=72_500.0,  # USDT
        )
        
        # bid_a_norm = 101_000_000 / 1370 = 73,723 USDT
        # ask_b = 72,500 USDT
        # spread = (73723 - 72500) / 72500 * 10000 = 169 bps
        # spread - fee - slippage = 169 - 15 - 5 = 149 bps
        spread = arb_route._calculate_spread_b_to_a(snapshot)
        assert 147.0 < spread < 151.0  # Approx 149 bps
    
    def test_evaluate_skip_low_spread(self, arb_route):
        """Spread 낮으면 SKIP"""
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=100_000_000.0,
            best_ask_a=100_000_000.0,
            best_bid_b=73_000.0,
            best_ask_b=73_000.0,
        )
        
        decision = arb_route.evaluate(snapshot)
        assert decision.direction == RouteDirection.SKIP
        assert decision.score == 0.0
    
    def test_evaluate_long_b_short_a(self, arb_route):
        """LONG_B_SHORT_A direction"""
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=100_000_000.0,  # KRW
            best_ask_a=99_000_000.0,   # KRW
            best_bid_b=74_000.0,  # USDT (A가 높음)
            best_ask_b=73_000.0,  # USDT
        )
        
        decision = arb_route.evaluate(snapshot)
        assert decision.direction == RouteDirection.LONG_B_SHORT_A
        assert decision.score > 0.0
    
    def test_evaluate_long_a_short_b(self, arb_route):
        """LONG_A_SHORT_B direction"""
        snapshot = OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=102_000_000.0,  # KRW (B가 높음)
            best_ask_a=101_000_000.0,  # KRW
            best_bid_b=73_000.0,  # USDT
            best_ask_b=72_000.0,  # USDT
        )
        
        decision = arb_route.evaluate(snapshot)
        assert decision.direction == RouteDirection.LONG_A_SHORT_B
        assert decision.score > 0.0
    
    def test_health_score_with_monitors(self, market_spec, fee_model):
        """Health monitor가 있을 때 health score"""
        health_a = HealthMonitor("UPBIT")
        health_b = HealthMonitor("BINANCE")
        
        # Low latency
        for _ in range(10):
            health_a.update_latency(30.0)
            health_b.update_latency(40.0)
        
        route = ArbRoute(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            market_spec=market_spec,
            fee_model=fee_model,
            health_monitor_a=health_a,
            health_monitor_b=health_b,
        )
        
        health_score = route._calculate_health_score()
        
        # avg_latency = 35ms
        # penalty = 35 * 0.1 = 3.5
        # score = 100 - 3.5 = 96.5
        assert 95.0 < health_score < 97.0
    
    def test_inventory_penalty_same_direction(self, arb_route):
        """Inventory 방향과 trade 방향이 같으면 penalty"""
        # A가 이미 많음 (imbalance = 0.5)
        # Direction = LONG_A_SHORT_B (A 더 증가)
        penalty = arb_route._calculate_inventory_penalty(
            inventory_imbalance_ratio=0.5,
            direction=RouteDirection.LONG_A_SHORT_B,
        )
        
        # penalty = 0.5 * 100 = 50점 감점
        # score = 100 - 50 = 50
        assert 48.0 < penalty < 52.0
    
    def test_inventory_penalty_opposite_direction(self, arb_route):
        """Inventory 방향과 trade 방향이 반대면 no penalty"""
        # A가 많음 (imbalance = 0.5)
        # Direction = LONG_B_SHORT_A (A 감소, rebalance)
        penalty = arb_route._calculate_inventory_penalty(
            inventory_imbalance_ratio=0.5,
            direction=RouteDirection.LONG_B_SHORT_A,
        )
        
        # No penalty
        assert penalty == 100.0
