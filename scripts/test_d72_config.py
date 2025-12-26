#!/usr/bin/env python3
"""
D72-1 Config 통합 테스트

새로운 Config 시스템이 기존 코드와 호환되는지 검증
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_config


def test_config_loading():
    """Config 로딩 테스트"""
    print("\n" + "=" * 70)
    print("D72-1 CONFIG LOADING TEST")
    print("=" * 70)
    
    # Test 1: Development
    print("\n[TEST 1] Loading development config...")
    dev_config = load_config('development')
    assert dev_config.env == 'development'
    assert dev_config.session.mode == 'paper'
    print("✅ Development config loaded")
    
    # Test 2: Staging
    print("\n[TEST 2] Loading staging config...")
    staging_config = load_config('staging')
    assert staging_config.env == 'staging'
    assert staging_config.session.data_source == 'ws'
    print("✅ Staging config loaded")
    
    # Test 3: Production (D99-15 P14: Set required env vars for testing)
    print("\n[TEST 3] Loading production config...")
    os.environ.setdefault('POSTGRES_PASSWORD', 'test_password')
    os.environ.setdefault('UPBIT_ACCESS_KEY', 'test_upbit_key')
    os.environ.setdefault('BINANCE_API_KEY', 'test_binance_key')
    try:
        prod_config = load_config('production')
        assert prod_config.env == 'production'
        assert prod_config.monitoring.log_level == 'WARNING'
        print("✅ Production config loaded")
    finally:
        # Cleanup test env vars
        for key in ['POSTGRES_PASSWORD', 'UPBIT_ACCESS_KEY', 'BINANCE_API_KEY']:
            if os.environ.get(key) == f'test_{key.lower()}' or os.environ.get(key) == 'test_password':
                os.environ.pop(key, None)
    
    print("\n" + "=" * 70)
    print("✅ All config loading tests PASSED")
    print("=" * 70)


def test_legacy_conversion():
    """Legacy config 변환 테스트"""
    print("\n" + "=" * 70)
    print("D72-1 LEGACY CONVERSION TEST")
    print("=" * 70)
    
    config = load_config('development')
    
    # Test 1: Legacy ArbitrageConfig
    print("\n[TEST 1] Converting to legacy ArbitrageConfig...")
    legacy_config = config.to_legacy_config()
    assert legacy_config.min_spread_bps == config.trading.min_spread_bps
    assert legacy_config.max_position_usd == config.risk.max_notional_per_trade
    print("✅ Legacy ArbitrageConfig conversion successful")
    
    # Test 2: Legacy ArbitrageLiveConfig
    print("\n[TEST 2] Converting to legacy ArbitrageLiveConfig...")
    live_config = config.to_live_config()
    assert live_config.mode == config.session.mode
    assert live_config.loop_interval_ms == config.session.loop_interval_ms
    print("✅ Legacy ArbitrageLiveConfig conversion successful")
    
    # Test 3: Legacy RiskLimits
    print("\n[TEST 3] Converting to legacy RiskLimits...")
    risk_limits = config.to_risk_limits()
    assert risk_limits.max_notional_per_trade == config.risk.max_notional_per_trade
    assert risk_limits.max_daily_loss == config.risk.max_daily_loss
    print("✅ Legacy RiskLimits conversion successful")
    
    print("\n" + "=" * 70)
    print("✅ All legacy conversion tests PASSED")
    print("=" * 70)


def test_validation():
    """Validation 테스트"""
    print("\n" + "=" * 70)
    print("D72-1 VALIDATION TEST")
    print("=" * 70)
    
    # Test 1: Spread vs Fees
    print("\n[TEST 1] Spread profitability validation...")
    config = load_config('development')
    total_cost = (
        config.trading.taker_fee_a_bps +
        config.trading.taker_fee_b_bps +
        config.trading.slippage_bps
    )
    assert config.trading.min_spread_bps > total_cost * 1.5
    print(f"  Spread: {config.trading.min_spread_bps} bps")
    print(f"  Total cost: {total_cost} bps")
    print(f"  Required: > {total_cost * 1.5} bps")
    print("✅ Spread validation passed")
    
    # Test 2: Risk constraints
    print("\n[TEST 2] Risk constraints validation...")
    assert config.risk.max_daily_loss >= config.risk.max_notional_per_trade
    print(f"  Daily loss limit: ${config.risk.max_daily_loss}")
    print(f"  Per-trade limit: ${config.risk.max_notional_per_trade}")
    print("✅ Risk validation passed")
    
    print("\n" + "=" * 70)
    print("✅ All validation tests PASSED")
    print("=" * 70)


def main():
    """메인 함수"""
    try:
        test_config_loading()
        test_legacy_conversion()
        test_validation()
        
        print("\n" + "=" * 70)
        print("🎉 D72-1 CONFIG TESTS: ALL PASSED")
        print("=" * 70)
        return 0
    
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
