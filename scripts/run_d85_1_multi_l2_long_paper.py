#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
D85-1: Multi L2 Long PAPER & Calibration Data Collection Runner

목적:
- MultiExchangeL2Provider (Upbit + Binance)를 사용한 20분 이상 Long PAPER
- 다양한 Entry/TP 조합으로 Zone별 Fill Event 수집
- D84-2 인프라 재사용 (CalibratedFillModel, FillEventCollector)
- 100개 이상의 Fill Event 수집 목표

실행 조건:
- 단일 심볼 (BTC)
- Multi L2 (Upbit + Binance)
- CalibratedFillModel (d84_1_calibration.json 사용)
- Entry/TP 조합: 랜덤 또는 iteration 기반으로 다양화
- FillEventCollector 활성화

Usage:
    # 5분 스모크 테스트
    python scripts/run_d85_1_multi_l2_long_paper.py --smoke
    
    # 20분 본 실행 (기본값)
    python scripts/run_d85_1_multi_l2_long_paper.py
    
    # 30분 실행
    python scripts/run_d85_1_multi_l2_long_paper.py --duration-seconds 1800
"""

import argparse
import json
import logging
import sys
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

# D85-1: 필수 Import (D84-2와 동일)
from arbitrage.types import PortfolioState, OrderSide
from arbitrage.live_runner import RiskGuard, RiskLimits
from arbitrage.config.settings import Settings
from arbitrage.execution.executor_factory import ExecutorFactory
from arbitrage.execution.fill_model import SimpleFillModel, CalibratedFillModel, CalibrationTable
from arbitrage.metrics.fill_stats import FillEventCollector
from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.exchanges.market_data_provider import MarketDataProvider

# D85-1: Multi L2 Provider Import
from arbitrage.exchanges.multi_exchange_l2_provider import MultiExchangeL2Provider

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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
    
    # CalibrationTable은 6개 필드만 받음
    calibration = CalibrationTable(
        version=calibration_data["version"],
        zones=calibration_data["zones"],
        default_buy_fill_ratio=calibration_data["default_buy_fill_ratio"],
        default_sell_fill_ratio=calibration_data["default_sell_fill_ratio"],
        created_at=calibration_data["created_at"],
        source=calibration_data["source"],
    )
    logger.info(
        f"[D85-1] Calibration 로드 완료: version={calibration.version}, "
        f"zones={len(calibration.zones)}, "
        f"default_buy_fill_ratio={calibration.default_buy_fill_ratio:.4f}"
    )
    
    return calibration


def generate_entry_tp_pairs() -> List[Tuple[float, float]]:
    """
    다양한 Entry/TP 조합 생성
    
    Zone별로 고르게 분포되도록:
    - Zone 1 (Entry 5-7bps): (5.0, 7.0), (5.0, 10.0), (7.0, 10.0)
    - Zone 2 (Entry 7-12bps): (7.0, 12.0), (10.0, 12.0), (10.0, 15.0)
    - Zone 3 (Entry 12-20bps): (12.0, 15.0), (12.0, 20.0), (15.0, 20.0)
    - Zone 4 (Entry >20bps): (20.0, 25.0), (20.0, 30.0), (25.0, 30.0)
    
    Returns:
        (entry_bps, tp_bps) 튜플 리스트
    """
    return [
        # Zone 1: Entry 5-7bps
        (5.0, 7.0),
        (5.0, 10.0),
        (7.0, 10.0),
        # Zone 2: Entry 7-12bps
        (7.0, 12.0),
        (10.0, 12.0),
        (10.0, 15.0),
        # Zone 3: Entry 12-20bps
        (12.0, 15.0),
        (12.0, 20.0),
        (15.0, 20.0),
        # Zone 4: Entry >20bps
        (20.0, 25.0),
        (20.0, 30.0),
        (25.0, 30.0),
    ]


def run_multi_l2_long_paper(
    duration_seconds: int,
    calibration_path: Path,
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Multi L2 Long PAPER 실행
    
    Args:
        duration_seconds: 실행 시간 (초)
        calibration_path: Calibration JSON 파일 경로
        output_dir: 출력 디렉토리 (logs/d85-1, logs/d85-2 등)
    
    Returns:
        실행 KPI (dict)
    """
    # 0. 세션 ID 및 출력 경로 설정
    session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    fill_events_path = output_dir / f"fill_events_{session_id}.jsonl"
    kpi_path = output_dir / f"kpi_{session_id}.json"
    
    logger.info(f"[D85-1] Session ID: {session_id}")
    logger.info(f"[D85-1] Duration: {duration_seconds}초 ({duration_seconds/60:.1f}분)")
    logger.info(f"[D85-1] Fill Events 경로: {fill_events_path}")
    logger.info(f"[D85-1] KPI 경로: {kpi_path}")
    logger.info("")
    
    # 1. Calibration 로드
    calibration = load_calibration(calibration_path)
    
    # 2. Entry/TP 조합 생성
    entry_tp_pairs = generate_entry_tp_pairs()
    logger.info(f"[D85-1] Entry/TP 조합: {len(entry_tp_pairs)}개")
    for i, (entry, tp) in enumerate(entry_tp_pairs, 1):
        logger.info(f"  {i}. Entry={entry}bps, TP={tp}bps")
    logger.info("")
    
    # 3. MultiExchangeL2Provider 생성
    market_data_provider = MultiExchangeL2Provider(
        symbols=["BTC"],
        staleness_threshold_seconds=2.0,
    )
    market_data_provider.start()
    logger.info("[D85-1] MultiExchangeL2Provider 시작 (Upbit + Binance)")
    
    # WebSocket 연결 대기 (최대 15초)
    logger.info("[D85-1] WebSocket 연결 대기 중...")
    for i in range(15):
        time.sleep(1)
        snapshot = market_data_provider.get_latest_snapshot("BTC")
        if snapshot:
            logger.info(f"[D85-1] 첫 스냅샷 수신 완료")
            break
    else:
        logger.warning("[D85-1] 15초 대기 후에도 스냅샷 없음, 계속 진행...")
    logger.info("")
    
    # 4. FillEventCollector 초기화
    fill_event_collector = FillEventCollector(
        output_path=fill_events_path,
        enabled=True,
        session_id=session_id,
    )
    
    # 5. Settings, RiskGuard, ExecutorFactory 초기화
    settings = Settings.from_env()
    settings.fill_model.enable_fill_model = True  # 강제 활성화
    
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
    
    # 6. PaperExecutor 생성
    symbol = "BTC"
    executor = executor_factory.create_paper_executor(
        symbol=symbol,
        portfolio_state=portfolio_state,
        risk_guard=risk_guard,
        fill_model_config=settings.fill_model,
        market_data_provider=market_data_provider,
        fill_event_collector=fill_event_collector,
    )
    
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
        notional_usd: float = 0.0
    
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
        "entry_tp_pairs_used": {},
    }
    
    iteration = 0
    pair_index = 0  # Entry/TP 조합 순환 인덱스
    
    while time.time() < end_time:
        iteration += 1
        
        # Mock Trade 생성 (매 10초마다)
        if iteration % 10 == 0:
            # Entry/TP 조합 순환 선택
            entry_bps, tp_bps = entry_tp_pairs[pair_index % len(entry_tp_pairs)]
            pair_index += 1
            
            # CalibratedFillModel 재생성 (Entry/TP 변경)
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
            
            # Executor Fill Model 업데이트
            executor.fill_model = fill_model
            executor.enable_fill_model = True
            
            # Trade 생성
            trade = MockTrade(
                trade_id=f"TRADE_{iteration}",
                buy_exchange="upbit",
                sell_exchange="binance",
                buy_price=50000.0,
                sell_price=50100.0,
                quantity=0.001,
                notional_usd=50.0,
            )
            
            # Executor 실행
            results = executor.execute_trades([trade])
            
            if results and results[0].status in ["success", "partial"]:
                metrics["entry_trades"] += 1
                metrics["total_pnl_usd"] += results[0].pnl
                
                # Entry/TP 조합 사용 횟수 기록
                pair_key = f"{entry_bps}_{tp_bps}"
                metrics["entry_tp_pairs_used"][pair_key] = metrics["entry_tp_pairs_used"].get(pair_key, 0) + 1
                
                if iteration % 50 == 0:  # 50번마다 요약 로그
                    logger.info(
                        f"[D85-1] Iteration {iteration}: Entry={entry_bps}bps, TP={tp_bps}bps, "
                        f"status={results[0].status}, "
                        f"filled_qty={results[0].quantity:.6f}, "
                        f"buy_fill={results[0].buy_fill_ratio*100:.2f}%, "
                        f"sell_fill={results[0].sell_fill_ratio*100:.2f}%, "
                        f"pnl=${results[0].pnl:.2f}"
                    )
        
        time.sleep(1)
    
    # 9. 종료 처리
    market_data_provider.stop()
    metrics["end_time"] = time.time()
    metrics["actual_duration_seconds"] = metrics["end_time"] - metrics["start_time"]
    
    # 10. FillEventCollector 요약
    collector_summary = fill_event_collector.get_summary()
    metrics["fill_events_count"] = collector_summary["events_count"]
    metrics["fill_events_path"] = str(fill_events_path)
    
    # 11. KPI 저장
    with open(kpi_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[D85-1] KPI 저장 완료: {kpi_path}")
    logger.info(f"[D85-1] Fill Events 저장 완료: {fill_events_path}")
    logger.info("")
    
    return metrics


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description="D85-1: Multi L2 Long PAPER & Calibration Data Collection"
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
        "--output-dir",
        type=str,
        default="logs/d85-1",
        help="출력 디렉토리 (기본값: logs/d85-1)"
    )
    
    args = parser.parse_args()
    
    # 스모크 모드
    if args.smoke:
        duration_seconds = 300  # 5분
    else:
        duration_seconds = args.duration_seconds
    
    calibration_path = Path(args.calibration_path)
    if not calibration_path.exists():
        logger.error(f"[D85-1] Calibration 파일이 존재하지 않습니다: {calibration_path}")
        sys.exit(1)
    
    logger.info("=" * 100)
    logger.info("[D85-1] Multi L2 Long PAPER & Calibration Data Collection 시작")
    logger.info("=" * 100)
    logger.info(f"Duration: {duration_seconds}초 ({duration_seconds/60:.1f}분)")
    logger.info(f"Calibration: {calibration_path}")
    logger.info(f"L2 Source: Multi (Upbit + Binance)")
    logger.info("")
    
    # 실행
    output_dir = Path(args.output_dir)
    metrics = run_multi_l2_long_paper(duration_seconds, calibration_path, output_dir)
    
    # 요약 출력
    logger.info("")
    logger.info("=" * 100)
    logger.info("[D85-1] 실행 요약")
    logger.info("=" * 100)
    logger.info(f"Session ID: {metrics['session_id']}")
    logger.info(f"Symbol: {metrics['symbol']}")
    logger.info(f"Duration: {metrics['actual_duration_seconds']:.1f}초 ({metrics['actual_duration_seconds']/60:.1f}분)")
    logger.info(f"Entry Trades: {metrics['entry_trades']}")
    logger.info(f"Fill Events 수집: {metrics['fill_events_count']}")
    logger.info(f"Total PnL: ${metrics['total_pnl_usd']:.2f}")
    logger.info(f"Fill Events 경로: {metrics['fill_events_path']}")
    logger.info("")
    logger.info("Entry/TP 조합 사용 횟수:")
    for pair_key, count in sorted(metrics['entry_tp_pairs_used'].items()):
        entry, tp = pair_key.split("_")
        logger.info(f"  Entry={entry}bps, TP={tp}bps: {count}회")
    logger.info("=" * 100)
    logger.info("")
    logger.info("[D85-1] 다음 단계: scripts/analyze_d85_1_fill_results.py 실행")


if __name__ == "__main__":
    main()
