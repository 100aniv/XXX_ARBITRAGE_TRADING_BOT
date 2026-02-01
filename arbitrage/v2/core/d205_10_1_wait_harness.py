"""
D205-10-1: Wait Harness (10h Market Watch + Trigger Execute)

목적:
- 10시간 동안 시장 조건 감시 (poll_seconds 간격)
- edge_bps >= trigger_min_edge_bps 조건 충족 시 자동 sweep/smoke 실행
- Evidence: market_watch.jsonl + watch_summary.json
"""

import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from arbitrage.v2.core.runtime_factory import build_break_even_params_from_config_path
from arbitrage.v2.domain.break_even import BreakEvenParams
from arbitrage.v2.opportunity import build_candidate
from arbitrage.v2.marketdata.rest import BinanceRestProvider, UpbitRestProvider

logger = logging.getLogger(__name__)


@dataclass
class WaitHarnessConfig:
    """Wait Harness 설정"""
    duration_hours: int = 10
    poll_seconds: int = 30
    trigger_min_edge_bps: float = 0.0
    fx_rate: float = 1450.0
    evidence_dir: str = ""
    sweep_duration_minutes: int = 2
    db_mode: str = "off"
    config_path: str = "config/v2/config.yml"
    break_even_params: Optional[BreakEvenParams] = None

    def __post_init__(self):
        if not self.evidence_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.evidence_dir = f"logs/evidence/d205_10_1_wait_{timestamp}"


@dataclass
class MarketSnapshot:
    """시장 스냅샷"""
    timestamp: str
    upbit_price: float
    binance_price: float
    binance_price_krw: float
    fx_rate: float
    spread_bps: float
    break_even_bps: float
    edge_bps: float
    trigger: bool
    error: Optional[str] = None


class WaitHarness:
    """
    Wait Harness 엔진

    Flow:
        1. Market snapshot 수집 (poll_seconds 간격)
        2. Edge 계산 (build_candidate 재사용)
        3. Trigger 조건 체크 (edge_bps >= trigger_min_edge_bps)
        4. Trigger 시 subprocess로 sweep + smoke 실행
        5. Evidence 저장 (market_watch.jsonl + watch_summary.json)
    """

    def __init__(self, config: WaitHarnessConfig):
        self.config = config

        # Evidence 디렉토리 생성
        self.evidence_dir = Path(config.evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

        # MarketData Providers
        try:
            self.upbit_provider = UpbitRestProvider(timeout=10.0)
            self.binance_provider = BinanceRestProvider(timeout=10.0)
            logger.info("[D205-10-1 WAIT] ✅ MarketData Providers initialized")
        except Exception as e:
            logger.error(f"[D205-10-1 WAIT] ❌ Provider init failed: {e}", exc_info=True)
            raise RuntimeError(f"MarketData Provider initialization failed: {e}")

        if config.break_even_params is not None:
            self.break_even_params = config.break_even_params
        else:
            self.break_even_params = build_break_even_params_from_config_path(config.config_path)

        # Watch 기록
        self.snapshots: List[MarketSnapshot] = []
        self.trigger_timestamps: List[str] = []

        logger.info("[D205-10-1 WAIT] WaitHarness initialized")
        logger.info(f"[D205-10-1 WAIT] duration_hours: {config.duration_hours}h")
        logger.info(f"[D205-10-1 WAIT] poll_seconds: {config.poll_seconds}s")
        logger.info(f"[D205-10-1 WAIT] trigger_min_edge_bps: {config.trigger_min_edge_bps} bps")
        logger.info(f"[D205-10-1 WAIT] evidence_dir: {self.evidence_dir}")

    def watch_market(self) -> Optional[MarketSnapshot]:
        """
        단일 시장 스냅샷 수집 + edge 계산

        Returns:
            MarketSnapshot 또는 None (에러 시)
        """
        try:
            # Upbit BTC/KRW ticker
            ticker_upbit = self.upbit_provider.get_ticker("BTC/KRW")
            if not ticker_upbit or ticker_upbit.last <= 0:
                return MarketSnapshot(
                    timestamp=datetime.now().isoformat(),
                    upbit_price=0,
                    binance_price=0,
                    binance_price_krw=0,
                    fx_rate=self.config.fx_rate,
                    spread_bps=0,
                    break_even_bps=0,
                    edge_bps=0,
                    trigger=False,
                    error="Upbit ticker fetch failed",
                )

            # Binance BTC/USDT ticker
            ticker_binance = self.binance_provider.get_ticker("BTC/USDT")
            if not ticker_binance or ticker_binance.last <= 0:
                return MarketSnapshot(
                    timestamp=datetime.now().isoformat(),
                    upbit_price=ticker_upbit.last,
                    binance_price=0,
                    binance_price_krw=0,
                    fx_rate=self.config.fx_rate,
                    spread_bps=0,
                    break_even_bps=0,
                    edge_bps=0,
                    trigger=False,
                    error="Binance ticker fetch failed",
                )

            # Price normalization (Binance USDT → KRW)
            price_a = ticker_upbit.last
            price_b_usdt = ticker_binance.last
            price_b_krw = price_b_usdt * self.config.fx_rate

            # Build candidate (edge 계산)
            candidate = build_candidate(
                symbol="BTC/KRW",
                exchange_a="upbit",
                exchange_b="binance",
                price_a=price_a,
                price_b=price_b_krw,
                params=self.break_even_params,
            )

            if not candidate:
                return MarketSnapshot(
                    timestamp=datetime.now().isoformat(),
                    upbit_price=price_a,
                    binance_price=price_b_usdt,
                    binance_price_krw=price_b_krw,
                    fx_rate=self.config.fx_rate,
                    spread_bps=0,
                    break_even_bps=0,
                    edge_bps=0,
                    trigger=False,
                    error="build_candidate returned None",
                )

            # Trigger 조건 체크
            trigger = candidate.edge_bps >= self.config.trigger_min_edge_bps

            return MarketSnapshot(
                timestamp=datetime.now().isoformat(),
                upbit_price=price_a,
                binance_price=price_b_usdt,
                binance_price_krw=price_b_krw,
                fx_rate=self.config.fx_rate,
                spread_bps=candidate.spread_bps,
                break_even_bps=candidate.break_even_bps,
                edge_bps=candidate.edge_bps,
                trigger=trigger,
            )

        except Exception as e:
            logger.warning(f"[D205-10-1 WAIT] watch_market error: {e}")
            return MarketSnapshot(
                timestamp=datetime.now().isoformat(),
                upbit_price=0,
                binance_price=0,
                binance_price_krw=0,
                fx_rate=self.config.fx_rate,
                spread_bps=0,
                break_even_bps=0,
                edge_bps=0,
                trigger=False,
                error=str(e),
            )

    def run_watch_loop(self) -> int:
        """
        10시간 감시 루프

        Returns:
            0: 성공 (트리거 발생 + sweep/smoke 실행)
            1: 실패 (트리거 미발생 또는 에러)
        """
        start_time = time.time()
        end_time = start_time + (self.config.duration_hours * 3600)

        logger.info("[D205-10-1 WAIT] ========================================")
        logger.info(f"[D205-10-1 WAIT] Starting {self.config.duration_hours}h watch loop")
        logger.info("[D205-10-1 WAIT] ========================================")

        triggered = False

        try:
            while time.time() < end_time:
                elapsed_seconds = int(time.time() - start_time)
                logger.info(
                    f"[D205-10-1 WAIT] Polling... (elapsed: {elapsed_seconds}s / {self.config.duration_hours * 3600}s)"
                )

                # Market snapshot
                snapshot = self.watch_market()

                if snapshot:
                    self.snapshots.append(snapshot)

                    # JSONL 저장 (실시간)
                    self._append_jsonl(snapshot)

                    # Trigger 조건 충족 시
                    if snapshot.trigger and not triggered:
                        logger.info(
                            f"[D205-10-1 WAIT] ✅ TRIGGER! edge_bps={snapshot.edge_bps:.2f} "
                            f">= {self.config.trigger_min_edge_bps}"
                        )
                        self.trigger_timestamps.append(snapshot.timestamp)
                        triggered = True

                        # Sweep + Smoke 실행
                        sweep_ok = self._trigger_sweep_and_smoke()

                        if sweep_ok:
                            logger.info("[D205-10-1 WAIT] ✅ Sweep + Smoke executed successfully")
                            self._save_watch_summary()
                            return 0

                        logger.error("[D205-10-1 WAIT] ❌ Sweep + Smoke failed")
                        self._save_watch_summary()
                        return 1

                    # 로그 (10회마다)
                    if len(self.snapshots) % 10 == 0:
                        logger.info(
                            f"[D205-10-1 WAIT] Samples: {len(self.snapshots)}, "
                            f"Max edge: {max([s.edge_bps for s in self.snapshots], default=0):.2f} bps"
                        )

                # Poll 간격 대기
                time.sleep(self.config.poll_seconds)

            # 10시간 종료 (트리거 미발생)
            logger.warning(f"[D205-10-1 WAIT] ⏰ {self.config.duration_hours}h elapsed without trigger")
            self._save_watch_summary()

            # Auto-Postmortem Rule
            logger.error("[D205-10-1 WAIT] ❌ AUTO-POSTMORTEM: Market conditions did not meet trigger threshold")
            logger.error("[D205-10-1 WAIT] D205-10-1 status: PARTIAL (시장 환경 제약)")
            logger.error("[D205-10-1 WAIT] Recommendation: Recalibrate break_even params or wait for higher volatility")

            return 1

        except KeyboardInterrupt:
            logger.warning("[D205-10-1 WAIT] Interrupted by user (Ctrl+C)")
            self._save_watch_summary()
            return 1

        except Exception as e:
            logger.error(f"[D205-10-1 WAIT] Fatal error: {e}", exc_info=True)
            self._save_watch_summary()
            return 1

    def _trigger_sweep_and_smoke(self) -> bool:
        """
        Trigger 발생 시 subprocess로 sweep + smoke 실행

        Returns:
            True: 성공
            False: 실패
        """
        try:
            # 1) Sweep 실행
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sweep_evidence_dir = self.evidence_dir / f"sweep_{timestamp}"

            logger.info("[D205-10-1 WAIT] Executing sweep...")
            sweep_cmd = [
                sys.executable,
                "scripts/run_d205_10_1_sweep.py",
                "--duration-minutes", str(self.config.sweep_duration_minutes),
                "--use-real-data",
                "--db-mode", self.config.db_mode,
                "--fx-krw-per-usdt", str(self.config.fx_rate),
                "--out-evidence-dir", str(sweep_evidence_dir),
            ]

            sweep_result = subprocess.run(
                sweep_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )

            if sweep_result.returncode != 0:
                logger.error(f"[D205-10-1 WAIT] Sweep failed with exit code {sweep_result.returncode}")
                logger.error(f"[D205-10-1 WAIT] Sweep stderr: {sweep_result.stderr[:500]}")
                return False

            logger.info("[D205-10-1 WAIT] ✅ Sweep completed")

            # 2) sweep_summary.json 분석
            sweep_summary_path = sweep_evidence_dir / "sweep_summary.json"
            if not sweep_summary_path.exists():
                logger.error(f"[D205-10-1 WAIT] sweep_summary.json not found: {sweep_summary_path}")
                return False

            with open(sweep_summary_path, "r") as f:
                summary = json.load(f)

            best_buffer_bps = summary.get("best_selection", {}).get("best_buffer_bps")

            if best_buffer_bps is None:
                logger.warning("[D205-10-1 WAIT] No best_buffer selected (closed_trades=0)")
                logger.warning("[D205-10-1 WAIT] Skipping 20m smoke test")

                # Sweep link 저장
                self._save_link("sweep_link.txt", str(sweep_evidence_dir))
                return False

            logger.info(f"[D205-10-1 WAIT] Best buffer: {best_buffer_bps} bps")

            # 3) 20m Smoke 실행
            smoke_evidence_dir = self.evidence_dir / f"smoke_{timestamp}"

            logger.info(f"[D205-10-1 WAIT] Executing 20m smoke (best_buffer={best_buffer_bps})...")
            smoke_cmd = [
                sys.executable,
                "scripts/run_d205_10_1_smoke_best_buffer.py",
                "--sweep-summary", str(sweep_summary_path),
                "--use-real-data",
                "--db-mode", self.config.db_mode,
                "--fx-krw-per-usdt", str(self.config.fx_rate),
                "--out-evidence-dir", str(smoke_evidence_dir),
            ]

            smoke_result = subprocess.run(
                smoke_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )

            if smoke_result.returncode != 0:
                logger.error(f"[D205-10-1 WAIT] Smoke failed with exit code {smoke_result.returncode}")
                logger.error(f"[D205-10-1 WAIT] Smoke stderr: {smoke_result.stderr[:500]}")

                # Links 저장
                self._save_link("sweep_link.txt", str(sweep_evidence_dir))
                self._save_link("smoke_link.txt", str(smoke_evidence_dir))
                return False

            logger.info("[D205-10-1 WAIT] ✅ 20m smoke completed")

            # Links 저장
            self._save_link("sweep_link.txt", str(sweep_evidence_dir))
            self._save_link("smoke_link.txt", str(smoke_evidence_dir))

            return True

        except Exception as e:
            logger.error(f"[D205-10-1 WAIT] _trigger_sweep_and_smoke error: {e}", exc_info=True)
            return False

    def _append_jsonl(self, snapshot: MarketSnapshot):
        """market_watch.jsonl에 실시간 추가"""
        jsonl_path = self.evidence_dir / "market_watch.jsonl"
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot.__dict__) + "\n")

    def _save_watch_summary(self):
        """watch_summary.json 저장 (종료 시)"""
        summary = {
            "start_time": self.snapshots[0].timestamp if self.snapshots else None,
            "end_time": self.snapshots[-1].timestamp if self.snapshots else None,
            "duration_hours": self.config.duration_hours,
            "poll_seconds": self.config.poll_seconds,
            "trigger_min_edge_bps": self.config.trigger_min_edge_bps,
            "samples_total": len(self.snapshots),
            "trigger_count": len(self.trigger_timestamps),
            "trigger_timestamps": self.trigger_timestamps,
            "max_edge_bps": max([s.edge_bps for s in self.snapshots], default=0),
            "min_edge_bps": min([s.edge_bps for s in self.snapshots], default=0),
            "mean_edge_bps": sum([s.edge_bps for s in self.snapshots]) / len(self.snapshots) if self.snapshots else 0,
            "sweep_executed": len(self.trigger_timestamps) > 0,
            "smoke_executed": len(self.trigger_timestamps) > 0,
        }

        summary_path = self.evidence_dir / "watch_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"[D205-10-1 WAIT] watch_summary.json saved: {summary_path}")

    def _save_link(self, filename: str, target_path: str):
        """Link 파일 저장 (sweep/smoke evidence 경로)"""
        link_path = self.evidence_dir / filename
        with open(link_path, "w", encoding="utf-8") as f:
            f.write(target_path)
        logger.info(f"[D205-10-1 WAIT] Link saved: {link_path} → {target_path}")
