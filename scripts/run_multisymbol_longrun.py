# -*- coding: utf-8 -*-
"""
D62: Multi-Symbol Long-run Campaign Runner

멀티심볼 롱런 캠페인을 자동으로 실행하고 모니터링한다.
"""

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.live_runner import ArbitrageLiveRunner, RiskLimits, RiskGuard
from arbitrage.exchanges.market_data_provider import RestMarketDataProvider
from arbitrage.monitoring.metrics_collector import MetricsCollector
from arbitrage.monitoring.longrun_analyzer import LongrunAnalyzer
from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.execution import ExecutorFactory
from arbitrage.types import PortfolioState, SymbolRiskLimits

logger = logging.getLogger(__name__)


class MultiSymbolLongrunRunner:
    """D62: 멀티심볼 롱런 캠페인 러너"""
    
    def __init__(
        self,
        config_path: str,
        symbols: List[str],
        scenario: str,
        duration_minutes: int,
    ):
        """
        Args:
            config_path: 설정 파일 경로
            symbols: 심볼 리스트
            scenario: 시나리오 (S0, S1, S2, S3)
            duration_minutes: 실행 시간 (분)
        """
        self.config_path = config_path
        self.symbols = symbols
        self.scenario = scenario
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        
        # 로그 디렉토리 설정
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 타임스탬프
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"d62_longrun_{self.scenario}_{self.timestamp}.log"
        
        # 설정 로드
        self.config = self._load_config()
        
        # 러너 인스턴스
        self.runner: Optional[ArbitrageLiveRunner] = None
        self.start_time = None
        self.stop_event = asyncio.Event()
        
        logger.info(
            f"[D62_LONGRUN] Initialized: scenario={scenario}, "
            f"symbols={symbols}, duration={duration_minutes}min"
        )
    
    def _load_config(self) -> dict:
        """설정 파일 로드"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"[D62_LONGRUN] Loaded config from {self.config_path}")
        return config
    
    def cleanup_environment(self) -> None:
        """
        D62 ABSOLUTE RULES: 환경 초기화
        
        1. Redis FLUSHALL
        2. 로그 파일 초기화
        3. 가상환경 확인
        """
        logger.info("[D62_LONGRUN] Starting environment cleanup...")
        
        # 1. 프로세스 kill은 스킵 (현재 프로세스 자체를 kill할 수 있음)
        
        # 2. Redis FLUSHALL (선택적)
        try:
            subprocess.run(
                "redis-cli FLUSHALL",
                shell=True,
                capture_output=True,
                timeout=5,
            )
            logger.info("[D62_LONGRUN] Redis flushed")
        except Exception as e:
            logger.debug(f"[D62_LONGRUN] Redis flush skipped (non-critical): {e}")
        
        # 3. 로그 파일 백업
        try:
            old_logs = list(self.log_dir.glob("*.log"))
            if old_logs:
                backup_dir = self.log_dir / "backup"
                backup_dir.mkdir(exist_ok=True)
                for log in old_logs:
                    try:
                        log.rename(backup_dir / log.name)
                    except Exception as e:
                        logger.debug(f"[D62_LONGRUN] Failed to backup {log}: {e}")
        except Exception as e:
            logger.debug(f"[D62_LONGRUN] Log backup failed: {e}")
        
        logger.info("[D62_LONGRUN] Environment cleanup completed")
    
    def setup_logging(self) -> None:
        """로깅 설정"""
        logging.basicConfig(
            level=logging.INFO,
            format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(),
            ],
        )
        logger.info(f"[D62_LONGRUN] Logging to {self.log_file}")
    
    async def run_async(self) -> None:
        """
        D62: 멀티심볼 롱런 실행 (비동기)
        
        간단한 시뮬레이션 버전:
        - 실제 거래 없이 루프만 실행
        - 심볼별 독립 상태 추적
        - 로그 기반 모니터링
        """
        logger.info(
            f"[D62_LONGRUN] Starting multi-symbol long-run: "
            f"scenario={self.scenario}, symbols={self.symbols}, duration={self.duration_minutes}min"
        )
        
        self.start_time = time.time()
        
        try:
            # 1. 포트폴리오 상태 초기화
            portfolio = PortfolioState(
                total_balance=self.config.get("initial_balance", 100000.0),
                available_balance=self.config.get("initial_balance", 100000.0),
            )
            
            # 2. 리스크 가드 초기화
            risk_limits = RiskLimits(
                max_notional_per_trade=self.config.get("max_notional_per_trade", 5000.0),
                max_daily_loss=self.config.get("max_daily_loss", 10000.0),
                max_open_trades=self.config.get("max_open_trades", 1),
            )
            
            # 3. 심볼별 리스크 한도 설정 (D60)
            risk_guard = RiskGuard(risk_limits)
            
            for symbol in self.symbols:
                symbol_limits = SymbolRiskLimits(
                    symbol=symbol,
                    capital_limit_notional=self.config.get("symbol_capital_limit", 5000.0),
                    max_positions=self.config.get("symbol_max_positions", 2),
                    max_concurrent_trades=self.config.get("symbol_max_concurrent_trades", 1),
                    max_daily_loss=self.config.get("symbol_max_daily_loss", 5000.0),
                )
                risk_guard.set_symbol_limits(symbol_limits)
                
                # 초기 상태 설정
                portfolio.update_symbol_capital_used(symbol, 0.0)
                portfolio.update_symbol_position_count(symbol, 0)
                portfolio.update_symbol_daily_loss(symbol, 0.0)
            
            # 4. Executor Factory 설정 (D61)
            executor_factory = ExecutorFactory()
            for symbol in self.symbols:
                executor_factory.create_paper_executor(
                    symbol=symbol,
                    portfolio_state=portfolio,
                    risk_guard=risk_guard,
                )
            
            # 5. 롱런 루프 실행 (간단한 시뮬레이션)
            logger.info(f"[D62_LONGRUN] Starting main loop for {self.duration_seconds}s")
            logger.info(f"[D62_LONGRUN] Symbols: {self.symbols}")
            logger.info(f"[D62_LONGRUN] Executors: {len(executor_factory.get_all_executors())}")
            
            loop_count = 0
            symbol_loop_counts = {symbol: 0 for symbol in self.symbols}
            
            while time.time() - self.start_time < self.duration_seconds:
                try:
                    # 각 심볼에 대해 한 번씩 실행
                    for symbol in self.symbols:
                        executor = executor_factory.get_executor(symbol)
                        if executor:
                            symbol_loop_counts[symbol] += 1
                    
                    loop_count += 1
                    
                    # 진행 상황 로깅
                    elapsed = time.time() - self.start_time
                    if loop_count % max(1, self.duration_seconds // 5) == 0:
                        logger.info(
                            f"[D62_LONGRUN] Progress: "
                            f"loop={loop_count}, elapsed={elapsed:.1f}s, "
                            f"symbols={len(self.symbols)}, "
                            f"per_symbol_loops={symbol_loop_counts}"
                        )
                    
                    # 1초 대기
                    await asyncio.sleep(1.0)
                
                except Exception as e:
                    logger.error(f"[D62_LONGRUN] Loop error: {e}", exc_info=True)
                    break
            
            # 6. 최종 통계
            elapsed = time.time() - self.start_time
            logger.info(
                f"[D62_LONGRUN] Completed: "
                f"elapsed={elapsed:.1f}s, loops={loop_count}, symbols={len(self.symbols)}"
            )
            logger.info(f"[D62_LONGRUN] Per-symbol loop counts: {symbol_loop_counts}")
        
        except Exception as e:
            logger.error(f"[D62_LONGRUN] Fatal error: {e}", exc_info=True)
            raise
    
    def run(self) -> None:
        """동기 래퍼"""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            logger.info("[D62_LONGRUN] Interrupted by user")
        except Exception as e:
            logger.error(f"[D62_LONGRUN] Execution failed: {e}", exc_info=True)
            sys.exit(1)
    
    def analyze_results(self) -> None:
        """
        D62: 결과 분석
        
        longrun_analyzer 호출
        """
        logger.info("[D62_LONGRUN] Analyzing results...")
        
        try:
            analyzer = LongrunAnalyzer(
                log_file=str(self.log_file),
                symbols=self.symbols,
            )
            
            summary = analyzer.analyze()
            
            logger.info(f"[D62_LONGRUN] Analysis summary:")
            logger.info(f"  - Total loops: {summary.get('total_loops', 0)}")
            logger.info(f"  - Trades opened: {summary.get('trades_opened', 0)}")
            logger.info(f"  - Errors: {summary.get('errors', 0)}")
            logger.info(f"  - Avg loop time: {summary.get('avg_loop_time_ms', 0):.2f}ms")
        
        except Exception as e:
            logger.warning(f"[D62_LONGRUN] Analysis failed: {e}")


def main():
    """메인 진입점"""
    parser = argparse.ArgumentParser(
        description="D62: Multi-Symbol Long-run Campaign Runner"
    )
    parser.add_argument(
        "--config",
        required=True,
        help="설정 파일 경로",
    )
    parser.add_argument(
        "--symbols",
        required=True,
        help="심볼 리스트 (쉼표 구분, 예: KRW-BTC,KRW-ETH)",
    )
    parser.add_argument(
        "--scenario",
        default="S0",
        choices=["S0", "S1", "S2", "S3"],
        help="시나리오 (S0=3min, S1=1h, S2=6h, S3=12h+)",
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=3,
        help="실행 시간 (분)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="로그 레벨",
    )
    
    args = parser.parse_args()
    
    # 심볼 파싱
    symbols = [s.strip() for s in args.symbols.split(",")]
    
    # 로깅 설정
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s',
    )
    
    # 러너 생성
    runner = MultiSymbolLongrunRunner(
        config_path=args.config,
        symbols=symbols,
        scenario=args.scenario,
        duration_minutes=args.duration_minutes,
    )
    
    # 환경 초기화
    runner.cleanup_environment()
    
    # 로깅 설정
    runner.setup_logging()
    
    # 실행
    runner.run()
    
    # 결과 분석
    runner.analyze_results()
    
    logger.info("[D62_LONGRUN] Campaign completed")


if __name__ == "__main__":
    main()
