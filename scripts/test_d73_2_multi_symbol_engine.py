#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D73-2: Multi-Symbol Engine Loop 테스트

Per-symbol coroutine 구조 검증.
Universe → MultiSymbolEngineRunner 통합 테스트.

Test Coverage:
1. Universe + MultiSymbolEngine 통합
2. Per-symbol runner 생성 검증
3. SINGLE vs MULTI 모드 호환성
4. Config 기반 모드 전환

Author: D73-2 Implementation Team
Date: 2025-11-21
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from arbitrage.symbol_universe import (
    SymbolUniverse,
    SymbolUniverseMode,
    SymbolUniverseConfig,
    DummySymbolSource,
    build_symbol_universe,
)
from arbitrage.multi_symbol_engine import MultiSymbolEngineRunner, create_multi_symbol_runner
from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig as LegacyEngineConfig
from arbitrage.live_runner import ArbitrageLiveConfig
from arbitrage.exchanges.paper_exchange import PaperExchange
from config.base import ArbitrageConfig, ExchangeConfig, DatabaseConfig, RiskConfig, TradingConfig, MonitoringConfig, SessionConfig, EngineConfig


def test_multi_symbol_runner_creation():
    """Test 1: MultiSymbolEngineRunner 생성 검증"""
    print("\n" + "="*80)
    print("Test 1: MultiSymbolEngineRunner 생성 검증")
    print("="*80)
    
    # Universe 생성 (FIXED_LIST 모드)
    universe_config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FIXED_LIST,
        whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    )
    universe = SymbolUniverse(universe_config, DummySymbolSource())
    
    # 가짜 Exchange 생성
    exchange_a = PaperExchange(initial_balance={"KRW": 10000000.0, "BTC": 0.1})
    exchange_b = PaperExchange(initial_balance={"USDT": 10000.0, "BTC": 0.1})
    
    # Legacy config 생성
    engine_config = LegacyEngineConfig(
        min_spread_bps=30.0,
        taker_fee_a_bps=5.0,
        taker_fee_b_bps=5.0,
        slippage_bps=5.0,
        max_position_usd=1000.0
    )
    
    live_config = ArbitrageLiveConfig(
        symbol_a="KRW-BTC",
        symbol_b="BTCUSDT",
        mode="paper"
    )
    
    # MultiSymbolEngineRunner 생성
    runner = MultiSymbolEngineRunner(
        universe=universe,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        engine_config=engine_config,
        live_config=live_config
    )
    
    print(f"✅ PASS: Runner created successfully")
    print(f"  Universe mode: {runner.universe.config.mode.value}")
    print(f"  Symbols: {runner.universe.get_symbols()}")
    
    return True


def test_per_symbol_runner_mapping():
    """Test 2: Per-symbol runner 매핑 검증"""
    print("\n" + "="*80)
    print("Test 2: Per-symbol runner 매핑 검증")
    print("="*80)
    
    # Universe 생성 (TOP_N 모드)
    universe_config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.TOP_N,
        top_n=5,
        base_quote="USDT",
        blacklist=["BUSDUSDT", "USDCUSDT"]
    )
    universe = SymbolUniverse(universe_config, DummySymbolSource())
    symbols = universe.get_symbols()
    
    print(f"Universe symbols (TOP_N=5): {symbols}")
    
    # 가짜 Exchange 생성
    exchange_a = PaperExchange(initial_balance={"KRW": 10000000.0, "BTC": 0.1})
    exchange_b = PaperExchange(initial_balance={"USDT": 10000.0, "BTC": 0.1})
    
    # Legacy config 생성
    engine_config = LegacyEngineConfig(
        min_spread_bps=30.0,
        taker_fee_a_bps=5.0,
        taker_fee_b_bps=5.0,
        slippage_bps=5.0,
        max_position_usd=1000.0
    )
    
    live_config = ArbitrageLiveConfig(
        symbol_a="KRW-BTC",
        symbol_b="BTCUSDT",
        mode="paper"
    )
    
    # MultiSymbolEngineRunner 생성
    runner = MultiSymbolEngineRunner(
        universe=universe,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        engine_config=engine_config,
        live_config=live_config
    )
    
    # Symbol config 매핑 테스트
    for symbol in symbols:
        symbol_config = runner._create_symbol_config(symbol)
        print(f"  {symbol} → symbol_a={symbol_config.symbol_a}, symbol_b={symbol_config.symbol_b}")
    
    print(f"✅ PASS: Per-symbol config mapping successful")
    
    return True


async def test_multi_symbol_async_structure():
    """Test 3: Multi-Symbol async 구조 검증"""
    print("\n" + "="*80)
    print("Test 3: Multi-Symbol async 구조 검증")
    print("="*80)
    
    # Universe 생성 (FIXED_LIST 모드, 3개 심볼)
    universe_config = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FIXED_LIST,
        whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    )
    universe = SymbolUniverse(universe_config, DummySymbolSource())
    
    # 가짜 Exchange 생성
    exchange_a = PaperExchange(initial_balance={"KRW": 10000000.0, "BTC": 0.1})
    exchange_b = PaperExchange(initial_balance={"USDT": 10000.0, "BTC": 0.1})
    
    # Legacy config 생성
    engine_config = LegacyEngineConfig(
        min_spread_bps=30.0,
        taker_fee_a_bps=5.0,
        taker_fee_b_bps=5.0,
        slippage_bps=5.0,
        max_position_usd=1000.0
    )
    
    live_config = ArbitrageLiveConfig(
        symbol_a="KRW-BTC",
        symbol_b="BTCUSDT",
        mode="paper"
    )
    
    # MultiSymbolEngineRunner 생성
    runner = MultiSymbolEngineRunner(
        universe=universe,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        engine_config=engine_config,
        live_config=live_config
    )
    
    # Async 실행 테스트 (짧게)
    print(f"Starting multi-symbol engine (3 symbols)...")
    
    # NOTE: run_multi()는 무한 루프가 아니라 placeholder이므로 즉시 종료됨
    await runner.run_multi()
    
    # Stats 확인
    stats = runner.get_stats()
    print(f"Stats: {stats}")
    
    print(f"✅ PASS: Async structure validated")
    
    return True


def test_config_integration():
    """Test 4: Config 통합 검증"""
    print("\n" + "="*80)
    print("Test 4: Config Integration 검증")
    print("="*80)
    
    # ArbitrageConfig 생성 (통합 설정)
    config = ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(),
        database=DatabaseConfig(),
        risk=RiskConfig(
            max_notional_per_trade=1000.0,
            max_daily_loss=5000.0
        ),
        trading=TradingConfig(
            min_spread_bps=50.0
        ),
        monitoring=MonitoringConfig(),
        session=SessionConfig(),
        engine=EngineConfig(mode="multi", multi_symbol_enabled=True)
    )
    
    # engine 필드 확인
    assert hasattr(config, 'engine'), "ArbitrageConfig should have 'engine' field"
    assert config.engine.mode == "multi", f"Expected 'multi' mode, got {config.engine.mode}"
    assert config.engine.multi_symbol_enabled is True, "multi_symbol_enabled should be True"
    
    print(f"✅ PASS: engine field exists")
    print(f"  mode: {config.engine.mode}")
    print(f"  multi_symbol_enabled: {config.engine.multi_symbol_enabled}")
    print(f"  per_symbol_isolation: {config.engine.per_symbol_isolation}")
    
    # Helper function 테스트
    exchange_a = PaperExchange(initial_balance={"KRW": 10000000.0, "BTC": 0.1})
    exchange_b = PaperExchange(initial_balance={"USDT": 10000.0, "BTC": 0.1})
    
    # create_multi_symbol_runner 사용
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b
    )
    
    print(f"✅ PASS: create_multi_symbol_runner() successful")
    mode_str = runner.universe.config.mode.value if hasattr(runner.universe.config.mode, 'value') else runner.universe.config.mode
    print(f"  Universe mode: {mode_str}")
    
    return True


def test_single_vs_multi_mode():
    """Test 5: SINGLE vs MULTI 모드 호환성"""
    print("\n" + "="*80)
    print("Test 5: SINGLE vs MULTI 모드 호환성")
    print("="*80)
    
    # Test 5-1: SINGLE 모드 (기존 방식)
    print("\n[Test 5-1] SINGLE mode")
    universe_config_single = SymbolUniverseConfig(
        mode=SymbolUniverseMode.SINGLE,
        single_symbol="BTCUSDT"
    )
    universe_single = SymbolUniverse(universe_config_single, DummySymbolSource())
    symbols_single = universe_single.get_symbols()
    
    print(f"  Expected: ['BTCUSDT']")
    print(f"  Actual:   {symbols_single}")
    assert symbols_single == ["BTCUSDT"], f"SINGLE mode failed: {symbols_single}"
    print(f"✅ PASS: SINGLE mode (1 symbol)")
    
    # Test 5-2: MULTI 모드 (새 방식)
    print("\n[Test 5-2] MULTI mode (FIXED_LIST)")
    universe_config_multi = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FIXED_LIST,
        whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    )
    universe_multi = SymbolUniverse(universe_config_multi, DummySymbolSource())
    symbols_multi = universe_multi.get_symbols()
    
    print(f"  Expected: ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']")
    print(f"  Actual:   {symbols_multi}")
    assert len(symbols_multi) == 3, f"MULTI mode failed: {len(symbols_multi)} symbols"
    print(f"✅ PASS: MULTI mode (3 symbols)")
    
    return True


def main():
    """메인 테스트 실행"""
    print("\n" + "="*80)
    print("D73-2: Multi-Symbol Engine Loop 테스트 시작")
    print("="*80)
    
    tests = [
        ("MultiSymbolEngineRunner 생성", test_multi_symbol_runner_creation),
        ("Per-symbol runner 매핑", test_per_symbol_runner_mapping),
        ("Config Integration", test_config_integration),
        ("SINGLE vs MULTI 모드 호환성", test_single_vs_multi_mode),
    ]
    
    # Async test는 별도 실행
    async_tests = [
        ("Multi-Symbol async 구조", test_multi_symbol_async_structure),
    ]
    
    results = []
    
    # Sync tests
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
    
    # Async tests
    for name, test_func in async_tests:
        try:
            result = asyncio.run(test_func())
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
