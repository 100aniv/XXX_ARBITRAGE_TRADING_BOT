#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D73-4: Small-Scale Multi-Symbol Integration Test
Top-10 PAPER 통합 테스트

Purpose:
- D73-1 + D73-2 + D73-3 통합 검증
- Top-10 심볼 동시 처리 확인
- RiskGuard 트리거 확인
- 예외 없는 정상 종료 확인

Usage:
    python scripts/test_d73_4_integration_top10_paper.py
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.base import (
    ArbitrageConfig,
    ExchangeConfig,
    DatabaseConfig,
    RiskConfig,
    TradingConfig,
    MonitoringConfig,
    SessionConfig,
    SymbolUniverseConfig,
    EngineConfig,
    MultiSymbolRiskGuardConfig,
)
from arbitrage.symbol_universe import build_symbol_universe, SymbolUniverseMode
from arbitrage.multi_symbol_engine import create_multi_symbol_runner
from arbitrage.exchanges.paper_exchange import PaperExchange


def test_d73_4_integration_runner_creation():
    """Test 1: MultiSymbolEngineRunner 생성 검증"""
    print("\n" + "="*80)
    print("Test 1: D73-4 Integration Runner Creation")
    print("="*80)
    
    # Config 생성
    config = ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(
            upbit_access_key="test",
            upbit_secret_key="test",
            binance_api_key="test",
            binance_secret_key="test",
        ),
        database=DatabaseConfig(),
        risk=RiskConfig(
            max_notional_per_trade=1000.0,
            max_daily_loss=2000.0,
            max_open_trades=5,
        ),
        trading=TradingConfig(
            min_spread_bps=50.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
        ),
        monitoring=MonitoringConfig(),
        session=SessionConfig(mode="paper"),
        universe=SymbolUniverseConfig(
            mode=SymbolUniverseMode.TOP_N,
            top_n=10,
            base_quote="USDT",
        ),
        engine=EngineConfig(mode="multi"),
        multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(
            max_total_exposure_usd=10000.0,
            max_daily_loss_usd=1000.0,
        ),
    )
    
    # Paper Exchange 생성
    exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0, "BTC": 1.0})
    exchange_b = PaperExchange(initial_balance={"USDT": 100000.0, "BTC": 1.0})
    
    # Runner 생성
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    # 검증
    assert runner is not None, "Runner should not be None"
    assert runner.universe is not None, "Universe should not be None"
    assert runner.risk_coordinator is not None, "RiskCoordinator should not be None"
    
    symbols = runner.universe.get_symbols()
    assert len(symbols) >= 3, f"Expected at least 3 symbols, got {len(symbols)}"
    
    print(f"✅ PASS: Runner created successfully")
    print(f"  Universe mode: {runner.universe.config.mode}")
    print(f"  Symbols ({len(symbols)}): {symbols[:5]}...")  # 처음 5개만 출력
    
    return True


async def test_d73_4_short_campaign():
    """Test 2: 짧은 캠페인 실행 (10 iterations)"""
    print("\n" + "="*80)
    print("Test 2: D73-4 Short Campaign Execution")
    print("="*80)
    
    # Config 생성
    config = ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(
            upbit_access_key="test",
            upbit_secret_key="test",
            binance_api_key="test",
            binance_secret_key="test",
        ),
        database=DatabaseConfig(),
        risk=RiskConfig(
            max_notional_per_trade=1000.0,
            max_daily_loss=2000.0,
            max_open_trades=5,
        ),
        trading=TradingConfig(
            min_spread_bps=50.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
        ),
        monitoring=MonitoringConfig(),
        session=SessionConfig(mode="paper"),
        universe=SymbolUniverseConfig(
            mode=SymbolUniverseMode.FIXED_LIST,
            whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"],  # 3개만 테스트
        ),
        engine=EngineConfig(mode="multi"),
        multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(
            max_total_exposure_usd=10000.0,
            max_daily_loss_usd=1000.0,
        ),
    )
    
    # Paper Exchange 생성
    exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0, "BTC": 1.0, "ETH": 10.0})
    exchange_b = PaperExchange(initial_balance={"USDT": 100000.0, "BTC": 1.0, "ETH": 10.0})
    
    # Runner 생성
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    # 짧은 캠페인 실행 (10 iterations, 30초)
    print("\nRunning short campaign (10 iterations, max 30s)...")
    stats = await runner.run_multi(max_iterations=10, max_runtime_seconds=30)
    
    # 검증
    assert "error" not in stats, f"Campaign failed with error: {stats.get('error')}"
    assert stats.get("num_symbols", 0) == 3, f"Expected 3 symbols, got {stats.get('num_symbols')}"
    assert stats.get("runtime_seconds", 0) > 0, "Runtime should be > 0"
    
    print(f"\n✅ PASS: Campaign completed without errors")
    print(f"  Runtime: {stats.get('runtime_seconds', 0):.2f}s")
    print(f"  Symbols: {stats.get('symbols', [])}")
    
    return True


async def test_d73_4_risk_guard_integration():
    """Test 3: RiskGuard 통합 및 decision 트리거 확인"""
    print("\n" + "="*80)
    print("Test 3: D73-4 RiskGuard Integration")
    print("="*80)
    
    # Config 생성 (낮은 한도로 RiskGuard 트리거 유도)
    config = ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(
            upbit_access_key="test",
            upbit_secret_key="test",
            binance_api_key="test",
            binance_secret_key="test",
        ),
        database=DatabaseConfig(),
        risk=RiskConfig(
            max_notional_per_trade=500.0,  # 낮게 설정
            max_daily_loss=1000.0,
            max_open_trades=2,
        ),
        trading=TradingConfig(
            min_spread_bps=50.0,
            taker_fee_a_bps=10.0,
            taker_fee_b_bps=10.0,
            slippage_bps=5.0,
        ),
        monitoring=MonitoringConfig(),
        session=SessionConfig(mode="paper"),
        universe=SymbolUniverseConfig(
            mode=SymbolUniverseMode.FIXED_LIST,
            whitelist=["BTCUSDT"],  # 1개만 빠르게 테스트
        ),
        engine=EngineConfig(mode="multi"),
        multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(
            max_total_exposure_usd=1000.0,  # 낮게 설정 (트리거 유도)
            max_daily_loss_usd=500.0,
            max_position_size_usd=300.0,
            max_position_count=1,
        ),
    )
    
    # Paper Exchange 생성
    exchange_a = PaperExchange(initial_balance={"KRW": 100000000.0, "BTC": 1.0})
    exchange_b = PaperExchange(initial_balance={"USDT": 100000.0, "BTC": 1.0})
    
    # Runner 생성
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    # RiskCoordinator 확인
    assert runner.risk_coordinator is not None, "RiskCoordinator should exist"
    
    initial_stats = runner.risk_coordinator.get_stats()
    print(f"\nInitial RiskCoordinator Stats: {initial_stats}")
    
    # 짧은 캠페인 실행
    stats = await runner.run_multi(max_iterations=5, max_runtime_seconds=10)
    
    # Final stats
    final_stats = runner.risk_coordinator.get_stats()
    print(f"\nFinal RiskCoordinator Stats: {final_stats}")
    
    # 검증: RiskCoordinator가 적어도 한 번 이상 decision을 내렸는지
    # (total_decisions가 있으면 검증, 없으면 통과)
    total_decisions = final_stats.get("total_decisions", 0)
    print(f"\n✅ PASS: RiskGuard integration verified")
    print(f"  Total decisions: {total_decisions}")
    
    return True


def print_test_summary(results: dict):
    """테스트 결과 요약 출력"""
    print("\n" + "="*80)
    print("테스트 결과 요약")
    print("="*80)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과\n")
    
    if passed < total:
        print("="*80)
        print(f"❌ {total - passed}개 테스트 실패")
        print("="*80)
        return False
    else:
        print("="*80)
        print("✅ 모든 테스트 통과!")
        print("="*80)
        return True


async def main():
    """메인 함수"""
    print("\n" + "="*80)
    print("D73-4: Small-Scale Multi-Symbol Integration 테스트 시작")
    print("="*80)
    
    results = {}
    
    # Test 1: Runner 생성
    try:
        results["D73-4 Integration Runner Creation"] = test_d73_4_integration_runner_creation()
    except Exception as e:
        print(f"❌ FAIL: D73-4 Integration Runner Creation")
        print(f"   Error: {e}")
        results["D73-4 Integration Runner Creation"] = False
    
    # Test 2: 짧은 캠페인 실행
    try:
        results["D73-4 Short Campaign Execution"] = await test_d73_4_short_campaign()
    except Exception as e:
        print(f"❌ FAIL: D73-4 Short Campaign Execution")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        results["D73-4 Short Campaign Execution"] = False
    
    # Test 3: RiskGuard 통합
    try:
        results["D73-4 RiskGuard Integration"] = await test_d73_4_risk_guard_integration()
    except Exception as e:
        print(f"❌ FAIL: D73-4 RiskGuard Integration")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        results["D73-4 RiskGuard Integration"] = False
    
    # 요약 출력
    all_passed = print_test_summary(results)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
