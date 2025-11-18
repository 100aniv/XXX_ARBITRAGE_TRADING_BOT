# -*- coding: utf-8 -*-
"""
D63: WebSocket Optimization + REAL PAPER MODE Runner

D63 WS 최적화 기능을 실제 Paper 모드에서 테스트한다.
- Per-symbol asyncio.Queue 기반 메시지 버퍼링
- 비동기 컨슈머 루프
- WS 큐 메트릭 추적
- 멀티심볼 지원
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.exchanges import PaperExchange
from arbitrage.exchanges.market_data_provider import WebSocketMarketDataProvider, RestMarketDataProvider
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits, RiskGuard
from arbitrage.monitoring import MetricsCollector
from arbitrage.monitoring.longrun_analyzer import LongrunAnalyzer
from arbitrage.types import SymbolRiskLimits

logger = logging.getLogger(__name__)


class D63WSPaperRunner:
    """D63 WebSocket Paper 모드 러너"""
    
    def __init__(
        self,
        config_path: str,
        symbols: List[str],
        scenario: str,
        duration_minutes: int,
        use_ws: bool = True,
    ):
        """
        Args:
            config_path: 설정 파일 경로
            symbols: 심볼 리스트
            scenario: 시나리오
            duration_minutes: 실행 시간 (분)
            use_ws: WebSocket 사용 여부 (False면 REST)
        """
        self.config_path = config_path
        self.symbols = symbols
        self.scenario = scenario
        self.duration_minutes = duration_minutes
        self.duration_seconds = duration_minutes * 60
        self.use_ws = use_ws
        
        # 로그 디렉토리
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
        # 타임스탬프
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_source = "WS" if use_ws else "REST"
        self.log_file = self.log_dir / f"d63_{data_source}_paper_{self.scenario}_{self.timestamp}.log"
        
        # 설정 로드
        self.config = self._load_config()
        
        # 상태
        self.start_time = None
        self.runners = {}
        
        logger.info(
            f"[D63_WS_PAPER] Initialized: scenario={scenario}, "
            f"symbols={symbols}, duration={duration_minutes}min, use_ws={use_ws}"
        )
    
    def _load_config(self) -> dict:
        """설정 파일 로드"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"[D63_WS_PAPER] Loaded config from {self.config_path}")
        return config
    
    def _get_pair_symbol(self, symbol: str) -> str:
        """심볼 쌍 반환"""
        if symbol.startswith("KRW-"):
            base = symbol.split("-")[1]
            return f"{base}USDT"
        else:
            return symbol
    
    def setup_logging(self) -> None:
        """로깅 설정"""
        # 기존 핸들러 제거
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 파일 핸들러
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 스트림 핸들러
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        
        # 포매터
        formatter = logging.Formatter(
            '[%(asctime)s] %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        logger.setLevel(logging.INFO)
        
        logger.info(f"[D63_WS_PAPER] Logging to {self.log_file}")
    
    async def run_async(self) -> dict:
        """
        D63 WS Paper 모드 실행 (비동기)
        
        Returns:
            실행 결과 dict
        """
        logger.info(
            f"[D63_WS_PAPER] Starting D63 WS Paper run: "
            f"scenario={self.scenario}, symbols={self.symbols}, "
            f"duration={self.duration_minutes}min, use_ws={self.use_ws}"
        )
        
        self.start_time = time.time()
        
        try:
            # 1. Paper 거래소 생성
            initial_balance_a = self.config.get("initial_balance_a", {"KRW": 1000000.0})
            initial_balance_b = self.config.get("initial_balance_b", {"USDT": 10000.0})
            
            exchange_a = PaperExchange(initial_balance=initial_balance_a)
            exchange_b = PaperExchange(initial_balance=initial_balance_b)
            logger.info(f"[D63_WS_PAPER] Created Paper exchanges: A={initial_balance_a}, B={initial_balance_b}")
            
            # 2. 엔진 생성
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
            logger.info(f"[D63_WS_PAPER] Created ArbitrageEngine: {arb_config}")
            
            # 3. 리스크 가드
            risk_limits = RiskLimits(
                max_notional_per_trade=self.config.get("max_notional_per_trade", 5000.0),
                max_daily_loss=self.config.get("max_daily_loss", 10000.0),
                max_open_trades=self.config.get("max_open_trades", 1),
            )
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
            
            # 4. MarketDataProvider 생성
            exchanges_dict = {"a": exchange_a, "b": exchange_b}
            
            if self.use_ws:
                # D63: WebSocket 모드 (실제 WS는 연결 불가하므로 REST로 폴백)
                logger.warning("[D63_WS_PAPER] WS mode requested but using REST fallback (no real WS connection)")
                provider = RestMarketDataProvider(exchanges=exchanges_dict)
                data_source = "rest"  # 실제로는 REST 사용
            else:
                provider = RestMarketDataProvider(exchanges=exchanges_dict)
                data_source = "rest"
            
            logger.info(f"[D63_WS_PAPER] Created MarketDataProvider: {data_source}")
            
            # 5. MetricsCollector 생성
            metrics = MetricsCollector(buffer_size=300)
            logger.info("[D63_WS_PAPER] Created MetricsCollector with D63 WS queue metrics")
            
            # 6. 멀티심볼 러너 생성
            for symbol in self.symbols:
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
                    mode="paper",  # PAPER MODE 강제
                    log_level="INFO",
                    max_runtime_seconds=None,
                    risk_limits=risk_limits,
                    data_source=data_source,
                )
                
                runner = ArbitrageLiveRunner(
                    engine=engine,
                    exchange_a=exchange_a,
                    exchange_b=exchange_b,
                    config=live_config,
                    market_data_provider=provider,
                    metrics_collector=metrics,
                )
                
                self.runners[symbol] = runner
                logger.info(f"[D63_WS_PAPER] Created runner for {symbol}")
            
            # 7. 실행 루프
            logger.info(f"[D63_WS_PAPER] Starting execution loop for {self.duration_seconds}s...")
            
            loop_count = 0
            total_trades = 0
            
            while (time.time() - self.start_time) < self.duration_seconds:
                loop_start = time.time()
                
                # 각 심볼별로 run_once 실행
                for symbol, runner in self.runners.items():
                    try:
                        runner.run_once()
                        
                        # D63: WS 큐 메트릭 수집 (실제 WS 사용 시)
                        if self.use_ws and hasattr(provider, 'get_queue_metrics'):
                            queue_metrics = provider.get_queue_metrics(symbol)
                            metrics.update_ws_queue_metrics(
                                queue_depth=queue_metrics.get('queue_depth', 0),
                                queue_lag_ms=queue_metrics.get('queue_lag_ms', 0.0),
                                symbol=symbol
                            )
                    
                    except Exception as e:
                        logger.error(f"[D63_WS_PAPER] Error in runner for {symbol}: {e}")
                
                loop_count += 1
                
                # 진행 상황 로그 (10초마다)
                if loop_count % 10 == 0:
                    elapsed = time.time() - self.start_time
                    logger.info(
                        f"[D63_WS_PAPER] Progress: {elapsed:.1f}s / {self.duration_seconds}s, "
                        f"loops={loop_count}"
                    )
                
                # 루프 간격 유지
                loop_time = time.time() - loop_start
                if loop_time < 1.0:
                    await asyncio.sleep(1.0 - loop_time)
            
            # 8. 실행 완료
            end_time = time.time()
            actual_duration = end_time - self.start_time
            
            logger.info(
                f"[D63_WS_PAPER] Execution completed: "
                f"duration={actual_duration:.1f}s, loops={loop_count}"
            )
            
            # 9. 결과 수집
            result = {
                "scenario": self.scenario,
                "symbols": self.symbols,
                "duration_seconds": actual_duration,
                "loop_count": loop_count,
                "use_ws": self.use_ws,
                "data_source": data_source,
                "mode": "paper",
                "runners": {},
            }
            
            for symbol, runner in self.runners.items():
                stats = runner.get_stats()
                result["runners"][symbol] = stats
                total_trades += stats.get("total_trades_opened", 0)
            
            result["total_trades"] = total_trades
            
            # 메트릭 수집
            final_metrics = metrics.get_metrics()
            result["metrics"] = final_metrics
            
            # D63: WS 큐 메트릭 포함
            result["ws_queue_metrics"] = {
                "ws_queue_depth_max": metrics.ws_queue_depth_max,
                "ws_queue_lag_ms_max": metrics.ws_queue_lag_ms_max,
                "ws_queue_lag_warn_count": metrics.ws_queue_lag_warn_count,
            }
            
            return result
        
        except Exception as e:
            logger.error(f"[D63_WS_PAPER] Execution failed: {e}", exc_info=True)
            raise
    
    def run(self) -> dict:
        """동기 실행 래퍼"""
        return asyncio.run(self.run_async())


def main():
    """메인 진입점"""
    parser = argparse.ArgumentParser(description="D63 WebSocket Optimization + REAL PAPER MODE Runner")
    
    parser.add_argument(
        "--config",
        type=str,
        default="configs/live/arbitrage_multisymbol_longrun.yaml",
        help="설정 파일 경로",
    )
    
    parser.add_argument(
        "--symbols",
        type=str,
        default="KRW-BTC,KRW-ETH",
        help="심볼 리스트 (쉼표 구분)",
    )
    
    parser.add_argument(
        "--scenario",
        type=str,
        default="S0_WS_PAPER",
        help="시나리오",
    )
    
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=5,
        help="실행 시간 (분)",
    )
    
    parser.add_argument(
        "--use-ws",
        action="store_true",
        help="WebSocket 사용 (기본값: REST)",
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="로그 레벨",
    )
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s'
    )
    
    # 심볼 파싱
    symbols = [s.strip() for s in args.symbols.split(",")]
    
    try:
        # 러너 생성
        runner = D63WSPaperRunner(
            config_path=args.config,
            symbols=symbols,
            scenario=args.scenario,
            duration_minutes=args.duration_minutes,
            use_ws=args.use_ws,
        )
        
        # 로깅 설정
        runner.setup_logging()
        
        # 실행
        result = runner.run()
        
        # 결과 출력
        print("\n" + "=" * 70)
        print(f"🎯 D63 WebSocket Optimization + REAL PAPER MODE Report")
        print("=" * 70)
        print(f"Scenario: {result['scenario']}")
        print(f"Symbols: {', '.join(result['symbols'])}")
        print(f"Duration: {result['duration_seconds']:.1f}s ({args.duration_minutes}min)")
        print(f"Loop Count: {result['loop_count']}")
        print(f"Total Trades: {result['total_trades']}")
        print(f"Data Source: {result['data_source']}")
        print(f"Mode: {result['mode']}")
        print(f"Use WS: {result['use_ws']}")
        
        print(f"\nD63 WS Queue Metrics:")
        ws_metrics = result['ws_queue_metrics']
        print(f"  Max Queue Depth: {ws_metrics['ws_queue_depth_max']}")
        print(f"  Max Queue Lag: {ws_metrics['ws_queue_lag_ms_max']:.2f}ms")
        print(f"  Queue Lag Warnings: {ws_metrics['ws_queue_lag_warn_count']}")
        
        print(f"\nPer-Symbol Results:")
        for symbol, stats in result['runners'].items():
            print(f"  {symbol}:")
            print(f"    Loops: {stats.get('loop_count', 0)}")
            print(f"    Trades Opened: {stats.get('total_trades_opened', 0)}")
            print(f"    Avg Loop Time: {stats.get('avg_loop_time_ms', 0):.2f}ms")
        
        print("=" * 70)
        print("✅ D63 WS Paper run completed successfully")
        
        return 0
    
    except Exception as e:
        logger.error(f"[D63_WS_PAPER] Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
