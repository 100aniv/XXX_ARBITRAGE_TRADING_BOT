#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D84-2: CalibratedFillModel 장기 PAPER 검증 Runner
D83-1: Real L2 WebSocket Provider 통합

목적:
- D84-1에서 구현한 CalibratedFillModel을 실제 PAPER 환경에서 20분 이상 실행
- D83-0 L2 Orderbook + D84-1 FillEventCollector 통합
- D83-1 Real L2 WebSocket Provider 검증
- Zone별 Fill Ratio 보정이 실제로 작동하는지 검증
- 50개 이상의 Fill Event 수집 및 분석

실행 조건:
- 단일 심볼 (BTC)
- CalibratedFillModel (d84_1_calibration.json 사용)
- L2 Orderbook Provider (Mock or Real WebSocket)
- FillEventCollector 활성화

Usage:
    # 5분 스모크 테스트 (Mock L2)
    python scripts/run_d84_2_calibrated_fill_paper.py --smoke
    
    # 5분 스모크 테스트 (Real L2)
    python scripts/run_d84_2_calibrated_fill_paper.py --smoke --l2-source real
    
    # 20분 본 실행 (Real L2)
    python scripts/run_d84_2_calibrated_fill_paper.py --duration-seconds 1200 --l2-source real
    
    # 사용자 지정 시간
    python scripts/run_d84_2_calibrated_fill_paper.py --duration-seconds 600 --l2-source mock
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# D84-2: 필수 Import
from arbitrage.types import PortfolioState, OrderSide
from arbitrage.live_runner import RiskGuard, RiskLimits
from arbitrage.config.settings import Settings
from arbitrage.execution.executor_factory import ExecutorFactory
from arbitrage.execution.fill_model import SimpleFillModel, CalibratedFillModel, CalibrationTable
from arbitrage.metrics.fill_stats import FillEventCollector
from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import MarketDataProvider

# D83-1: Real L2 WebSocket Provider Import (Upbit)
from arbitrage.exchanges.upbit_l2_ws_provider import UpbitL2WebSocketProvider

# D83-2: Real L2 WebSocket Provider Import (Binance)
from arbitrage.exchanges.binance_l2_ws_provider import BinanceL2WebSocketProvider

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class MockMarketDataProvider(MarketDataProvider):
    """
    D84-2: Mock MarketDataProvider (L2 Orderbook 시뮬레이션)
    
    실제 WebSocket 연결 없이 L2 데이터를 시뮬레이션.
    시간에 따라 volume을 변화시켜 available_volume 변동 재현.
    (D83-0.5와 동일한 로직)
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
        if self._counter % 20 == 0:
            logger.debug(f"[MOCK_L2] Generated snapshot for {symbol}: best_ask_volume={volume:.6f}")
        
        return snapshot
    
    def start(self):
        """Provider 시작 (Mock이므로 no-op)"""
        logger.info("[MOCK_L2] Started")
    
    def stop(self):
        """Provider 중단 (Mock이므로 no-op)"""
        logger.info("[MOCK_L2] Stopped")


def load_calibration(calibration_path: Path) -> CalibrationTable:
    """
    Calibration JSON 파일 로드
    
    Args:
        calibration_path: Calibration JSON 파일 경로
    
    Returns:
        CalibrationTable 인스턴스
    """
    with open(calibration_path, "r") as f:
        calibration_data = json.load(f)
    
    # CalibrationTable은 6개 필드만 받음 (total_events, unmatched_events 제외)
    calibration = CalibrationTable(
        version=calibration_data["version"],
        zones=calibration_data["zones"],
        default_buy_fill_ratio=calibration_data["default_buy_fill_ratio"],
        default_sell_fill_ratio=calibration_data["default_sell_fill_ratio"],
        created_at=calibration_data["created_at"],
        source=calibration_data["source"],
    )
    logger.info(
        f"[D84-2] Calibration 로드 완료: version={calibration.version}, "
        f"zones={len(calibration.zones)}, "
        f"default_buy_fill_ratio={calibration.default_buy_fill_ratio:.4f}"
    )
    
    return calibration


def run_calibrated_fill_paper(
    duration_seconds: int,
    calibration_path: Path,
    l2_source: str = "mock",
) -> Dict[str, Any]:
    """
    CalibratedFillModel 장기 PAPER 실행
    
    Args:
        duration_seconds: 실행 시간 (초)
        calibration_path: Calibration JSON 파일 경로
    
    Returns:
        실행 KPI (dict)
    """
    # 0. 세션 ID 및 출력 경로 설정
    session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    output_dir = Path(__file__).parent.parent / "logs" / "d84-2"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fill_events_path = output_dir / f"fill_events_{session_id}.jsonl"
    kpi_path = output_dir / f"kpi_{session_id}.json"
    
    logger.info(f"[D84-2] Session ID: {session_id}")
    logger.info(f"[D84-2] Duration: {duration_seconds}초")
    logger.info(f"[D84-2] L2 Source: {l2_source}")
    logger.info(f"[D84-2] Fill Events 경로: {fill_events_path}")
    logger.info(f"[D84-2] KPI 경로: {kpi_path}")
    logger.info("")
    
    # 1. Calibration 로드
    calibration = load_calibration(calibration_path)
    
    # 2. MarketDataProvider 생성 (L2 Source에 따라 분기)
    # D83-2: 하위 호환성 (real → upbit)
    if l2_source == "real":
        l2_source = "upbit"
        logger.info("[D83-2] l2_source 'real' → 'upbit' (backward compatibility)")
    
    if l2_source == "multi":
        # D83-3: Multi-exchange L2 Provider
        from arbitrage.exchanges.multi_exchange_l2_provider import MultiExchangeL2Provider
        
        market_data_provider = MultiExchangeL2Provider(
            symbols=["BTC"],
            staleness_threshold_seconds=2.0,
        )
        market_data_provider.start()
        logger.info("[D83-3] MultiExchangeL2Provider started (Upbit + Binance)")
        
        # WebSocket 연결 대기는 Provider 내부에서 처리됨
    
    elif l2_source == "upbit":
        # D83-1: Upbit Real L2 WebSocket Provider
        symbol_upbit = "KRW-BTC"  # Upbit 심볼 포맷
        market_data_provider = UpbitL2WebSocketProvider(
            symbols=[symbol_upbit],
            heartbeat_interval=30.0,
            timeout=10.0,
            max_reconnect_attempts=5,
            reconnect_backoff=2.0,
        )
        market_data_provider.start()
        logger.info(f"[D83-1] Upbit L2 WebSocket Provider started for {symbol_upbit}")
        
        # WebSocket 연결 대기 (최대 10초)
        logger.info("[D83-1] Waiting for WebSocket connection...")
        for i in range(10):
            time.sleep(1)
            snapshot = market_data_provider.get_latest_snapshot(symbol_upbit)
            if snapshot:
                logger.info(f"[D83-1] First snapshot received: {len(snapshot.bids)} bids, {len(snapshot.asks)} asks")
                break
        else:
            logger.warning("[D83-1] No snapshot received after 10s, continuing anyway...")
    
    elif l2_source == "binance":
        # D83-2: Binance Real L2 WebSocket Provider
        symbol_binance = "BTCUSDT"  # Binance 심볼 포맷
        market_data_provider = BinanceL2WebSocketProvider(
            symbols=[symbol_binance],
            depth="20",
            interval="100ms",
            heartbeat_interval=30.0,
            timeout=10.0,
            max_reconnect_attempts=5,
            reconnect_backoff=2.0,
        )
        market_data_provider.start()
        logger.info(f"[D83-2] Binance L2 WebSocket Provider started for {symbol_binance}")
        
        # WebSocket 연결 대기 (최대 10초)
        logger.info("[D83-2] Waiting for WebSocket connection...")
        for i in range(10):
            time.sleep(1)
            snapshot = market_data_provider.get_latest_snapshot(symbol_binance)
            if snapshot:
                logger.info(f"[D83-2] First snapshot received: {len(snapshot.bids)} bids, {len(snapshot.asks)} asks")
                break
        else:
            logger.warning("[D83-2] No snapshot received after 10s, continuing anyway...")
    
    else:
        # D84-2: Mock L2 Provider (기본값)
        market_data_provider = MockMarketDataProvider()
        market_data_provider.start()
        logger.info("[D84-2] MockMarketDataProvider started")
    
    logger.info("")
    
    # 3. FillEventCollector 초기화
    fill_event_collector = FillEventCollector(
        output_path=fill_events_path,
        enabled=True,
        session_id=session_id,
    )
    
    
    # 4. Settings, RiskGuard, ExecutorFactory 초기화
    settings = Settings.from_env()
    settings.fill_model.enable_fill_model = True  # D84-2: 강제 활성화
    
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
    
    # 5. CalibratedFillModel 생성
    # Entry/TP를 10.0/12.0으로 고정 (Zone Z2 또는 Z3에 해당)
    entry_bps = 10.0
    tp_bps = 12.0
    
    base_model = SimpleFillModel(
        enable_partial_fill=True,
        enable_slippage=True,
        default_slippage_alpha=0.0001,
    )
    
    fill_model = CalibratedFillModel(
        base_model=base_model,
        calibration=calibration,
        entry_bps=entry_bps,
        tp_bps=tp_bps,
    )
    
    logger.info(f"[D84-2] CalibratedFillModel 생성 완료: Entry={entry_bps}bps, TP={tp_bps}bps")
    
    # 6. PaperExecutor 생성 (BTC 심볼)
    symbol = "BTC"
    executor = executor_factory.create_paper_executor(
        symbol=symbol,
        portfolio_state=portfolio_state,
        risk_guard=risk_guard,
        fill_model_config=settings.fill_model,
        market_data_provider=market_data_provider,
        fill_event_collector=fill_event_collector,
    )
    
    # Fill Model 강제 주입 (CalibratedFillModel 사용)
    executor.fill_model = fill_model
    executor.enable_fill_model = True
    
    logger.info(f"[D84-2] Executor 생성 완료 for {symbol}")
    logger.info("")
    
    # 7. Mock Trade 구조
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
    
    # 8. PAPER 실행 루프
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
                    f"[D84-2] Trade {iteration}: status={results[0].status}, "
                    f"filled_qty={results[0].quantity:.6f}, "
                    f"buy_fill={results[0].buy_fill_ratio*100:.2f}%, "
                    f"sell_fill={results[0].sell_fill_ratio*100:.2f}%, "
                    f"pnl=${results[0].pnl:.2f}"
                )
        
        time.sleep(1)  # 1초 대기
    
    # 9. 종료 처리
    market_data_provider.stop()
    metrics["end_time"] = time.time()
    metrics["actual_duration_seconds"] = metrics["end_time"] - metrics["start_time"]
    
    # 10. FillEventCollector 요약
    collector_summary = fill_event_collector.get_summary()
    metrics["fill_events_count"] = collector_summary["events_count"]
    metrics["fill_events_path"] = str(fill_events_path)
    
    # 11. KPI 저장
    with open(kpi_path, "w") as f:
        json.dump(metrics, f, indent=2)
    
    logger.info(f"[D84-2] KPI 저장 완료: {kpi_path}")
    logger.info(f"[D84-2] Fill Events 저장 완료: {fill_events_path}")
    logger.info("")
    
    return metrics


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D84-2/D83-1: CalibratedFillModel + Real L2 WebSocket PAPER 검증"
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=1200,
        help="실행 시간 (초), 기본값=1200 (20분)"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="스모크 테스트 모드 (5분)"
    )
    parser.add_argument(
        "--calibration-path",
        type=str,
        default="logs/d84/d84_1_calibration.json",
        help="Calibration JSON 파일 경로 (기본값: logs/d84/d84_1_calibration.json)"
    )
    parser.add_argument(
        "--l2-source",
        type=str,
        choices=["mock", "real", "upbit", "binance", "multi"],
        default="mock",
        help="L2 Orderbook 소스: mock, real (=upbit), upbit, binance, multi (Upbit+Binance) (기본값: mock)"
    )
    
    args = parser.parse_args()
    
    # 스모크 모드
    if args.smoke:
        duration_seconds = 300  # 5분
    else:
        duration_seconds = args.duration_seconds
    
    calibration_path = Path(args.calibration_path)
    if not calibration_path.exists():
        logger.error(f"[D84-2] Calibration 파일이 존재하지 않습니다: {calibration_path}")
        sys.exit(1)
    
    logger.info("=" * 100)
    logger.info(f"[D84-2/D83-1] CalibratedFillModel + {args.l2_source.upper()} L2 PAPER 검증 시작")
    logger.info("=" * 100)
    logger.info(f"Duration: {duration_seconds}초 ({duration_seconds/60:.1f}분)")
    logger.info(f"Calibration: {calibration_path}")
    logger.info(f"L2 Source: {args.l2_source}")
    logger.info("")
    
    # 실행
    metrics = run_calibrated_fill_paper(duration_seconds, calibration_path, l2_source=args.l2_source)
    
    # 요약 출력
    logger.info("")
    logger.info("=" * 100)
    logger.info("[D84-2] 실행 요약")
    logger.info("=" * 100)
    logger.info(f"Session ID: {metrics['session_id']}")
    logger.info(f"Symbol: {metrics['symbol']}")
    logger.info(f"Duration: {metrics['actual_duration_seconds']:.1f}초")
    logger.info(f"Entry Trades: {metrics['entry_trades']}")
    logger.info(f"Fill Events 수집: {metrics['fill_events_count']}")
    logger.info(f"Total PnL: ${metrics['total_pnl_usd']:.2f}")
    logger.info(f"Fill Events 경로: {metrics['fill_events_path']}")
    logger.info("=" * 100)
    logger.info("")
    logger.info("[D84-2] 다음 단계: scripts/analyze_d84_2_fill_results.py 실행")


if __name__ == "__main__":
    main()
