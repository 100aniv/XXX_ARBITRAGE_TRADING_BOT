# -*- coding: utf-8 -*-
"""
D43 Arbitrage Live Runner CLI

Paper 모드 우선 구현.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import yaml

from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig
from arbitrage.exchanges import PaperExchange
from arbitrage.exchanges.market_data_provider import (
    RestMarketDataProvider,
    WebSocketMarketDataProvider,
)
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits
from arbitrage.monitoring import MetricsCollector

try:
    from arbitrage.monitoring.metrics_server import MetricsServer
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """
    YAML 설정 파일 로드.
    
    Args:
        config_path: 설정 파일 경로
    
    Returns:
        설정 dict
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    logger.info(f"[D43_CLI] Loaded config from {config_path}")
    return config


def create_exchanges(config: dict, mode: str):
    """
    거래소 인스턴스 생성.
    
    Args:
        config: 설정 dict
        mode: "paper" | "live_readonly"
    
    Returns:
        (exchange_a, exchange_b) 튜플
    """
    exchanges_config = config.get("exchanges", {})
    
    if mode == "paper":
        # Paper 모드: 두 개의 PaperExchange 생성
        initial_balance_a = exchanges_config.get("initial_balance_a", {"KRW": 1000000.0})
        initial_balance_b = exchanges_config.get("initial_balance_b", {"USDT": 10000.0})
        
        exchange_a = PaperExchange(initial_balance=initial_balance_a)
        exchange_b = PaperExchange(initial_balance=initial_balance_b)
        
        logger.info(f"[D43_CLI] Created Paper exchanges: A={initial_balance_a}, B={initial_balance_b}")
        return exchange_a, exchange_b
    
    elif mode == "live_readonly":
        # D46: Read-Only 모드: 실제 거래소 어댑터 생성
        from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
        from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
        
        # Exchange A (Upbit)
        exchange_a_config = exchanges_config.get("a", {}).get("config", {})
        exchange_a = UpbitSpotExchange(exchange_a_config)
        
        # Exchange B (Binance)
        exchange_b_config = exchanges_config.get("b", {}).get("config", {})
        exchange_b = BinanceFuturesExchange(exchange_b_config)
        
        logger.info(f"[D46_CLI] Created Read-Only exchanges: A={exchange_a.name}, B={exchange_b.name}")
        return exchange_a, exchange_b
    
    elif mode == "live_trading":
        # D47: 실거래 모드: 실제 거래소 어댑터 생성
        from arbitrage.exchanges.upbit_spot import UpbitSpotExchange
        from arbitrage.exchanges.binance_futures import BinanceFuturesExchange
        
        # Exchange A (Upbit)
        exchange_a_config = exchanges_config.get("a", {}).get("config", {})
        exchange_a = UpbitSpotExchange(exchange_a_config)
        
        # Exchange B (Binance)
        exchange_b_config = exchanges_config.get("b", {}).get("config", {})
        exchange_b = BinanceFuturesExchange(exchange_b_config)
        
        logger.info(f"[D47_CLI] Created Live Trading exchanges: A={exchange_a.name}, B={exchange_b.name}")
        return exchange_a, exchange_b
    
    else:
        raise ValueError(f"Unsupported mode: {mode}")


def create_engine(config: dict) -> ArbitrageEngine:
    """
    ArbitrageEngine 생성.
    
    Args:
        config: 설정 dict
    
    Returns:
        ArbitrageEngine
    """
    engine_config = config.get("engine", {})
    
    arb_config = ArbitrageConfig(
        min_spread_bps=engine_config.get("min_spread_bps", 30.0),
        taker_fee_a_bps=engine_config.get("taker_fee_a_bps", 5.0),
        taker_fee_b_bps=engine_config.get("taker_fee_b_bps", 5.0),
        slippage_bps=engine_config.get("slippage_bps", 5.0),
        max_position_usd=engine_config.get("max_position_usd", 1000.0),
        max_open_trades=engine_config.get("max_open_trades", 1),
    )
    
    engine = ArbitrageEngine(arb_config)
    logger.info(f"[D43_CLI] Created ArbitrageEngine with config: {arb_config}")
    return engine


def create_live_config(config: dict, mode: str, max_runtime_seconds: Optional[int]) -> ArbitrageLiveConfig:
    """
    ArbitrageLiveConfig 생성 (D44: RiskLimits 포함).
    
    Args:
        config: 설정 dict
        mode: "paper" | "live"
        max_runtime_seconds: 최대 런타임 (CLI 인자로 오버라이드)
    
    Returns:
        ArbitrageLiveConfig
    """
    symbols = config.get("symbols", {})
    live_config = config.get("live", {})
    risk_limits_config = config.get("risk_limits", {})
    paper_sim_config = config.get("paper_simulation", {})
    
    # RiskLimits 생성 (D44)
    risk_limits = RiskLimits(
        max_notional_per_trade=risk_limits_config.get("max_notional_per_trade", 10000.0),
        max_daily_loss=risk_limits_config.get("max_daily_loss", 1000.0),
        max_open_trades=risk_limits_config.get("max_open_trades", 1),
    )
    
    # D50.5: data_source 설정 (기본값: rest)
    data_source = live_config.get("data_source", "rest")
    
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
        max_runtime_seconds=max_runtime_seconds or live_config.get("max_runtime_seconds"),
        risk_limits=risk_limits,  # D44
        paper_simulation_enabled=paper_sim_config.get("enable_price_volatility", False),  # D44
        paper_volatility_range_bps=paper_sim_config.get("volatility_range_bps", 100.0),  # D44
        paper_spread_injection_interval=paper_sim_config.get("spread_injection_interval", 5),  # D44
        data_source=data_source,  # D50.5
    )
    
    logger.info(f"[D43_CLI] Created ArbitrageLiveConfig: {live_cfg}")
    return live_cfg


def main():
    """메인 진입점"""
    parser = argparse.ArgumentParser(
        description="D43 Arbitrage Live Runner (Paper Mode)"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="설정 파일 경로 (YAML)",
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        default="paper",
        choices=["paper", "live_readonly", "live_trading"],  # D47: live_trading 모드 추가
        help="실행 모드: paper (시뮬레이션), live_readonly (실거래소 Read-Only), live_trading (실거래)",
    )
    
    parser.add_argument(
        "--max-runtime-seconds",
        type=int,
        default=None,
        help="최대 런타임 (초, 기본값: 무제한)",
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
    
    try:
        # 설정 로드
        config = load_config(args.config)
        
        # 거래소 생성
        exchange_a, exchange_b = create_exchanges(config, args.mode)
        
        # 엔진 생성
        engine = create_engine(config)
        
        # Live Config 생성
        live_config = create_live_config(config, args.mode, args.max_runtime_seconds)
        
        # D50.5: MarketDataProvider 생성
        market_data_provider = None
        if live_config.data_source == "rest":
            market_data_provider = RestMarketDataProvider(
                exchanges={"a": exchange_a, "b": exchange_b}
            )
            logger.info("[D50_CLI] Created RestMarketDataProvider")
        elif live_config.data_source == "ws":
            # WebSocket 모드 (실험용)
            market_data_provider = WebSocketMarketDataProvider(ws_adapters={})
            logger.info("[D50_CLI] Created WebSocketMarketDataProvider (experimental)")
        
        # D50.5: MetricsCollector 생성
        metrics_collector = MetricsCollector(buffer_size=300)
        logger.info("[D50_CLI] Created MetricsCollector")
        
        # D50.5: MetricsServer 생성 (FastAPI 설치 시)
        metrics_server = None
        if HAS_FASTAPI:
            try:
                monitoring_config = config.get("monitoring", {})
                metrics_server = MetricsServer(
                    metrics_collector=metrics_collector,
                    host=monitoring_config.get("host", "127.0.0.1"),
                    port=monitoring_config.get("port", 8001),
                    metrics_format=monitoring_config.get("format", "json"),
                )
                metrics_server.start()
                logger.info(
                    f"[D50_CLI] Started MetricsServer on "
                    f"{metrics_server.host}:{metrics_server.port}"
                )
            except Exception as e:
                logger.warning(f"[D50_CLI] Failed to start MetricsServer: {e}")
        else:
            logger.warning("[D50_CLI] FastAPI not installed, MetricsServer skipped")
        
        # Runner 생성
        runner = ArbitrageLiveRunner(
            engine=engine,
            exchange_a=exchange_a,
            exchange_b=exchange_b,
            config=live_config,
            market_data_provider=market_data_provider,
            metrics_collector=metrics_collector,
        )
        
        logger.info(f"[D43_CLI] Starting Arbitrage Live Runner in {args.mode} mode")
        
        # 실행
        runner.run_forever()
        
        # 통계 출력
        stats = runner.get_stats()
        logger.info(f"[D43_CLI] Final stats: {json.dumps(stats, indent=2)}")
        
        print("\n" + "="*60)
        print("🎯 Arbitrage Live Runner - Final Report")
        print("="*60)
        print(f"Mode: {args.mode}")
        print(f"Duration: {stats['elapsed_seconds']:.1f}s")
        print(f"Loops: {stats['loop_count']}")
        print(f"Trades Opened: {stats['total_trades_opened']}")
        print(f"Trades Closed: {stats['total_trades_closed']}")
        print(f"Total PnL: ${stats['total_pnl_usd']:.2f}")
        print(f"Active Orders: {stats['active_orders']}")
        print(f"Avg Loop Time: {stats['avg_loop_time_ms']:.2f}ms")
        print("="*60)
        
        return 0
    
    except Exception as e:
        logger.error(f"[D43_CLI] Error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
