# -*- coding: utf-8 -*-
"""
Arbitrage Test Utilities

D68/D69 테스트 스크립트를 위한 공통 유틸리티 함수 모음.
엔진/Exchange/Runner 설정 중복 코드를 제거하고 재사용성을 높입니다.
"""

import time
from typing import Tuple, Dict, Any, Optional

from arbitrage.exchanges.paper_exchange import PaperExchange
from arbitrage.exchanges.base import OrderBookSnapshot
from arbitrage.live_runner import ArbitrageLiveRunner, ArbitrageLiveConfig, RiskLimits
from arbitrage.arbitrage_core import ArbitrageEngine, ArbitrageConfig


def create_default_paper_exchanges(
    symbol_a: str = "KRW-BTC",
    symbol_b: str = "BTCUSDT",
    price_a: float = 100000.0,
    price_b: float = 40000.0,
    quantity: float = 1.0,
) -> Tuple[PaperExchange, PaperExchange]:
    """
    기본 Paper Exchange 쌍 생성
    
    Args:
        symbol_a: Exchange A 심볼 (기본: KRW-BTC)
        symbol_b: Exchange B 심볼 (기본: BTCUSDT)
        price_a: Exchange A 초기 가격 (기본: 100000.0)
        price_b: Exchange B 초기 가격 (기본: 40000.0)
        quantity: 호가 수량 (기본: 1.0)
    
    Returns:
        (exchange_a, exchange_b) 튜플
    """
    exchange_a = PaperExchange()
    exchange_b = PaperExchange()
    
    # Exchange A 초기 호가 설정
    snapshot_a = OrderBookSnapshot(
        symbol=symbol_a,
        timestamp=time.time(),
        bids=[(price_a, quantity)],
        asks=[(price_a, quantity)],
    )
    exchange_a.set_orderbook(symbol_a, snapshot_a)
    
    # Exchange B 초기 호가 설정
    snapshot_b = OrderBookSnapshot(
        symbol=symbol_b,
        timestamp=time.time(),
        bids=[(price_b, quantity)],
        asks=[(price_b, quantity)],
    )
    exchange_b.set_orderbook(symbol_b, snapshot_b)
    
    return exchange_a, exchange_b


def create_paper_runner(
    engine: ArbitrageEngine,
    symbol_a: str = "KRW-BTC",
    symbol_b: str = "BTCUSDT",
    campaign_id: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    paper_spread_injection_interval: int = 5,
    risk_limits: Optional[RiskLimits] = None,
) -> ArbitrageLiveRunner:
    """
    Paper Runner 생성 (테스트용)
    
    Args:
        engine: ArbitrageEngine 인스턴스
        symbol_a: Exchange A 심볼
        symbol_b: Exchange B 심볼
        campaign_id: Paper 캠페인 ID (None이면 자동 생성)
        duration_seconds: 최대 실행 시간 (None이면 무제한)
        paper_spread_injection_interval: 스프레드 주입 간격 (초)
        risk_limits: RiskLimits 설정 (None이면 기본값)
    
    Returns:
        ArbitrageLiveRunner 인스턴스
    """
    # Exchange 생성
    exchange_a, exchange_b = create_default_paper_exchanges(
        symbol_a=symbol_a,
        symbol_b=symbol_b
    )
    
    # RiskLimits 기본값
    if risk_limits is None:
        risk_limits = RiskLimits(
            max_notional_per_trade=5000.0,
            max_daily_loss=10000.0,
            max_open_trades=1,
        )
    
    # ArbitrageLiveConfig 설정
    config = ArbitrageLiveConfig(
        symbol_a=symbol_a,
        symbol_b=symbol_b,
        mode="paper",
        data_source="paper",
        paper_spread_injection_interval=paper_spread_injection_interval,
        paper_simulation_enabled=True,
        risk_limits=risk_limits,
        max_runtime_seconds=duration_seconds,
        poll_interval_seconds=1.0
    )
    
    # Runner 생성
    runner = ArbitrageLiveRunner(
        engine=engine,
        exchange_a=exchange_a,
        exchange_b=exchange_b,
        config=config
    )
    
    # Campaign ID 설정
    if campaign_id is not None:
        runner._paper_campaign_id = campaign_id
    
    return runner


def collect_runner_metrics(runner: ArbitrageLiveRunner) -> Dict[str, Any]:
    """
    Runner로부터 메트릭 수집 (공개 인터페이스)
    
    Args:
        runner: ArbitrageLiveRunner 인스턴스
    
    Returns:
        메트릭 딕셔너리
    """
    # Private 변수 직접 접근 (현재 방식)
    # TODO: ArbitrageLiveRunner.get_session_summary() 메서드로 대체
    total_exits = getattr(runner, '_total_trades_closed', 0)
    
    return {
        'total_entries': getattr(runner, '_total_trades_opened', 0),
        'total_exits': total_exits,
        'total_pnl': getattr(runner, '_total_pnl_usd', 0.0),
        'winning_trades': getattr(runner, '_total_winning_trades', 0),
        'losing_trades': total_exits - getattr(runner, '_total_winning_trades', 0),
        'winrate_pct': (
            (getattr(runner, '_total_winning_trades', 0) / total_exits * 100.0)
            if total_exits > 0
            else 0.0
        ),
        'max_drawdown': abs(getattr(runner, '_max_dd_usd', 0.0)),
        'avg_pnl_per_trade': (
            (getattr(runner, '_total_pnl_usd', 0.0) / total_exits)
            if total_exits > 0
            else 0.0
        ),
    }
