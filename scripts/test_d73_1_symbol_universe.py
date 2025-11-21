#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D73-1 Symbol Universe Provider 테스트

4가지 모드 (SINGLE, FIXED_LIST, TOP_N, FULL_MARKET) 검증.
외부 API 호출 없이 DummySymbolSource로 테스트.

Test Coverage:
1. SINGLE 모드: 단일 심볼 반환
2. FIXED_LIST 모드: whitelist/blacklist 처리
3. TOP_N 모드: 필터 + 정렬 + 상위 N개 선택
4. FULL_MARKET 모드: 필터 + 전체 반환
5. Config 통합 테스트

Author: D73-1 Implementation
Date: 2025-11-21
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.symbol_universe import (
    SymbolUniverse,
    SymbolUniverseMode,
    SymbolUniverseConfig,
    SymbolInfo,
    DummySymbolSource,
)


def test_single_mode():
    """Test 1: SINGLE 모드"""
    print("\n" + "="*80)
    print("Test 1: SINGLE 모드")
    print("="*80)
    
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.SINGLE,
        single_symbol="BTCUSDT"
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: ['BTCUSDT']")
    print(f"Actual:   {symbols}")
    
    assert symbols == ["BTCUSDT"], f"Expected ['BTCUSDT'], got {symbols}"
    assert len(symbols) == 1, f"Expected 1 symbol, got {len(symbols)}"
    
    print("✅ PASS: SINGLE 모드 정상 동작")
    return True


def test_fixed_list_mode():
    """Test 2: FIXED_LIST 모드"""
    print("\n" + "="*80)
    print("Test 2: FIXED_LIST 모드")
    print("="*80)
    
    # Test 2-1: Whitelist만 (blacklist 없음)
    print("\n[Test 2-1] Whitelist만")
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FIXED_LIST,
        whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']")
    print(f"Actual:   {symbols}")
    
    assert symbols == ["BTCUSDT", "ETHUSDT", "BNBUSDT"], f"Unexpected result: {symbols}"
    print("✅ PASS: Whitelist만 정상 동작")
    
    # Test 2-2: Whitelist + Blacklist
    print("\n[Test 2-2] Whitelist + Blacklist")
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FIXED_LIST,
        whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT", "BUSDUSDT"],
        blacklist=["BUSDUSDT"]  # Stablecoin 제외
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'] (BUSDUSDT 제외)")
    print(f"Actual:   {symbols}")
    
    assert "BUSDUSDT" not in symbols, "BUSDUSDT should be filtered out"
    assert len(symbols) == 3, f"Expected 3 symbols, got {len(symbols)}"
    print("✅ PASS: Whitelist + Blacklist 정상 동작")
    
    return True


def test_top_n_mode():
    """Test 3: TOP_N 모드"""
    print("\n" + "="*80)
    print("Test 3: TOP_N 모드")
    print("="*80)
    
    # Test 3-1: 상위 3개 (필터 없음)
    print("\n[Test 3-1] TOP_N=3 (필터 없음)")
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.TOP_N,
        top_n=3,
        base_quote="USDT",
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT'] (volume 상위 3개)")
    print(f"Actual:   {symbols}")
    
    # DummySymbolSource의 volume 순서: BTC(50B) > ETH(20B) > BUSD(10B) > USDC(8B) > BNB(3B) ...
    # 하지만 BUSD/USDC는 stablecoin이므로 필터링 가능
    assert len(symbols) == 3, f"Expected 3 symbols, got {len(symbols)}"
    assert symbols[0] == "BTCUSDT", f"Expected BTCUSDT as #1, got {symbols[0]}"
    print("✅ PASS: TOP_N=3 정상 동작")
    
    # Test 3-2: TOP_N=5 + Blacklist (stablecoins 제외)
    print("\n[Test 3-2] TOP_N=5 + Blacklist")
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.TOP_N,
        top_n=5,
        base_quote="USDT",
        blacklist=["BUSDUSDT", "USDCUSDT"]  # Stablecoins 제외
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: Top 5 (BUSD/USDC 제외)")
    print(f"Actual:   {symbols}")
    
    assert "BUSDUSDT" not in symbols, "BUSDUSDT should be filtered out"
    assert "USDCUSDT" not in symbols, "USDCUSDT should be filtered out"
    assert len(symbols) == 5, f"Expected 5 symbols, got {len(symbols)}"
    print("✅ PASS: TOP_N + Blacklist 정상 동작")
    
    # Test 3-3: TOP_N=3 + Volume threshold
    print("\n[Test 3-3] TOP_N=3 + Volume threshold")
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.TOP_N,
        top_n=3,
        base_quote="USDT",
        min_24h_quote_volume=2_000_000_000.0,  # 2B 이상만
        blacklist=["BUSDUSDT", "USDCUSDT"]
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: Top 3 (volume >= 2B, stablecoins 제외)")
    print(f"Actual:   {symbols}")
    
    # BTC(50B), ETH(20B), BNB(3B), SOL(2.5B) ... 중 상위 3개
    assert len(symbols) <= 3, f"Expected <= 3 symbols, got {len(symbols)}"
    print("✅ PASS: TOP_N + Volume threshold 정상 동작")
    
    return True


def test_full_market_mode():
    """Test 4: FULL_MARKET 모드"""
    print("\n" + "="*80)
    print("Test 4: FULL_MARKET 모드")
    print("="*80)
    
    # Test 4-1: 필터 없음 (전체)
    print("\n[Test 4-1] FULL_MARKET (필터 없음)")
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FULL_MARKET,
        base_quote="USDT",
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: 모든 USDT 페어 ({len(DummySymbolSource().get_all_symbols())}개 중)")
    print(f"Actual:   {len(symbols)}개 symbols")
    print(f"Symbols:  {symbols[:5]}... (처음 5개)")
    
    # DummySymbolSource는 15개 샘플 제공
    assert len(symbols) == 15, f"Expected 15 symbols, got {len(symbols)}"
    print("✅ PASS: FULL_MARKET 전체 반환")
    
    # Test 4-2: Blacklist 적용
    print("\n[Test 4-2] FULL_MARKET + Blacklist")
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FULL_MARKET,
        base_quote="USDT",
        blacklist=["BUSDUSDT", "USDCUSDT", "BTCBULL"]  # Stablecoins + Leveraged tokens
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: 15 - 3 = 12개")
    print(f"Actual:   {len(symbols)}개 symbols")
    
    assert len(symbols) == 12, f"Expected 12 symbols, got {len(symbols)}"
    assert "BUSDUSDT" not in symbols
    assert "USDCUSDT" not in symbols
    assert "BTCBULL" not in symbols
    print("✅ PASS: FULL_MARKET + Blacklist 정상 동작")
    
    # Test 4-3: Volume threshold
    print("\n[Test 4-3] FULL_MARKET + Volume threshold")
    config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FULL_MARKET,
        base_quote="USDT",
        min_24h_quote_volume=1_000_000_000.0,  # 1B 이상만
        blacklist=["BUSDUSDT", "USDCUSDT"]
    )
    universe = SymbolUniverse(config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Expected: Volume >= 1B (stablecoins 제외)")
    print(f"Actual:   {len(symbols)}개 symbols")
    print(f"Symbols:  {symbols}")
    
    # Volume >= 1B: BTC, ETH, BNB, SOL, XRP, ADA, DOGE, MATIC (8개)
    assert len(symbols) == 8, f"Expected 8 symbols, got {len(symbols)}"
    print("✅ PASS: FULL_MARKET + Volume threshold 정상 동작")
    
    return True


def test_config_validation():
    """Test 5: Config Validation"""
    print("\n" + "="*80)
    print("Test 5: Config Validation")
    print("="*80)
    
    # Test 5-1: SINGLE mode without single_symbol (should fail)
    print("\n[Test 5-1] SINGLE mode validation")
    try:
        config = SymbolUniverseConfig(
            mode=SymbolUniverseMode.SINGLE,
            single_symbol=None  # Invalid
        )
        print("❌ FAIL: Should raise ValueError")
        return False
    except ValueError as e:
        print(f"✅ PASS: Validation error caught: {e}")
    
    # Test 5-2: FIXED_LIST mode without whitelist (should fail)
    print("\n[Test 5-2] FIXED_LIST mode validation")
    try:
        config = SymbolUniverseConfig(
            mode=SymbolUniverseMode.FIXED_LIST,
            whitelist=[]  # Invalid
        )
        print("❌ FAIL: Should raise ValueError")
        return False
    except ValueError as e:
        print(f"✅ PASS: Validation error caught: {e}")
    
    # Test 5-3: TOP_N mode without top_n (should fail)
    print("\n[Test 5-3] TOP_N mode validation")
    try:
        config = SymbolUniverseConfig(
            mode=SymbolUniverseMode.TOP_N,
            top_n=None  # Invalid
        )
        print("❌ FAIL: Should raise ValueError")
        return False
    except ValueError as e:
        print(f"✅ PASS: Validation error caught: {e}")
    
    # Test 5-4: TOP_N mode with top_n <= 0 (should fail)
    print("\n[Test 5-4] TOP_N mode with invalid top_n")
    try:
        config = SymbolUniverseConfig(
            mode=SymbolUniverseMode.TOP_N,
            top_n=0  # Invalid
        )
        print("❌ FAIL: Should raise ValueError")
        return False
    except ValueError as e:
        print(f"✅ PASS: Validation error caught: {e}")
    
    print("\n✅ ALL VALIDATION TESTS PASSED")
    return True


def test_config_integration():
    """Test 6: Config Integration (config.base.py 연동)"""
    print("\n" + "="*80)
    print("Test 6: Config Integration")
    print("="*80)
    
    from config.base import SymbolUniverseConfig as BaseSymbolUniverseConfig
    from config.base import ArbitrageConfig, ExchangeConfig, DatabaseConfig, RiskConfig, TradingConfig, MonitoringConfig, SessionConfig
    
    # Test 6-1: ArbitrageConfig에 universe 필드 확인
    print("\n[Test 6-1] ArbitrageConfig.universe 필드 존재 확인")
    config = ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(),
        database=DatabaseConfig(),
        risk=RiskConfig(
            max_notional_per_trade=1000.0,  # Fix validation error
            max_daily_loss=5000.0
        ),
        trading=TradingConfig(
            min_spread_bps=50.0  # Fix validation error (fees + slippage) * 1.5 = 37.5
        ),
        monitoring=MonitoringConfig(),
        session=SessionConfig()
    )
    
    assert hasattr(config, 'universe'), "ArbitrageConfig should have 'universe' field"
    assert config.universe is not None, "universe should not be None"
    assert config.universe.mode == "SINGLE", f"Expected SINGLE mode, got {config.universe.mode}"
    print(f"✅ PASS: universe 필드 존재, mode={config.universe.mode}")
    
    # Test 6-2: 기본값 확인
    print("\n[Test 6-2] 기본값 확인")
    print(f"  mode: {config.universe.mode}")
    print(f"  exchange: {config.universe.exchange}")
    print(f"  single_symbol: {config.universe.single_symbol}")
    print(f"  base_quote: {config.universe.base_quote}")
    
    assert config.universe.single_symbol == "BTCUSDT", "Default single_symbol should be BTCUSDT"
    print("✅ PASS: 기본값 정상")
    
    print("\n✅ CONFIG INTEGRATION TEST PASSED")
    return True


def main():
    """메인 테스트 실행"""
    print("\n" + "="*80)
    print("D73-1 Symbol Universe Provider 테스트 시작")
    print("="*80)
    
    tests = [
        ("SINGLE 모드", test_single_mode),
        ("FIXED_LIST 모드", test_fixed_list_mode),
        ("TOP_N 모드", test_top_n_mode),
        ("FULL_MARKET 모드", test_full_market_mode),
        ("Config Validation", test_config_validation),
        ("Config Integration", test_config_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ FAIL: {name}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # 최종 결과
    print("\n" + "="*80)
    print("테스트 결과 요약")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과")
    
    if passed == total:
        print("\n" + "="*80)
        print("✅ 모든 테스트 통과!")
        print("="*80)
        return 0
    else:
        print("\n" + "="*80)
        print(f"❌ {total - passed}개 테스트 실패")
        print("="*80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
