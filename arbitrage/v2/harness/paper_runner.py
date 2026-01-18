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
from typing import Optional

from arbitrage.v2.opportunity import BreakEvenParams
from arbitrage.domain.fee_model import FeeModel, FeeStructure

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PaperRunnerConfig:
    """Paper Runner 설정"""
    duration_minutes: int
    phase: str = "smoke"
    run_id: str = ""
    output_dir: str = ""
    symbols_top: int = 10
    db_connection_string: str = ""
    read_only: bool = True
    db_mode: str = "optional"
    ensure_schema: bool = True
    use_real_data: bool = False
    fx_krw_per_usdt: float = 1450.0
    break_even_params: Optional[BreakEvenParams] = None
    
    def __post_init__(self):
        """자동 생성: run_id, output_dir"""
        if not self.run_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            self.run_id = f"d205_18_2d_{self.phase}_{timestamp}"
        
        if not self.output_dir:
            self.output_dir = f"logs/evidence/{self.run_id}"
        
        if not self.db_connection_string:
            self.db_connection_string = os.getenv(
                "POSTGRES_CONNECTION_STRING",
                "postgresql://arbitrage:arbitrage@localhost:5432/arbitrage"
            )
        
        if self.db_mode == "strict":
            self.ensure_schema = True
        
        if not self.break_even_params:
            self.break_even_params = BreakEvenParams(
                fee_model=FeeModel(
                    fee_a=FeeStructure(exchange_name="upbit", maker_fee_bps=5.0, taker_fee_bps=5.0),
                    fee_b=FeeStructure(exchange_name="binance", maker_fee_bps=10.0, taker_fee_bps=10.0),
                ),
                slippage_bps=5.0,
                latency_bps=2.0,
                buffer_bps=3.0,
            )


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
        logger.info(f"[D207-1] PaperRunner initialized: {config.run_id}")
    
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
        
        Returns:
            Exit code (0=success, 1=failure)
        """
        logger.info(f"[D207-1] PaperRunner starting (duration={self.config.duration_minutes}m)")
        
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
            
            logger.info(f"[D207-1] PaperRunner completed: exit_code={exit_code}")
            return exit_code
            
        except Exception as e:
            logger.error(f"[D207-1] PaperRunner failed: {e}", exc_info=True)
            return 1


def main():
    """CLI 엔트리포인트"""
    parser = argparse.ArgumentParser(description="D205-18-2D Paper Runner (Thin Wrapper)")
    parser.add_argument("--duration", type=int, required=True, help="Duration in minutes")
    parser.add_argument("--phase", default="smoke", choices=["smoke", "smoke_test", "baseline", "longrun", "test_1min"], help="Execution phase")
    parser.add_argument("--symbols-top", type=int, default=10, help="Top N symbols")
    parser.add_argument("--db-connection-string", default="", help="PostgreSQL connection string")
    parser.add_argument("--db-mode", default="optional", choices=["strict", "optional", "off"], help="DB mode")
    parser.add_argument("--ensure-schema", action=argparse.BooleanOptionalAction, default=True, help="Verify DB schema")
    parser.add_argument("--use-real-data", action="store_true", help="Use Real MarketData")
    args = parser.parse_args()
    
    # D207-1 REAL 강제 가드: baseline/longrun은 REAL MarketData 필수
    if args.phase in ["baseline", "longrun"] and not args.use_real_data:
        logger.error(f"[D207-1 GUARD] FAIL: phase={args.phase} requires --use-real-data")
        logger.error(f"[D207-1 GUARD] Reason: MOCK data is invalid for {args.phase} validation")
        logger.error(f"[D207-1 GUARD] Fix: Add --use-real-data flag")
        sys.exit(1)
    
    config = PaperRunnerConfig(
        duration_minutes=args.duration,
        phase=args.phase,
        symbols_top=args.symbols_top,
        db_connection_string=args.db_connection_string or "",
        db_mode=args.db_mode,
        ensure_schema=args.ensure_schema,
        use_real_data=args.use_real_data,
    )
    
    runner = PaperRunner(config)
    exit_code = runner.run()
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
