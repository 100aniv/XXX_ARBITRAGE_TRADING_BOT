"""
D205-6: ExecutionQuality v1 테스트

목표:
- SimpleExecutionQualityModel 단조성 검증
- MarketTick size 필드 호환성 검증
- DecisionRecord execution quality 필드 검증
- net_edge_after_exec_bps 계산 정확성

네트워크 호출 없음 (단위 테스트)
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.execution_quality.model_v1 import SimpleExecutionQualityModel
from arbitrage.v2.execution_quality.schemas import ExecutionCostBreakdown
from arbitrage.v2.replay.schemas import MarketTick, DecisionRecord


class TestSimpleExecutionQualityModel:
    """SimpleExecutionQualityModel 테스트"""
    
    def test_initialization(self):
        """모델 초기화 검증"""
        model = SimpleExecutionQualityModel(
            default_spread_cost_bps=25.0,
            slippage_alpha=10.0,
            partial_fill_penalty_bps=20.0,
            max_safe_ratio=0.3,
        )
        
        assert model.default_spread_cost_bps == 25.0
        assert model.slippage_alpha == 10.0
        assert model.partial_fill_penalty_bps == 20.0
        assert model.max_safe_ratio == 0.3
    
    def test_compute_execution_cost_no_size(self):
        """Size 정보 없을 때 보수적 페널티 적용 검증"""
        model = SimpleExecutionQualityModel()
        
        result = model.compute_execution_cost(
            edge_bps=100.0,
            notional=100000.0,
            upbit_bid_size=None,
            upbit_ask_size=None,
            binance_bid_size=None,
            binance_ask_size=None,
        )
        
        assert isinstance(result, ExecutionCostBreakdown)
        assert result.spread_cost_bps == 25.0  # 기본값
        assert result.slippage_cost_bps == 20.0  # 보수적 페널티
        assert result.partial_fill_risk_bps == 20.0  # 페널티
        assert result.total_exec_cost_bps == 65.0  # 25 + 20 + 20
        assert result.net_edge_after_exec_bps == 35.0  # 100 - 65
        assert result.exec_model_version == "v1"
    
    def test_compute_execution_cost_with_size(self):
        """Size 정보 있을 때 슬리피지 계산 검증"""
        model = SimpleExecutionQualityModel(slippage_alpha=10.0, max_safe_ratio=0.3)
        
        result = model.compute_execution_cost(
            edge_bps=100.0,
            notional=200000.0,  # 20만원 (size ratio = 0.2 <= 0.3 → no penalty)
            upbit_bid_size=1000000.0,  # 100만원 (충분)
            upbit_ask_size=1000000.0,
            binance_bid_size=1000000.0,
            binance_ask_size=1000000.0,
        )
        
        # notional / avg_size = 200000 / 1000000 = 0.2
        # slippage_cost = 10.0 * 0.2 = 2.0 bps
        assert result.slippage_cost_bps == pytest.approx(2.0, abs=0.1)
        
        # size ratio = 0.2 <= max_safe_ratio(0.3) → no partial fill penalty
        assert result.partial_fill_risk_bps == 0.0
        
        # total = 25 (spread) + 2 (slippage) + 0 (partial) = 27
        assert result.total_exec_cost_bps == pytest.approx(27.0, abs=0.1)
        
        # net edge = 100 - 27 = 73
        assert result.net_edge_after_exec_bps == pytest.approx(73.0, abs=0.1)
    
    def test_slippage_monotonicity(self):
        """슬리피지 단조성 검증 (notional 증가 → cost 비감소)"""
        model = SimpleExecutionQualityModel(slippage_alpha=10.0)
        
        notionals = [50000.0, 100000.0, 200000.0, 500000.0]
        costs = []
        
        for notional in notionals:
            result = model.compute_execution_cost(
                edge_bps=100.0,
                notional=notional,
                upbit_bid_size=1000000.0,
                upbit_ask_size=1000000.0,
                binance_bid_size=1000000.0,
                binance_ask_size=1000000.0,
            )
            costs.append(result.slippage_cost_bps)
        
        # 단조 비감소 검증
        for i in range(len(costs) - 1):
            assert costs[i] <= costs[i + 1], f"Slippage cost decreased: {costs[i]} > {costs[i + 1]}"
    
    def test_partial_fill_penalty_threshold(self):
        """부분체결 페널티 임계값 검증 (큰 주문에 페널티)"""
        model = SimpleExecutionQualityModel(
            max_safe_ratio=0.3,
            partial_fill_penalty_bps=20.0,
        )
        
        # Case 1: notional / avg_size = 0.2 <= 0.3 → 안전 (페널티 없음)
        result1 = model.compute_execution_cost(
            edge_bps=100.0,
            notional=200000.0,
            upbit_bid_size=1000000.0,
            upbit_ask_size=1000000.0,
            binance_bid_size=1000000.0,
            binance_ask_size=1000000.0,
        )
        assert result1.partial_fill_risk_bps == 0.0
        
        # Case 2: notional / avg_size = 0.4 > 0.3 → 위험 (페널티 적용)
        result2 = model.compute_execution_cost(
            edge_bps=100.0,
            notional=400000.0,
            upbit_bid_size=1000000.0,
            upbit_ask_size=1000000.0,
            binance_bid_size=1000000.0,
            binance_ask_size=1000000.0,
        )
        assert result2.partial_fill_risk_bps == pytest.approx(5.0)


    def test_large_order_penalty_inverse_logic(self):
        """큰 주문에 페널티 검증 (Inverse Logic Check)"""
        model = SimpleExecutionQualityModel(max_safe_ratio=0.3, partial_fill_penalty_bps=20.0)
        
        # Small order (safe): notional=100k, avg_size=1000k → ratio=0.1
        result_small = model.compute_execution_cost(
            edge_bps=100.0,
            notional=100000.0,
            upbit_bid_size=1000000.0,
            upbit_ask_size=1000000.0,
            binance_bid_size=1000000.0,
            binance_ask_size=1000000.0,
        )
        
        # Large order (risky): notional=500k, avg_size=1000k → ratio=0.5
        result_large = model.compute_execution_cost(
            edge_bps=100.0,
            notional=500000.0,
            upbit_bid_size=1000000.0,
            upbit_ask_size=1000000.0,
            binance_bid_size=1000000.0,
            binance_ask_size=1000000.0,
        )
        
        # Small order: no penalty
        assert result_small.partial_fill_risk_bps == 0.0
        
        # Large order: penalty applied
        assert result_large.partial_fill_risk_bps == pytest.approx(8.0)
        
        # Large order should have higher total cost
        assert result_large.total_exec_cost_bps > result_small.total_exec_cost_bps


class TestMarketTickSizeCompatibility:
    """MarketTick size 필드 호환성 테스트"""
    
    def test_market_tick_without_size(self):
        """Size 없는 기존 MarketTick 호환성 검증"""
        tick = MarketTick(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            upbit_bid=100000.0,
            upbit_ask=100100.0,
            binance_bid=99900.0,
            binance_ask=100000.0,
        )
        
        assert tick.upbit_bid_size is None
        assert tick.upbit_ask_size is None
        assert tick.binance_bid_size is None
        assert tick.binance_ask_size is None
    
    def test_market_tick_with_size(self):
        """Size 있는 MarketTick 생성 검증"""
        tick = MarketTick(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            upbit_bid=100000.0,
            upbit_ask=100100.0,
            binance_bid=99900.0,
            binance_ask=100000.0,
            upbit_bid_size=1000000.0,
            upbit_ask_size=1000000.0,
            binance_bid_size=1000000.0,
            binance_ask_size=1000000.0,
        )
        
        assert tick.upbit_bid_size == 1000000.0
        assert tick.upbit_ask_size == 1000000.0
        assert tick.binance_bid_size == 1000000.0
        assert tick.binance_ask_size == 1000000.0
    
    def test_market_tick_from_dict_compatibility(self):
        """from_dict 하위 호환성 검증 (size 없는 dict)"""
        data = {
            "timestamp": "2025-12-31T00:00:00",
            "symbol": "BTC/KRW",
            "upbit_bid": 100000.0,
            "upbit_ask": 100100.0,
            "binance_bid": 99900.0,
            "binance_ask": 100000.0,
        }
        
        tick = MarketTick.from_dict(data)
        
        assert tick.upbit_bid == 100000.0
        assert tick.upbit_bid_size is None  # 기본값


class TestDecisionRecordExecutionQuality:
    """DecisionRecord execution quality 필드 테스트"""
    
    def test_decision_record_without_exec_quality(self):
        """Execution quality 없는 기존 DecisionRecord 호환성"""
        decision = DecisionRecord(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            spread_bps=100.0,
            break_even_bps=50.0,
            edge_bps=50.0,
            profitable=True,
            gate_reasons=[],
            latency_ms=10.0,
        )
        
        assert decision.exec_cost_bps is None
        assert decision.net_edge_after_exec_bps is None
        assert decision.exec_model_version is None
    
    def test_decision_record_with_exec_quality(self):
        """Execution quality 포함 DecisionRecord 생성"""
        decision = DecisionRecord(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            spread_bps=100.0,
            break_even_bps=50.0,
            edge_bps=50.0,
            profitable=True,
            gate_reasons=[],
            latency_ms=10.0,
            exec_cost_bps=26.0,
            net_edge_after_exec_bps=24.0,
            exec_model_version="v1",
        )
        
        assert decision.exec_cost_bps == 26.0
        assert decision.net_edge_after_exec_bps == 24.0
        assert decision.exec_model_version == "v1"
    
    def test_net_edge_calculation(self):
        """net_edge_after_exec_bps = edge_bps - exec_cost_bps 검증"""
        edge_bps = 100.0
        exec_cost_bps = 35.0
        
        decision = DecisionRecord(
            timestamp="2025-12-31T00:00:00",
            symbol="BTC/KRW",
            spread_bps=150.0,
            break_even_bps=50.0,
            edge_bps=edge_bps,
            profitable=True,
            gate_reasons=[],
            latency_ms=10.0,
            exec_cost_bps=exec_cost_bps,
            net_edge_after_exec_bps=edge_bps - exec_cost_bps,
            exec_model_version="v1",
        )
        
        assert decision.net_edge_after_exec_bps == 65.0
