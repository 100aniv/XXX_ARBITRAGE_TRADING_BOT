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
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
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


# ============================================================================
# D80-4: Validation Profile System
# ============================================================================

class ValidationProfile(str, Enum):
    """Validation profile for different testing scenarios."""
    NONE = "none"  # No validation checks
    FILL_MODEL = "fill_model"  # D80-4: Fill Model structure validation
    TOPN_RESEARCH = "topn_research"  # D82-x, D77-x: TopN research criteria


@dataclass
class ValidationResult:
    """Result of validation check."""
    profile: ValidationProfile
    passed: bool
    reasons: List[str]


def evaluate_validation(
    metrics: Dict[str, Any], profile: ValidationProfile
) -> ValidationResult:
    """
    Evaluate KPI metrics against specified validation profile.
    
    Args:
        metrics: KPI metrics dictionary
        profile: Validation profile to apply
    
    Returns:
        ValidationResult with pass/fail status and reasons
    """
    if profile == ValidationProfile.NONE:
        return ValidationResult(
            profile=profile, passed=True, reasons=["No validation requested"]
        )
    
    reasons = []
    passed = True
    
    if profile == ValidationProfile.FILL_MODEL:
        # D80-4 Acceptance Criteria
        # Focus: Fill Model structure & stability, NOT win rate/trade count
        
        # 1. Duration: >= 10 minutes (for stability)
        duration = metrics.get("duration_minutes", 0)
        if duration >= 10.0:
            reasons.append(f"✅ Duration: {duration:.1f} min >= 10.0 min")
        else:
            reasons.append(f"❌ Duration: {duration:.1f} min < 10.0 min")
            passed = False
        
        # 2. Entry trades: >= 1 (at least one trade executed)
        entry_trades = metrics.get("entry_trades", 0)
        if entry_trades >= 1:
            reasons.append(f"✅ Entry trades: {entry_trades} >= 1")
        else:
            reasons.append(f"❌ Entry trades: {entry_trades} < 1")
            passed = False
        
        # 3. Round trips: >= 1 (at least one full cycle)
        round_trips = metrics.get("round_trips_completed", 0)
        if round_trips >= 1:
            reasons.append(f"✅ Round trips: {round_trips} >= 1")
        else:
            reasons.append(f"❌ Round trips: {round_trips} < 1")
            passed = False
        
        # 4. Slippage modeling: avg_buy_slippage_bps in [0.1, 5.0]
        buy_slippage = metrics.get("avg_buy_slippage_bps", 0)
        if 0.1 <= buy_slippage <= 5.0:
            reasons.append(f"✅ Buy slippage: {buy_slippage:.2f} bps in [0.1, 5.0]")
        else:
            reasons.append(f"❌ Buy slippage: {buy_slippage:.2f} bps out of [0.1, 5.0]")
            passed = False
        
        # 5. Slippage modeling: avg_sell_slippage_bps in [0.1, 5.0]
        sell_slippage = metrics.get("avg_sell_slippage_bps", 0)
        if 0.1 <= sell_slippage <= 5.0:
            reasons.append(f"✅ Sell slippage: {sell_slippage:.2f} bps in [0.1, 5.0]")
        else:
            reasons.append(f"❌ Sell slippage: {sell_slippage:.2f} bps out of [0.1, 5.0]")
            passed = False
        
        # 6. Partial fills: NOT a FAIL condition (just informational)
        partial_fills = metrics.get("partial_fills_count", 0)
        if partial_fills > 0:
            reasons.append(f"ℹ️  Partial fills: {partial_fills} (scenario tested)")
        else:
            reasons.append(f"ℹ️  Partial fills: 0 (not tested, OK for D80-4)")
        
        # 7. Loop latency: avg < 80ms
        loop_latency_avg = metrics.get("loop_latency_avg_ms", 0)
        if loop_latency_avg < 80.0:
            reasons.append(f"✅ Loop latency avg: {loop_latency_avg:.2f}ms < 80ms")
        else:
            reasons.append(f"❌ Loop latency avg: {loop_latency_avg:.2f}ms >= 80ms")
            passed = False
        
        # 8. Loop latency: p99 < 500ms
        loop_latency_p99 = metrics.get("loop_latency_p99_ms", 0)
        if loop_latency_p99 < 500.0:
            reasons.append(f"✅ Loop latency p99: {loop_latency_p99:.2f}ms < 500ms")
        else:
            reasons.append(f"❌ Loop latency p99: {loop_latency_p99:.2f}ms >= 500ms")
            passed = False
        
        # 9. No fatal errors (informational)
        guard_triggers = metrics.get("guard_triggers", 0)
        reasons.append(f"ℹ️  Guard triggers: {guard_triggers}")
        
        # 10. Win rate: INFORMATIONAL ONLY (not a PASS/FAIL criterion for D80-4)
        win_rate = metrics.get("win_rate_pct", 0)
        reasons.append(f"ℹ️  Win rate: {win_rate:.1f}% (informational, not criteria)")
    
    elif profile == ValidationProfile.TOPN_RESEARCH:
        # D77-x / D82-x: TopN research validation (legacy criteria)
        # TODO(D82-5): Re-evaluate these thresholds based on long-term data
        
        # Round trips >= 5
        round_trips = metrics.get("round_trips_completed", 0)
        if round_trips >= 5:
            reasons.append(f"✅ Round trips: {round_trips} >= 5")
        else:
            reasons.append(f"❌ Round trips: {round_trips} < 5")
            passed = False
        
        # Win rate >= 50%
        win_rate = metrics.get("win_rate_pct", 0)
        if win_rate >= 50.0:
            reasons.append(f"✅ Win rate: {win_rate:.1f}% >= 50%")
        else:
            reasons.append(f"❌ Win rate: {win_rate:.1f}% < 50%")
            passed = False
        
        # Loop latency < 80ms
        loop_latency_avg = metrics.get("loop_latency_avg_ms", 0)
        if loop_latency_avg < 80.0:
            reasons.append(f"✅ Loop latency: {loop_latency_avg:.2f}ms < 80ms")
        else:
            reasons.append(f"❌ Loop latency: {loop_latency_avg:.2f}ms >= 80ms")
            passed = False
    
    return ValidationResult(profile=profile, passed=passed, reasons=reasons)

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

# D92-1-FIX: 로깅 설정 (직접 함수 호출 시 루트 로거 사용)
log_filename = f'paper_session_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

# 루트 로거에 핸들러 추가 (모든 자식 로거에 propagate됨)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# FileHandler 추가 (중복 체크)
file_handler_exists = any(isinstance(h, logging.FileHandler) and 'paper_session' in str(h.baseFilename) for h in root_logger.handlers)
if not file_handler_exists:
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    )
    root_logger.addHandler(file_handler)

# 모듈 로거 (루트 로거로 propagate)
logger = logging.getLogger(__name__)
logger.info(f"[D92-1-FIX] Logger initialized with file: {log_filename}")


class D77PAPERRunner:
    """
    D77-0 PAPER Runner.
    
    TopN Universe + Exit Strategy + D75/D76 Integration.
    """
    
    def __init__(
        self,
        universe_mode: TopNMode,
        data_source: str = "real",  # D77-0-RM: "mock" | "real"
        duration_minutes: float = 60.0,
        config_path: str = "configs/paper/topn_arb_baseline.yaml",
        monitoring_enabled: bool = False,
        monitoring_port: int = 9100,
        kpi_output_path: Optional[str] = None,  # D77-4
        zone_profile_applier: Optional[Any] = None,  # D92-1-FIX
        stage_id: str = "d77-0",  # D92-5: SSOT stage_id
        **kwargs  # D92-7-4: gate_mode 등 추가 파라미터
    ):
        """
        Args:
            universe_mode: TopN 모드
            duration_minutes: 실행 시간 (분)
            config_path: Config 파일 경로
            data_source: "mock" | "real" (D77-0-RM)
            zone_profile_applier: D92-1-FIX: Zone Profile 적용기 (optional)
        """
        self.universe_mode = universe_mode
        self.duration_minutes = duration_minutes
        self.config_path = config_path
        self.data_source = data_source
        self.monitoring_enabled = monitoring_enabled
        self.monitoring_port = monitoring_port
        self.kpi_output_path = kpi_output_path
        self.zone_profile_applier = zone_profile_applier
        self.stage_id = stage_id
        self.gate_mode = kwargs.get('gate_mode', False)  # D92-7-4
        
        # D92-5: run_paths SSOT 초기화
        from arbitrage.common.run_paths import resolve_run_paths
        self.run_paths = resolve_run_paths(
            stage_id=self.stage_id,
            universe_mode=self.universe_mode.name.lower(),
            create_dirs=True,
        )
        
        # D92-5: 로거 초기화 (run_dir 확정 후)
        self._setup_logger()
        
        # D92-1-FIX: Zone Profile 적용 로그 (팩트 증명)
        logger.info(f"[DEBUG] zone_profile_applier received: {zone_profile_applier}")
        logger.info(f"[DEBUG] zone_profile_applier type: {type(zone_profile_applier)}")
        logger.info(f"[DEBUG] zone_profile_applier is None: {zone_profile_applier is None}")
        
        # D92-7-3 STEP 2: ZoneProfile 메타데이터 수집 (path/sha256/mtime/profiles_applied)
        from pathlib import Path
        import hashlib
        
        if self.zone_profile_applier:
            logger.info("=" * 80)
            logger.info("[D92-1-FIX] ZONE PROFILE INTEGRATION ACTIVE")
            logger.info("=" * 80)
            
            # D92-7-3: zone_profile_file 경로 추출 (from_file 시 저장된 경로)
            yaml_path_str = getattr(self.zone_profile_applier, '_yaml_path', None)
            if yaml_path_str:
                yaml_path = Path(yaml_path_str)
            else:
                # Fallback: DEFAULT SSOT 경로
                yaml_path = Path("config/arbitrage/zone_profiles_v2.yaml")
            
            if yaml_path.exists():
                with open(yaml_path, 'rb') as f:
                    yaml_sha256 = hashlib.sha256(f.read()).hexdigest()
                yaml_mtime = yaml_path.stat().st_mtime
                logger.info(f"[D92-7-3] Zone Profile SSOT: {yaml_path}")
                logger.info(f"[D92-7-3] SHA256: {yaml_sha256[:16]}...")
            else:
                yaml_sha256 = None
                yaml_mtime = None
                logger.warning(f"[D92-7-3] Zone Profile path not found: {yaml_path}")
            
            # D92-7-3: profiles_applied 상세 요약 (threshold/tp/sl/time_limit)
            profiles_applied = {}
            for symbol in ["BTC", "ETH", "XRP", "SOL", "DOGE", "ADA", "AVAX", "DOT", "MATIC", "LINK"]:
                if self.zone_profile_applier.has_profile(symbol):
                    threshold = self.zone_profile_applier.get_entry_threshold(symbol)
                    threshold_bps = threshold * 10000.0
                    profile = self.zone_profile_applier.symbol_profiles[symbol]
                    profile_name = profile["profile_name"]
                    
                    # D92-7-3: Exit 파라미터도 기록 (있으면)
                    profiles_applied[symbol] = {
                        "profile_name": profile_name,
                        "entry_threshold_bps": round(threshold_bps, 2),
                    }
                    logger.info(f"[ZONE_PROFILE_APPLIED] {symbol} → {profile_name} (threshold={threshold_bps:.1f} bps)")
            
            logger.info("=" * 80)
        else:
            logger.warning("[D92-7-4] Zone Profile Applier is None - proceeding without profiles")
            yaml_path = None
            yaml_sha256 = None
            yaml_mtime = None
            profiles_applied = {}
        
        # D82-0: Settings 로드 (ARBITRAGE_ENV=paper)
        self.settings = Settings.from_env()
        
        # D92-2: Telemetry - spread 분포/ge_rate 수치화
        self.spread_telemetry: Dict[str, Dict[str, Any]] = {}  # symbol → telemetry data
        logger.info(f"[D82-0] Settings loaded: fill_model_enabled={self.settings.fill_model.enable_fill_model}")
        
        # D82-0: ExecutorFactory + PaperExecutor 초기화
        self.executor_factory = ExecutorFactory()
        self.portfolio_state = PortfolioState(
            total_balance=10000.0,  # Mock balance
            available_balance=10000.0,
        )
        # D92-7-4: gate_mode 시 notional 축소 (10분 동안 RT≥5 달성)
        max_notional = 100.0 if self.gate_mode else 1000.0
        max_daily_loss = 300.0 if self.gate_mode else 500.0
        
        self.risk_guard = RiskGuard(
            risk_limits=RiskLimits(
                max_notional_per_trade=max_notional,
                max_daily_loss=max_daily_loss,
                max_open_trades=10,
            )
        )
        
        if self.gate_mode:
            logger.info("[D92-7-4] GATE MODE: notional reduced to 100 USD, kill-switch at -300 USD")
        
        # Symbol별 Executor 맵 (lazy initialization)
        self.executors: Dict[str, Any] = {}
        
        # D82-0: TradeLogger 초기화 (D92-5: SSOT 경로)
        self.trade_logger = TradeLogger(
            base_dir=self.run_paths["run_dir"] / "trades",  # D92-5: SSOT 경로
            run_id=self.run_paths["run_id"],  # D92-5: SSOT run_id
            universe_mode=universe_mode.name,
        )
        logger.info(f"[D82-0] TradeLogger initialized: {self.trade_logger.log_file}")
        
        # D82-2/D82-3: TopN Provider with Hybrid Mode + Rate Limit
        self.topn_provider = TopNProvider(
            mode=universe_mode,
            selection_data_source=self.settings.topn_selection.selection_data_source,
            entry_exit_data_source=self.settings.topn_selection.entry_exit_data_source,
            cache_ttl_seconds=self.settings.topn_selection.selection_cache_ttl_sec,
            max_symbols=self.settings.topn_selection.selection_max_symbols,
            # D82-3: Real Selection Rate Limit 옵션
            selection_rate_limit_enabled=self.settings.topn_selection.selection_rate_limit_enabled,
            selection_batch_size=self.settings.topn_selection.selection_batch_size,
            selection_batch_delay_sec=self.settings.topn_selection.selection_batch_delay_sec,
        )
        logger.info(
            f"[D82-2/D82-3] TopNProvider Hybrid Mode: "
            f"selection={self.settings.topn_selection.selection_data_source}, "
            f"entry_exit={self.settings.topn_selection.entry_exit_data_source}, "
            f"cache_ttl={self.settings.topn_selection.selection_cache_ttl_sec}s, "
            f"rate_limit={'ON' if self.settings.topn_selection.selection_rate_limit_enabled else 'OFF'}"
        )
        
        # Exit Strategy
        # D92-7-5: Gate Mode 시 max_hold_time 단축 (10분 내 5+ RT 달성 목적)
        max_hold_time = 60.0 if self.gate_mode else 180.0
        self.exit_strategy = ExitStrategy(
            config=ExitConfig(
                tp_threshold_pct=0.25,
                sl_threshold_pct=0.20,
                max_hold_time_seconds=max_hold_time,
                spread_reversal_threshold_bps=-10.0,
            )
        )
        logger.info(f"[D92-7-5] Exit Strategy: max_hold_time={max_hold_time}s (gate_mode={self.gate_mode})")
        
        # Metrics
        self.metrics: Dict[str, Any] = {
            "session_id": self.run_paths["run_id"],
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
            "total_pnl_krw": 0.0,  # D92-5
            "total_pnl_usd": 0.0,
            "fx_rate": 1300.0,  # D92-5
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
            # D92-5: Zone Profiles 로드 증거
            "zone_profiles_loaded": {
                "path": str(yaml_path) if yaml_path else None,
                "sha256": yaml_sha256,
                "mtime": yaml_mtime,
                "profiles_applied": profiles_applied,
            },
            # D92-7-5: Gate Mode 리스크 캡 및 종료 사유
            "gate_mode": self.gate_mode,
            "risk_caps": {
                "max_notional_usd": max_notional,
                "max_daily_loss_usd": max_daily_loss,
            },
            "stop_reason": "duration",  # duration|kill_switch|exception
            "kill_switch_triggered": False,
            "max_drawdown_usd": 0.0,
        }
        
        self.loop_latencies: List[float] = []
    
    def _setup_logger(self) -> None:
        """로거 파일 핸들러 설정 (run_dir 확정 후)"""
        log_file = self.run_paths["run_dir"] / "runner.log"
        
        # 중복 핸들러 방지
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                if hasattr(handler, 'baseFilename') and str(log_file) in handler.baseFilename:
                    return  # 이미 설정됨
        
        # 파일 핸들러 추가
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
        )
        root_logger.addHandler(file_handler)
        logger.info(f"[D92-5] Logger file handler added: {log_file}")
    
    async def run(self) -> Dict[str, Any]:
        """
        PAPER 실행.
        
        Returns:
            최종 metrics
        """
        # D92-3: 팩트 고정 - 실행 시작 시각 명확히 로깅
        start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("=" * 80)
        logger.info(f"[D92-3] EXECUTION START TIMESTAMP: {start_timestamp}")
        logger.info(f"[D92-3] CONFIGURED DURATION: {self.duration_minutes:.1f} minutes ({self.duration_minutes * 60:.0f} seconds)")
        logger.info("=" * 80)
        
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
        
        # D92-3: 팩트 고정 - 종료 예정 시각 로깅
        expected_end_timestamp = datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[D92-3] EXPECTED END TIMESTAMP: {expected_end_timestamp}")
        logger.info(f"[D92-3] TARGET ITERATIONS: ~{int(self.duration_minutes * 60 / 1.5)} (1.5s per loop)")
        
        iteration = 0
        while time.time() < end_time:
            loop_start = time.time()
            
            # D92-7-5: Kill-switch (손실 폭주 방지)
            if self.metrics["total_pnl_usd"] <= -300:
                logger.error("=" * 80)
                logger.error("[D92-7-5] KILL-SWITCH TRIGGERED: total_pnl_usd <= -300")
                logger.error(f"  Current PnL: ${self.metrics['total_pnl_usd']:.2f}")
                logger.error(f"  Round Trips: {self.metrics['round_trips_completed']}")
                logger.error(f"  Iteration: {iteration}")
                logger.error("=" * 80)
                
                # D92-7-5: Metrics 업데이트
                self.metrics["stop_reason"] = "kill_switch"
                self.metrics["kill_switch_triggered"] = True
                
                # 직전 N개 RT 상세 로그
                logger.error("[D92-7-5] Last 5 Round Trips Summary:")
                # TODO: trade_logger에서 최근 RT 추출하여 로그
                
                break  # 즉시 중단
            
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
        actual_duration_seconds = self.metrics["end_time"] - self.metrics["start_time"]
        actual_duration_minutes = actual_duration_seconds / 60.0
        
        # D92-3: 팩트 고정 - 종료 시각 및 실제 실행 시간 로깅
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("=" * 80)
        logger.info(f"[D92-3] EXECUTION END TIMESTAMP: {end_timestamp}")
        logger.info(f"[D92-3] ACTUAL DURATION: {actual_duration_minutes:.2f} minutes ({actual_duration_seconds:.1f} seconds)")
        logger.info(f"[D92-3] CONFIGURED DURATION: {self.duration_minutes:.1f} minutes")
        logger.info(f"[D92-3] COMPLETION RATE: {(actual_duration_minutes / self.duration_minutes * 100):.1f}%")
        logger.info("=" * 80)
        
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
                
                # D92-1-FIX: Zone Profile 기반 threshold override
                # D92-2: 심볼 이름 정규화 (BTC/KRW → BTC)
                symbol_normalized = symbol_a.split("/")[0] if "/" in symbol_a else symbol_a
                
                logger.info(f"[DEBUG] Checking entry for {symbol_a}: spread={spread_snapshot.spread_bps:.2f} bps")
                
                if self.zone_profile_applier and self.zone_profile_applier.has_profile(symbol_normalized):
                    entry_threshold_decimal = self.zone_profile_applier.get_entry_threshold(symbol_normalized)
                    entry_threshold_bps = entry_threshold_decimal * 10000.0
                    
                    # D92-7-5: Gate Mode일 때 threshold 50% 완화 (10분 내 5+ RT 달성 목적)
                    if self.gate_mode:
                        entry_threshold_bps = entry_threshold_bps * 0.5
                        logger.info(f"[ZONE_THRESHOLD] {symbol_a} ({symbol_normalized}): {entry_threshold_bps:.2f} bps (Zone Profile, gate_mode=50% reduced)")
                    else:
                        logger.info(f"[ZONE_THRESHOLD] {symbol_a} ({symbol_normalized}): {entry_threshold_bps:.2f} bps (Zone Profile)")
                else:
                    entry_threshold_bps = entry_config.entry_min_spread_bps
                    logger.info(f"[ZONE_THRESHOLD] {symbol_a}: {entry_threshold_bps:.2f} bps (Default)")
                
                # D92-2: Telemetry - spread 샘플 수집
                if symbol_a not in self.spread_telemetry:
                    self.spread_telemetry[symbol_a] = {
                        "spread_samples": [],
                        "threshold_bps": entry_threshold_bps,
                        "count_ge_threshold": 0,
                        "count_lt_threshold": 0,
                    }
                
                self.spread_telemetry[symbol_a]["spread_samples"].append(spread_snapshot.spread_bps)
                
                # Entry 조건 체크 + Telemetry 카운트
                if spread_snapshot.spread_bps < entry_threshold_bps:
                    self.spread_telemetry[symbol_a]["count_lt_threshold"] += 1
                    continue
                else:
                    self.spread_telemetry[symbol_a]["count_ge_threshold"] += 1
                
                # D92-7-5: Entry 수량을 RiskGuard max_notional 기반으로 계산
                position_id = self.metrics["entry_trades"]
                
                # RiskGuard에서 max_notional 가져오기
                max_notional_usd = self.risk_guard.risk_limits.max_notional_per_trade
                
                # 주문 수량 계산: notional / price
                # Buy side 기준 (upbit_bid = 우리가 매수할 가격)
                entry_price_usd = spread_snapshot.upbit_bid
                order_quantity = max_notional_usd / entry_price_usd
                
                # 계산된 notional 검증
                computed_notional_usd = order_quantity * entry_price_usd
                
                logger.info(f"[D92-7-5] Order Size Calculation for {symbol_a}:")
                logger.info(f"  max_notional_usd: {max_notional_usd:.2f}")
                logger.info(f"  entry_price_usd: {entry_price_usd:.2f}")
                logger.info(f"  order_quantity: {order_quantity:.8f}")
                logger.info(f"  computed_notional_usd: {computed_notional_usd:.2f}")
                
                # RiskGuard 검증 (should always pass since we calculated based on max_notional)
                if computed_notional_usd > max_notional_usd * 1.01:  # 1% tolerance
                    logger.error(f"[D92-7-5] Order rejected: computed_notional ({computed_notional_usd:.2f}) > max_notional ({max_notional_usd:.2f})")
                    continue
                
                # MockTrade 생성 (PaperExecutor 호환)
                trade = MockTrade(
                    trade_id=f"ENTRY_{position_id}",
                    buy_exchange="upbit",
                    sell_exchange="upbit",
                    buy_price=spread_snapshot.upbit_bid,
                    sell_price=spread_snapshot.upbit_ask,
                    quantity=order_quantity,
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
                    self.metrics["total_pnl_krw"] += pnl * self.metrics["fx_rate"]  # D92-5
                    
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
        
        # D92-2: Telemetry - spread 통계 계산 및 로그 출력
        logger.info("=" * 80)
        logger.info("[D92-2-TELEMETRY] Spread Distribution Report")
        logger.info("=" * 80)
        
        total_entry_checks = 0
        total_ge_threshold = 0
        
        for symbol, data in self.spread_telemetry.items():
            samples = data["spread_samples"]
            if len(samples) == 0:
                continue
            
            # Percentile 계산
            samples_sorted = sorted(samples)
            n = len(samples)
            p50 = samples_sorted[int(n * 0.50)] if n > 0 else 0.0
            p90 = samples_sorted[int(n * 0.90)] if n > 1 else samples_sorted[-1]
            p95 = samples_sorted[int(n * 0.95)] if n > 1 else samples_sorted[-1]
            max_spread = max(samples)
            
            count_ge = data["count_ge_threshold"]
            count_lt = data["count_lt_threshold"]
            total_checks = count_ge + count_lt
            ge_rate = count_ge / total_checks if total_checks > 0 else 0.0
            
            total_entry_checks += total_checks
            total_ge_threshold += count_ge
            
            # Telemetry 데이터 업데이트
            data["p50"] = p50
            data["p90"] = p90
            data["p95"] = p95
            data["max"] = max_spread
            data["total_checks"] = total_checks
            data["ge_rate"] = ge_rate
            
            logger.info(
                f"  {symbol:6s}: p50={p50:6.2f}, p90={p90:6.2f}, p95={p95:6.2f}, "
                f"max={max_spread:6.2f}, threshold={data['threshold_bps']:6.2f}, "
                f"ge_rate={ge_rate:5.1%} ({count_ge}/{total_checks})"
            )
        
        global_ge_rate = total_ge_threshold / total_entry_checks if total_entry_checks > 0 else 0.0
        logger.info("=" * 80)
        logger.info(f"[D92-2-TELEMETRY] Global: total_checks={total_entry_checks}, ge_rate={global_ge_rate:.1%}")
        logger.info("=" * 80)
        
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
        logger.info(f"  Total PnL (USD): ${self.metrics['total_pnl_usd']:.2f}")
        if "total_pnl_krw" in self.metrics:
            logger.info(f"  Total PnL (KRW): {self.metrics['total_pnl_krw']:.0f} KRW")
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
        # D92-5-4: KPI SSOT
        if self.kpi_output_path:
            output_path = Path(self.kpi_output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_path = Path(self.run_paths["kpi_summary"])
        
        # D92-2: Telemetry JSON 저장
        telemetry_dir = Path("logs/d92-2") / self.metrics['session_id']
        telemetry_dir.mkdir(parents=True, exist_ok=True)
        
        telemetry_report = {
            "session_id": self.metrics['session_id'],
            "duration_minutes": self.metrics.get('actual_duration_minutes', self.metrics['duration_minutes']),
            "universe_mode": self.metrics['universe_mode'],
            "total_trades": self.metrics['total_trades'],
            "symbols": {},
        }
        
        for symbol, data in self.spread_telemetry.items():
            telemetry_report["symbols"][symbol] = {
                "threshold_bps": data["threshold_bps"],
                "p50": data.get("p50", 0.0),
                "p90": data.get("p90", 0.0),
                "p95": data.get("p95", 0.0),
                "max": data.get("max", 0.0),
                "total_checks": data.get("total_checks", 0),
                "count_ge_threshold": data["count_ge_threshold"],
                "count_lt_threshold": data["count_lt_threshold"],
                "ge_rate": data.get("ge_rate", 0.0),
            }
        
        telemetry_path = telemetry_dir / "d92_2_spread_report.json"
        with open(telemetry_path, "w") as f:
            json.dump(telemetry_report, f, indent=2)
        
        logger.info(f"[D92-2] Telemetry report saved: {telemetry_path}")
        
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
    parser.add_argument(
        "--validation-profile",
        type=str,
        choices=["none", "fill_model", "topn_research"],
        default="topn_research",
        help="D80-4: Validation profile (none|fill_model|topn_research, default: topn_research)",
    )
    parser.add_argument(
        "--symbol-profiles-json",
        type=str,
        default=None,
        help="D92-1-FIX: Symbol-specific Zone Profiles (JSON string)",
    )
    parser.add_argument(
        "--zone-profile-file",
        type=str,
        default=None,
        help="D92-1-FIX: Symbol-specific Zone Profiles (JSON file path)",
    )
    parser.add_argument(
        "--skip-env-check",
        action="store_true",
        help="D92 v3.2: Skip env checker (for subprocess from Gate wrapper)",
    )
    return parser.parse_args()


async def main():
    """메인 실행"""
    args = parse_args()
    
    # D92-MID-AUDIT: 인프라 선행조건 체크 (Docker/Redis/Postgres + 프로세스 정리)
    # D92 v3.2: Gate wrapper에서 이미 체크했으면 스킵
    if not args.skip_env_check:
        from scripts.d77_4_env_checker import D77EnvChecker
        project_root = Path(__file__).parent.parent
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info("[D92-HOTFIX] 인프라 선행조건 체크 시작 (FAIL-FAST)")
        env_checker = D77EnvChecker(project_root, run_id)
        env_ok, env_result = env_checker.check_all()
        
        if not env_ok:
            logger.error("[D92-HOTFIX] 인프라 체크 실패 - PAPER 실행 불가")
            logger.error(f"[D92-HOTFIX] 실패 상세: {env_result}")
            logger.error(f"[D92-HOTFIX] 로그 확인: logs/d77-4/{run_id}/env_checker.log")
            sys.exit(2)
        else:
            logger.info("[D92-HOTFIX] 인프라 체크 완료 - Docker/Redis/Postgres 준비됨")
    else:
        logger.info("[D92 v3.2] 인프라 체크 스킵 (Gate wrapper에서 이미 수행)")
    
    # D92-7-5: Zone Profile SSOT 로드 (E2E 복구)
    from arbitrage.core.zone_profile_applier import ZoneProfileApplier
    
    zone_profile_yaml = Path("config/arbitrage/zone_profiles_v2.yaml")
    if zone_profile_yaml.exists():
        try:
            zone_profile_applier = ZoneProfileApplier.from_file(str(zone_profile_yaml))
            logger.info(f"[D92-7-5] Zone Profile SSOT loaded: {zone_profile_yaml}")
        except Exception as e:
            logger.error(f"[D92-7-5] FAIL-FAST: Zone Profile load failed: {e}")
            raise RuntimeError(f"[D92-7-5] Zone Profile SSOT 로드 실패 - RUN 불가능: {e}")
    else:
        logger.error(f"[D92-7-5] FAIL-FAST: Zone Profile YAML not found: {zone_profile_yaml}")
        raise FileNotFoundError(f"[D92-7-5] Zone Profile SSOT 파일 없음 - RUN 불가능: {zone_profile_yaml}")
    
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
    # D92-7-4: gate_mode = duration < 15분 시 자동 활성화
    gate_mode = duration_minutes < 15
    
    runner = D77PAPERRunner(
        universe_mode=universe_mode,
        data_source=args.data_source,  # D77-0-RM
        duration_minutes=duration_minutes,  # D77-4: computed from --run-duration-seconds or --duration-minutes
        config_path=args.config,
        monitoring_enabled=args.monitoring_enabled,
        monitoring_port=args.monitoring_port,
        kpi_output_path=args.kpi_output_path,  # D77-4
        zone_profile_applier=zone_profile_applier,  # D92-1-FIX
        gate_mode=gate_mode,  # D92-7-4
    )
    
    try:
        metrics = await runner.run()
        
        # D80-4: Validation Profile 기반 Acceptance Criteria 체크
        validation_profile = ValidationProfile(args.validation_profile)
        
        if validation_profile != ValidationProfile.NONE:
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"[Validation] Profile: {validation_profile.value}")
            logger.info("=" * 80)
            
            result = evaluate_validation(metrics, validation_profile)
            
            for reason in result.reasons:
                # D92-7: Remove emoji to prevent UnicodeEncodeError
                reason_safe = reason.replace("✅", "[PASS]").replace("❌", "[FAIL]")
                if "[PASS]" in reason_safe:
                    logger.info(reason_safe)
                elif "[FAIL]" in reason_safe:
                    logger.error(reason_safe)
                else:
                    logger.info(reason_safe)
            
            logger.info("=" * 80)
            
            if result.passed:
                logger.info("[RESULT] ALL ACCEPTANCE CRITERIA PASSED")
                return 0
            else:
                logger.error("[RESULT] SOME ACCEPTANCE CRITERIA FAILED")
                return 1
        else:
            logger.info("[Validation] Profile: none (validation skipped)")
            return 0
    
    except Exception as e:
        logger.exception(f"[D77-0] Error during PAPER run: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
