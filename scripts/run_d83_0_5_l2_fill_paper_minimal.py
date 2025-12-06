#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D83-0.5: L2 Fill Model PAPER Minimal Runner (5~10분)

목적:
- D83-0 L2 Orderbook Integration 실전 검증
- D84-1 Fill Model Infrastructure 실전 검증
- FillEventCollector로 Fill 이벤트 수집
- 최소한의 코드로 핵심 기능만 테스트

실행 조건:
- 단일 심볼 (BTC)
- SimpleFillModel 사용
- L2 Orderbook Provider (Mock)
- FillEventCollector 활성화

Usage:
    python scripts/run_d83_0_5_l2_fill_paper_minimal.py --duration-seconds 300
    python scripts/run_d83_0_5_l2_fill_paper_minimal.py --duration-seconds 600
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# D83-0.5: 필수 Import
from arbitrage.types import PortfolioState, OrderSide
from arbitrage.live_runner import RiskGuard, RiskLimits
from arbitrage.config.settings import Settings
from arbitrage.execution.executor_factory import ExecutorFactory
from arbitrage.execution.fill_model import SimpleFillModel
from arbitrage.metrics.fill_stats import FillEventCollector
from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import MarketDataProvider

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class MockMarketDataProvider(MarketDataProvider):
    """
    D83-0.5: Mock MarketDataProvider (L2 Orderbook 시뮬레이션)
    
    실제 WebSocket 연결 없이 L2 데이터를 시뮬레이션.
    시간에 따라 volume을 변화시켜 available_volume 변동 재현.
    """
    
    def __init__(self):
        """초기화"""
        self._snapshots: Dict[str, OrderBookSnapshot] = {}
        self._counter = 0
    
    def get_latest_snapshot(self, symbol: str) -> OrderBookSnapshot:
        """
        최신 호가 스냅샷 반환 (Mock)
        
        Args:
            symbol: 거래 심볼
        
        Returns:
            OrderBookSnapshot
        """
        # 시간에 따라 volume 변화 (0.5 ~ 1.5 사이 랜덤)
        import random
        base_volume = 0.1
        variation = random.uniform(0.5, 1.5)
        volume = base_volume * variation
        
        # BTC/USDT 기준 Mock 호가
        snapshot = OrderBookSnapshot(
            symbol=symbol,
            timestamp=time.time(),
            bids=[
                (50000.0, volume),  # Best bid
                (49900.0, volume * 2),
                (49800.0, volume * 3),
            ],
            asks=[
                (50100.0, volume),  # Best ask
                (50200.0, volume * 2),
                (50300.0, volume * 3),
            ],
        )
        
        self._counter += 1
        if self._counter % 10 == 0:
            logger.debug(f"[MOCK_L2] Generated snapshot for {symbol}: best_ask_volume={volume:.6f}")
        
        return snapshot
    
    def start(self) -> None:
        """데이터 소스 시작 (Mock - no-op)"""
        logger.info("[MOCK_L2] Started")
    
    def stop(self) -> None:
        """데이터 소스 종료 (Mock - no-op)"""
        logger.info("[MOCK_L2] Stopped")


def run_minimal_paper(duration_seconds: int) -> Dict[str, Any]:
    """
    D83-0.5 최소 PAPER 실행
    
    Args:
        duration_seconds: 실행 시간 (초)
    
    Returns:
        실행 결과 요약
    """
    logger.info(f"[D83-0.5] Starting minimal PAPER (duration={duration_seconds}s)")
    
    # 1. 세션 ID 및 출력 경로
    session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("logs/d83-0.5")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fill_events_path = output_dir / f"fill_events_{session_id}.jsonl"
    kpi_path = output_dir / f"kpi_{session_id}.json"
    
    # 2. FillEventCollector 초기화
    fill_event_collector = FillEventCollector(
        output_path=fill_events_path,
        enabled=True,
        session_id=session_id,
    )
    
    # 3. MockMarketDataProvider 초기화
    market_data_provider = MockMarketDataProvider()
    market_data_provider.start()
    
    # 4. Settings, RiskGuard, ExecutorFactory 초기화
    settings = Settings.from_env()
    settings.fill_model.enable_fill_model = True  # D83-0.5: 강제 활성화
    
    portfolio_state = PortfolioState(
        total_balance=10000.0,
        available_balance=10000.0,
    )
    risk_limits = RiskLimits(
        max_notional_per_trade=10000.0,
        max_daily_loss=1000.0,
        max_open_trades=10,
    )
    risk_guard = RiskGuard(risk_limits=risk_limits)
    
    executor_factory = ExecutorFactory()
    
    # 5. PaperExecutor 생성 (BTC 심볼)
    symbol = "BTC"
    executor = executor_factory.create_paper_executor(
        symbol=symbol,
        portfolio_state=portfolio_state,
        risk_guard=risk_guard,
        fill_model_config=settings.fill_model,
        market_data_provider=market_data_provider,
        fill_event_collector=fill_event_collector,
    )
    
    logger.info(f"[D83-0.5] Executor created for {symbol}")
    
    # 6. Mock Trade 정의
    from dataclasses import dataclass
    
    @dataclass
    class MockTrade:
        """Mock Trade 객체"""
        trade_id: str
        buy_exchange: str
        sell_exchange: str
        buy_price: float
        sell_price: float
        quantity: float
        notional_usd: float = 0.0  # USD 명목가 (risk guard용)
    
    # 7. PAPER 실행 루프
    start_time = time.time()
    end_time = start_time + duration_seconds
    
    metrics = {
        "session_id": session_id,
        "symbol": symbol,
        "duration_seconds": duration_seconds,
        "start_time": start_time,
        "entry_trades": 0,
        "total_pnl_usd": 0.0,
    }
    
    iteration = 0
    while time.time() < end_time:
        iteration += 1
        
        # Mock Trade 생성 (매 10초마다)
        if iteration % 10 == 0:
            trade = MockTrade(
                trade_id=f"TRADE_{iteration}",
                buy_exchange="upbit",
                sell_exchange="binance",
                buy_price=50000.0,
                sell_price=50100.0,
                quantity=0.001,  # 0.001 BTC
                notional_usd=50.0,  # ~$50
            )
            
            # Executor 실행
            results = executor.execute_trades([trade])
            
            if results and results[0].status in ["success", "partial"]:
                metrics["entry_trades"] += 1
                metrics["total_pnl_usd"] += results[0].pnl
                
                logger.info(
                    f"[D83-0.5] Trade {iteration}: "
                    f"status={results[0].status}, "
                    f"filled_qty={results[0].quantity:.6f}, "
                    f"buy_fill={results[0].buy_fill_ratio:.2%}, "
                    f"sell_fill={results[0].sell_fill_ratio:.2%}, "
                    f"pnl=${results[0].pnl:.2f}"
                )
        
        time.sleep(1)  # 1초 대기
    
    # 8. 종료 처리
    market_data_provider.stop()
    metrics["end_time"] = time.time()
    metrics["actual_duration_seconds"] = metrics["end_time"] - metrics["start_time"]
    
    # 9. FillEventCollector 요약
    collector_summary = fill_event_collector.get_summary()
    metrics["fill_events_count"] = collector_summary["events_count"]
    metrics["fill_events_path"] = str(fill_events_path)
    
    # 10. KPI 저장
    with open(kpi_path, "w") as f:
        json.dump(metrics, f, indent=2)
    
    logger.info(f"[D83-0.5] KPI saved to: {kpi_path}")
    logger.info(f"[D83-0.5] Fill events saved to: {fill_events_path}")
    
    return metrics


def main():
    """D83-0.5 실행"""
    parser = argparse.ArgumentParser(description="D83-0.5: L2 Fill Model PAPER Minimal Runner")
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=300,
        help="실행 시간 (초, 기본: 300 = 5분)",
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("[D83-0.5] L2 Fill Model PAPER Minimal Runner")
    logger.info("=" * 80)
    logger.info(f"Duration: {args.duration_seconds} seconds ({args.duration_seconds / 60:.1f} minutes)")
    logger.info("")
    
    # 실행
    metrics = run_minimal_paper(args.duration_seconds)
    
    # 결과 요약
    logger.info("")
    logger.info("=" * 80)
    logger.info("[D83-0.5] Summary")
    logger.info("=" * 80)
    logger.info(f"Session ID: {metrics['session_id']}")
    logger.info(f"Symbol: {metrics['symbol']}")
    logger.info(f"Duration: {metrics['actual_duration_seconds']:.1f} seconds")
    logger.info(f"Entry Trades: {metrics['entry_trades']}")
    logger.info(f"Fill Events Collected: {metrics['fill_events_count']}")
    logger.info(f"Total PnL: ${metrics['total_pnl_usd']:.2f}")
    logger.info(f"Fill Events Path: {metrics['fill_events_path']}")
    logger.info("=" * 80)
    logger.info("")
    logger.info("[D83-0.5] Next: Analyze fill events with scripts/analyze_d83_0_5_fill_events.py")


if __name__ == "__main__":
    main()
