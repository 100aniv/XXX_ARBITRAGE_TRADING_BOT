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

from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits, RiskGuard
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
        # 기존 핸들러 제거
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 새 핸들러 추가
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        stream_handler = logging.StreamHandler()
        
        formatter = logging.Formatter('[%(asctime)s] %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        logger.setLevel(logging.INFO)
        
        logger.info(f"[D62_LONGRUN] Logging to {self.log_file}")
    
    async def run_async(self) -> None:
        """
        D62-REAL: 멀티심볼 롱런 실행 (비동기)
        
        실제 Arbitrage 엔진 기반:
        - ArbitrageLiveRunner를 각 심볼별로 실행
        - 실제 거래 시뮬레이션 (Paper Mode)
        - 심볼별 독립 상태 추적
        - 실시간 로그 모니터링
        """
        logger.info(
            f"[D62_LONGRUN] Starting REAL multi-symbol long-run: "
            f"scenario={self.scenario}, symbols={self.symbols}, duration={self.duration_minutes}min"
        )
        
        self.start_time = time.time()
        
        try:
            # 1. 거래소 생성 (Paper Mode)
            from arbitrage.exchanges import PaperExchange
            
            initial_balance_a = self.config.get("initial_balance_a", {"KRW": 1000000.0})
            initial_balance_b = self.config.get("initial_balance_b", {"USDT": 10000.0})
            
            exchange_a = PaperExchange(initial_balance=initial_balance_a)
            exchange_b = PaperExchange(initial_balance=initial_balance_b)
            logger.info(f"[D62_LONGRUN] Created Paper exchanges: A={initial_balance_a}, B={initial_balance_b}")
            
            # 2. 엔진 생성
            from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
            
            engine_config = self.config.get("engine", {})
            arb_config = ArbitrageConfig(
                min_spread_bps=engine_config.get("min_spread_bps", 30.0),
                taker_fee_a_bps=engine_config.get("taker_fee_a_bps", 5.0),
                taker_fee_b_bps=engine_config.get("taker_fee_b_bps", 5.0),
                slippage_bps=engine_config.get("slippage_bps", 5.0),
                max_position_usd=engine_config.get("max_position_usd", 1000.0),
                max_open_trades=engine_config.get("max_open_trades", 1),
            )
            engine = ArbitrageEngine(arb_config)
            logger.info(f"[D62_LONGRUN] Created ArbitrageEngine with config: {arb_config}")
            
            # 3. 리스크 가드 초기화
            risk_limits = RiskLimits(
                max_notional_per_trade=self.config.get("max_notional_per_trade", 5000.0),
                max_daily_loss=self.config.get("max_daily_loss", 10000.0),
                max_open_trades=self.config.get("max_open_trades", 1),
            )
            
            # 4. 심볼별 리스크 한도 설정 (D60)
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
            
            # 5. MarketDataProvider 생성 (REST 강제)
            exchanges_dict = {"a": exchange_a, "b": exchange_b}
            provider = RestMarketDataProvider(exchanges=exchanges_dict)
            logger.info("[D62_LONGRUN] Created RestMarketDataProvider")
            
            # 6. MetricsCollector 생성
            metrics = MetricsCollector(buffer_size=300)
            logger.info("[D62_LONGRUN] Created MetricsCollector")
            
            # 7. 멀티심볼 러너 생성 (각 심볼별로 ArbitrageLiveRunner 생성)
            runners = {}
            for symbol in self.symbols:
                # 각 심볼에 대해 쌍을 정의 (예: KRW-BTC vs BTCUSDT)
                symbol_a = symbol
                symbol_b = self._get_pair_symbol(symbol)
                
                live_config = ArbitrageLiveConfig(
                    symbol_a=symbol_a,
                    symbol_b=symbol_b,
                    min_spread_bps=engine_config.get("min_spread_bps", 30.0),
                    taker_fee_a_bps=engine_config.get("taker_fee_a_bps", 5.0),
                    taker_fee_b_bps=engine_config.get("taker_fee_b_bps", 5.0),
                    slippage_bps=engine_config.get("slippage_bps", 5.0),
                    max_position_usd=engine_config.get("max_position_usd", 1000.0),
                    poll_interval_seconds=1.0,
                    max_concurrent_trades=1,
                    mode="paper",
                    log_level="INFO",
                    max_runtime_seconds=None,
                    risk_limits=risk_limits,
                    paper_simulation_enabled=True,
                    paper_volatility_range_bps=100.0,
                    paper_spread_injection_interval=5,
                    data_source="rest",
                )
                
                runner = ArbitrageLiveRunner(
                    engine=engine,
                    exchange_a=exchange_a,
                    exchange_b=exchange_b,
                    config=live_config,
                    market_data_provider=provider,
                    metrics_collector=metrics,
                )
                runners[symbol] = runner
                logger.info(f"[D62_LONGRUN] Created ArbitrageLiveRunner for {symbol_a} vs {symbol_b}")
            
            # 8. 롱런 루프 실행
            logger.info(f"[D62_LONGRUN] Starting main loop for {self.duration_seconds}s")
            logger.info(f"[D62_LONGRUN] Symbols: {self.symbols}")
            logger.info(f"[D62_LONGRUN] Runners: {len(runners)}")
            
            loop_count = 0
            symbol_loop_counts = {symbol: 0 for symbol in self.symbols}
            total_trades_opened = 0
            total_trades_closed = 0
            
            while time.time() - self.start_time < self.duration_seconds:
                try:
                    # 각 심볼에 대해 한 번씩 실행
                    for symbol in self.symbols:
                        runner = runners[symbol]
                        
                        # 실제 엔진 루프 실행
                        success = runner.run_once()
                        
                        if success:
                            symbol_loop_counts[symbol] += 1
                            total_trades_opened += runner._total_trades_opened
                            total_trades_closed += runner._total_trades_closed
                    
                    loop_count += 1
                    
                    # 진행 상황 로깅
                    elapsed = time.time() - self.start_time
                    if loop_count % max(1, self.duration_seconds // 5) == 0:
                        logger.info(
                            f"[D62_LONGRUN] Progress: "
                            f"loop={loop_count}, elapsed={elapsed:.1f}s, "
                            f"symbols={len(self.symbols)}, "
                            f"trades_opened={total_trades_opened}, "
                            f"trades_closed={total_trades_closed}, "
                            f"per_symbol_loops={symbol_loop_counts}"
                        )
                    
                    # 1초 대기
                    await asyncio.sleep(1.0)
                
                except Exception as e:
                    logger.error(f"[D62_LONGRUN] Loop error: {e}", exc_info=True)
                    break
            
            # 9. 최종 통계
            elapsed = time.time() - self.start_time
            logger.info(
                f"[D62_LONGRUN] Completed: "
                f"elapsed={elapsed:.1f}s, loops={loop_count}, symbols={len(self.symbols)}, "
                f"total_trades_opened={total_trades_opened}, total_trades_closed={total_trades_closed}"
            )
            logger.info(f"[D62_LONGRUN] Per-symbol loop counts: {symbol_loop_counts}")
            
            # 10. 최종 메트릭 출력
            if metrics:
                avg_loop_time = sum(metrics.loop_times) / len(metrics.loop_times) if metrics.loop_times else 0
                logger.info(
                    f"[D62_LONGRUN] Metrics: "
                    f"avg_loop_time={avg_loop_time:.2f}ms, "
                    f"total_trades={metrics.trades_opened_total}, "
                    f"data_source={metrics.data_source}"
                )
        
        except Exception as e:
            logger.error(f"[D62_LONGRUN] Fatal error: {e}", exc_info=True)
            raise
    
    def _get_pair_symbol(self, symbol: str) -> str:
        """
        심볼에 대한 쌍 심볼 반환
        
        Args:
            symbol: 입력 심볼 (예: "KRW-BTC")
        
        Returns:
            쌍 심볼 (예: "BTCUSDT")
        """
        # KRW-BTC -> BTCUSDT 매핑
        mapping = {
            "KRW-BTC": "BTCUSDT",
            "KRW-ETH": "ETHUSDT",
            "KRW-XRP": "XRPUSDT",
            "KRW-ADA": "ADAUSDT",
            "BTCUSDT": "KRW-BTC",
            "ETHUSDT": "KRW-ETH",
            "XRPUSDT": "KRW-XRP",
            "ADAUSDT": "KRW-ADA",
        }
        return mapping.get(symbol, "BTCUSDT")
    
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
        type=str,
        default="S0",
        choices=["S0", "S0_REAL", "S1", "S2", "S3"],
        help="시나리오: S0 (1분 드라이런), S0_REAL (10분 실행), S1 (1시간), S2 (6시간), S3 (12시간+)",
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
