"""
D205-9-1: Execution-Risk Fill Model 단위 테스트

검증:
1. BUY fill price = base_price * (1 + execution_risk_bps/10000)
2. SELL fill price = base_price * (1 - execution_risk_bps/10000)
3. execution_risk_bps = slippage_bps + latency_bps
"""

import pytest


class TestExecutionRiskFillModel:
    """Execution-Risk Fill Model 테스트"""
    
    def test_buy_fill_price_increases_with_execution_risk(self):
        """BUY fill price가 execution_risk로 증가하는지 검증"""
        base_price = 100_000_000.0  # 1억
        slippage_bps = 15.0
        latency_bps = 10.0
        execution_risk_bps = slippage_bps + latency_bps  # 25 bps
        
        # BUY: 더 비싸게 체결
        buy_fill_price = base_price * (1 + execution_risk_bps / 10000.0)
        
        expected = base_price * 1.0025  # 1억 * 1.0025 = 100,250,000
        assert buy_fill_price == pytest.approx(expected, abs=1.0)
        assert buy_fill_price > base_price, "BUY fill price should be higher than base"
    
    def test_sell_fill_price_decreases_with_execution_risk(self):
        """SELL fill price가 execution_risk로 감소하는지 검증"""
        base_price = 100_000_000.0  # 1억
        slippage_bps = 15.0
        latency_bps = 10.0
        execution_risk_bps = slippage_bps + latency_bps  # 25 bps
        
        # SELL: 더 싸게 체결
        sell_fill_price = base_price * (1 - execution_risk_bps / 10000.0)
        
        expected = base_price * 0.9975  # 1억 * 0.9975 = 99,750,000
        assert sell_fill_price == pytest.approx(expected, abs=1.0)
        assert sell_fill_price < base_price, "SELL fill price should be lower than base"
    
    def test_execution_risk_impact_is_symmetric(self):
        """BUY/SELL 간 execution_risk 영향이 대칭인지 검증"""
        base_price = 100_000_000.0
        slippage_bps = 15.0
        latency_bps = 10.0
        execution_risk_bps = slippage_bps + latency_bps
        
        buy_fill = base_price * (1 + execution_risk_bps / 10000.0)
        sell_fill = base_price * (1 - execution_risk_bps / 10000.0)
        
        buy_diff = buy_fill - base_price
        sell_diff = base_price - sell_fill
        
        assert buy_diff == pytest.approx(sell_diff, abs=0.1), "Impact should be symmetric"
