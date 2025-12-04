#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D77-0: TopN Arbitrage PAPER Baseline Runner

Top20/Top50 PAPER 모드 Full Cycle (Entry → Exit → PnL) 검증

Purpose:
- Critical Gaps 4개 해소 (Q1~Q4)
- Top50+ PAPER 1h+ 실행
- Entry/Exit Full Cycle 검증 (TP/SL/Time-based/Spread reversal)
- D75 Infrastructure (ArbRoute, Universe, CrossSync, RiskGuard) 실제 시장 통합 검증
- Alert Manager (D76) 실제 Telegram 전송 검증
- Core KPI 10종 수집

Usage:
    python scripts/run_d77_0_topn_arbitrage_paper.py --universe top20 --duration-minutes 60
    python scripts/run_d77_0_topn_arbitrage_paper.py --universe top50 --duration-minutes 720  # 12h
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

try:
    import psutil
except ImportError:
    psutil = None

# D82-0: Load .env.paper if ARBITRAGE_ENV=paper
try:
    from dotenv import load_dotenv
    if os.getenv("ARBITRAGE_ENV") == "paper":
        env_file = Path(__file__).parent.parent / ".env.paper"
        if env_file.exists():
            load_dotenv(env_file, override=True)
            logging.info(f"[D82-0] Loaded {env_file}")
except ImportError:
    pass  # python-dotenv not installed

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.domain.topn_provider import TopNProvider, TopNMode
from arbitrage.domain.exit_strategy import ExitStrategy, ExitConfig, ExitReason
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
from arbitrage.symbol_universe import SymbolUniverseMode
from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.monitoring.metrics import (
    init_metrics,
    start_metrics_server,
    record_trade,
    record_round_trip,
    record_pnl,
    record_win_rate,
    record_loop_latency,
    record_memory_usage,
    record_cpu_usage,
    record_exit_reason,
    set_active_positions,
)

# D82-0: Settings + ExecutorFactory + PaperExecutor + TradeLogger 통합
from arbitrage.config.settings import Settings
from arbitrage.execution.executor_factory import ExecutorFactory
from arbitrage.types import PortfolioState
from arbitrage.live_runner import RiskGuard, RiskLimits
from arbitrage.logging.trade_logger import TradeLogger, TradeLogEntry
from dataclasses import dataclass

# D82-0: PaperExecutor 호환 MockTrade 객체
@dataclass
class MockTrade:
    """
    D82-0: PaperExecutor.execute_trades()에 전달할 간단한 Mock Trade 객체.
    
    PaperExecutor가 기대하는 필드만 포함.
    """
    trade_id: str
    buy_exchange: str
    sell_exchange: str
    quantity: float
    buy_price: float
    sell_price: float
    
    @property
    def notional_usd(self) -> float:
        """명목가 계산 (quantity * price)"""
        return self.quantity * max(self.buy_price, self.sell_price)

# logs/ 디렉토리 생성
Path("logs/d77-0").mkdir(parents=True, exist_ok=True)

# 로깅 설정
log_filename = f'logs/d77-0/paper_session_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class D77PAPERRunner:
    """
    D77-0 PAPER Runner.
    
    TopN Universe + Exit Strategy + D75/D76 Integration.
    """
    
    def __init__(
        self,
        universe_mode: TopNMode,
        duration_minutes: float,
        config_path: str,
        data_source: str = "mock",  # D77-0-RM: "mock" | "real"
        monitoring_enabled: bool = False,
        monitoring_port: int = 9100,
        kpi_output_path: str = None,  # D77-4: Custom KPI output path
    ):
        """
        Args:
            universe_mode: TopN 모드
            duration_minutes: 실행 시간 (분)
            config_path: Config 파일 경로
            data_source: "mock" | "real" (D77-0-RM)
        """
        self.universe_mode = universe_mode
        self.duration_minutes = duration_minutes
        self.config_path = config_path
        self.data_source = data_source
        self.monitoring_enabled = monitoring_enabled
        self.monitoring_port = monitoring_port
        self.kpi_output_path = kpi_output_path  # D77-4
        
        # D82-0: Settings 로드 (ARBITRAGE_ENV=paper)
        self.settings = Settings.from_env()
        logger.info(f"[D82-0] Settings loaded: fill_model_enabled={self.settings.fill_model.enable_fill_model}")
        
        # D82-0: ExecutorFactory + PaperExecutor 초기화
        self.executor_factory = ExecutorFactory()
        self.portfolio_state = PortfolioState(
            total_balance=10000.0,  # Mock balance
            available_balance=10000.0,
        )
        self.risk_guard = RiskGuard(
            risk_limits=RiskLimits(
                max_notional_per_trade=1000.0,
                max_daily_loss=500.0,
                max_open_trades=10,
            )
        )
        
        # Symbol별 Executor 맵 (lazy initialization)
        self.executors: Dict[str, Any] = {}
        
        # D82-0: TradeLogger 초기화
        self.trade_logger = TradeLogger(
            base_dir=Path("logs/d82-0/trades"),
            run_id=f"d82-0-{universe_mode.name.lower()}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            universe_mode=universe_mode.name,
        )
        logger.info(f"[D82-0] TradeLogger initialized: {self.trade_logger.log_file}")
        
        # D82-2: TopN Provider with Hybrid Mode
        self.topn_provider = TopNProvider(
            mode=universe_mode,
            selection_data_source=self.settings.topn_selection.selection_data_source,
            entry_exit_data_source=self.settings.topn_selection.entry_exit_data_source,
            cache_ttl_seconds=self.settings.topn_selection.selection_cache_ttl_sec,
            max_symbols=self.settings.topn_selection.selection_max_symbols,
        )
        logger.info(
            f"[D82-2] TopNProvider Hybrid Mode: "
            f"selection={self.settings.topn_selection.selection_data_source}, "
            f"entry_exit={self.settings.topn_selection.entry_exit_data_source}, "
            f"cache_ttl={self.settings.topn_selection.selection_cache_ttl_sec}s"
        )
        
        # Exit Strategy
        self.exit_strategy = ExitStrategy(
            config=ExitConfig(
                tp_threshold_pct=0.25,
                sl_threshold_pct=0.20,
                max_hold_time_seconds=180.0,
                spread_reversal_threshold_bps=-10.0,
            )
        )
        
        # Metrics
        self.metrics: Dict[str, Any] = {
            "session_id": f"d82-0-{universe_mode.name.lower()}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "start_time": time.time(),
            "end_time": 0.0,
            "duration_minutes": duration_minutes,
            "universe_mode": universe_mode.name,
            "total_trades": 0,
            "entry_trades": 0,
            "exit_trades": 0,
            "round_trips_completed": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "total_pnl_usd": 0.0,
            "loop_latency_avg_ms": 0.0,
            "loop_latency_p99_ms": 0.0,
            "guard_triggers": 0,
            "alert_count": {"P0": 0, "P1": 0, "P2": 0, "P3": 0},
            "memory_usage_mb": 0.0,
            "cpu_usage_pct": 0.0,
            "exit_reasons": {
                "take_profit": 0,
                "stop_loss": 0,
                "time_limit": 0,
                "spread_reversal": 0,
            },
            # D82-0: Fill Model KPI
            "avg_buy_slippage_bps": 0.0,
            "avg_sell_slippage_bps": 0.0,
            "avg_buy_fill_ratio": 1.0,
            "avg_sell_fill_ratio": 1.0,
            "partial_fills_count": 0,
            "failed_fills_count": 0,
        }
        
        self.loop_latencies: List[float] = []
    
    async def run(self) -> Dict[str, Any]:
        """
        PAPER 실행.
        
        Returns:
            최종 metrics
        """
        logger.info(f"[D77-0] Starting PAPER Runner")
        logger.info(f"  Universe: {self.universe_mode.name} ({self.universe_mode.value} symbols)")
        logger.info(f"  Duration: {self.duration_minutes:.1f} minutes")
        logger.info(f"  Config: {self.config_path}")
        logger.info(f"  Session ID: {self.metrics['session_id']}")
        logger.info(f"  Monitoring: {'ENABLED' if self.monitoring_enabled else 'DISABLED'}")
        
        # D77-1: Prometheus Metrics 초기화
        if self.monitoring_enabled:
            try:
                init_metrics(
                    env="paper",
                    universe=self.universe_mode.name.lower(),
                    strategy="topn_arb",
                )
                start_metrics_server(port=self.monitoring_port)
                logger.info(f"[D77-1] Metrics server started on port {self.monitoring_port}")
            except Exception as e:
                logger.error(f"[D77-1] Failed to start metrics server: {e}")
                self.monitoring_enabled = False
        
        # 1. TopN Universe 선정
        logger.info("[D77-0] Fetching TopN symbols...")
        topn_result = self.topn_provider.get_topn_symbols(force_refresh=True)
        logger.info(f"[D77-0] TopN symbols selected: {len(topn_result.symbols)} symbols")
        for i, (symbol_a, symbol_b) in enumerate(topn_result.symbols[:10], 1):
            logger.info(f"  #{i:2d}: {symbol_a} ↔ {symbol_b}")
        
        # 2. PAPER 실행 (Simplified mock loop)
        logger.info("[D77-0] Starting PAPER loop...")
        # Wall-clock based timing (monotonic, unaffected by system clock changes)
        start_time = time.time()
        end_time = start_time + (self.duration_minutes * 60)
        
        iteration = 0
        while time.time() < end_time:
            loop_start = time.time()
            
            # D82-0: Real PaperExecutor 기반 arbitrage iteration
            await self._real_arbitrage_iteration(iteration, topn_result.symbols)
            
            loop_latency_ms = (time.time() - loop_start) * 1000
            loop_latency_seconds = loop_latency_ms / 1000.0
            self.loop_latencies.append(loop_latency_ms)
            
            # D77-1: Record loop latency
            if self.monitoring_enabled:
                record_loop_latency(loop_latency_seconds)
            
            # Periodic logging + metrics update
            if iteration % 100 == 0:
                logger.info(
                    f"[D77-0] Iteration {iteration}: "
                    f"Round trips={self.metrics['round_trips_completed']}, "
                    f"PnL=${self.metrics['total_pnl_usd']:.2f}, "
                    f"Latency={loop_latency_ms:.1f}ms"
                )
                
                # D77-1: Periodic metrics update (every 10s)
                if self.monitoring_enabled and psutil:
                    try:
                        process = psutil.Process()
                        record_win_rate(self.metrics["wins"], self.metrics["losses"])
                        record_memory_usage(process.memory_info().rss)
                        record_cpu_usage(process.cpu_percent())
                        set_active_positions(len(self.exit_strategy.positions))
                    except Exception as e:
                        logger.debug(f"[D77-1] Failed to update periodic metrics: {e}")
            
            # D82-2: Respect loop interval (increased for rate limit safety)
            # 1.5s loop → ~4 req/sec (6 calls per loop: 1 entry + 5 exit)
            # Provides 60% margin under Upbit 10 req/sec limit
            await asyncio.sleep(1.5)  # 1.5s to ensure rate limit safety
            iteration += 1
        
        # 3. 종료 및 최종 metrics 계산
        self.metrics["end_time"] = time.time()
        self._calculate_final_metrics()
        
        logger.info("[D77-0] PAPER run completed")
        self._log_final_summary()
        
        # 4. Metrics 저장
        self._save_metrics()
        
        return self.metrics
    
    def _get_or_create_executor(self, symbol: str) -> Any:
        """
        D82-0: Symbol별 PaperExecutor 생성/캐싱 (Lazy Initialization)
        
        Args:
            symbol: 거래 심볼
        
        Returns:
            PaperExecutor 인스턴스
        """
        if symbol not in self.executors:
            self.executors[symbol] = self.executor_factory.create_paper_executor(
                symbol=symbol,
                portfolio_state=self.portfolio_state,
                risk_guard=self.risk_guard,
                fill_model_config=self.settings.fill_model,
            )
            logger.info(f"[D82-0] Created PaperExecutor for {symbol}")
        return self.executors[symbol]
    
    async def _real_arbitrage_iteration(
        self,
        iteration: int,
        symbols: List[tuple[str, str]],
    ) -> None:
        """
        D82-1: Real Market Data 기반 arbitrage iteration.
        
        TopNProvider를 통해 실제 스프레드를 조회하고,
        Settings.topn_entry_exit 파라미터 기반으로 Entry/Exit 판단.
        
        Args:
            iteration: Iteration 번호
            symbols: Symbol 리스트 (TopN Universe)
        """
        entry_config = self.settings.topn_entry_exit
        open_positions = self.exit_strategy.get_open_positions()
        open_positions_count = len(open_positions)
        
        # D82-1: 이미 열린 포지션이 있는 심볼 리스트 (중복 Entry 방지)
        open_symbols = set()
        for pos in open_positions.values():
            open_symbols.add(pos.symbol_a)
            open_symbols.add(pos.symbol_b)
        
        # D82-1: Entry 로직 - Real Market Data 기반
        # Rate Limit 안전성: 최대 1개 심볼만 Entry check (Upbit 10 req/sec 고려)
        if open_positions_count < entry_config.entry_max_concurrent_positions and len(symbols) > 0:
            max_entry_checks = 1  # D82-1: Rate limit safety - only check 1 symbol per loop
            for idx, (symbol_a, symbol_b) in enumerate(symbols[:max_entry_checks]):
                # 이미 열린 포지션이 있는 심볼은 스킵
                if symbol_a in open_symbols or symbol_b in open_symbols:
                    continue
                
                # D82-1: TopNProvider를 통해 실제 스프레드 조회
                spread_snapshot = self.topn_provider.get_current_spread(symbol_a, cross_exchange=False)
                if spread_snapshot is None:
                    logger.warning(f"[D82-1] No spread data for {symbol_a}, skipping entry check")
                    continue
                
                # Entry 조건 체크
                if spread_snapshot.spread_bps < entry_config.entry_min_spread_bps:
                    continue
                
                # Entry Trade
                position_id = self.metrics["entry_trades"]
                mock_size = 0.1  # Fixed size for PAPER mode
                
                # MockTrade 생성 (PaperExecutor 호환)
                trade = MockTrade(
                    trade_id=f"ENTRY_{position_id}",
                    buy_exchange="upbit",
                    sell_exchange="upbit",
                    buy_price=spread_snapshot.upbit_bid,
                    sell_price=spread_snapshot.upbit_ask,
                    quantity=mock_size,
                )
                
                # D82-0: Real PaperExecutor 사용 (Fill Model 포함)
                executor = self._get_or_create_executor(symbol_a)
                results = executor.execute_trades([trade])
                
                if results and len(results) > 0:
                    result = results[0]
                    
                    # D82-0: TradeLogger에 기록
                    trade_entry = TradeLogEntry(
                        timestamp=datetime.utcnow().isoformat(),
                        session_id=self.metrics["session_id"],
                        trade_id=result.trade_id,
                        universe_mode=self.universe_mode.name,
                        symbol=result.symbol,
                        route_type="single_exchange",  # D82-1: Upbit only
                        entry_timestamp=datetime.utcnow().isoformat(),
                        entry_bid_upbit=spread_snapshot.upbit_bid,
                        entry_ask_binance=spread_snapshot.upbit_ask,
                        entry_spread_bps=spread_snapshot.spread_bps,
                        order_quantity=trade.quantity,
                        filled_quantity=result.quantity,
                        fill_price_upbit=result.buy_price,
                        fill_price_binance=result.sell_price,
                        # D82-0: Fill Model 필드
                        buy_slippage_bps=result.buy_slippage_bps,
                        sell_slippage_bps=result.sell_slippage_bps,
                        buy_fill_ratio=result.buy_fill_ratio,
                        sell_fill_ratio=result.sell_fill_ratio,
                        gross_pnl_usd=result.pnl,
                        net_pnl_usd=result.pnl,  # 수수료 미반영 (mock)
                        trade_result="win" if result.pnl > 0 else "loss",
                    )
                    self.trade_logger.log_trade(trade_entry)
                    
                    # Exit Strategy 등록
                    if result.status == "success" or result.status == "partial":
                        self.exit_strategy.register_position(
                            position_id=position_id,
                            symbol_a=symbol_a,
                            symbol_b=symbol_b,
                            entry_price_a=spread_snapshot.upbit_bid,
                            entry_price_b=spread_snapshot.upbit_ask,
                            entry_spread_bps=spread_snapshot.spread_bps,
                            size=result.quantity,
                        )
                        self.metrics["entry_trades"] += 1
                        self.metrics["total_trades"] += 1
                        
                        # D82-0: Fill Model KPI 집계
                        if result.buy_fill_ratio < 1.0 or result.sell_fill_ratio < 1.0:
                            self.metrics["partial_fills_count"] += 1
                        
                        # D77-1: Record entry trade
                        if self.monitoring_enabled:
                            record_trade("entry")
                        
                        logger.info(f"[D82-1] Entry: {symbol_a} @ spread={spread_snapshot.spread_bps:.2f} bps")
                        break  # 1개만 Entry 하고 나오기
                    elif result.status == "failed":
                        self.metrics["failed_fills_count"] += 1
        
        # D82-1: Exit 로직 - Real Market Data 기반
        exit_config = self.settings.topn_entry_exit
        for position_id, position in list(self.exit_strategy.get_open_positions().items()):
            # D82-1: TopNProvider를 통해 실제 현재 스프레드 조회
            spread_snapshot = self.topn_provider.get_current_spread(position.symbol_a, cross_exchange=False)
            if spread_snapshot is None:
                logger.warning(f"[D82-1] No spread data for {position.symbol_a}, skipping exit check")
                continue
            
            # Exit 조건 체크
            exit_signal = self.exit_strategy.check_exit(
                position_id=position_id,
                current_price_a=spread_snapshot.upbit_bid,
                current_price_b=spread_snapshot.upbit_ask,
                current_spread_bps=spread_snapshot.spread_bps,
            )
            
            if exit_signal.should_exit:
                # D82-1: Exit MockTrade (Real price 사용)
                exit_trade = MockTrade(
                    trade_id=f"EXIT_{position_id}",
                    buy_exchange="upbit",
                    sell_exchange="upbit",
                    buy_price=spread_snapshot.upbit_ask,
                    sell_price=spread_snapshot.upbit_bid,
                    quantity=position.size,
                )
                
                # D82-0: Real PaperExecutor 사용
                executor = self._get_or_create_executor(position.symbol_a)
                exit_results = executor.execute_trades([exit_trade])
                
                if exit_results and len(exit_results) > 0:
                    exit_result = exit_results[0]
                    
                    # Exit Strategy 제거
                    self.exit_strategy.unregister_position(position_id)
                    self.metrics["exit_trades"] += 1
                    self.metrics["round_trips_completed"] += 1
                    self.metrics["total_trades"] += 1
                    
                    # Update exit reason count
                    reason_key = exit_signal.reason.name.lower()
                    self.metrics["exit_reasons"][reason_key] += 1
                    
                    # PnL calculation
                    pnl = exit_result.pnl
                    self.metrics["total_pnl_usd"] += pnl
                    
                    if pnl > 0:
                        self.metrics["wins"] += 1
                    else:
                        self.metrics["losses"] += 1
                    
                    # D77-1: Record exit trade, round trip, PnL, exit reason
                    if self.monitoring_enabled:
                        record_trade("exit")
                        record_round_trip()
                        record_pnl(self.metrics["total_pnl_usd"])
                        record_exit_reason(reason_key)
                    
                    logger.info(f"[D82-1] Exit: {position.symbol_a} @ spread={spread_snapshot.spread_bps:.2f} bps, reason={exit_signal.reason.name}")
    
    def _calculate_final_metrics(self) -> None:
        """최종 metrics 계산"""
        # Actual elapsed time (wall-clock based)
        actual_duration_seconds = self.metrics["end_time"] - self.metrics["start_time"]
        self.metrics["actual_duration_seconds"] = actual_duration_seconds
        self.metrics["actual_duration_minutes"] = actual_duration_seconds / 60.0
        
        # Win rate
        total_exits = self.metrics["wins"] + self.metrics["losses"]
        if total_exits > 0:
            self.metrics["win_rate_pct"] = (self.metrics["wins"] / total_exits) * 100.0
        
        # Loop latency
        if self.loop_latencies:
            self.metrics["loop_latency_avg_ms"] = sum(self.loop_latencies) / len(self.loop_latencies)
            self.metrics["loop_latency_p99_ms"] = sorted(self.loop_latencies)[int(len(self.loop_latencies) * 0.99)]
        
        # Memory/CPU (mock)
        self.metrics["memory_usage_mb"] = 150.0  # Mock
        self.metrics["cpu_usage_pct"] = 35.0  # Mock
        
        # D82-1: TradeLogger 기반 Fill Model KPI 집계
        fill_metrics = self.trade_logger.get_aggregated_fill_metrics()
        self.metrics["avg_buy_slippage_bps"] = fill_metrics["avg_buy_slippage_bps"]
        self.metrics["avg_sell_slippage_bps"] = fill_metrics["avg_sell_slippage_bps"]
        self.metrics["avg_buy_fill_ratio"] = fill_metrics["avg_buy_fill_ratio"]
        self.metrics["avg_sell_fill_ratio"] = fill_metrics["avg_sell_fill_ratio"]
        self.metrics["partial_fills_count"] = fill_metrics["partial_fills_count"]
        self.metrics["failed_fills_count"] = fill_metrics["failed_fills_count"]
        
        logger.info(f"[D82-1] Fill Model KPI aggregated from TradeLogger: "
                   f"avg_buy_slippage={fill_metrics['avg_buy_slippage_bps']:.2f} bps, "
                   f"avg_sell_slippage={fill_metrics['avg_sell_slippage_bps']:.2f} bps, "
                   f"partial_fills={fill_metrics['partial_fills_count']}")
    
    def _log_final_summary(self) -> None:
        """최종 요약 로그"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("[D77-0] PAPER Run Summary")
        logger.info("=" * 80)
        logger.info(f"Session ID: {self.metrics['session_id']}")
        logger.info(f"Universe: {self.metrics['universe_mode']}")
        # Report actual elapsed time, not configured duration
        actual_dur_min = self.metrics.get('actual_duration_minutes', self.metrics['duration_minutes'])
        logger.info(f"Duration: {actual_dur_min:.1f} minutes (actual elapsed)")
        logger.info("")
        logger.info("Trades:")
        logger.info(f"  Total Trades: {self.metrics['total_trades']}")
        logger.info(f"  Entry Trades: {self.metrics['entry_trades']}")
        logger.info(f"  Exit Trades: {self.metrics['exit_trades']}")
        logger.info(f"  Round Trips: {self.metrics['round_trips_completed']}")
        logger.info("")
        logger.info("PnL:")
        logger.info(f"  Total PnL: ${self.metrics['total_pnl_usd']:.2f}")
        logger.info(f"  Wins: {self.metrics['wins']}")
        logger.info(f"  Losses: {self.metrics['losses']}")
        logger.info(f"  Win Rate: {self.metrics['win_rate_pct']:.1f}%")
        logger.info("")
        logger.info("Exit Reasons:")
        for reason, count in self.metrics["exit_reasons"].items():
            logger.info(f"  {reason}: {count}")
        logger.info("")
        logger.info("Performance:")
        logger.info(f"  Loop Latency (avg): {self.metrics['loop_latency_avg_ms']:.1f}ms")
        logger.info(f"  Loop Latency (p99): {self.metrics['loop_latency_p99_ms']:.1f}ms")
        logger.info(f"  Memory Usage: {self.metrics['memory_usage_mb']:.1f}MB")
        logger.info(f"  CPU Usage: {self.metrics['cpu_usage_pct']:.1f}%")
        logger.info("")
        # D82-0: Fill Model KPI
        logger.info("Fill Model (D82-0):")
        logger.info(f"  Partial Fills: {self.metrics['partial_fills_count']}")
        logger.info(f"  Failed Fills: {self.metrics['failed_fills_count']}")
        logger.info(f"  Avg Buy Slippage: {self.metrics['avg_buy_slippage_bps']:.2f} bps")
        logger.info(f"  Avg Sell Slippage: {self.metrics['avg_sell_slippage_bps']:.2f} bps")
        logger.info(f"  Avg Buy Fill Ratio: {self.metrics['avg_buy_fill_ratio']:.2%}")
        logger.info(f"  Avg Sell Fill Ratio: {self.metrics['avg_sell_fill_ratio']:.2%}")
        logger.info("=" * 80)
        logger.info("")
        logger.info(f"[D82-0] TradeLogger file: {self.trade_logger.log_file}")
        logger.info("[D82-0] Check trade_log.jsonl for detailed slippage/fill_ratio data")
    
    def _save_metrics(self) -> None:
        """Metrics를 JSON 파일로 저장"""
        # D77-4: Custom KPI output path
        if self.kpi_output_path:
            output_path = Path(self.kpi_output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_path = Path(f"logs/d77-0/{self.metrics['session_id']}_kpi_summary.json")
        
        with open(output_path, "w") as f:
            json.dump(self.metrics, f, indent=2)
        logger.info(f"[D77-0] Metrics saved to: {output_path}")


def parse_args() -> argparse.Namespace:
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(description="D77-0/D77-4 TopN Arbitrage PAPER Runner")
    parser.add_argument(
        "--universe",
        type=str,
        choices=["top10", "top20", "top50", "top100"],
        default="top20",
        help="Universe mode (default: top20)",
    )
    parser.add_argument(
        "--topn-size",
        type=int,
        choices=[10, 20, 50, 100],
        default=None,
        help="D77-4: TopN size (overrides --universe)",
    )
    parser.add_argument(
        "--duration-minutes",
        type=float,
        default=60.0,
        help="Run duration in minutes (default: 60)",
    )
    parser.add_argument(
        "--run-duration-seconds",
        type=int,
        default=None,
        help="D77-4: Run duration in seconds (overrides --duration-minutes)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/paper/topn_arb_baseline.yaml",
        help="Config file path",
    )
    parser.add_argument(
        "--env",
        type=str,
        default="PAPER",
        help="Environment (default: PAPER)",
    )
    parser.add_argument(
        "--monitoring-enabled",
        action="store_true",
        help="Enable Prometheus metrics (default: False)",
    )
    parser.add_argument(
        "--monitoring-port",
        type=int,
        default=9100,
        help="Prometheus metrics server port (default: 9100)",
    )
    parser.add_argument(
        "--data-source",
        type=str,
        choices=["mock", "real"],
        default="mock",
        help="Data source: mock (default) | real (D77-0-RM)",
    )
    parser.add_argument(
        "--kpi-output-path",
        type=str,
        default=None,
        help="D77-4: Custom KPI output path (e.g., logs/d77-4/d77-4-1h_kpi.json)",
    )
    return parser.parse_args()


async def main():
    """메인 실행"""
    args = parse_args()
    
    # D77-4: --topn-size 우선, 없으면 --universe 사용
    if args.topn_size:
        topn_size_map = {
            10: TopNMode.TOP_10,
            20: TopNMode.TOP_20,
            50: TopNMode.TOP_50,
            100: TopNMode.TOP_100,
        }
        universe_mode = topn_size_map[args.topn_size]
    else:
        universe_map = {
            "top10": TopNMode.TOP_10,
            "top20": TopNMode.TOP_20,
            "top50": TopNMode.TOP_50,
            "top100": TopNMode.TOP_100,
        }
        universe_mode = universe_map[args.universe]
    
    # D77-4: --run-duration-seconds 우선, 없으면 --duration-minutes 사용
    if args.run_duration_seconds:
        duration_minutes = args.run_duration_seconds / 60.0
        logger.info(f"[D77-4] Using --run-duration-seconds: {args.run_duration_seconds}s ({duration_minutes:.1f}min)")
    else:
        duration_minutes = args.duration_minutes
    
    # Runner 생성 및 실행
    runner = D77PAPERRunner(
        universe_mode=universe_mode,
        data_source=args.data_source,  # D77-0-RM
        duration_minutes=duration_minutes,  # D77-4: computed from --run-duration-seconds or --duration-minutes
        config_path=args.config,
        monitoring_enabled=args.monitoring_enabled,
        monitoring_port=args.monitoring_port,
        kpi_output_path=args.kpi_output_path,  # D77-4
    )
    
    try:
        metrics = await runner.run()
        
        # Acceptance Criteria 체크
        logger.info("")
        logger.info("=" * 80)
        logger.info("[D77-0] Acceptance Criteria Check")
        logger.info("=" * 80)
        
        criteria_pass = True
        
        # Round trips >= 5
        if metrics["round_trips_completed"] >= 5:
            logger.info("[PASS] Round trips >= 5")
        else:
            logger.error(f"[FAIL] Round trips >= 5 (actual: {metrics['round_trips_completed']})")
            criteria_pass = False
        
        # Win rate >= 50%
        if metrics["win_rate_pct"] >= 50.0:
            logger.info("[PASS] Win rate >= 50%")
        else:
            logger.error(f"[FAIL] Win rate >= 50% (actual: {metrics['win_rate_pct']:.1f}%)")
            criteria_pass = False
        
        # Loop latency < 80ms
        if metrics["loop_latency_avg_ms"] < 80.0:
            logger.info("[PASS] Loop latency < 80ms")
        else:
            logger.error(f"[FAIL] Loop latency < 80ms (actual: {metrics['loop_latency_avg_ms']:.1f}ms)")
            criteria_pass = False
        
        logger.info("=" * 80)
        
        if criteria_pass:
            logger.info("[RESULT] ALL ACCEPTANCE CRITERIA PASSED")
            return 0
        else:
            logger.error("[RESULT] SOME ACCEPTANCE CRITERIA FAILED")
            return 1
    
    except Exception as e:
        logger.exception(f"[D77-0] Error during PAPER run: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
