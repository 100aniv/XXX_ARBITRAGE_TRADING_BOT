"""
D207-1-2: FX Real-time + Staleness Guard Test

목표: LiveFxProvider의 FX rate info 기록 및 staleness guard 검증

AC:
- FX rate info (rate, source, timestamp, age_sec, degraded) KPI에 기록
- FX age > TTL 시 FAIL (stop_reason="FX_STALE")

SSOT: D_ROADMAP.md → D207-1-2
"""

import pytest
import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from arbitrage.v2.core.fx_provider import LiveFxProvider, FxRateInfo, FixedFxProvider
from arbitrage.v2.core.opportunity_source import RealOpportunitySource
from arbitrage.v2.core.metrics import PaperMetrics
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure


class TestFxRealtimeAndStaleGuard:
    """D207-1-2: FX Real-time + Staleness Guard"""
    
    def test_fx_rate_info_recorded_in_kpi(self):
        """AU-1: FX rate info가 KPI에 기록되는지 검증"""
        # Given: LiveFxProvider with mock market data
        market_data_fetcher = Mock()
        market_data_fetcher.get_mid_price = Mock(side_effect=lambda ex, sym: 105_000_000.0 if ex == "upbit" else 70_000.0)
        
        fx_provider = LiveFxProvider(
            source="crypto_implied",
            ttl_seconds=10.0,
            market_data_fetcher=market_data_fetcher
        )
        
        kpi = PaperMetrics()
        break_even_params = BreakEvenParams(
            fee_model=FeeModel(
                fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0),
                fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=10.0),
            ),
            slippage_bps=5.0,
            latency_bps=2.0,
            buffer_bps=3.0,
        )
        
        upbit_provider = Mock()
        upbit_provider.get_ticker = Mock(
            return_value=Mock(bid=104_000_000.0, ask=104_100_000.0, last=104_050_000.0)
        )
        binance_provider = Mock()
        binance_provider.get_ticker = Mock(
            return_value=Mock(bid=70_000.0, ask=70_100.0, last=70_050.0)
        )
        
        rate_limiter_upbit = Mock()
        rate_limiter_upbit.consume = Mock(return_value=True)
        rate_limiter_binance = Mock()
        rate_limiter_binance.consume = Mock(return_value=True)
        
        profit_core = Mock()
        profit_core.check_price_sanity = Mock(return_value=True)
        profit_core.get_default_price = Mock(return_value=100_000_000.0)
        
        opp_source = RealOpportunitySource(
            upbit_provider=upbit_provider,
            binance_provider=binance_provider,
            rate_limiter_upbit=rate_limiter_upbit,
            rate_limiter_binance=rate_limiter_binance,
            fx_provider=fx_provider,
            break_even_params=break_even_params,
            kpi=kpi,
            profit_core=profit_core,
        )
        
        # When: Generate opportunity (triggers FX rate fetch)
        candidate = opp_source.generate(iteration=1)
        
        # Then: FX rate info should be recorded in KPI
        assert candidate is not None, "Candidate should be generated"
        assert kpi.fx_rate > 0, "fx_rate should be recorded"
        assert kpi.fx_rate_source in ["crypto_implied", "crypto_implied_fallback"], "fx_rate_source should be set"
        assert kpi.fx_rate_timestamp != "", "fx_rate_timestamp should be set"
        assert kpi.fx_rate_age_sec >= 0, "fx_rate_age_sec should be >= 0"
        
        print(f"✅ FX rate info recorded: rate={kpi.fx_rate}, source={kpi.fx_rate_source}, age={kpi.fx_rate_age_sec}s")

    def test_real_opportunity_uses_bid_ask_execution_prices(self):
        """AU-4: bid/ask 실행 가격 우선 사용 (last fallback)"""
        fx_provider = FixedFxProvider(fx_krw_per_usdt=1400.0)

        kpi = PaperMetrics()
        break_even_params = BreakEvenParams(
            fee_model=FeeModel(
                fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0),
                fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=10.0),
            ),
            slippage_bps=5.0,
            latency_bps=2.0,
            buffer_bps=3.0,
        )

        upbit_provider = Mock()
        upbit_provider.get_ticker = Mock(
            return_value=Mock(bid=100_000_000.0, ask=100_100_000.0, last=150_000_000.0)
        )
        binance_provider = Mock()
        binance_provider.get_ticker = Mock(
            return_value=Mock(bid=70_000.0, ask=70_100.0, last=120_000.0)
        )

        rate_limiter_upbit = Mock()
        rate_limiter_upbit.consume = Mock(return_value=True)
        rate_limiter_binance = Mock()
        rate_limiter_binance.consume = Mock(return_value=True)

        profit_core = Mock()
        profit_core.check_price_sanity = Mock(return_value=True)

        opp_source = RealOpportunitySource(
            upbit_provider=upbit_provider,
            binance_provider=binance_provider,
            rate_limiter_upbit=rate_limiter_upbit,
            rate_limiter_binance=rate_limiter_binance,
            fx_provider=fx_provider,
            break_even_params=break_even_params,
            kpi=kpi,
            profit_core=profit_core,
        )

        candidate = opp_source.generate(iteration=1)

        assert candidate is not None
        bid_a = 100_000_000.0
        ask_a = 100_100_000.0
        bid_b = 70_000.0 * 1400.0
        ask_b = 70_100.0 * 1400.0
        assert candidate.price_a in (pytest.approx(bid_a), pytest.approx(ask_a))
        assert candidate.price_b in (pytest.approx(bid_b), pytest.approx(ask_b))
    
    def test_fx_stale_guard_triggers_fail(self):
        """AU-2: FX rate age > TTL 시 FAIL 검증"""
        # Given: LiveFxProvider with stale FX rate
        market_data_fetcher = Mock()
        market_data_fetcher.get_mid_price = Mock(side_effect=lambda ex, sym: 100_000_000.0 if ex == "upbit" else 70_000.0)
        
        fx_provider = LiveFxProvider(
            source="crypto_implied",
            ttl_seconds=10.0,
            market_data_fetcher=market_data_fetcher
        )
        
        # Fetch rate once
        fx_provider.get_fx_rate("USDT", "KRW")
        
        # Mock stale timestamp (61 seconds ago)
        stale_timestamp = datetime.now(timezone.utc).timestamp() - 61.0
        fx_provider._last_rate_info = FxRateInfo(
            rate=1400.0,
            source="crypto_implied",
            timestamp=datetime.fromtimestamp(stale_timestamp, tz=timezone.utc),
            degraded=False,
        )
        
        kpi = PaperMetrics()
        break_even_params = BreakEvenParams(
            fee_model=FeeModel(
                fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0),
                fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=10.0),
            ),
            slippage_bps=5.0,
            latency_bps=2.0,
            buffer_bps=3.0,
        )
        
        upbit_provider = Mock()
        upbit_provider.get_ticker = Mock(return_value=Mock(last=100_000_000.0))
        binance_provider = Mock()
        binance_provider.get_ticker = Mock(return_value=Mock(last=70_000.0))
        
        rate_limiter_upbit = Mock()
        rate_limiter_upbit.consume = Mock(return_value=True)
        rate_limiter_binance = Mock()
        rate_limiter_binance.consume = Mock(return_value=True)
        
        profit_core = Mock()
        profit_core.check_price_sanity = Mock(return_value=True)
        
        opp_source = RealOpportunitySource(
            upbit_provider=upbit_provider,
            binance_provider=binance_provider,
            rate_limiter_upbit=rate_limiter_upbit,
            rate_limiter_binance=rate_limiter_binance,
            fx_provider=fx_provider,
            break_even_params=break_even_params,
            kpi=kpi,
            profit_core=profit_core,
        )
        
        # When: Generate opportunity with stale FX
        candidate = opp_source.generate(iteration=1)
        
        # Then: Should reject (FX too old)
        assert candidate is None, "Candidate should be None (FX_STALE)"
        assert kpi.reject_reasons.get("fx_stale", 0) > 0, "fx_stale reject should be incremented"
        assert kpi.fx_rate_age_sec > 60, "fx_rate_age_sec should be > 60"
        
        print(f"✅ FX stale guard triggered: age={kpi.fx_rate_age_sec}s > 60s")
    
    def test_fixed_fx_provider_records_source(self):
        """AU-3: FixedFxProvider는 source='fixed' 기록"""
        # Given: FixedFxProvider
        fx_provider = FixedFxProvider(fx_krw_per_usdt=1450.0)
        
        kpi = PaperMetrics()
        break_even_params = BreakEvenParams(
            fee_model=FeeModel(
                fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0),
                fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=10.0),
            ),
            slippage_bps=5.0,
            latency_bps=2.0,
            buffer_bps=3.0,
        )
        
        upbit_provider = Mock()
        upbit_provider.get_ticker = Mock(return_value=Mock(last=100_000_000.0))
        binance_provider = Mock()
        binance_provider.get_ticker = Mock(return_value=Mock(last=70_000.0))
        
        rate_limiter_upbit = Mock()
        rate_limiter_upbit.consume = Mock(return_value=True)
        rate_limiter_binance = Mock()
        rate_limiter_binance.consume = Mock(return_value=True)
        
        profit_core = Mock()
        profit_core.check_price_sanity = Mock(return_value=True)
        
        opp_source = RealOpportunitySource(
            upbit_provider=upbit_provider,
            binance_provider=binance_provider,
            rate_limiter_upbit=rate_limiter_upbit,
            rate_limiter_binance=rate_limiter_binance,
            fx_provider=fx_provider,
            break_even_params=break_even_params,
            kpi=kpi,
            profit_core=profit_core,
        )
        
        # When: Generate opportunity
        candidate = opp_source.generate(iteration=1)
        
        # Then: source='fixed' should be recorded
        assert candidate is not None
        assert kpi.fx_rate == 1450.0, "fx_rate should be 1450.0"
        assert kpi.fx_rate_source == "fixed", "fx_rate_source should be 'fixed'"
        assert kpi.fx_rate_age_sec == 0.0, "fx_rate_age_sec should be 0.0"
        
        print(f"✅ FixedFxProvider source recorded: rate={kpi.fx_rate}, source={kpi.fx_rate_source}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
