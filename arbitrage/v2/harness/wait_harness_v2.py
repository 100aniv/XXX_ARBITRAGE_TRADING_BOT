"""
D205-10-2: Wait Harness v2 (Wallclock Verified, 3h→5h Phased, Early-Stop)

목적:
- Wallclock + Monotonic 이중 타임소스로 정확한 시간 측정
- 3시간 도달 시 feasibility 평가 → early-stop 또는 5h까지 연장
- watch_summary.json 주기적 갱신 (60초마다) + 종료 시 최종화
- heartbeat.json으로 진행중 상태 기록
- 완료 선언은 watch_summary.json의 ended_at_utc + stop_reason만 기준

책임:
- Market snapshot 수집 (bid/ask 포함)
- Wallclock/Monotonic 시간 측정
- Phase checkpoint (3h) 평가
- Early-stop 판정 (infeasible_margin_bps 기반)
- Evidence 자동 생성 (watch_summary.json, heartbeat.json, market_watch.jsonl)
- Watchdog (내부 자가감시)

금지:
- 외부 스크립트 감시 (내부 자가진단만)
- 시간 기반 상태 선언 (watch_summary.json 기반만)
"""

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from statistics import quantiles

from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.v2.opportunity import BreakEvenParams, build_candidate
from arbitrage.v2.marketdata.rest import BinanceRestProvider, UpbitRestProvider

logger = logging.getLogger(__name__)


@dataclass
class WaitHarnessV2Config:
    """Wait Harness v2 설정"""
    phase_hours: List[int] = field(default_factory=lambda: [3, 5])
    poll_seconds: int = 30
    trigger_min_edge_bps: float = 0.0
    fx_rate: float = 1450.0
    evidence_dir: str = ""
    sweep_duration_minutes: int = 2
    db_mode: str = "off"
    infeasible_margin_bps: float = 30.0
    heartbeat_interval_sec: int = 60
    
    def __post_init__(self):
        if not self.evidence_dir:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.evidence_dir = f"logs/evidence/d205_10_2_wait_{timestamp}"


@dataclass
class MarketSnapshot:
    """시장 스냅샷 (bid/ask 포함)"""
    timestamp_utc: str
    monotonic_elapsed_sec: float
    upbit_price_last: float
    upbit_bid: float
    upbit_ask: float
    binance_price_last: float
    binance_bid: float
    binance_ask: float
    binance_price_krw: float
    fx_rate: float
    spread_last_bps: float
    spread_conservative_bps: float
    break_even_bps: float
    edge_bps_last: float
    edge_bps_conservative: float
    trigger: bool
    error: Optional[str] = None


@dataclass
class WatchSummary:
    """Watch 요약 (SSOT 기반)"""
    planned_total_hours: int
    phase_hours: List[int]
    started_at_utc: str
    last_tick_at_utc: str
    ended_at_utc: Optional[str] = None
    monotonic_elapsed_sec: float = 0.0
    poll_sec: int = 30
    samples_collected: int = 0
    expected_samples: int = 0
    completeness_ratio: float = 0.0
    max_spread_bps: float = 0.0
    p95_spread_bps: float = 0.0
    max_edge_bps: float = 0.0
    min_edge_bps: float = 0.0
    mean_edge_bps: float = 0.0
    trigger_count: int = 0
    trigger_timestamps: List[str] = field(default_factory=list)
    stop_reason: Optional[str] = None
    phase_checkpoint_reached: bool = False
    phase_checkpoint_time_utc: Optional[str] = None
    feasibility_decision: Optional[str] = None


class WaitHarnessV2:
    """
    Wait Harness v2 엔진
    
    Flow:
        1. Monotonic 시작 시각 기록
        2. Poll loop: snapshot 수집 → edge 계산 → trigger 체크
        3. 60초마다 watch_summary.json + heartbeat.json 갱신
        4. 3h 도달 시 feasibility 평가
           - if max_spread < (break_even - infeasible_margin) → EARLY_INFEASIBLE
           - else → 5h까지 계속
        5. 종료 시 watch_summary.json 최종화 (ended_at_utc + stop_reason)
    """
    
    def __init__(self, config: WaitHarnessV2Config):
        self.config = config
        self.evidence_dir = Path(config.evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        
        # Wallclock + Monotonic
        self.start_time_utc = datetime.now(timezone.utc)
        self.start_time_monotonic = time.monotonic()
        
        # MarketData Providers
        try:
            self.upbit_provider = UpbitRestProvider(timeout=10.0)
            self.binance_provider = BinanceRestProvider(timeout=10.0)
            logger.info(f"[D205-10-2 WAIT] ✅ MarketData Providers initialized")
        except Exception as e:
            logger.error(f"[D205-10-2 WAIT] ❌ Provider init failed: {e}", exc_info=True)
            raise RuntimeError(f"MarketData Provider initialization failed: {e}")
        
        # Break-even params
        fee_a = FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=25.0)
        fee_b = FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=25.0)
        fee_model = FeeModel(fee_a=fee_a, fee_b=fee_b)
        
        self.break_even_params = BreakEvenParams(
            fee_model=fee_model,
            slippage_bps=15.0,
            latency_bps=10.0,
            buffer_bps=0.0,
        )
        
        # Watch 기록
        self.snapshots: List[MarketSnapshot] = []
        self.trigger_timestamps: List[str] = []
        self.last_heartbeat_time = time.monotonic()
        self.phase_checkpoint_reached = False
        self.phase_checkpoint_time_utc: Optional[str] = None
        self.feasibility_decision: Optional[str] = None
        
        logger.info(f"[D205-10-2 WAIT] WaitHarness v2 initialized")
        logger.info(f"[D205-10-2 WAIT] phase_hours: {config.phase_hours}")
        logger.info(f"[D205-10-2 WAIT] infeasible_margin_bps: {config.infeasible_margin_bps}")
    
    def _get_elapsed_seconds(self) -> float:
        """Monotonic 기반 경과 시간 (초)"""
        return time.monotonic() - self.start_time_monotonic
    
    def _get_utc_now(self) -> str:
        """UTC 현재 시각 (ISO 8601)"""
        return datetime.now(timezone.utc).isoformat()
    
    def watch_market(self) -> Optional[MarketSnapshot]:
        """단일 시장 스냅샷 수집"""
        try:
            elapsed = self._get_elapsed_seconds()
            timestamp_utc = self._get_utc_now()
            
            # Upbit ticker
            ticker_upbit = self.upbit_provider.get_ticker("BTC/KRW")
            if not ticker_upbit or ticker_upbit.last <= 0:
                return MarketSnapshot(
                    timestamp_utc=timestamp_utc,
                    monotonic_elapsed_sec=elapsed,
                    upbit_price_last=0, upbit_bid=0, upbit_ask=0,
                    binance_price_last=0, binance_bid=0, binance_ask=0,
                    binance_price_krw=0, fx_rate=self.config.fx_rate,
                    spread_last_bps=0, spread_conservative_bps=0,
                    break_even_bps=0, edge_bps_last=0, edge_bps_conservative=0,
                    trigger=False, error="Upbit ticker fetch failed",
                )
            
            # Binance ticker
            ticker_binance = self.binance_provider.get_ticker("BTC/USDT")
            if not ticker_binance or ticker_binance.last <= 0:
                return MarketSnapshot(
                    timestamp_utc=timestamp_utc,
                    monotonic_elapsed_sec=elapsed,
                    upbit_price_last=ticker_upbit.last,
                    upbit_bid=ticker_upbit.bid, upbit_ask=ticker_upbit.ask,
                    binance_price_last=0, binance_bid=0, binance_ask=0,
                    binance_price_krw=0, fx_rate=self.config.fx_rate,
                    spread_last_bps=0, spread_conservative_bps=0,
                    break_even_bps=0, edge_bps_last=0, edge_bps_conservative=0,
                    trigger=False, error="Binance ticker fetch failed",
                )
            
            # Price normalization
            price_upbit = ticker_upbit.last
            price_binance_usdt = ticker_binance.last
            price_binance_krw = price_binance_usdt * self.config.fx_rate
            
            # Edge 계산 (last 기반)
            candidate_last = build_candidate(
                symbol="BTC/KRW",
                exchange_a="upbit",
                exchange_b="binance",
                price_a=price_upbit,
                price_b=price_binance_krw,
                params=self.break_even_params,
            )
            
            if not candidate_last:
                return MarketSnapshot(
                    timestamp_utc=timestamp_utc,
                    monotonic_elapsed_sec=elapsed,
                    upbit_price_last=price_upbit,
                    upbit_bid=ticker_upbit.bid, upbit_ask=ticker_upbit.ask,
                    binance_price_last=price_binance_usdt,
                    binance_bid=ticker_binance.bid, binance_ask=ticker_binance.ask,
                    binance_price_krw=price_binance_krw,
                    fx_rate=self.config.fx_rate,
                    spread_last_bps=0, spread_conservative_bps=0,
                    break_even_bps=0, edge_bps_last=0, edge_bps_conservative=0,
                    trigger=False, error="build_candidate returned None",
                )
            
            # Conservative spread (bid/ask 기반)
            # Buy at ask, sell at bid → conservative spread
            conservative_spread_bps = abs(
                (ticker_upbit.ask - ticker_binance.bid * self.config.fx_rate) / 
                (ticker_binance.bid * self.config.fx_rate) * 10000
            )
            
            candidate_conservative = build_candidate(
                symbol="BTC/KRW",
                exchange_a="upbit",
                exchange_b="binance",
                price_a=ticker_upbit.ask,
                price_b=ticker_binance.bid * self.config.fx_rate,
                params=self.break_even_params,
            )
            
            edge_conservative = candidate_conservative.edge_bps if candidate_conservative else 0.0
            
            # Trigger 조건
            trigger = candidate_last.edge_bps >= self.config.trigger_min_edge_bps
            
            return MarketSnapshot(
                timestamp_utc=timestamp_utc,
                monotonic_elapsed_sec=elapsed,
                upbit_price_last=price_upbit,
                upbit_bid=ticker_upbit.bid,
                upbit_ask=ticker_upbit.ask,
                binance_price_last=price_binance_usdt,
                binance_bid=ticker_binance.bid,
                binance_ask=ticker_binance.ask,
                binance_price_krw=price_binance_krw,
                fx_rate=self.config.fx_rate,
                spread_last_bps=candidate_last.spread_bps,
                spread_conservative_bps=conservative_spread_bps,
                break_even_bps=candidate_last.break_even_bps,
                edge_bps_last=candidate_last.edge_bps,
                edge_bps_conservative=edge_conservative,
                trigger=trigger,
            )
        
        except Exception as e:
            logger.warning(f"[D205-10-2 WAIT] watch_market error: {e}")
            return MarketSnapshot(
                timestamp_utc=self._get_utc_now(),
                monotonic_elapsed_sec=self._get_elapsed_seconds(),
                upbit_price_last=0, upbit_bid=0, upbit_ask=0,
                binance_price_last=0, binance_bid=0, binance_ask=0,
                binance_price_krw=0, fx_rate=self.config.fx_rate,
                spread_last_bps=0, spread_conservative_bps=0,
                break_even_bps=0, edge_bps_last=0, edge_bps_conservative=0,
                trigger=False, error=str(e),
            )
    
    def _evaluate_feasibility(self) -> bool:
        """
        3h checkpoint에서 feasibility 평가
        
        Returns:
            True: 계속 진행 (5h까지)
            False: EARLY_INFEASIBLE (종료)
        """
        if not self.snapshots:
            return True
        
        max_spread = max([s.spread_last_bps for s in self.snapshots], default=0)
        break_even = self.snapshots[0].break_even_bps if self.snapshots else 0
        
        # Infeasible 판정: max_spread < (break_even - margin)
        threshold = break_even - self.config.infeasible_margin_bps
        
        if max_spread < threshold:
            logger.warning(
                f"[D205-10-2 WAIT] ⚠️ EARLY_INFEASIBLE: "
                f"max_spread={max_spread:.2f} < threshold={threshold:.2f}"
            )
            self.feasibility_decision = "INFEASIBLE"
            return False
        
        logger.info(
            f"[D205-10-2 WAIT] ✅ FEASIBLE: "
            f"max_spread={max_spread:.2f} >= threshold={threshold:.2f}, continuing to 5h"
        )
        self.feasibility_decision = "FEASIBLE"
        return True
    
    def _update_heartbeat(self):
        """heartbeat.json 갱신 (진행중 상태)"""
        elapsed = self._get_elapsed_seconds()
        heartbeat = {
            "timestamp_utc": self._get_utc_now(),
            "monotonic_elapsed_sec": elapsed,
            "samples_collected": len(self.snapshots),
            "trigger_count": len(self.trigger_timestamps),
            "phase_checkpoint_reached": self.phase_checkpoint_reached,
            "feasibility_decision": self.feasibility_decision,
            "last_max_edge_bps": max([s.edge_bps_last for s in self.snapshots], default=0),
        }
        
        heartbeat_path = self.evidence_dir / "heartbeat.json"
        with open(heartbeat_path, "w", encoding='utf-8') as f:
            json.dump(heartbeat, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
    
    def _update_watch_summary(self, stop_reason: Optional[str] = None):
        """watch_summary.json 갱신 (주기적 또는 종료 시)"""
        elapsed = self._get_elapsed_seconds()
        expected_samples = int(elapsed / self.config.poll_seconds) + 1
        completeness = len(self.snapshots) / expected_samples if expected_samples > 0 else 0.0
        
        # Spread 통계
        spreads = [s.spread_last_bps for s in self.snapshots if s.spread_last_bps > 0]
        p95_spread = quantiles(spreads, n=20)[18] if len(spreads) >= 20 else (max(spreads) if spreads else 0)
        
        summary = WatchSummary(
            planned_total_hours=self.config.phase_hours[-1],
            phase_hours=self.config.phase_hours,
            started_at_utc=self.start_time_utc.isoformat(),
            last_tick_at_utc=self._get_utc_now(),
            ended_at_utc=self._get_utc_now() if stop_reason else None,
            monotonic_elapsed_sec=elapsed,
            poll_sec=self.config.poll_seconds,
            samples_collected=len(self.snapshots),
            expected_samples=expected_samples,
            completeness_ratio=completeness,
            max_spread_bps=max([s.spread_last_bps for s in self.snapshots], default=0),
            p95_spread_bps=p95_spread,
            max_edge_bps=max([s.edge_bps_last for s in self.snapshots], default=0),
            min_edge_bps=min([s.edge_bps_last for s in self.snapshots], default=0),
            mean_edge_bps=sum([s.edge_bps_last for s in self.snapshots]) / len(self.snapshots) if self.snapshots else 0,
            trigger_count=len(self.trigger_timestamps),
            trigger_timestamps=self.trigger_timestamps,
            stop_reason=stop_reason,
            phase_checkpoint_reached=self.phase_checkpoint_reached,
            phase_checkpoint_time_utc=self.phase_checkpoint_time_utc,
            feasibility_decision=self.feasibility_decision,
        )
        
        summary_path = self.evidence_dir / "watch_summary.json"
        with open(summary_path, "w", encoding='utf-8') as f:
            json.dump(asdict(summary), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        
        logger.info(f"[D205-10-2 WAIT] watch_summary.json updated (stop_reason={stop_reason})")
    
    def _append_jsonl(self, snapshot: MarketSnapshot):
        """market_watch.jsonl에 실시간 추가"""
        jsonl_path = self.evidence_dir / "market_watch.jsonl"
        with open(jsonl_path, "a", encoding='utf-8') as f:
            f.write(json.dumps(asdict(snapshot)) + "\n")
            f.flush()
            os.fsync(f.fileno())
    
    def run_watch_loop(self) -> int:
        """
        Phased watch loop (3h → 5h)
        
        Returns:
            0: 성공 (trigger 발생)
            1: 실패 (trigger 미발생 또는 early-stop)
        """
        total_seconds = self.config.phase_hours[-1] * 3600
        phase_1_seconds = self.config.phase_hours[0] * 3600
        
        logger.info(f"[D205-10-2 WAIT] ========================================")
        logger.info(f"[D205-10-2 WAIT] Starting {self.config.phase_hours} phased watch loop")
        logger.info(f"[D205-10-2 WAIT] ========================================")
        
        triggered = False
        
        try:
            while self._get_elapsed_seconds() < total_seconds:
                elapsed = self._get_elapsed_seconds()
                
                # Poll
                snapshot = self.watch_market()
                if snapshot:
                    self.snapshots.append(snapshot)
                    self._append_jsonl(snapshot)
                    
                    # Trigger 체크
                    if snapshot.trigger and not triggered:
                        logger.info(f"[D205-10-2 WAIT] ✅ TRIGGER! edge_bps={snapshot.edge_bps_last:.2f}")
                        self.trigger_timestamps.append(snapshot.timestamp_utc)
                        triggered = True
                        self._update_watch_summary(stop_reason="TRIGGER_HIT")
                        return 0
                    
                    # 로그 (10회마다)
                    if len(self.snapshots) % 10 == 0:
                        logger.info(
                            f"[D205-10-2 WAIT] Samples: {len(self.snapshots)}, "
                            f"Max edge: {max([s.edge_bps_last for s in self.snapshots], default=0):.2f} bps"
                        )
                
                # Phase 1 checkpoint (3h)
                if elapsed >= phase_1_seconds and not self.phase_checkpoint_reached:
                    self.phase_checkpoint_reached = True
                    self.phase_checkpoint_time_utc = self._get_utc_now()
                    logger.info(f"[D205-10-2 WAIT] 📍 Phase 1 checkpoint reached (3h)")
                    
                    # Feasibility 평가
                    if not self._evaluate_feasibility():
                        logger.warning(f"[D205-10-2 WAIT] ❌ EARLY_INFEASIBLE, terminating")
                        self._update_watch_summary(stop_reason="EARLY_INFEASIBLE")
                        return 1
                
                # Heartbeat + Summary (60초마다)
                if time.monotonic() - self.last_heartbeat_time >= self.config.heartbeat_interval_sec:
                    self._update_heartbeat()
                    self._update_watch_summary()
                    self.last_heartbeat_time = time.monotonic()
                
                # Poll 대기
                time.sleep(self.config.poll_seconds)
            
            # 종료 (trigger 미발생)
            logger.warning(f"[D205-10-2 WAIT] ⏰ {self.config.phase_hours[-1]}h elapsed without trigger")
            self._update_watch_summary(stop_reason="TIME_REACHED")
            return 1
        
        except KeyboardInterrupt:
            logger.warning(f"[D205-10-2 WAIT] Interrupted by user (Ctrl+C)")
            self._update_watch_summary(stop_reason="INTERRUPTED")
            return 1
        
        except Exception as e:
            logger.error(f"[D205-10-2 WAIT] Fatal error: {e}", exc_info=True)
            self._update_watch_summary(stop_reason="ERROR")
            return 1
