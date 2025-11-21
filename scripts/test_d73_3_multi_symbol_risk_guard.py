# -*- coding: utf-8 -*-
"""
D73-3: Multi-Symbol RiskGuard 통합 테스트

테스트 항목:
1. GlobalGuard 한도 체크
2. PortfolioGuard 자본 할당
3. SymbolGuard 필터링
4. MultiSymbolRiskCoordinator 3-tier 평가
5. MultiSymbolEngineRunner 통합
6. Config integration
7. D73-1, D73-2 회귀 테스트
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from arbitrage.risk.multi_symbol_risk_guard import (
    GlobalGuard,
    PortfolioGuard,
    SymbolGuard,
    MultiSymbolRiskCoordinator,
    RiskGuardDecision,
)
from arbitrage.symbol_universe import (
    SymbolUniverse,
    SymbolUniverseMode,
    SymbolUniverseConfig,
    DummySymbolSource,
)
from arbitrage.multi_symbol_engine import create_multi_symbol_runner
from arbitrage.exchanges.paper_exchange import PaperExchange
from config.base import (
    ArbitrageConfig,
    ExchangeConfig,
    DatabaseConfig,
    RiskConfig,
    TradingConfig,
    MonitoringConfig,
    SessionConfig,
    EngineConfig,
    MultiSymbolRiskGuardConfig,
)


def test_global_guard():
    """Test 1: GlobalGuard 한도 체크"""
    print("\n" + "="*80)
    print("Test 1: GlobalGuard 한도 체크")
    print("="*80)
    
    guard = GlobalGuard(
        max_total_exposure_usd=1000.0,
        max_daily_loss_usd=100.0,
        emergency_stop_loss_usd=200.0,
    )
    
    # 1-1: 정상 노출
    decision = guard.check_global_limits(additional_exposure_usd=500.0)
    assert decision == RiskGuardDecision.OK, f"Expected OK, got {decision}"
    print("✅ PASS: 정상 노출 허용")
    
    # 1-2: 최대 노출 초과
    guard.state.total_exposure_usd = 900.0
    decision = guard.check_global_limits(additional_exposure_usd=200.0)
    assert decision == RiskGuardDecision.REJECTED_GLOBAL, f"Expected REJECTED_GLOBAL, got {decision}"
    print("✅ PASS: 최대 노출 초과 차단")
    
    # 1-3: 일일 최대 손실 도달
    guard.state.total_exposure_usd = 0.0
    guard.state.total_daily_loss_usd = 100.0
    decision = guard.check_global_limits()
    assert decision == RiskGuardDecision.REJECTED_GLOBAL, f"Expected REJECTED_GLOBAL, got {decision}"
    print("✅ PASS: 일일 최대 손실 도달 차단")
    
    # 1-4: 긴급 중단
    guard.state.total_daily_loss_usd = 200.0
    decision = guard.check_global_limits()
    assert decision == RiskGuardDecision.SESSION_STOP, f"Expected SESSION_STOP, got {decision}"
    print("✅ PASS: 긴급 중단 트리거")
    
    return True


def test_portfolio_guard():
    """Test 2: PortfolioGuard 자본 할당"""
    print("\n" + "="*80)
    print("Test 2: PortfolioGuard 자본 할당")
    print("="*80)
    
    guard = PortfolioGuard(
        total_capital_usd=10000.0,
        max_symbol_allocation_pct=0.3,
    )
    
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    # 2-1: 균등 자본 할당
    allocations = guard.allocate_capital(symbols)
    print(f"\n균등 할당 결과: {allocations}")
    
    # 각 심볼은 최대 30% (3000 USD)
    for symbol, allocated in allocations.items():
        assert allocated <= 3000.0, f"{symbol}: {allocated} > 3000"
    
    print("✅ PASS: 균등 자본 할당")
    
    # 2-2: 가중치 기반 자본 할당
    weights = {"BTCUSDT": 0.5, "ETHUSDT": 0.3, "BNBUSDT": 0.2}
    allocations = guard.allocate_capital(symbols, weights)
    print(f"\n가중치 할당 결과: {allocations}")
    
    # BTC는 50% 요청했지만 30% max로 제한됨 (3000 USD)
    # ETH는 30% 요청으로 30% max (3000 USD)
    # BNB는 20% 요청으로 2000 USD
    # 따라서 BTC == ETH > BNB가 올바름
    assert allocations["BTCUSDT"] == 3000.0, f"Expected 3000.0, got {allocations['BTCUSDT']}"
    assert allocations["ETHUSDT"] == 3000.0, f"Expected 3000.0, got {allocations['ETHUSDT']}"
    assert allocations["BNBUSDT"] == 2000.0, f"Expected 2000.0, got {allocations['BNBUSDT']}"
    assert allocations["BNBUSDT"] < allocations["BTCUSDT"]
    print("✅ PASS: 가중치 기반 자본 할당 (max_allocation 제한 적용)")
    
    # 2-3: 심볼별 할당 한도 체크
    guard.state.symbol_exposures["BTCUSDT"] = 2500.0
    decision = guard.check_symbol_allocation("BTCUSDT", 600.0)
    assert decision == RiskGuardDecision.REJECTED_PORTFOLIO, f"Expected REJECTED_PORTFOLIO, got {decision}"
    print("✅ PASS: 심볼별 할당 한도 체크")
    
    return True


def test_symbol_guard():
    """Test 3: SymbolGuard 필터링"""
    print("\n" + "="*80)
    print("Test 3: SymbolGuard 필터링")
    print("="*80)
    
    guard = SymbolGuard(
        symbol="BTCUSDT",
        max_position_size_usd=1000.0,
        max_position_count=3,
        cooldown_seconds=10.0,
        max_symbol_daily_loss_usd=200.0,
        circuit_breaker_loss_count=3,
        circuit_breaker_duration=60.0,
    )
    
    # 3-1: 정상 진입
    decision = guard.check_symbol_limits(position_size_usd=500.0)
    assert decision == RiskGuardDecision.OK, f"Expected OK, got {decision}"
    print("✅ PASS: 정상 진입 허용")
    
    # 3-2: 포지션 크기 초과
    decision = guard.check_symbol_limits(position_size_usd=1500.0)
    assert decision == RiskGuardDecision.REJECTED_SYMBOL, f"Expected REJECTED_SYMBOL, got {decision}"
    print("✅ PASS: 포지션 크기 초과 차단")
    
    # 3-3: 포지션 수 초과
    guard.state.current_position_count = 3
    decision = guard.check_symbol_limits(position_size_usd=500.0)
    assert decision == RiskGuardDecision.REJECTED_SYMBOL, f"Expected REJECTED_SYMBOL, got {decision}"
    print("✅ PASS: 포지션 수 초과 차단")
    
    # 3-4: 쿨다운 테스트
    guard.state.current_position_count = 0
    guard.on_entry(500.0)
    decision = guard.check_symbol_limits(position_size_usd=500.0)
    assert decision == RiskGuardDecision.REJECTED_SYMBOL, f"Expected REJECTED_SYMBOL (cooldown), got {decision}"
    print("✅ PASS: 쿨다운 차단")
    
    # 3-5: Circuit breaker 테스트
    guard.state.cooldown_until = 0.0
    # 연속 3회 손실 발생
    guard.on_exit(-50.0)
    guard.on_exit(-50.0)
    guard.on_exit(-50.0)
    
    # Circuit breaker 발동 확인
    assert guard.state.circuit_breaker_triggered, "Circuit breaker should be triggered"
    decision = guard.check_symbol_limits(position_size_usd=500.0)
    assert decision == RiskGuardDecision.REJECTED_SYMBOL, f"Expected REJECTED_SYMBOL (circuit breaker), got {decision}"
    print("✅ PASS: Circuit breaker 트리거")
    
    return True


def test_risk_coordinator():
    """Test 4: MultiSymbolRiskCoordinator 3-tier 평가"""
    print("\n" + "="*80)
    print("Test 4: MultiSymbolRiskCoordinator 3-tier 평가")
    print("="*80)
    
    global_guard = GlobalGuard(
        max_total_exposure_usd=10000.0,
        max_daily_loss_usd=500.0,
    )
    
    portfolio_guard = PortfolioGuard(
        total_capital_usd=10000.0,
        max_symbol_allocation_pct=0.3,
    )
    
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    portfolio_guard.allocate_capital(symbols)
    
    coordinator = MultiSymbolRiskCoordinator(
        global_guard=global_guard,
        portfolio_guard=portfolio_guard,
        symbols=symbols,
        symbol_guard_config={
            "max_position_size_usd": 1000.0,
            "max_position_count": 3,
            "cooldown_seconds": 10.0,
        },
    )
    
    # 4-1: 정상 거래 허용
    decision = coordinator.check_trade_allowed("BTCUSDT", 500.0)
    assert decision == RiskGuardDecision.OK, f"Expected OK, got {decision}"
    print("✅ PASS: 정상 거래 허용 (3-tier 통과)")
    
    # 4-2: 진입/청산 이벤트 처리
    coordinator.on_trade_entry("BTCUSDT", 500.0)
    assert coordinator.global_guard.state.total_exposure_usd == 500.0
    print("✅ PASS: 진입 이벤트 처리")
    
    coordinator.on_trade_exit("BTCUSDT", 500.0, 50.0)
    assert coordinator.global_guard.state.total_exposure_usd == 0.0
    print("✅ PASS: 청산 이벤트 처리")
    
    # 4-3: Global Guard 거부
    coordinator.global_guard.state.total_exposure_usd = 9000.0
    decision = coordinator.check_trade_allowed("ETHUSDT", 2000.0)
    assert decision == RiskGuardDecision.REJECTED_GLOBAL, f"Expected REJECTED_GLOBAL, got {decision}"
    print("✅ PASS: Global Guard 거부")
    
    # 4-4: Portfolio Guard 거부
    coordinator.global_guard.state.total_exposure_usd = 0.0
    coordinator.portfolio_guard.state.symbol_exposures["BTCUSDT"] = 2900.0
    decision = coordinator.check_trade_allowed("BTCUSDT", 200.0)
    assert decision == RiskGuardDecision.REJECTED_PORTFOLIO, f"Expected REJECTED_PORTFOLIO, got {decision}"
    print("✅ PASS: Portfolio Guard 거부")
    
    # 4-5: Symbol Guard 거부
    coordinator.portfolio_guard.state.symbol_exposures["BTCUSDT"] = 0.0
    symbol_guard = coordinator.get_symbol_guard("BTCUSDT")
    symbol_guard.on_entry(500.0)  # 쿨다운 시작
    decision = coordinator.check_trade_allowed("BTCUSDT", 500.0)
    assert decision == RiskGuardDecision.REJECTED_SYMBOL, f"Expected REJECTED_SYMBOL, got {decision}"
    print("✅ PASS: Symbol Guard 거부 (쿨다운)")
    
    # 4-6: 통계 조회
    stats = coordinator.get_stats()
    assert "global" in stats
    assert "portfolio" in stats
    assert "symbols" in stats
    assert "BTCUSDT" in stats["symbols"]
    print("✅ PASS: 통계 조회")
    
    return True


def test_config_integration():
    """Test 5: Config Integration"""
    print("\n" + "="*80)
    print("Test 5: Config Integration")
    print("="*80)
    
    # Config 생성
    config = ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(
            upbit_access_key="test",
            upbit_secret_key="test",
            binance_api_key="test",
            binance_secret_key="test"
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
        session=SessionConfig(),
        engine=EngineConfig(mode="multi"),
        multi_symbol_risk_guard=MultiSymbolRiskGuardConfig(
            max_total_exposure_usd=5000.0,
            max_daily_loss_usd=250.0,
            total_capital_usd=5000.0,
            max_position_size_usd=500.0,
        ),
    )
    
    # Config 검증
    assert hasattr(config, 'multi_symbol_risk_guard'), "Config should have multi_symbol_risk_guard field"
    assert config.multi_symbol_risk_guard.max_total_exposure_usd == 5000.0
    assert config.multi_symbol_risk_guard.max_daily_loss_usd == 250.0
    print("✅ PASS: Config 필드 존재 및 값 검증")
    
    # create_multi_symbol_runner 테스트
    exchange_a = PaperExchange(initial_balance={"KRW": 10000000.0, "BTC": 0.1})
    exchange_b = PaperExchange(initial_balance={"USDT": 10000.0, "BTC": 0.1})
    
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    assert runner.risk_coordinator is not None, "Runner should have risk_coordinator"
    print("✅ PASS: create_multi_symbol_runner with RiskCoordinator")
    
    # RiskCoordinator 검증
    assert runner.risk_coordinator.global_guard.max_total_exposure_usd == 5000.0
    assert runner.risk_coordinator.portfolio_guard.total_capital_usd == 5000.0
    print("✅ PASS: RiskCoordinator 설정 검증")
    
    return True


def test_d73_1_regression():
    """Test 6: D73-1 회귀 테스트"""
    print("\n" + "="*80)
    print("Test 6: D73-1 Symbol Universe 회귀 테스트")
    print("="*80)
    
    # SINGLE 모드
    config_single = SymbolUniverseConfig(
        mode=SymbolUniverseMode.SINGLE,
        single_symbol="BTCUSDT",
    )
    universe = SymbolUniverse(config_single, DummySymbolSource())
    symbols = universe.get_symbols()
    assert symbols == ["BTCUSDT"], f"Expected ['BTCUSDT'], got {symbols}"
    print("✅ PASS: SINGLE 모드")
    
    # FIXED_LIST 모드
    config_list = SymbolUniverseConfig(
        mode=SymbolUniverseMode.FIXED_LIST,
        whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
    )
    universe = SymbolUniverse(config_list, DummySymbolSource())
    symbols = universe.get_symbols()
    assert len(symbols) == 3, f"Expected 3 symbols, got {len(symbols)}"
    print("✅ PASS: FIXED_LIST 모드")
    
    # TOP_N 모드
    config_topn = SymbolUniverseConfig(
        mode=SymbolUniverseMode.TOP_N,
        top_n=5,
        blacklist=["BUSDUSDT", "USDCUSDT"],
    )
    universe = SymbolUniverse(config_topn, DummySymbolSource())
    symbols = universe.get_symbols()
    assert len(symbols) == 5, f"Expected 5 symbols, got {len(symbols)}"
    print("✅ PASS: TOP_N 모드")
    
    return True


def test_d73_2_regression():
    """Test 7: D73-2 회귀 테스트"""
    print("\n" + "="*80)
    print("Test 7: D73-2 Multi-Symbol Engine 회귀 테스트")
    print("="*80)
    
    # Config 생성
    config = ArbitrageConfig(
        env="development",
        exchange=ExchangeConfig(
            upbit_access_key="test",
            upbit_secret_key="test",
            binance_api_key="test",
            binance_secret_key="test"
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
        session=SessionConfig(),
        engine=EngineConfig(mode="multi"),
        universe=SymbolUniverseConfig(
            mode=SymbolUniverseMode.FIXED_LIST,
            whitelist=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        ),
    )
    
    exchange_a = PaperExchange(initial_balance={"KRW": 10000000.0, "BTC": 0.1})
    exchange_b = PaperExchange(initial_balance={"USDT": 10000.0, "BTC": 0.1})
    
    runner = create_multi_symbol_runner(
        config=config,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
    )
    
    # Runner 검증
    assert runner.universe is not None
    assert runner.risk_coordinator is not None
    symbols = runner.universe.get_symbols()
    assert len(symbols) == 3, f"Expected 3 symbols, got {len(symbols)}"
    print("✅ PASS: MultiSymbolEngineRunner 생성")
    
    return True


def main():
    """메인 테스트 실행"""
    print("="*80)
    print("D73-3: Multi-Symbol RiskGuard 통합 테스트 시작")
    print("="*80)
    
    tests = [
        ("GlobalGuard 한도 체크", test_global_guard),
        ("PortfolioGuard 자본 할당", test_portfolio_guard),
        ("SymbolGuard 필터링", test_symbol_guard),
        ("MultiSymbolRiskCoordinator 3-tier 평가", test_risk_coordinator),
        ("Config Integration", test_config_integration),
        ("D73-1 회귀 테스트", test_d73_1_regression),
        ("D73-2 회귀 테스트", test_d73_2_regression),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                print(f"\n✅ PASS: {test_name}")
            else:
                failed += 1
                print(f"\n❌ FAIL: {test_name}")
        except Exception as e:
            failed += 1
            print(f"\n❌ FAIL: {test_name}")
            print(f"   Error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("테스트 결과 요약")
    print("="*80)
    for test_name, _ in tests:
        status = "✅ PASS" if test_name in [t[0] for t in tests[:passed]] else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n총 {len(tests)}개 테스트 중 {passed}개 통과")
    
    if failed == 0:
        print("\n" + "="*80)
        print("✅ 모든 테스트 통과!")
        print("="*80)
        return 0
    else:
        print("\n" + "="*80)
        print(f"❌ {failed}개 테스트 실패")
        print("="*80)
        return 1


if __name__ == "__main__":
    exit(main())
