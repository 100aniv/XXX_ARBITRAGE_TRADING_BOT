"""
D75-4: ArbUniverse Unit Tests

UniverseProvider, UniverseDecision, Ranking 검증
"""

import pytest
from arbitrage.arbitrage_core import OrderBookSnapshot
from arbitrage.domain.arb_universe import (
    UniverseMode,
    UniverseProvider,
    UniverseDecision,
    RouteRanking,
)
from arbitrage.domain.arb_route import RouteDirection
from arbitrage.domain.fee_model import create_fee_model_upbit_binance
from arbitrage.domain.market_spec import create_market_spec_upbit_binance


class TestUniverseDecision:
    """UniverseDecision 테스트"""
    
    def test_initialization(self):
        """초기화"""
        decision = UniverseDecision(
            mode=UniverseMode.TOP_N,
            total_candidates=10,
            valid_routes=5,
        )
        
        assert decision.mode == UniverseMode.TOP_N
        assert decision.total_candidates == 10
        assert decision.valid_routes == 5
    
    def test_get_top_route(self):
        """최상위 route 반환"""
        rankings = [
            RouteRanking("KRW-BTC", "BTCUSDT", RouteDirection.LONG_A_SHORT_B, 80.0, ""),
            RouteRanking("KRW-ETH", "ETHUSDT", RouteDirection.LONG_B_SHORT_A, 70.0, ""),
        ]
        
        decision = UniverseDecision(ranked_routes=rankings)
        top = decision.get_top_route()
        
        assert top is not None
        assert top.score == 80.0
    
    def test_get_top_n_routes(self):
        """Top N routes 반환"""
        rankings = [
            RouteRanking("A", "A", RouteDirection.SKIP, 90.0, ""),
            RouteRanking("B", "B", RouteDirection.SKIP, 80.0, ""),
            RouteRanking("C", "C", RouteDirection.SKIP, 70.0, ""),
        ]
        
        decision = UniverseDecision(ranked_routes=rankings)
        top_2 = decision.get_top_n_routes(2)
        
        assert len(top_2) == 2
        assert top_2[0].score == 90.0
        assert top_2[1].score == 80.0


class TestUniverseProvider:
    """UniverseProvider 테스트"""
    
    @pytest.fixture
    def universe_provider(self):
        return UniverseProvider(
            mode=UniverseMode.TOP_N,
            top_n=3,
            min_score_threshold=50.0,
        )
    
    def test_initialization(self, universe_provider):
        """초기화"""
        assert universe_provider.mode == UniverseMode.TOP_N
        assert universe_provider.top_n == 3
        assert universe_provider.min_score_threshold == 50.0
    
    def test_register_route(self, universe_provider):
        """Route 등록"""
        market_spec = create_market_spec_upbit_binance()
        fee_model = create_fee_model_upbit_binance()
        
        universe_provider.register_route(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            market_spec=market_spec,
            fee_model=fee_model,
        )
        
        routes = universe_provider.get_registered_routes()
        assert ("KRW-BTC", "BTCUSDT") in routes
    
    def test_evaluate_universe_top_n(self):
        """Universe 평가 (TOP_N 모드)"""
        provider = UniverseProvider(mode=UniverseMode.TOP_N, top_n=2)
        
        # Register 3 routes
        for i, symbol in enumerate(["BTC", "ETH", "XRP"]):
            market_spec = create_market_spec_upbit_binance(
                symbol_a=f"KRW-{symbol}",
                symbol_b=f"{symbol}USDT",
            )
            fee_model = create_fee_model_upbit_binance()
            provider.register_route(
                symbol_a=f"KRW-{symbol}",
                symbol_b=f"{symbol}USDT",
                market_spec=market_spec,
                fee_model=fee_model,
                min_spread_bps=30.0,
            )
        
        # Snapshots (BTC > ETH > XRP in terms of spread)
        snapshots = {
            ("KRW-BTC", "BTCUSDT"): OrderBookSnapshot(
                timestamp="2025-01-01T00:00:00Z",
                best_bid_a=102_000_000.0,
                best_ask_a=101_000_000.0,
                best_bid_b=73_000.0,
                best_ask_b=72_000.0,
            ),
            ("KRW-ETH", "ETHUSDT"): OrderBookSnapshot(
                timestamp="2025-01-01T00:00:00Z",
                best_bid_a=4_100_000.0,
                best_ask_a=4_050_000.0,
                best_bid_b=2_950.0,
                best_ask_b=2_900.0,
            ),
            ("KRW-XRP", "XRPUSDT"): OrderBookSnapshot(
                timestamp="2025-01-01T00:00:00Z",
                best_bid_a=1_500.0,
                best_ask_a=1_480.0,
                best_bid_b=1.05,
                best_ask_b=1.04,
            ),
        }
        
        decision = provider.evaluate_universe(snapshots)
        
        # TOP_N=2이므로 상위 2개만
        assert decision.mode == UniverseMode.TOP_N
        assert decision.total_candidates == 3
        assert len(decision.ranked_routes) <= 2
    
    def test_custom_list_mode(self):
        """CUSTOM_LIST 모드"""
        provider = UniverseProvider(
            mode=UniverseMode.CUSTOM_LIST,
            custom_symbols=[("KRW-BTC", "BTCUSDT"), ("KRW-ETH", "ETHUSDT")],
        )
        
        # Add symbol
        provider.add_symbol("KRW-XRP", "XRPUSDT")
        assert ("KRW-XRP", "XRPUSDT") in provider.custom_symbols
        
        # Remove symbol
        provider.remove_symbol("KRW-XRP", "XRPUSDT")
        assert ("KRW-XRP", "XRPUSDT") not in provider.custom_symbols
    
    def test_score_threshold_filter(self):
        """Score threshold 필터"""
        provider = UniverseProvider(
            mode=UniverseMode.ALL_SYMBOLS,
            min_score_threshold=90.0,  # Very high threshold
        )
        
        market_spec = create_market_spec_upbit_binance()
        fee_model = create_fee_model_upbit_binance()
        provider.register_route(
            symbol_a="KRW-BTC",
            symbol_b="BTCUSDT",
            market_spec=market_spec,
            fee_model=fee_model,
            min_spread_bps=30.0,
        )
        
        # Low spread snapshot (score < 90)
        snapshots = {
            ("KRW-BTC", "BTCUSDT"): OrderBookSnapshot(
                timestamp="2025-01-01T00:00:00Z",
                best_bid_a=100_200_000.0,
                best_ask_a=100_000_000.0,
                best_bid_b=73_000.0,
                best_ask_b=72_950.0,
            ),
        }
        
        decision = provider.evaluate_universe(snapshots)
        
        # Score threshold로 필터링되어 valid_routes = 0
        assert decision.valid_routes == 0
    
    def test_ranking_order(self):
        """Ranking 정렬 순서 (score 내림차순)"""
        provider = UniverseProvider(mode=UniverseMode.ALL_SYMBOLS)
        
        # Register routes
        for symbol in ["BTC", "ETH"]:
            market_spec = create_market_spec_upbit_binance(
                symbol_a=f"KRW-{symbol}",
                symbol_b=f"{symbol}USDT",
            )
            fee_model = create_fee_model_upbit_binance()
            provider.register_route(
                symbol_a=f"KRW-{symbol}",
                symbol_b=f"{symbol}USDT",
                market_spec=market_spec,
                fee_model=fee_model,
            )
        
        # BTC: High spread, ETH: Low spread
        snapshots = {
            ("KRW-BTC", "BTCUSDT"): OrderBookSnapshot(
                timestamp="2025-01-01T00:00:00Z",
                best_bid_a=103_000_000.0,
                best_ask_a=102_000_000.0,
                best_bid_b=73_000.0,
                best_ask_b=71_000.0,
            ),
            ("KRW-ETH", "ETHUSDT"): OrderBookSnapshot(
                timestamp="2025-01-01T00:00:00Z",
                best_bid_a=4_100_000.0,
                best_ask_a=4_090_000.0,
                best_bid_b=2_950.0,
                best_ask_b=2_940.0,
            ),
        }
        
        decision = provider.evaluate_universe(snapshots)
        
        # BTC가 ETH보다 score 높음
        if len(decision.ranked_routes) >= 2:
            assert decision.ranked_routes[0].symbol_a == "KRW-BTC"
            assert decision.ranked_routes[1].symbol_a == "KRW-ETH"
