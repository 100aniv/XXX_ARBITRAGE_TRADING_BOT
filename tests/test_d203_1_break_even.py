"""
D203-1: Break-even Threshold 테스트

테스트 케이스 (최소 6개):
1. Fee만 있는 경우
2. Fee + Slippage
3. Fee + Slippage + Buffer
4. Spread < Break-even (edge < 0)
5. Spread > Break-even (edge > 0)
6. 극단값 (0 / 매우 큰 값) 안정성
"""

import pytest
from arbitrage.v2.domain.break_even import (
    BreakEvenParams,
    compute_break_even_bps,
    compute_edge_bps,
    explain_break_even,
)
from arbitrage.domain.fee_model import FeeModel, FeeStructure


class TestBreakEvenThreshold:
    """Break-even Threshold 계산 테스트"""
    
    def test_case1_fee_only(self):
        """
        Case 1: Fee만 있는 경우 (slippage=0, latency=0, buffer=0)
        
        Expected:
            break_even_bps = fee_entry + fee_exit
        """
        # Upbit: 5 bps, Binance: 10 bps
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=0.0,
            latency_bps=0.0,
            buffer_bps=0.0,
        )
        
        break_even = compute_break_even_bps(params)
        
        # D205-9-1 FIX: slippage/latency는 break_even에서 제외
        # fee_entry = 5 + 10 = 15
        # fee_exit = 15 (왕복)
        # slippage = 0
        # buffer = 0
        # → break_even = 15 + 15 = 30
        assert break_even == 30.0
    
    def test_case2_fee_plus_slippage(self):
        """
        Case 2: Fee + Slippage (buffer=0)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            latency_bps=0.0,
            buffer_bps=0.0,
        )
        
        break_even = compute_break_even_bps(params)
        
        # D205-9-2 FIX: fee=30 + exec_risk_round_trip=2*(10+0)=20 = 50
        assert break_even == 50.0
    
    def test_case3_fee_plus_slippage_plus_buffer(self):
        """
        Case 3: Fee + Slippage + Buffer (전체)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            latency_bps=0.0,
            buffer_bps=5.0,
        )
        
        break_even = compute_break_even_bps(params)
        
        # D205-9-2 FIX: fee=30 + exec_risk_round_trip=20 + buffer=5 = 55
        assert break_even == 55.0
    
    def test_case4_negative_edge_when_spread_below_break_even(self):
        """
        Case 4: Spread < Break-even → Edge < 0 (손실 예상)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            latency_bps=0.0,
            buffer_bps=5.0,
        )
        
        break_even = compute_break_even_bps(params)  # D205-9-2 FIX: 55 bps
        spread_bps = 30.0  # 관측된 스프레드 (break-even보다 작음)
        
        edge = compute_edge_bps(spread_bps, break_even)
        
        # D205-9-2 FIX: edge = 30 - 55 = -25 (손실 예상)
        assert edge == -25.0
        assert edge < 0  # 손실 예상
    
    def test_case5_positive_edge_when_spread_above_break_even(self):
        """
        Case 5: Spread > Break-even → Edge > 0 (수익 가능)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            latency_bps=0.0,
            buffer_bps=5.0,
        )
        
        break_even = compute_break_even_bps(params)  # D205-9-2 FIX: 55 bps
        spread_bps = 100.0  # 관측된 스프레드 (break-even보다 큼)
        
        edge = compute_edge_bps(spread_bps, break_even)
        
        # D205-9-2 FIX: edge = 100 - 55 = 45 (수익 가능)
        assert edge == 45.0
        assert edge > 0  # 수익 가능
    
    def test_case6_extreme_values_stability(self):
        """
        Case 6: 극단값 (0 / 매우 큰 값) 안정성
        
        Sub-cases:
        - 6a: slippage=0, buffer=0 (최소)
        - 6b: 매우 큰 slippage (1000 bps = 10%)
        - 6c: 매우 큰 spread (100000 bps)
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        # 6a: 최소값
        params_min = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=0.0,
            latency_bps=0.0,  # D205-9-1: 명시적으로 0 설정
            buffer_bps=0.0,
        )
        break_even_min = compute_break_even_bps(params_min)
        assert break_even_min == 30.0  # fee_entry + fee_exit only
        
        # 6b: 매우 큰 slippage
        params_high_slip = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=1000.0,  # 10% slippage (매우 큼)
            latency_bps=0.0,  # D205-9-2: 명시적으로 0 설정
            buffer_bps=5.0,
        )
        break_even_high = compute_break_even_bps(params_high_slip)
        # D205-9-2 FIX: 30 + 2*(1000+0) + 5 = 2035
        assert break_even_high == 2035.0
        
        # 6c: 매우 큰 spread
        spread_huge = 100000.0  # 1000% spread (비현실적이지만 안정성 체크)
        edge_huge = compute_edge_bps(spread_huge, break_even_high)
        # D205-9-2 FIX: 100000 - 2035
        assert edge_huge == 100000.0 - 2035.0
        assert edge_huge > 0  # 여전히 수익 가능


class TestExplainBreakEven:
    """explain_break_even() 함수 테스트"""
    
    def test_explain_breakdown(self):
        """
        explain_break_even()이 모든 구성 요소를 반환하는지 확인
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            latency_bps=0.0,
            buffer_bps=5.0,
        )
        
        spread_bps = 100.0  # D205-9-2: break_even(55)보다 큰 값
        explanation = explain_break_even(params, spread_bps)
        
        assert explanation["fee_entry_bps"] == 15.0
        assert explanation["fee_exit_bps"] == 15.0
        assert explanation["slippage_bps"] == 10.0
        assert explanation["exec_risk_per_leg_bps"] == 10.0  # D205-9-2: 편도
        assert explanation["exec_risk_round_trip_bps"] == 20.0  # D205-9-2: 왕복
        assert explanation["buffer_bps"] == 5.0
        # D205-9-2 FIX: break_even = 30 + 20 + 5 = 55
        assert explanation["break_even_bps"] == 55.0
        assert explanation["spread_bps"] == 100.0
        assert explanation["edge_bps"] == 45.0
        assert explanation["profitable"] is True
    
    def test_explain_unprofitable(self):
        """
        explain_break_even()에서 profitable=False 케이스
        """
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            latency_bps=0.0,
            buffer_bps=5.0,
        )
        
        spread_bps = 30.0  # D205-9-2 FIX: break_even(55) 미만
        result = explain_break_even(params, spread_bps)
        
        assert result["edge_bps"] == -25.0
        assert result["profitable"] is False


class TestBreakEvenParamsFromConfig:
    """BreakEvenParams.from_threshold_config() 테스트"""
    
    def test_from_threshold_config(self):
        """
        ThresholdConfig에서 BreakEvenParams 생성
        """
        from arbitrage.v2.core.config import ThresholdConfig
        
        fee_a = FeeStructure("UPBIT", maker_fee_bps=5.0, taker_fee_bps=5.0)
        fee_b = FeeStructure("BINANCE", maker_fee_bps=10.0, taker_fee_bps=10.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        threshold_config = ThresholdConfig(
            use_exchange_fees=True,
            slippage_bps=12.0,
            buffer_bps=8.0,
        )
        
        params = BreakEvenParams.from_threshold_config(
            fee_model=fee_model,
            threshold_config=threshold_config,
        )
        
        assert params.fee_model == fee_model
        assert params.slippage_bps == 12.0
        assert params.buffer_bps == 8.0
        
        # Break-even 계산
        # D205-9-2: latency_bps 기본값 = 10
        # exec_risk_round_trip = 2 * (12 + 10) = 44
        break_even = compute_break_even_bps(params)
        # D205-9-2 FIX: 30 + 44 + 8 = 82
        assert break_even == 82.0
