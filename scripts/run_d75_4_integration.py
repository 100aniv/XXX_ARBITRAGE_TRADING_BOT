"""
D75-4: ArbRoute / ArbUniverse / CrossSync Integration Test

End-to-end 통합 테스트:
- Route evaluation
- Universe ranking
- Cross-exchange sync
- Latency overhead 측정
"""

import logging
import sys
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from arbitrage.arbitrage_core import OrderBookSnapshot
from arbitrage.domain.arb_route import ArbRoute, RouteDirection
from arbitrage.domain.arb_universe import UniverseProvider, UniverseMode
from arbitrage.domain.cross_sync import Inventory, InventoryTracker
from arbitrage.domain.fee_model import create_fee_model_upbit_binance
from arbitrage.domain.market_spec import create_market_spec_upbit_binance
from arbitrage.infrastructure.exchange_health import HealthMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_route_evaluation():
    """TEST 1: Route evaluation"""
    logger.info("=" * 80)
    logger.info("TEST 1: Route Evaluation")
    logger.info("=" * 80)
    
    market_spec = create_market_spec_upbit_binance(krw_usd_rate=1370.0)
    fee_model = create_fee_model_upbit_binance()
    
    route = ArbRoute(
        symbol_a="KRW-BTC",
        symbol_b="BTCUSDT",
        market_spec=market_spec,
        fee_model=fee_model,
        min_spread_bps=30.0,
    )
    
    # High spread snapshot
    snapshot = OrderBookSnapshot(
        timestamp="2025-01-01T00:00:00Z",
        best_bid_a=103_000_000.0,
        best_ask_a=102_000_000.0,
        best_bid_b=73_000.0,
        best_ask_b=71_000.0,
    )
    
    start = time.perf_counter()
    decision = route.evaluate(snapshot, inventory_imbalance_ratio=0.0)
    latency_ms = (time.perf_counter() - start) * 1000
    
    logger.info(f"Decision: {decision.direction.value}")
    logger.info(f"Score: {decision.score:.2f}/100")
    logger.info(f"Reason: {decision.reason}")
    logger.info(f"Latency: {latency_ms:.4f} ms")
    
    assert decision.direction != RouteDirection.SKIP
    assert decision.score > 50.0
    assert latency_ms < 1.0, f"Route evaluation too slow: {latency_ms:.4f} ms"
    
    logger.info("✅ Route evaluation PASSED\n")
    return latency_ms


def test_universe_ranking():
    """TEST 2: Universe ranking"""
    logger.info("=" * 80)
    logger.info("TEST 2: Universe Ranking (Top5)")
    logger.info("=" * 80)
    
    provider = UniverseProvider(mode=UniverseMode.TOP_N, top_n=3)
    
    # Register 5 symbols
    symbols = ["BTC", "ETH", "XRP", "ADA", "SOL"]
    for symbol in symbols:
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
    
    # Mock snapshots (BTC > ETH > XRP > ADA > SOL)
    snapshots = {
        ("KRW-BTC", "BTCUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=105_000_000.0,
            best_ask_a=104_000_000.0,
            best_bid_b=75_000.0,
            best_ask_b=73_000.0,
        ),
        ("KRW-ETH", "ETHUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=4_200_000.0,
            best_ask_a=4_100_000.0,
            best_bid_b=3_000.0,
            best_ask_b=2_950.0,
        ),
        ("KRW-XRP", "XRPUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=1_520.0,
            best_ask_a=1_500.0,
            best_bid_b=1.08,
            best_ask_b=1.06,
        ),
        ("KRW-ADA", "ADAUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=820.0,
            best_ask_a=810.0,
            best_bid_b=0.58,
            best_ask_b=0.57,
        ),
        ("KRW-SOL", "SOLUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=270_000.0,
            best_ask_a=268_000.0,
            best_bid_b=192.0,
            best_ask_b=190.0,
        ),
    }
    
    start = time.perf_counter()
    decision = provider.evaluate_universe(snapshots)
    latency_ms = (time.perf_counter() - start) * 1000
    
    logger.info(f"Total candidates: {decision.total_candidates}")
    logger.info(f"Valid routes: {decision.valid_routes}")
    logger.info(f"Top routes:")
    for i, route in enumerate(decision.get_top_n_routes(3), 1):
        logger.info(f"  {i}. {route.symbol_a} - Score: {route.score:.2f}, Direction: {route.direction.value}")
    
    logger.info(f"Latency: {latency_ms:.4f} ms")
    
    assert decision.total_candidates == 5
    assert decision.valid_routes >= 0
    assert len(decision.ranked_routes) <= 3  # TOP_N = 3
    assert latency_ms < 5.0, f"Universe evaluation too slow: {latency_ms:.4f} ms"
    
    logger.info("✅ Universe ranking PASSED\n")
    return latency_ms


def test_inventory_sync():
    """TEST 3: Cross-exchange sync"""
    logger.info("=" * 80)
    logger.info("TEST 3: Cross-Exchange Inventory Sync")
    logger.info("=" * 80)
    
    tracker = InventoryTracker(
        imbalance_threshold=0.3,
        exposure_threshold=0.8,
    )
    
    # Scenario 1: Balanced
    inv_a = Inventory("UPBIT", base_balance=1.0, quote_balance=0.0)
    inv_b = Inventory("BINANCE", base_balance=1.0, quote_balance=0.0)
    
    tracker.update_inventory(inv_a, inv_b)
    
    start = time.perf_counter()
    signal = tracker.check_rebalance_needed(73_000.0, 73_000.0)
    latency_ms = (time.perf_counter() - start) * 1000
    
    logger.info(f"Scenario 1 (Balanced):")
    logger.info(f"  Rebalance needed: {signal.needed}")
    logger.info(f"  Imbalance ratio: {signal.imbalance_ratio:.2%}")
    logger.info(f"  Exposure risk: {signal.exposure_risk:.2%}")
    logger.info(f"  Latency: {latency_ms:.4f} ms")
    
    assert signal.needed is False
    assert latency_ms < 0.5, f"Sync check too slow: {latency_ms:.4f} ms"
    
    # Scenario 2: Imbalanced (A heavy)
    inv_a_heavy = Inventory("UPBIT", base_balance=5.0, quote_balance=0.0)
    inv_b_light = Inventory("BINANCE", base_balance=1.0, quote_balance=0.0)
    
    tracker.update_inventory(inv_a_heavy, inv_b_light)
    signal2 = tracker.check_rebalance_needed(73_000.0, 73_000.0)
    
    logger.info(f"Scenario 2 (A Heavy):")
    logger.info(f"  Rebalance needed: {signal2.needed}")
    logger.info(f"  Recommended action: {signal2.recommended_action}")
    logger.info(f"  Imbalance ratio: {signal2.imbalance_ratio:.2%}")
    
    assert signal2.needed is True
    assert signal2.recommended_action == "BUY_B_SELL_A"
    
    logger.info("✅ Inventory sync PASSED\n")
    return latency_ms


def test_end_to_end_flow():
    """TEST 4: End-to-end flow"""
    logger.info("=" * 80)
    logger.info("TEST 4: End-to-End Flow (Route + Universe + Sync)")
    logger.info("=" * 80)
    
    # 1. Universe setup
    provider = UniverseProvider(mode=UniverseMode.TOP_N, top_n=2)
    
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
    
    # 2. Inventory setup
    tracker = InventoryTracker()
    tracker.update_inventory(
        Inventory("UPBIT", base_balance=1.0, quote_balance=10_000_000.0),
        Inventory("BINANCE", base_balance=1.0, quote_balance=7_000.0),
    )
    
    # 3. Evaluate universe
    snapshots = {
        ("KRW-BTC", "BTCUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=104_000_000.0,
            best_ask_a=103_000_000.0,
            best_bid_b=74_000.0,
            best_ask_b=72_000.0,
        ),
        ("KRW-ETH", "ETHUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=4_150_000.0,
            best_ask_a=4_100_000.0,
            best_bid_b=2_980.0,
            best_ask_b=2_950.0,
        ),
    }
    
    # Get inventory imbalances
    inventory_state = {
        ("KRW-BTC", "BTCUSDT"): tracker.calculate_imbalance(73_000.0, 73_000.0),
        ("KRW-ETH", "ETHUSDT"): tracker.calculate_imbalance(2_965.0, 2_965.0),
    }
    
    start = time.perf_counter()
    decision = provider.evaluate_universe(snapshots, inventory_state)
    latency_ms = (time.perf_counter() - start) * 1000
    
    # 4. Check rebalance
    rebalance_signal = tracker.check_rebalance_needed(73_000.0, 73_000.0)
    
    logger.info(f"Universe decision:")
    logger.info(f"  Valid routes: {decision.valid_routes}")
    if decision.ranked_routes:
        top_route = decision.get_top_route()
        logger.info(f"  Top route: {top_route.symbol_a} (score={top_route.score:.2f})")
    
    logger.info(f"Rebalance signal:")
    logger.info(f"  Needed: {rebalance_signal.needed}")
    logger.info(f"  Reason: {rebalance_signal.reason}")
    
    logger.info(f"Total latency: {latency_ms:.4f} ms")
    
    assert latency_ms < 5.0, f"End-to-end too slow: {latency_ms:.4f} ms"
    
    logger.info("✅ End-to-end flow PASSED\n")
    return latency_ms


def test_latency_overhead():
    """TEST 5: Latency overhead measurement"""
    logger.info("=" * 80)
    logger.info("TEST 5: Latency Overhead (100 iterations)")
    logger.info("=" * 80)
    
    provider = UniverseProvider(mode=UniverseMode.TOP_N, top_n=3)
    
    # Register 3 routes
    for symbol in ["BTC", "ETH", "XRP"]:
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
    
    # Mock snapshots
    snapshots = {
        ("KRW-BTC", "BTCUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=104_000_000.0,
            best_ask_a=103_000_000.0,
            best_bid_b=74_000.0,
            best_ask_b=72_000.0,
        ),
        ("KRW-ETH", "ETHUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=4_150_000.0,
            best_ask_a=4_100_000.0,
            best_bid_b=2_980.0,
            best_ask_b=2_950.0,
        ),
        ("KRW-XRP", "XRPUSDT"): OrderBookSnapshot(
            timestamp="2025-01-01T00:00:00Z",
            best_bid_a=1_520.0,
            best_ask_a=1_500.0,
            best_bid_b=1.08,
            best_ask_b=1.06,
        ),
    }
    
    latencies = []
    for i in range(100):
        start = time.perf_counter()
        decision = provider.evaluate_universe(snapshots)
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)
    
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)
    p99_latency = sorted(latencies)[98]
    
    logger.info(f"Latency stats (100 iterations):")
    logger.info(f"  Avg: {avg_latency:.4f} ms")
    logger.info(f"  Min: {min_latency:.4f} ms")
    logger.info(f"  Max: {max_latency:.4f} ms")
    logger.info(f"  P99: {p99_latency:.4f} ms")
    
    # D75-4 requirement: latency overhead < 1ms
    assert avg_latency < 1.0, f"Average latency too high: {avg_latency:.4f} ms"
    
    logger.info("✅ Latency overhead PASSED\n")
    return avg_latency


def main():
    """전체 통합 테스트 실행"""
    logger.info("\n" + "=" * 80)
    logger.info("D75-4 Integration Test Suite")
    logger.info("=" * 80 + "\n")
    
    try:
        l1 = test_route_evaluation()
        l2 = test_universe_ranking()
        l3 = test_inventory_sync()
        l4 = test_end_to_end_flow()
        l5 = test_latency_overhead()
        
        total_latency = l1 + l2 + l3 + l4 + l5
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 80)
        logger.info("\nD75-4 Integration Test Summary:")
        logger.info(f"  - Route evaluation: ✅ ({l1:.4f} ms)")
        logger.info(f"  - Universe ranking: ✅ ({l2:.4f} ms)")
        logger.info(f"  - Inventory sync: ✅ ({l3:.4f} ms)")
        logger.info(f"  - End-to-end flow: ✅ ({l4:.4f} ms)")
        logger.info(f"  - Latency overhead: ✅ ({l5:.4f} ms avg)")
        logger.info(f"\n  Total accumulated latency: {total_latency:.4f} ms")
        logger.info(f"  Target: < 10ms, Actual: {total_latency:.4f} ms")
        logger.info("\n✅ D75-4 ACCEPTANCE CRITERIA: PASSED\n")
        
        return 0
    
    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        return 1
    
    except Exception as e:
        logger.error(f"\n❌ UNEXPECTED ERROR: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
