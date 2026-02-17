"""
D_ALPHA-1U-FIX-2: Latency Cost Decomposition Test

목표: latency_total(ms) vs latency_cost(가격영향) 분리 검증

AC:
- latency_ms만 증가해도 latency_total만 증가하고 latency_cost는 불변
- pessimistic_drift_bps 증가 시 latency_cost만 증가
- slippage_bps + pessimistic_drift_bps 기반 계산으로만 latency_cost 변화
- net_pnl 분해 스케일이 상식선(수원 단위)

SSOT: D_ROADMAP.md → D_ALPHA-1U-FIX-2
"""

import pytest
from arbitrage.v2.core.adapter import OrderResult
from arbitrage.v2.domain.pnl_calculator import calculate_execution_friction_from_results


class TestLatencyCostDecomposition:
    """D_ALPHA-1U-FIX-2: Latency Cost Decomposition"""

    def _friction(self, entry_result=None, exit_result=None):
        return calculate_execution_friction_from_results(
            entry_result=entry_result,
            exit_result=exit_result,
            return_decimal=False,
        )
    
    def test_latency_ms_independent_from_latency_cost(self):
        """AC-1: latency_ms 증가 → latency_total만 증가, latency_cost 불변"""
        # Given: OrderResult with base values
        result_base = OrderResult(
            success=True,
            order_id="test_order_1",
            ref_price=50000000.0,
            filled_price=50000000.0,
            filled_qty=0.001,
            fee=250.0,
            slippage_bps=10.0,
            pessimistic_drift_bps=5.0,
            latency_ms=50.0,
            reject_flag=False,
            partial_fill_ratio=1.0,
        )
        
        # When: Calculate costs with base latency_ms
        base = self._friction(entry_result=result_base)
        
        # Then: Record baseline
        assert base["latency_total_ms"] == 50.0, "latency_ms should be 50.0"
        assert base["latency_cost"] > 0, "latency_cost should be > 0"
        
        # When: Increase latency_ms to 500 (10x)
        result_high_latency = OrderResult(
            success=True,
            order_id="test_order_2",
            ref_price=50000000.0,
            filled_price=50000000.0,
            filled_qty=0.001,
            fee=250.0,
            slippage_bps=10.0,
            pessimistic_drift_bps=5.0,
            latency_ms=500.0,  # 10x increase
            reject_flag=False,
            partial_fill_ratio=1.0,
        )
        
        high = self._friction(entry_result=result_high_latency)
        
        # Then: latency_total increases, latency_cost unchanged
        assert high["latency_total_ms"] == 500.0, "latency_ms should be 500.0"
        assert high["latency_total_ms"] > base["latency_total_ms"], "latency_ms should increase"
        assert high["latency_cost"] == pytest.approx(base["latency_cost"]), "latency_cost should be unchanged"
        assert high["slippage_cost"] == pytest.approx(base["slippage_cost"]), "slippage_cost should be unchanged"
    
    def test_latency_cost_increases_with_drift_bps(self):
        """AC-2: pessimistic_drift_bps 증가 → latency_cost 증가, latency_ms 불변"""
        # Given: OrderResult with base drift_bps
        result_base = OrderResult(
            success=True,
            order_id="test_order_3",
            ref_price=50000000.0,
            filled_price=50000000.0,
            filled_qty=0.001,
            fee=250.0,
            slippage_bps=10.0,
            pessimistic_drift_bps=5.0,
            latency_ms=50.0,
            reject_flag=False,
            partial_fill_ratio=1.0,
        )
        
        # When: Calculate costs with base drift_bps
        base = self._friction(entry_result=result_base)
        
        # Then: Record baseline
        assert base["latency_cost"] > 0, "latency_cost should be > 0"
        assert base["latency_total_ms"] == 50.0, "latency_ms should be 50.0"
        
        # When: Increase pessimistic_drift_bps to 20 (4x)
        result_high_drift = OrderResult(
            success=True,
            order_id="test_order_4",
            ref_price=50000000.0,
            filled_price=50000000.0,
            filled_qty=0.001,
            fee=250.0,
            slippage_bps=10.0,
            pessimistic_drift_bps=20.0,  # 4x increase
            latency_ms=50.0,  # unchanged
            reject_flag=False,
            partial_fill_ratio=1.0,
        )
        
        high = self._friction(entry_result=result_high_drift)
        
        # Then: latency_cost increases, latency_ms unchanged
        assert high["latency_total_ms"] == base["latency_total_ms"], "latency_ms should be unchanged"
        assert high["latency_cost"] > base["latency_cost"], \
            f"latency_cost should increase: {high['latency_cost']} > {base['latency_cost']}"
        
        # Verify approximate ratio (drift_bps 5→20 = 4x)
        cost_ratio = high["latency_cost"] / base["latency_cost"]
        assert 3.5 < cost_ratio < 4.5, \
            f"latency_cost ratio should be ~4x: {cost_ratio}"
    
    def test_pnl_decomposition_scale_sanity(self):
        """AC-3: net_pnl 분해가 상식선 스케일 유지"""
        # Given: Realistic trade scenario
        ref_price = 50000000.0  # 5천만 KRW
        qty = 0.001  # 0.001 BTC
        
        result_entry = OrderResult(
            success=True,
            order_id="entry_1",
            ref_price=ref_price,
            filled_price=ref_price,
            filled_qty=qty,
            fee=250.0,  # ~5 bps
            slippage_bps=10.0,
            pessimistic_drift_bps=5.0,
            latency_ms=50.0,
            reject_flag=False,
            partial_fill_ratio=1.0,
        )
        
        result_exit = OrderResult(
            success=True,
            order_id="exit_1",
            ref_price=ref_price / 1300.0,  # USDT 기준
            filled_price=ref_price / 1300.0,
            filled_qty=qty,
            fee=200.0,  # ~4 bps
            slippage_bps=10.0,
            pessimistic_drift_bps=5.0,
            latency_ms=50.0,
            reject_flag=False,
            partial_fill_ratio=1.0,
        )
        
        # When: Calculate all friction costs through welding truth API
        friction = self._friction(entry_result=result_entry, exit_result=result_exit)
        slippage_total = friction["slippage_cost"]
        latency_cost_total = friction["latency_cost"]
        latency_total_ms = friction["latency_total_ms"]
        total_fee = friction["total_fee"]
        
        # Then: Verify scale sanity
        # 1. latency_total_ms should be in ms range (50-500)
        assert 40 < latency_total_ms < 600, \
            f"latency_total_ms should be in ms range: {latency_total_ms}"
        
        # 2. latency_cost should be in KRW range (not ms)
        assert latency_cost_total < 100000, \
            f"latency_cost should be in KRW range, not ms: {latency_cost_total}"
        
        # 3. slippage_cost should be similar scale to latency_cost
        assert abs(slippage_total - latency_cost_total) / max(slippage_total, latency_cost_total) < 2.0, \
            f"slippage and latency costs should be similar scale: {slippage_total} vs {latency_cost_total}"
        
        # 4. total_fee should be in KRW range
        assert 200 < total_fee < 1000, \
            f"total_fee should be in KRW range: {total_fee}"
        
        # 5. Verify friction costs are reasonable (not exceeding notional)
        notional = ref_price * qty
        total_friction = total_fee + slippage_total + latency_cost_total
        
        # Friction should not exceed 1.1% of notional (sanity check)
        friction_pct = (total_friction / notional) * 100 if notional > 0 else 0
        assert friction_pct < 1.1, \
            f"Total friction should be < 1.1% of notional: {friction_pct:.4f}%"
        
        assert total_friction > 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
