"""
D205-14-3: AutoTuner Metrics Diversity Test

Synthetic 데이터로 파라미터 변경 시 metrics가 달라지는지 검증
(실제 REST ticker 데이터는 spread=0이므로 synthetic으로 대체)
"""

import json
import pytest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.execution_quality.sweep import ParameterSweep
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure


def create_synthetic_market_file(spread_bps_list, temp_dir):
    """
    다양한 spread를 가진 synthetic market.ndjson 생성
    
    Args:
        spread_bps_list: spread 값 리스트 (bps)
        temp_dir: 임시 디렉토리
        
    Returns:
        market.ndjson 경로
    """
    market_path = temp_dir / "market.ndjson"
    
    with open(market_path, "w", encoding="utf-8") as f:
        for i, spread_bps in enumerate(spread_bps_list):
            # Base price: 100,000,000 KRW
            base_price = 100_000_000
            
            # Calculate bid/ask with spread
            # spread_bps = (ask - bid) / bid * 10000
            # ask = bid * (1 + spread_bps / 10000)
            upbit_bid = base_price
            upbit_ask = upbit_bid * (1 + spread_bps / 10000)
            
            # Binance (USDT) - slightly different to create arbitrage opportunity
            binance_bid = base_price / 1450.0  # KRW to USDT
            binance_ask = binance_bid * 1.001  # Small spread
            
            tick = {
                "timestamp": f"2026-01-07T09:00:{i:02d}.000000",
                "symbol": "BTC/KRW",
                "upbit_bid": upbit_bid,
                "upbit_ask": upbit_ask,
                "upbit_bid_size": 1.0,
                "upbit_ask_size": 1.0,
                "binance_bid": binance_bid,
                "binance_ask": binance_ask,
                "binance_bid_size": 1.0,
                "binance_ask_size": 1.0,
                "upbit_quote": "KRW",
                "binance_quote": "USDT",
            }
            
            f.write(json.dumps(tick, ensure_ascii=False) + "\n")
    
    return market_path


def test_autotune_metrics_diversity():
    """
    파라미터 변경 시 metrics가 달라지는지 검증
    
    AC-3: leaderboard Top10에서 mean_net_edge_bps가 최소 2종 이상
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Synthetic market data with varied spreads (50 ticks)
        # 다양한 spread: 10, 20, 30, 40, 50 bps
        spread_bps_list = [10, 20, 30, 40, 50] * 10  # 50 ticks
        market_path = create_synthetic_market_file(spread_bps_list, temp_path)
        
        # Output directory
        output_dir = temp_path / "autotune_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Break-even params
        fee_a = FeeStructure("upbit", maker_fee_bps=5.0, taker_fee_bps=25.0)
        fee_b = FeeStructure("binance", maker_fee_bps=10.0, taker_fee_bps=25.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        break_even_params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            buffer_bps=5.0,
        )
        
        # Parameter grid (small for testing)
        param_grid = {
            "slippage_alpha": [5.0, 10.0],
            "partial_fill_penalty_bps": [10.0, 20.0],
            "max_safe_ratio": [0.2, 0.3],
            "min_spread_bps": [20.0, 30.0],
        }
        
        # Run sweep
        sweep = ParameterSweep(
            input_path=market_path,
            output_dir=output_dir,
            break_even_params=break_even_params,
            param_grid=param_grid,
        )
        
        result = sweep.run()
        
        # Verify sweep completed
        assert result["status"] == "PASS"
        assert result["combinations_total"] == 16  # 2*2*2*2
        
        # Load leaderboard
        leaderboard_path = output_dir / "leaderboard.json"
        assert leaderboard_path.exists()
        
        with open(leaderboard_path, "r", encoding="utf-8") as f:
            leaderboard = json.load(f)
        
        # Verify leaderboard structure
        assert len(leaderboard) == 10
        
        # Extract unique mean_net_edge_bps values
        unique_mean_net_edge_bps = set()
        for entry in leaderboard:
            unique_mean_net_edge_bps.add(entry["metrics"]["mean_net_edge_bps"])
        
        # AC-3: 최소 2종 이상의 metrics
        assert len(unique_mean_net_edge_bps) >= 2, \
            f"Expected >= 2 unique mean_net_edge_bps, got {len(unique_mean_net_edge_bps)}: {unique_mean_net_edge_bps}"
        
        print(f"\n✅ Diversity Check PASS: {len(unique_mean_net_edge_bps)} unique mean_net_edge_bps values")
        print(f"   Values: {sorted(unique_mean_net_edge_bps)}")


def test_market_stats_calculation():
    """
    market_stats.json 계산 검증
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create synthetic market with known spreads
        spread_bps_list = [10, 20, 30]  # 3 ticks
        market_path = create_synthetic_market_file(spread_bps_list, temp_path)
        
        # Calculate stats manually
        from scripts.analyze_market_diversity import analyze_market_file
        
        result = analyze_market_file(market_path)
        
        assert result["status"] == "PASS"
        assert result["ticks_count"] == 3
        assert result["unique_lines_count"] == 3
        assert result["unique_ratio"] == 1.0
        
        # Spread stats
        spread_stats = result["spread_bps_stats"]
        assert spread_stats["min"] == 10.0
        assert spread_stats["max"] == 30.0
        assert spread_stats["median"] == 20.0
        
        print(f"\n✅ Stats Calculation PASS")
        print(f"   Spread: min={spread_stats['min']}, median={spread_stats['median']}, max={spread_stats['max']}")
