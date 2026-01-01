"""
D205-4: Reality Wiring 테스트

목표:
- DecisionTrace 기록 검증
- Latency 계산 검증
- Edge 분포 계산 검증
- 가짜 낙관 경고 검증

네트워크 호출 없음 (Mock 기반)
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.v2.core.decision_trace import DecisionTrace, LatencyMetrics
from arbitrage.v2.opportunity.detector import OpportunityDirection
from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.v2.domain.break_even import BreakEvenParams


class TestDecisionTrace:
    """DecisionTrace 테스트"""
    
    def test_initialization(self):
        """DecisionTrace 초기화 검증"""
        trace = DecisionTrace()
        
        assert trace.evaluated_ticks_total == 0
        assert trace.opportunities_total == 0
        assert trace.gate_spread_insufficient_count == 0
        assert trace.gate_liquidity_insufficient_count == 0
        assert trace.gate_cooldown_count == 0
        assert trace.gate_ratelimit_count == 0
        assert trace.is_optimistic_warning is False
        assert isinstance(trace.latency_metrics, LatencyMetrics)
    
    def test_record_tick_evaluated(self):
        """Tick 평가 기록 검증"""
        trace = DecisionTrace()
        
        trace.record_tick_evaluated()
        trace.record_tick_evaluated()
        trace.record_tick_evaluated()
        
        assert trace.evaluated_ticks_total == 3
    
    def test_record_opportunity_edge_distribution(self):
        """기회 기록 및 edge 분포 검증"""
        trace = DecisionTrace()
        
        # negative edge
        trace.record_opportunity(-5.0)
        assert trace.opportunities_total == 1
        assert trace.edge_after_cost_distribution["negative"] == 1
        
        # 0~10 edge
        trace.record_opportunity(5.0)
        assert trace.opportunities_total == 2
        assert trace.edge_after_cost_distribution["zero_to_10"] == 1
        
        # 10~50 edge
        trace.record_opportunity(30.0)
        assert trace.opportunities_total == 3
        assert trace.edge_after_cost_distribution["10_to_50"] == 1
        
        # 50+ edge
        trace.record_opportunity(100.0)
        assert trace.opportunities_total == 4
        assert trace.edge_after_cost_distribution["50_plus"] == 1
    
    def test_record_gate_spread_insufficient(self):
        """Spread 부족 게이트 기록 검증"""
        trace = DecisionTrace()
        
        trace.record_gate_spread_insufficient()
        trace.record_gate_spread_insufficient()
        
        assert trace.gate_spread_insufficient_count == 2
    
    def test_record_gate_liquidity_insufficient(self):
        """유동성 부족 게이트 기록 검증"""
        trace = DecisionTrace()
        
        trace.record_gate_liquidity_insufficient()
        
        assert trace.gate_liquidity_insufficient_count == 1
    
    def test_record_gate_cooldown(self):
        """쿨다운 게이트 기록 검증"""
        trace = DecisionTrace()
        
        trace.record_gate_cooldown()
        trace.record_gate_cooldown()
        trace.record_gate_cooldown()
        
        assert trace.gate_cooldown_count == 3
    
    def test_record_gate_ratelimit(self):
        """Rate limit 게이트 기록 검증"""
        trace = DecisionTrace()
        
        trace.record_gate_ratelimit()
        
        assert trace.gate_ratelimit_count == 1
    
    def test_set_optimistic_warning(self):
        """가짜 낙관 경고 설정 검증"""
        trace = DecisionTrace()
        
        assert trace.is_optimistic_warning is False
        
        trace.set_optimistic_warning(True)
        assert trace.is_optimistic_warning is True
        
        trace.set_optimistic_warning(False)
        assert trace.is_optimistic_warning is False
    
    def test_to_dict(self):
        """딕셔너리 변환 검증"""
        trace = DecisionTrace()
        
        trace.record_tick_evaluated()
        trace.record_opportunity(50.0)
        trace.record_gate_spread_insufficient()
        trace.set_optimistic_warning(True)
        
        result = trace.to_dict()
        
        assert result["evaluated_ticks_total"] == 1
        assert result["opportunities_total"] == 1
        assert result["gate_breakdown"]["spread_insufficient"] == 1
        assert result["is_optimistic_warning"] is True
        assert "latency_metrics" in result


class TestLatencyMetrics:
    """LatencyMetrics 테스트"""
    
    def test_initialization(self):
        """LatencyMetrics 초기화 검증"""
        metrics = LatencyMetrics()
        
        assert metrics.tick_to_decision_ms == []
        assert metrics.decision_to_intent_ms == []
        assert metrics.tick_to_intent_ms == []
    
    def test_add_tick_to_decision(self):
        """Tick→Decision 레이턴시 추가 검증"""
        metrics = LatencyMetrics()
        
        metrics.add_tick_to_decision(10.5)
        metrics.add_tick_to_decision(20.3)
        
        assert len(metrics.tick_to_decision_ms) == 2
        assert metrics.tick_to_decision_ms[0] == 10.5
        assert metrics.tick_to_decision_ms[1] == 20.3
    
    def test_add_decision_to_intent(self):
        """Decision→Intent 레이턴시 추가 검증"""
        metrics = LatencyMetrics()
        
        metrics.add_decision_to_intent(5.0)
        
        assert len(metrics.decision_to_intent_ms) == 1
        assert metrics.decision_to_intent_ms[0] == 5.0
    
    def test_add_tick_to_intent(self):
        """Tick→Intent 레이턴시 추가 검증"""
        metrics = LatencyMetrics()
        
        metrics.add_tick_to_intent(15.5)
        
        assert len(metrics.tick_to_intent_ms) == 1
        assert metrics.tick_to_intent_ms[0] == 15.5
    
    def test_percentile_calculation(self):
        """퍼센타일 계산 검증"""
        metrics = LatencyMetrics()
        
        # 빈 리스트
        assert metrics.percentile([], 50) == 0.0
        
        # 단일 값
        assert metrics.percentile([100.0], 50) == 100.0
        
        # 정렬된 값들
        data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        p50 = metrics.percentile(data, 50)
        p95 = metrics.percentile(data, 95)
        
        # 50% ~ 60% 사이
        assert 50.0 <= p50 <= 60.0
        # 95% ~ 100% 사이
        assert 95.0 <= p95 <= 100.0
    
    def test_to_dict(self):
        """딕셔너리 변환 검증"""
        metrics = LatencyMetrics()
        
        metrics.add_tick_to_decision(10.0)
        metrics.add_tick_to_decision(20.0)
        metrics.add_decision_to_intent(5.0)
        metrics.add_tick_to_intent(15.0)
        
        result = metrics.to_dict()
        
        assert "tick_to_decision_ms" in result
        assert "decision_to_intent_ms" in result
        assert "tick_to_intent_ms" in result
        
        # 각 항목에 p50, p95, p99, max, count 포함
        assert "p50" in result["tick_to_decision_ms"]
        assert "p95" in result["tick_to_decision_ms"]
        assert "count" in result["tick_to_decision_ms"]
        assert result["tick_to_decision_ms"]["count"] == 2


class TestBreakEvenParams:
    """BreakEvenParams 테스트"""
    
    def test_break_even_calculation(self):
        """Break-even 계산 검증"""
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            latency_bps=0.0,
            buffer_bps=5.0,
        )
        
        # D205-9-2 FIX:
        # fee_entry = 5 + 10 = 15
        # fee_exit = 5 + 10 = 15
        # exec_risk_round_trip = 2 * (10 + 0) = 20
        # buffer = 5
        # → break_even = 15 + 15 + 20 + 5 = 55 bps
        from arbitrage.v2.domain.break_even import compute_break_even_bps
        
        break_even = compute_break_even_bps(params)
        assert break_even == 55.0


class TestRealityWiringIntegration:
    """Reality Wiring 통합 테스트 (Mock 기반)"""
    
    @patch('scripts.run_d205_4_reality_wiring.UpbitRestProvider')
    @patch('scripts.run_d205_4_reality_wiring.BinanceRestProvider')
    def test_runner_initialization(self, mock_binance, mock_upbit):
        """Runner 초기화 검증"""
        from scripts.run_d205_4_reality_wiring import RealityWiringRunner
        
        runner = RealityWiringRunner(
            symbols=["BTC/KRW"],
            duration_sec=10,
        )
        
        assert runner.symbols == ["BTC/KRW"]
        assert runner.duration_sec == 10
        assert runner.run_id.startswith("d205_4_reality_wiring_")
        assert runner.evidence_dir.exists()
        assert isinstance(runner.decision_trace, DecisionTrace)
    
    @patch('scripts.run_d205_4_reality_wiring.UpbitRestProvider')
    @patch('scripts.run_d205_4_reality_wiring.BinanceRestProvider')
    def test_runner_evidence_directory_creation(self, mock_binance, mock_upbit):
        """Evidence 디렉토리 생성 검증"""
        from scripts.run_d205_4_reality_wiring import RealityWiringRunner
        
        runner = RealityWiringRunner(
            symbols=["BTC/KRW"],
            duration_sec=10,
            run_id="test_evidence_dir",
        )
        
        assert runner.evidence_dir.exists()
        assert runner.evidence_dir.name == "test_evidence_dir"
        assert "logs" in runner.evidence_dir.parts
        assert "evidence" in runner.evidence_dir.parts
