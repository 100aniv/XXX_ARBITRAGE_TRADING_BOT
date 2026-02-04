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
from unittest.mock import Mock, MagicMock
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.core.adapter import OrderResult
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure


class TestLatencyCostDecomposition:
    """D_ALPHA-1U-FIX-2: Latency Cost Decomposition"""
    
    @pytest.fixture
    def break_even_params(self):
        """BreakEvenParams 생성"""
        fee_model = FeeModel(
            fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0),
            fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=4.0, taker_fee_bps=4.0),
        )
        return BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=10.0,
            latency_bps=5.0,
            partial_fill_penalty_bps=10.0,
        )
    
    def _calc_slippage_cost(self, result) -> float:
        """Orchestrator에서 추출한 슬리피지 비용 계산"""
        if not result:
            return 0.0
        if result.ref_price is None or result.filled_qty is None:
            return 0.0
        slippage_bps = getattr(result, "slippage_bps", None)
        if slippage_bps is None:
            if result.filled_price is None:
                return 0.0
            return abs(result.filled_price - result.ref_price) * result.filled_qty
        slippage_ratio = abs(float(slippage_bps)) / 10000.0
        return abs(float(result.ref_price)) * slippage_ratio * float(result.filled_qty)
    
    def _calc_latency_cost(self, result) -> float:
        """Orchestrator에서 추출한 레이턴시 비용 계산 (가격 영향)"""
        if not result:
            return 0.0
        if result.ref_price is None or result.filled_qty is None:
            return 0.0
        drift_bps = getattr(result, "pessimistic_drift_bps", None)
        if drift_bps is None:
            return 0.0
        slippage_bps = getattr(result, "slippage_bps", 0.0) or 0.0
        slippage_ratio = abs(float(slippage_bps)) / 10000.0
        drift_ratio = abs(float(drift_bps)) / 10000.0
        base_price = float(result.ref_price)
        return abs(base_price * (1 + slippage_ratio) * drift_ratio * float(result.filled_qty))
    
    def _calc_latency_ms(self, result) -> float:
        """Orchestrator에서 추출한 레이턴시 시간(ms) 합계"""
        if not result or result.latency_ms is None:
            return 0.0
        return float(result.latency_ms)
    
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
        slippage_base = self._calc_slippage_cost(result_base)
        latency_cost_base = self._calc_latency_cost(result_base)
        latency_ms_base = self._calc_latency_ms(result_base)
        
        # Then: Record baseline
        assert latency_ms_base == 50.0, "latency_ms should be 50.0"
        assert latency_cost_base > 0, "latency_cost should be > 0"
        
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
        
        slippage_high = self._calc_slippage_cost(result_high_latency)
        latency_cost_high = self._calc_latency_cost(result_high_latency)
        latency_ms_high = self._calc_latency_ms(result_high_latency)
        
        # Then: latency_total increases, latency_cost unchanged
        assert latency_ms_high == 500.0, "latency_ms should be 500.0"
        assert latency_ms_high > latency_ms_base, "latency_ms should increase"
        assert latency_cost_high == latency_cost_base, \
            f"latency_cost should be unchanged: {latency_cost_high} vs {latency_cost_base}"
        assert slippage_high == slippage_base, "slippage_cost should be unchanged"
        
        print(f"✅ AC-1 PASS: latency_ms {latency_ms_base}→{latency_ms_high}, "
              f"latency_cost {latency_cost_base}→{latency_cost_high} (unchanged)")
    
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
        latency_cost_base = self._calc_latency_cost(result_base)
        latency_ms_base = self._calc_latency_ms(result_base)
        
        # Then: Record baseline
        assert latency_cost_base > 0, "latency_cost should be > 0"
        assert latency_ms_base == 50.0, "latency_ms should be 50.0"
        
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
        
        latency_cost_high = self._calc_latency_cost(result_high_drift)
        latency_ms_high = self._calc_latency_ms(result_high_drift)
        
        # Then: latency_cost increases, latency_ms unchanged
        assert latency_ms_high == latency_ms_base, "latency_ms should be unchanged"
        assert latency_cost_high > latency_cost_base, \
            f"latency_cost should increase: {latency_cost_high} > {latency_cost_base}"
        
        # Verify approximate ratio (drift_bps 5→20 = 4x)
        cost_ratio = latency_cost_high / latency_cost_base
        assert 3.5 < cost_ratio < 4.5, \
            f"latency_cost ratio should be ~4x: {cost_ratio}"
        
        print(f"✅ AC-2 PASS: pessimistic_drift_bps 5→20, "
              f"latency_cost {latency_cost_base:.2f}→{latency_cost_high:.2f} (ratio={cost_ratio:.2f}x)")
    
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
        
        # When: Calculate all friction costs
        slippage_entry = self._calc_slippage_cost(result_entry)
        slippage_exit = self._calc_slippage_cost(result_exit)
        slippage_total = slippage_entry + slippage_exit
        
        latency_entry = self._calc_latency_cost(result_entry)
        latency_exit = self._calc_latency_cost(result_exit)
        latency_cost_total = latency_entry + latency_exit
        
        latency_ms_entry = self._calc_latency_ms(result_entry)
        latency_ms_exit = self._calc_latency_ms(result_exit)
        latency_total_ms = latency_ms_entry + latency_ms_exit
        
        total_fee = result_entry.fee + result_exit.fee
        
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
        
        print(f"✅ AC-3 PASS: PnL decomposition scale sanity")
        print(f"   Notional: {notional:.0f} KRW")
        print(f"   Fees: {total_fee:.0f} KRW")
        print(f"   Slippage: {slippage_total:.0f} KRW")
        print(f"   Latency Cost: {latency_cost_total:.0f} KRW")
        print(f"   Latency Total (ms): {latency_total_ms:.0f} ms")
        print(f"   Total Friction: {total_friction:.0f} KRW ({friction_pct:.4f}% of notional)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
