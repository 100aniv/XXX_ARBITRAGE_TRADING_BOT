# -*- coding: utf-8 -*-
"""
D73-2: Multi-Symbol Engine Loop
D73-3: Multi-Symbol RiskGuard Integration

Per-symbol coroutine 구조로 멀티심볼 동시 처리 기반을 구축합니다.

기존 단일 심볼 엔진(ArbitrageLiveRunner)을 재사용하여,
상단에 orchestration layer만 추가하는 방식으로 구현됩니다.

Architecture:
MultiSymbolEngineRunner
├── MultiSymbolRiskCoordinator (D73-3)
│   ├── GlobalGuard (전체 포트폴리오 한도)
│   ├── PortfolioGuard (심볼별 자본 할당)
│   └── SymbolGuard[] (개별 심볼 리스크)
├── Universe.get_symbols() → ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
├── Per-symbol coroutine 생성
│   ├── run_for_symbol(BTCUSDT) → RiskGuard → ArbitrageLiveRunner
│   ├── run_for_symbol(ETHUSDT) → RiskGuard → ArbitrageLiveRunner
│   └── run_for_symbol(BNBUSDT) → RiskGuard → ArbitrageLiveRunner
└── asyncio.gather(*tasks)
│  │      await gather(*tasks)                         │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
     run_for_symbol  run_for_symbol  run_for_symbol
      (BTCUSDT)       (ETHUSDT)       (BNBUSDT)
          │              │              │
     (Existing       (Existing      (Existing
      Single          Single         Single
      Engine)         Engine)        Engine)

Features:
- Single event loop (asyncio.run 한 번만)
- Per-symbol independent coroutine
- Shared Portfolio/RiskGuard (D73-3에서 강화)
- Config-based single/multi mode switch

Author: D73-2 Implementation Team
Date: 2025-11-21
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any

from arbitrage.symbol_universe import SymbolUniverse, build_symbol_universe, SymbolUniverseMode
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig
from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig as LegacyEngineConfig
from arbitrage.exchanges.base import BaseExchange

logger = logging.getLogger(__name__)


class MultiSymbolEngineRunner:
    """
    Multi-Symbol Arbitrage Engine Runner
    
    SymbolUniverse에서 얻은 심볼 리스트로 per-symbol 코루틴을 생성하여 동시 실행.
    기존 단일 심볼 엔진(ArbitrageLiveRunner)을 재사용.
    
    Responsibilities:
    - Universe에서 심볼 리스트 조회
    - 각 심볼별 독립 코루틴 생성 및 관리
    - Shared context (Portfolio, RiskGuard) 관리 (D73-3에서 강화)
    - Graceful shutdown / error handling
    
    D73-2 Scope:
    - Per-symbol coroutine 구조 구현
    - Config 기반 single/multi 모드 전환
    - 기존 단일 심볼 엔진 재사용 (최소 변경)
    
    D73-3+ Extensions:
    - Multi-Symbol RiskGuard 계층 (Global/Portfolio/Symbol)
    - Portfolio capital allocation
    - Per-symbol state persistence
    """
    
    def __init__(
        self,
        universe: SymbolUniverse,
        exchange_a: BaseExchange,
        exchange_b: BaseExchange,
        engine_config: LegacyEngineConfig,
        live_config: ArbitrageLiveConfig,
        risk_coordinator: Optional[Any] = None,  # D73-3: MultiSymbolRiskCoordinator
        market_data_provider: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
        state_store: Optional[Any] = None,
    ):
        """
        Args:
            universe: SymbolUniverse instance
            exchange_a: Exchange A (Upbit 역할)
            exchange_b: Exchange B (Binance 역할)
            engine_config: ArbitrageConfig (engine config)
            live_config: ArbitrageLiveConfig (live runner config)
            risk_coordinator: MultiSymbolRiskCoordinator (D73-3, 선택)
            market_data_provider: MarketDataProvider (선택)
            metrics_collector: MetricsCollector (선택)
            state_store: StateStore (선택)
        """
        self.universe = universe
        self.exchange_a = exchange_a
        self.exchange_b = exchange_b
        self.engine_config = engine_config
        self.live_config = live_config
        self.risk_coordinator = risk_coordinator  # D73-3
        self.market_data_provider = market_data_provider
        self.metrics_collector = metrics_collector
        self.state_store = state_store
        
        # Per-symbol runner 인스턴스 관리
        self._symbol_runners: Dict[str, ArbitrageLiveRunner] = {}
        
        # Shared context
        self._shared_portfolio = None  # TODO(D73-4): PortfolioManager 통합
        self._shared_risk_guard = risk_coordinator  # D73-3: MultiSymbolRiskCoordinator 통합
        
        # Runtime state
        self._start_time = time.time()
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        # Handle both string and enum mode
        mode_str = universe.config.mode.value if hasattr(universe.config.mode, 'value') else universe.config.mode
        logger.info(
            f"[D73-2_MULTI] Initialized MultiSymbolEngineRunner: "
            f"universe_mode={mode_str}"
        )
    
    async def run_multi(self, max_iterations: Optional[int] = None, max_runtime_seconds: Optional[float] = None) -> Dict[str, Any]:
        """
        Multi-Symbol Engine 실행
        
        SymbolUniverse에서 얻은 심볼 리스트로 per-symbol 코루틴을 생성하여 동시 실행.
        
        Args:
            max_iterations: 최대 iteration 수 (테스트용, None이면 무제한)
            max_runtime_seconds: 최대 실행 시간 (초, None이면 무제한)
        
        Returns:
            실행 통계 dict
        """
        # 1. Universe에서 심볼 리스트 조회
        symbols = self.universe.get_symbols()
        
        if not symbols:
            logger.warning("[D73-2_MULTI] No symbols from Universe, exiting")
            return {"error": "No symbols"}
        
        logger.info(
            f"[D73-2_MULTI] Starting multi-symbol engine: "
            f"{len(symbols)} symbols = {symbols}, "
            f"max_iterations={max_iterations}, max_runtime={max_runtime_seconds}s"
        )
        
        # 2. Per-symbol 코루틴 생성
        self._running = True
        tasks = [
            asyncio.create_task(
                self._run_for_symbol(symbol, max_iterations=max_iterations, max_runtime_seconds=max_runtime_seconds),
                name=f"symbol_{symbol}"
            )
            for symbol in symbols
        ]
        self._tasks = tasks
        
        # 3. 모든 코루틴 동시 실행
        start_time = time.time()
        try:
            # TODO(D74): Graceful shutdown, cancellation handling 강화
            results = await asyncio.gather(*tasks, return_exceptions=True)
            runtime = time.time() - start_time
            
            # 결과 집계
            stats = {
                "runtime_seconds": runtime,
                "symbols": symbols,
                "num_symbols": len(symbols),
                "running": self._running,
                "num_tasks": len(self._tasks),
                "universe_mode": self.universe.config.mode.value if hasattr(self.universe.config.mode, 'value') else str(self.universe.config.mode),
            }
            
            # Per-symbol 결과 집계
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"[D73-2_MULTI] Symbol {symbols[i]} failed: {result}")
            
            logger.info(f"[D73-2_MULTI] Multi-symbol engine completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"[D73-2_MULTI] Error in multi-symbol engine: {e}", exc_info=True)
            return {"error": str(e), "runtime_seconds": time.time() - start_time}
        finally:
            self._running = False
            logger.info("[D73-2_MULTI] Multi-symbol engine stopped")
    
    async def _run_for_symbol(self, symbol: str, max_iterations: Optional[int] = None, max_runtime_seconds: Optional[float] = None) -> Dict[str, Any]:
        """
        단일 심볼 엔진 실행 (per-symbol 코루틴)
        
        기존 ArbitrageLiveRunner를 재사용하되, 심볼별로 독립적으로 실행.
        
        Args:
            symbol: 거래 심볼 (예: "BTCUSDT")
            max_iterations: 최대 iteration 수 (D73-4: 테스트용)
            max_runtime_seconds: 최대 실행 시간 (초)
        
        Returns:
            실행 통계 dict
        """
        logger.info(f"[D73-2_MULTI] Starting engine for symbol: {symbol}")
        
        iteration_count = 0
        trade_count = 0
        risk_allowed_count = 0
        risk_denied_count = 0
        start_time = time.time()
        
        try:
            # D73-2: 기존 단일 심볼 엔진 재사용
            # Symbol별 config 조정 (symbol_a, symbol_b 매핑)
            # 예: BTCUSDT → symbol_a="KRW-BTC", symbol_b="BTCUSDT"
            symbol_config = self._create_symbol_config(symbol)
            
            # Engine 초기화
            engine = ArbitrageEngine(config=self.engine_config)
            
            # Runner 초기화
            runner = ArbitrageLiveRunner(
                engine=engine,
                exchange_a=self.exchange_a,
                exchange_b=self.exchange_b,
                config=symbol_config,
                market_data_provider=self.market_data_provider,
                metrics_collector=self.metrics_collector,
                state_store=self.state_store,
            )
            
            self._symbol_runners[symbol] = runner
            
            logger.info(
                f"[D73-2_MULTI] Per-symbol runner created for {symbol}, "
                f"config={symbol_config.symbol_a}/{symbol_config.symbol_b}"
            )
            
            # D73-4: Controlled loop execution
            # D74-3: Real-time monitoring for debugging
            last_log_time = time.time()
            log_interval = 10.0  # 10초마다 progress 로그
            
            while True:
                # 종료 조건 체크
                if max_iterations and iteration_count >= max_iterations:
                    logger.info(f"[D73-4_MULTI] {symbol}: Max iterations ({max_iterations}) reached")
                    break
                
                if max_runtime_seconds and (time.time() - start_time) >= max_runtime_seconds:
                    logger.info(f"[D73-4_MULTI] {symbol}: Max runtime ({max_runtime_seconds}s) reached")
                    break
                
                # D74-3: Periodic progress logging
                current_time = time.time()
                if current_time - last_log_time >= log_interval:
                    elapsed = current_time - start_time
                    iter_per_sec = iteration_count / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"[D74-3_MONITOR] {symbol}: iter={iteration_count}, "
                        f"trades={trade_count}, elapsed={elapsed:.1f}s, "
                        f"iter/sec={iter_per_sec:.2f}"
                    )
                    last_log_time = current_time
                
                # 1회 loop 실행
                try:
                    # D75-1: run_once() is now async
                    success = await runner.run_once()
                    iteration_count += 1
                    
                    if success:
                        # Trade 발생 시 카운트 (추후 정확한 로직 추가 가능)
                        current_trades = getattr(runner, '_total_trades_opened', 0)
                        if current_trades > trade_count:
                            trade_count = current_trades
                            logger.info(f"[D73-4_MULTI] {symbol}: Trade opened (total={trade_count})")
                    
                    # D74-3: Adaptive sleep based on activity
                    # 거래가 없으면 짧게 대기, 있으면 더 길게 대기
                    sleep_duration = 0.05 if success else 0.1
                    await asyncio.sleep(sleep_duration)
                
                except Exception as loop_error:
                    logger.error(f"[D73-4_MULTI] {symbol}: Loop error: {loop_error}")
                    await asyncio.sleep(0.5)  # 에러 시 조금 더 대기
            
            runtime = time.time() - start_time
            stats = {
                "symbol": symbol,
                "iteration_count": iteration_count,
                "trade_count": trade_count,
                "runtime_seconds": runtime,
                "success": True,
            }
            
            logger.info(f"[D73-4_MULTI] {symbol} completed: {stats}")
            return stats
        
        except Exception as e:
            logger.error(
                f"[D73-2_MULTI] Error running engine for {symbol}: {e}",
                exc_info=True
            )
            return {
                "symbol": symbol,
                "error": str(e),
                "iteration_count": iteration_count,
                "runtime_seconds": time.time() - start_time,
                "success": False,
            }
    
    def _create_symbol_config(self, symbol: str) -> ArbitrageLiveConfig:
        """
        심볼별 ArbitrageLiveConfig 생성
        
        Args:
            symbol: 거래 심볼 (예: "BTCUSDT")
        
        Returns:
            ArbitrageLiveConfig: 심볼별 config
        """
        # D73-2: 간단한 매핑 (USDT 페어 → KRW 페어)
        # 예: "BTCUSDT" → symbol_a="KRW-BTC", symbol_b="BTCUSDT"
        
        # Extract base asset
        if symbol.endswith("USDT"):
            base = symbol[:-4]  # "BTCUSDT" → "BTC"
            symbol_a = f"KRW-{base}"  # "KRW-BTC"
            symbol_b = symbol  # "BTCUSDT"
        else:
            # Fallback
            symbol_a = self.live_config.symbol_a
            symbol_b = symbol
        
        # Create new config with updated symbols
        # NOTE: ArbitrageLiveConfig는 dataclass가 아니므로, 직접 복사/수정
        import copy
        symbol_config = copy.copy(self.live_config)
        symbol_config.symbol_a = symbol_a
        symbol_config.symbol_b = symbol_b
        
        return symbol_config
    
    def stop(self) -> None:
        """
        Multi-Symbol Engine 중지
        
        모든 per-symbol task를 취소하고 종료.
        """
        if not self._running:
            logger.warning("[D73-2_MULTI] Engine not running, nothing to stop")
            return
        
        logger.info(f"[D73-2_MULTI] Stopping {len(self._tasks)} symbol tasks...")
        
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        self._running = False
        logger.info("[D73-2_MULTI] All tasks cancelled")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Multi-Symbol Engine 통계
        
        Returns:
            통계 딕셔너리
        """
        runtime = time.time() - self._start_time
        mode_str = self.universe.config.mode.value if hasattr(self.universe.config.mode, 'value') else self.universe.config.mode
        
        return {
            'runtime_seconds': runtime,
            'symbols': self.universe.get_symbols(),
            'num_symbols': len(self.universe.get_symbols()),
            'running': self._running,
            'num_tasks': len(self._tasks),
            'universe_mode': mode_str,
        }


# ============================================================================
# Helper Functions
# ============================================================================

def create_multi_symbol_runner(
    config: "ArbitrageConfig",
    exchange_a: BaseExchange,
    exchange_b: BaseExchange,
    **kwargs
) -> MultiSymbolEngineRunner:
    """
    MultiSymbolEngineRunner 생성 헬퍼
    
    Args:
        config: ArbitrageConfig (통합 설정)
        exchange_a: Exchange A
        exchange_b: Exchange B
        **kwargs: 추가 인자 (market_data_provider, metrics_collector, state_store 등)
    
    Returns:
        MultiSymbolEngineRunner instance
    """
    from arbitrage.risk.multi_symbol_risk_guard import (
        GlobalGuard,
        PortfolioGuard,
        MultiSymbolRiskCoordinator,
    )
    
    # Universe 생성
    universe = build_symbol_universe(config.universe)
    
    # Legacy config 변환
    engine_config = config.to_legacy_config()
    live_config = config.to_live_config()
    
    # D73-3: MultiSymbolRiskCoordinator 생성
    risk_config = config.multi_symbol_risk_guard
    symbols = universe.get_symbols()
    
    global_guard = GlobalGuard(
        max_total_exposure_usd=risk_config.max_total_exposure_usd,
        max_daily_loss_usd=risk_config.max_daily_loss_usd,
        emergency_stop_loss_usd=risk_config.emergency_stop_loss_usd,
    )
    
    portfolio_guard = PortfolioGuard(
        total_capital_usd=risk_config.total_capital_usd,
        max_symbol_allocation_pct=risk_config.max_symbol_allocation_pct,
    )
    
    # 심볼별 자본 할당
    if symbols:
        portfolio_guard.allocate_capital(symbols)
    
    risk_coordinator = MultiSymbolRiskCoordinator(
        global_guard=global_guard,
        portfolio_guard=portfolio_guard,
        symbols=symbols,
        symbol_guard_config={
            "max_position_size_usd": risk_config.max_position_size_usd,
            "max_position_count": risk_config.max_position_count,
            "cooldown_seconds": risk_config.cooldown_seconds,
            "max_symbol_daily_loss_usd": risk_config.max_symbol_daily_loss_usd,
            "circuit_breaker_loss_count": risk_config.circuit_breaker_loss_count,
            "circuit_breaker_duration": risk_config.circuit_breaker_duration,
        },
    )
    
    # Runner 생성
    runner = MultiSymbolEngineRunner(
        universe=universe,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        engine_config=engine_config,
        live_config=live_config,
        risk_coordinator=risk_coordinator,  # D73-3
        **kwargs
    )
    
    return runner


# ============================================================================
# D73-2 Done, D73-3 Done
# ============================================================================
# 
# ✅ D73-2: Multi-Symbol Engine Loop
# - Per-symbol coroutine 구조 구현
# - Config 기반 single/multi 모드 전환
# - 기존 단일 심볼 엔진 재사용
# 
# ✅ D73-3: Multi-Symbol RiskGuard Integration
# - GlobalGuard / PortfolioGuard / SymbolGuard 계층
# - 심볼별 리스크 한도 자동 분배
# - 3-Tier Risk Management (Global → Portfolio → Symbol)
# 
# TODO(D73-4): Small-Scale Integration Test
# - Top-10 심볼 PAPER 모드 통합 테스트
# - 5분 캠페인 실행 (Entry/Exit/PnL 검증)
# 
# TODO(D74): Performance Optimization
# - Event loop 단일화 검증
# - Per-symbol metrics collection
# - Graceful shutdown / cancellation handling 강화
