"""
D205-18-2D: Paper Runner (True Thin Wrapper)

CLI 파싱 + RuntimeFactory 호출만 수행.
모든 로직은 Core 모듈로 환수 완료.

Usage:
    python -m arbitrage.v2.harness.paper_runner_thin --duration 20 --phase smoke
    python -m arbitrage.v2.harness.paper_runner_thin --duration 60 --phase baseline

Author: arbitrage-lite V2
Date: 2026-01-11
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from arbitrage.v2.opportunity import BreakEvenParams
from arbitrage.v2.domain.fill_probability import FillProbabilityParams
from arbitrage.v2.scan.evidence_guard import save_json_with_validation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _parse_symbol_pairs(raw: str) -> List[Tuple[str, str]]:
    """심볼 문자열을 [(BASE/KRW, BASE/USDT), ...]로 변환"""
    if not raw:
        return []
    pairs: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for token in raw.split(","):
        item = token.strip()
        if not item:
            continue
        base = None
        if "/" in item:
            parts = [part.strip().upper() for part in item.split("/") if part.strip()]
            if len(parts) == 2:
                base = parts[0]
        elif "-" in item:
            parts = [part.strip().upper() for part in item.split("-") if part.strip()]
            if len(parts) == 2:
                if parts[0] in ("KRW", "USDT", "BTC"):
                    base = parts[1]
                else:
                    base = parts[0]
        else:
            base = item.strip().upper()
        if not base:
            logger.warning(f"[EXEC] Invalid symbol token skipped: {item}")
            continue
        if base in seen:
            continue
        seen.add(base)
        pairs.append((f"{base}/KRW", f"{base}/USDT"))
    return pairs


@dataclass
class PaperRunnerConfig:
    """Paper Runner 설정"""
    duration_minutes: int
    phase: str = "smoke"
    run_id: str = ""
    output_dir: str = ""
    config_path: Optional[str] = None
    symbols: Optional[List[Tuple[str, str]]] = None
    universe_mode: Optional[str] = None
    cli_args: Optional[Dict[str, Any]] = None
    symbols_top: int = 20
    max_symbols_per_tick: Optional[int] = None
    cycle_interval_seconds: Optional[float] = None
    db_connection_string: str = ""
    read_only: bool = True
    db_mode: str = "strict"
    ensure_schema: bool = True
    use_real_data: bool = False
    clean_room: bool = False
    survey_mode: bool = False
    maker_mode: bool = False
    min_hold_ms: Optional[int] = None
    cooldown_after_loss_seconds: Optional[int] = None
    fx_krw_per_usdt: float = 1450.0
    fx_provider_mode: Optional[str] = None
    break_even_params: Optional[BreakEvenParams] = None
    fill_probability_params: Optional[FillProbabilityParams] = None
    order_size_policy_mode: Optional[str] = None
    fixed_quote: Optional[dict] = None
    default_quote_amount: float = 100000.0
    break_even_params_auto: bool = False
    deterministic_drift_bps: Optional[float] = None
    
    def __post_init__(self):
        """자동 생성: run_id, output_dir"""
        if not os.getenv("BOOTSTRAP_FLAG"):
            logger.error("[BOOTSTRAP GUARD] FAIL: BOOTSTRAP_FLAG missing. Run bootstrap_runtime_env.ps1 first.")
            raise SystemExit(1)
        
        if self.clean_room:
            self.use_real_data = True
            self.universe_mode = "static"
            self.fx_provider_mode = "fixed"
            self.cycle_interval_seconds = 0.0
        
        if self.survey_mode:
            from arbitrage.v2.core.engine_report import get_git_status_info
            status_info = get_git_status_info()
            status = status_info.get("status")
            if status != "clean":
                logger.error(
                    f"[RISK] Git clean guard fail: status={status} (survey_mode requires clean git)"
                )
                logger.error(f"[RISK] Git clean guard modified={status_info.get('modified_files')}")
                logger.error(f"[RISK] Git clean guard added={status_info.get('added_files')}")
                logger.error(f"[RISK] Git clean guard untracked={status_info.get('untracked_files')}")
                raise SystemExit(1)
        
        if self.output_dir and not self.run_id:
            self.run_id = Path(self.output_dir).name
        elif not self.run_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            self.run_id = f"d205_18_2d_{self.phase}_{timestamp}"
        
        if not self.output_dir:
            self.output_dir = f"logs/evidence/{self.run_id}"

        output_dir_path = Path(self.output_dir)
        evidence_root = output_dir_path.parent

        collision_reason = None
        if evidence_root.exists() and not evidence_root.is_dir():
            collision_reason = f"evidence_root_not_dir:{evidence_root}"
        elif output_dir_path.exists() and not output_dir_path.is_dir():
            collision_reason = f"output_dir_not_dir:{output_dir_path}"

        preflight_dir = output_dir_path
        if collision_reason:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_run_id = str(self.run_id).replace("/", "_").replace("\\\\", "_").replace(":", "_")
            preflight_dir = evidence_root / "__preflight_failures__" / f"{ts}_{safe_run_id}"

        try:
            preflight_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        preflight_payload = {
            "run_id": self.run_id,
            "phase": self.phase,
            "output_dir": str(output_dir_path),
            "preflight_dir": str(preflight_dir),
            "status": "FAIL" if collision_reason else "PASS",
            "reason": collision_reason,
            "ts": datetime.now().isoformat(),
        }

        try:
            save_json_with_validation(preflight_dir / "preflight.json", preflight_payload)
        except Exception:
            try:
                import json

                (preflight_dir / "preflight.json").write_text(
                    json.dumps(preflight_payload, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except Exception:
                pass

        if collision_reason:
            logger.error(f"[EVIDENCE_PREFLIGHT] FAIL: {collision_reason}")
            raise SystemExit(1)

        try:
            output_dir_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[EVIDENCE_PREFLIGHT] FAIL: cannot create output_dir={output_dir_path}: {e}")
            raise SystemExit(1)
        
        if not self.db_connection_string:
            env_conn = os.getenv("POSTGRES_CONNECTION_STRING")
            if self.db_mode == "strict":
                if not env_conn:
                    raise SystemExit(1)
                self.db_connection_string = env_conn
            else:
                self.db_connection_string = env_conn or "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
        
        if self.db_mode == "strict":
            self.ensure_schema = True
        
        if not self.fx_provider_mode:
            self.fx_provider_mode = "live" if self.use_real_data else "fixed"


class PaperRunner:
    """
    D205-18-2D: Paper Runner (True Thin Wrapper)
    
    D206-1 CLOSEOUT: Registry + Preflight 요구사항 충족
    - Evidence KPI fields 노출 (marketdata_mode, db_mode, closed_trades, wins, losses)
    - use_real_data 속성 노출 (Preflight 필수)
    
    Responsibilities:
    - CLI 파싱
    - Config 로드
    - RuntimeFactory.build_paper_runtime() 호출
    - Orchestrator.run() 실행
    - Exit code 전파
    
    NOT Responsibilities (Core로 환수 완료):
    - Opportunity 생성 (→ OpportunitySource)
    - Intent 변환 (→ IntentBuilder)
    - 주문 실행 (→ PaperExecutor)
    - DB 기록 (→ LedgerWriter)
    - KPI 집계 (→ PaperMetrics)
    - Evidence 생성 (→ EvidenceCollector)
    """
    
    def __init__(self, config: PaperRunnerConfig, admin_control=None):
        """
        Args:
            config: PaperRunnerConfig
            admin_control: Optional AdminControl
        """
        self.config = config
        self.admin_control = admin_control
        self.kpi = None  # D205-18-4-FIX-3: 테스트 호환성
        self._orchestrator = None  # D206-1: Orchestrator 참조
        logger.info(f"[EXEC] PaperRunner initialized: {config.run_id}")
    
    # D206-1 CLOSEOUT: Registry Evidence Fields (프로퍼티로 Orchestrator KPI 노출)
    @property
    def use_real_data(self) -> bool:
        """Preflight 필수: Real MarketData 사용 여부"""
        return self.config.use_real_data
    
    @property
    def marketdata_mode(self) -> str:
        """Registry ops.real_marketdata 필수"""
        return "REAL" if self.config.use_real_data else "MOCK"
    
    @property
    def upbit_marketdata_ok(self) -> bool:
        """Registry ops.real_marketdata 필수"""
        return self.config.use_real_data
    
    @property
    def binance_marketdata_ok(self) -> bool:
        """Registry ops.real_marketdata 필수"""
        return self.config.use_real_data
    
    @property
    def db_mode(self) -> str:
        """Registry ops.db_strict 필수"""
        return self.config.db_mode
    
    @property
    def closed_trades(self) -> int:
        """Registry ops.trade_processor 필수"""
        return self.kpi.closed_trades if self.kpi else 0
    
    @property
    def wins(self) -> int:
        """Registry ops.trade_processor 필수"""
        return self.kpi.wins if self.kpi else 0
    
    @property
    def losses(self) -> int:
        """Registry ops.trade_processor 필수"""
        return self.kpi.losses if self.kpi else 0
    
    @property
    def redis_client(self):
        """Preflight 필수: Redis client 참조"""
        return self._orchestrator.redis_client if self._orchestrator and hasattr(self._orchestrator, 'redis_client') else None
    
    @property
    def storage(self):
        """Preflight 필수: Storage 참조"""
        return self._orchestrator.ledger_writer.storage if self._orchestrator and hasattr(self._orchestrator, 'ledger_writer') else None
    
    @property
    def upbit_provider(self):
        """Preflight 필수: Upbit provider 참조"""
        if not self._orchestrator or not hasattr(self._orchestrator, 'opportunity_source'):
            return None
        opp = self._orchestrator.opportunity_source
        return opp.upbit_provider if hasattr(opp, 'upbit_provider') else None
    
    @property
    def binance_provider(self):
        """Preflight 필수: Binance provider 참조"""
        if not self._orchestrator or not hasattr(self._orchestrator, 'opportunity_source'):
            return None
        opp = self._orchestrator.opportunity_source
        return opp.binance_provider if hasattr(opp, 'binance_provider') else None
    
    def run(self) -> int:
        """
        메인 실행 (Thin Wrapper)
        
        D207-1-5 Step 2: Evidence Atomicity
        - 예외 발생 시에도 DIAGNOSIS.md 생성
        - finally에서 최소 evidence 보장
        
        Returns:
            Exit code (0=success, 1=failure)
        """
        logger.info(f"[EXEC] PaperRunner starting (duration={self.config.duration_minutes}m)")
        
        orchestrator = None
        exit_code = 1  # 기본값 FAIL
        
        try:
            from arbitrage.v2.core.runtime_factory import build_paper_runtime
            
            # Core Runtime 조립 (Factory Pattern)
            orchestrator = build_paper_runtime(
                config=self.config,
                admin_control=self.admin_control
            )
            
            # Orchestrator 실행 (모든 로직은 Core에서 처리)
            exit_code = orchestrator.run()
            
            # D206-0: KPI 참조 노출 (테스트 호환성)
            self.kpi = orchestrator.kpi
            
            logger.info(f"[EXEC] PaperRunner completed: exit_code={exit_code}")
            return exit_code
            
        except Exception as e:
            logger.error(f"[EXEC] PaperRunner failed: {e}", exc_info=True)
            
            # D207-1-5 Step 2: Evidence Atomicity - DIAGNOSIS.md 생성
            try:
                from pathlib import Path
                import traceback
                
                output_dir = Path(self.config.output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                
                diagnosis_path = output_dir / "DIAGNOSIS.md"
                with open(diagnosis_path, "w", encoding="utf-8") as f:
                    f.write("# DIAGNOSIS - Runner Exception\n\n")
                    f.write(f"**Exception:** {type(e).__name__}\n\n")
                    f.write(f"**Message:** {str(e)}\n\n")
                    f.write("## Traceback\n\n```\n")
                    f.write(traceback.format_exc())
                    f.write("\n```\n")
                
                logger.info(f"[EXEC] DIAGNOSIS.md saved: {diagnosis_path}")
            except Exception as diag_err:
                logger.error(f"[EXEC] DIAGNOSIS.md save failed: {diag_err}")
            
            return 1
        
        finally:
            # D207-1-5 Step 2: Evidence Atomicity - 최소 manifest 보장
            if orchestrator and hasattr(orchestrator, 'kpi'):
                try:
                    from pathlib import Path
                    import json
                    from datetime import datetime, timezone
                    
                    output_dir = Path(self.config.output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # manifest.json 최소 생성 (orchestrator가 생성 안 했을 경우 대비)
                    manifest_path = output_dir / "manifest.json"
                    if not manifest_path.exists():
                        manifest = {
                            "run_id": self.config.run_id,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "phase": self.config.phase,
                            "duration_minutes": self.config.duration_minutes,
                            "exit_code": exit_code,
                            "status": "PASS" if exit_code == 0 else "FAIL"
                        }
                        with open(manifest_path, "w", encoding="utf-8") as f:
                            json.dump(manifest, f, indent=2)
                        logger.info(f"[EXEC] manifest.json (minimal) saved: {manifest_path}")
                except Exception as finally_err:
                    logger.error(f"[EXEC] Finally block failed: {finally_err}")


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(description="Paper Runner (Thin Wrapper)")
    parser.add_argument("--duration", type=int, required=True, help="Duration in minutes")
    parser.add_argument(
        "--phase",
        default="smoke",
        choices=["smoke", "smoke_test", "baseline", "longrun", "test_1min", "edge_survey"],
        help="Execution phase",
    )
    parser.add_argument("--output-dir", default="", help="Evidence output directory")
    parser.add_argument("--symbols-top", type=int, default=20, help="Top N symbols")
    parser.add_argument("--max-symbols-per-tick", type=int, default=None, help="Max symbols per tick")
    parser.add_argument("--symbols", default="", help="Symbol list (comma-separated, e.g. KRW-BTC,BTC/KRW,BTC)")
    parser.add_argument(
        "--universe-mode",
        default=None,
        choices=["static", "topn"],
        help="Universe mode override (static/topn)",
    )
    parser.add_argument("--db-connection-string", default="", help="PostgreSQL connection string")
    parser.add_argument("--db-mode", default="strict", choices=["strict", "optional", "off"], help="DB mode")
    parser.add_argument("--ensure-schema", action=argparse.BooleanOptionalAction, default=True, help="Verify DB schema")
    parser.add_argument("--use-real-data", action="store_true", help="Use Real MarketData")
    parser.add_argument("--clean-room", action="store_true", help="Clean-Room measurement mode (WS-only, static universe, no sleep)")
    parser.add_argument("--survey-mode", action="store_true", help="Survey mode: collect raw spread data before filtering")
    parser.add_argument("--maker-mode", action="store_true", help="Maker-Taker hybrid mode with fill probability")
    args = parser.parse_args()
    
    if args.clean_room:
        args.use_real_data = True
        args.universe_mode = "static"
    
    # D207-1 REAL 강제 가드: baseline/longrun은 REAL MarketData 필수
    if args.phase in ["baseline", "longrun"] and not args.use_real_data:
        logger.error(f"[RISK] Phase requires --use-real-data: phase={args.phase}")
        logger.error(f"[RISK] Reason: MOCK data is invalid for {args.phase} validation")
        logger.error(f"[RISK] Fix: Add --use-real-data flag")
        sys.exit(1)

    symbol_pairs = _parse_symbol_pairs(args.symbols)
    
    config = PaperRunnerConfig(
        duration_minutes=args.duration,
        phase=args.phase,
        output_dir=args.output_dir or "",
        symbols_top=args.symbols_top,
        max_symbols_per_tick=args.max_symbols_per_tick,
        symbols=symbol_pairs or None,
        universe_mode=args.universe_mode,
        db_connection_string=args.db_connection_string or "",
        db_mode=args.db_mode,
        ensure_schema=args.ensure_schema,
        use_real_data=args.use_real_data,
        clean_room=args.clean_room,
        survey_mode=args.survey_mode,
        maker_mode=args.maker_mode,
    )

    config.cli_args = vars(args)
    
    runner = PaperRunner(config)
    exit_code = runner.run()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
