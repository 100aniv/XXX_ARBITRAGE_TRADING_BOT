# -*- coding: utf-8 -*-
"""
D51 Paper Long-run Runner

Paper 모드 롱런 테스트 실행 스크립트.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import yaml

from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.exchanges import PaperExchange
from arbitrage.exchanges.market_data_provider import RestMarketDataProvider
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits
from arbitrage.monitoring import MetricsCollector

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """설정 파일 로드"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    logger.info(f"[D51_CLI] Loaded config from {config_path}")
    return config


def create_exchanges(config: dict, mode: str):
    """거래소 생성"""
    exchange_a = PaperExchange(
        initial_balance={
            "KRW": 100000000.0,
            "BTC": 10.0,
        }
    )
    
    exchange_b = PaperExchange(
        initial_balance={
            "USDT": 1000000.0,
            "BTC": 10.0,
        }
    )
    
    logger.info("[D51_CLI] Created Paper exchanges: A and B")
    
    return exchange_a, exchange_b


def create_engine(config: dict) -> ArbitrageEngine:
    """엔진 생성"""
    engine_config = config.get("engine", {})
    
    arb_config = ArbitrageConfig(
        min_spread_bps=engine_config.get("min_spread_bps", 20.0),
        taker_fee_a_bps=engine_config.get("taker_fee_a_bps", 5.0),
        taker_fee_b_bps=engine_config.get("taker_fee_b_bps", 4.0),
        slippage_bps=engine_config.get("slippage_bps", 5.0),
        max_position_usd=engine_config.get("max_position_usd", 5000.0),
        max_open_trades=engine_config.get("max_open_trades", 1),
    )
    
    engine = ArbitrageEngine(arb_config)
    logger.info(f"[D51_CLI] Created ArbitrageEngine with config: {arb_config}")
    return engine


def create_live_config(
    config: dict,
    mode: str,
    max_runtime_seconds: Optional[int],
) -> ArbitrageLiveConfig:
    """Live Config 생성"""
    symbols = config.get("symbols", {})
    live_config = config.get("live", {})
    risk_limits_config = config.get("risk_limits", {})
    paper_sim_config = config.get("paper_simulation", {})
    
    # RiskLimits 생성
    risk_limits = RiskLimits(
        max_notional_per_trade=risk_limits_config.get("max_notional_per_trade", 10000.0),
        max_daily_loss=risk_limits_config.get("max_daily_loss", 1000.0),
        max_open_trades=risk_limits_config.get("max_open_trades", 1),
    )
    
    # D51: data_source 강제 설정 (rest-only)
    data_source = "rest"
    
    live_cfg = ArbitrageLiveConfig(
        symbol_a=symbols.get("symbol_a", "KRW-BTC"),
        symbol_b=symbols.get("symbol_b", "BTCUSDT"),
        min_spread_bps=config.get("engine", {}).get("min_spread_bps", 30.0),
        taker_fee_a_bps=config.get("engine", {}).get("taker_fee_a_bps", 5.0),
        taker_fee_b_bps=config.get("engine", {}).get("taker_fee_b_bps", 5.0),
        slippage_bps=config.get("engine", {}).get("slippage_bps", 5.0),
        max_position_usd=config.get("engine", {}).get("max_position_usd", 1000.0),
        poll_interval_seconds=live_config.get("poll_interval_seconds", 1.0),
        max_concurrent_trades=live_config.get("max_concurrent_trades", 1),
        mode=mode,
        log_level=live_config.get("log_level", "INFO"),
        max_runtime_seconds=max_runtime_seconds,
        risk_limits=risk_limits,
        paper_simulation_enabled=paper_sim_config.get("enable_price_volatility", False),
        paper_volatility_range_bps=paper_sim_config.get("volatility_range_bps", 100.0),
        paper_spread_injection_interval=paper_sim_config.get("spread_injection_interval", 5),
        data_source=data_source,  # D51: 강제 rest
    )
    
    logger.info(f"[D51_CLI] Created ArbitrageLiveConfig: {live_cfg}")
    return live_cfg


def main():
    """메인 진입점"""
    parser = argparse.ArgumentParser(
        description="D51 Paper Long-run Runner"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="설정 파일 경로 (YAML)",
    )
    
    parser.add_argument(
        "--scenario",
        type=str,
        default="S1",
        choices=["S1", "S2", "S3"],
        help="시나리오: S1 (1시간), S2 (6시간), S3 (24시간)",
    )
    
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=None,
        help="실행 시간 (분, 기본값: 시나리오별 기본값)",
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="로그 레벨 (기본값: INFO)",
    )
    
    args = parser.parse_args()
    
    # 로그 레벨 설정
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # 시나리오별 기본 duration
    scenario_defaults = {
        "S1": 60,      # 1시간
        "S2": 360,     # 6시간
        "S3": 1440,    # 24시간
    }
    
    duration_minutes = args.duration_minutes or scenario_defaults.get(args.scenario, 60)
    max_runtime_seconds = duration_minutes * 60
    
    try:
        logger.info(
            f"[D51_CLI] Starting Paper Long-run: "
            f"scenario={args.scenario}, duration={duration_minutes}min"
        )
        
        # 설정 로드
        config = load_config(args.config)
        
        # 거래소 생성
        exchange_a, exchange_b = create_exchanges(config, "paper")
        
        # 엔진 생성
        engine = create_engine(config)
        
        # Live Config 생성
        live_config = create_live_config(config, "paper", max_runtime_seconds)
        
        # D51: MarketDataProvider 생성 (rest-only)
        market_data_provider = RestMarketDataProvider(
            exchanges={"a": exchange_a, "b": exchange_b}
        )
        logger.info("[D51_CLI] Created RestMarketDataProvider (forced for longrun)")
        
        # D51: MetricsCollector 생성
        metrics_collector = MetricsCollector(buffer_size=300)
        logger.info("[D51_CLI] Created MetricsCollector")
        
        # Runner 생성
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=live_config,
            market_data_provider=market_data_provider,
            metrics_collector=metrics_collector,
        )
        
        logger.info(
            f"[D51_CLI] Starting Paper Long-run in paper mode: "
            f"duration={max_runtime_seconds}s"
        )
        
        # 실행 시작 시간
        run_start = time.time()
        
        # 실행
        runner.run_forever()
        
        # 실행 종료 시간
        run_end = time.time()
        actual_duration = run_end - run_start
        
        # 통계 출력
        stats = runner.get_stats()
        logger.info(f"[D51_CLI] Final stats: {json.dumps(stats, indent=2)}")
        
        # 메트릭 요약
        metrics = metrics_collector.get_metrics()
        logger.info(f"[D51_CLI] Final metrics: {json.dumps(metrics, indent=2)}")
        
        # 최종 리포트 출력
        print("\n" + "=" * 70)
        print(f"🎯 D51 Paper Long-run Report - Scenario {args.scenario}")
        print("=" * 70)
        print(f"Config: {args.config}")
        print(f"Scenario: {args.scenario}")
        print(f"Expected Duration: {duration_minutes} min")
        print(f"Actual Duration: {actual_duration:.1f}s")
        print(f"Loops: {stats['loop_count']}")
        print(f"Trades Opened: {stats['total_trades_opened']}")
        print(f"Trades Closed: {stats['total_trades_closed']}")
        print(f"Total PnL: ${stats['total_pnl_usd']:.2f}")
        print(f"Active Orders: {stats['active_orders']}")
        print(f"Avg Loop Time: {stats['avg_loop_time_ms']:.2f}ms")
        
        if metrics:
            print(f"\nMetrics Summary:")
            print(f"  Loop Time Avg: {metrics.get('loop_time_avg_ms', 0):.2f}ms")
            print(f"  Loop Time Max: {metrics.get('loop_time_max_ms', 0):.2f}ms")
            print(f"  Loop Time Min: {metrics.get('loop_time_min_ms', 0):.2f}ms")
            print(f"  Trades Opened (Recent): {metrics.get('trades_opened_recent', 0)}")
            print(f"  Data Source: {metrics.get('data_source', 'unknown')}")
        
        print("=" * 70)
        
        return 0
    
    except Exception as e:
        logger.error(f"[D51_CLI] Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
