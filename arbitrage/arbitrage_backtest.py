"""
D37 Arbitrage Strategy MVP – Backtest Engine

Offline backtesting framework for arbitrage strategy.
No external API calls, no network I/O.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from arbitrage.arbitrage_core import (
    ArbitrageEngine,
    OrderBookSnapshot,
    ArbitrageTrade,
)

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """백테스트 설정."""

    initial_balance_usd: float = 10_000.0
    max_steps: Optional[int] = None  # 최대 단계 수
    stop_on_drawdown_pct: Optional[float] = None  # 최대 낙폭 (%)


@dataclass
class BacktestResult:
    """백테스트 결과."""

    total_trades: int  # 총 거래 수
    closed_trades: int  # 종료된 거래 수
    open_trades: int  # 개설된 거래 수
    final_balance_usd: float  # 최종 잔액
    realized_pnl_usd: float  # 실현 손익
    max_drawdown_pct: float  # 최대 낙폭 (%)
    win_rate: float  # 승률 (0..1)
    avg_pnl_per_trade_usd: float  # 거래당 평균 손익
    stats: dict = field(default_factory=dict)  # 추가 통계


class ArbitrageBacktester:
    """차익거래 백테스터."""

    def __init__(
        self,
        arb_engine: ArbitrageEngine,
        config: BacktestConfig,
    ):
        """백테스터 초기화."""
        self.arb_engine = arb_engine
        self.config = config

    def run(self, snapshots: List[OrderBookSnapshot]) -> BacktestResult:
        """
        스냅샷 시리즈에 대해 백테스트 실행.

        프로세스:
        1. 각 스냅샷에 대해 엔진 호출
        2. 개설/종료된 거래 추적
        3. 손익 계산
        4. 낙폭 확인
        5. 최종 메트릭 계산
        """
        balance = self.config.initial_balance_usd
        peak_balance = balance
        max_drawdown = 0.0

        all_trades: List[ArbitrageTrade] = []
        closed_trades: List[ArbitrageTrade] = []
        realized_pnl = 0.0

        steps_processed = 0

        for snapshot in snapshots:
            # 최대 단계 수 확인
            if (
                self.config.max_steps is not None
                and steps_processed >= self.config.max_steps
            ):
                break

            # 엔진 호출
            trades_changed = self.arb_engine.on_snapshot(snapshot)

            # 거래 추적
            for trade in trades_changed:
                if trade not in all_trades:
                    all_trades.append(trade)

                # 종료된 거래 처리
                if not trade.is_open and trade.pnl_usd is not None:
                    if trade not in closed_trades:
                        closed_trades.append(trade)
                        realized_pnl += trade.pnl_usd

            # 잔액 업데이트 (실현 손익 기반)
            balance = self.config.initial_balance_usd + realized_pnl

            # 낙폭 계산
            if balance > peak_balance:
                peak_balance = balance
            drawdown = (peak_balance - balance) / peak_balance if peak_balance > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

            # 낙폭 한계 확인
            if (
                self.config.stop_on_drawdown_pct is not None
                and drawdown * 100 >= self.config.stop_on_drawdown_pct
            ):
                logger.info(
                    f"Stopped at drawdown {drawdown*100:.2f}% >= {self.config.stop_on_drawdown_pct}%"
                )
                break

            steps_processed += 1

        # 최종 메트릭 계산
        total_trades = len(all_trades)
        num_closed = len(closed_trades)
        num_open = len(self.arb_engine.get_open_trades())

        # 승률 계산
        winning_trades = sum(1 for t in closed_trades if t.pnl_usd and t.pnl_usd > 0)
        win_rate = winning_trades / num_closed if num_closed > 0 else 0.0

        # 거래당 평균 손익
        avg_pnl = realized_pnl / num_closed if num_closed > 0 else 0.0

        return BacktestResult(
            total_trades=total_trades,
            closed_trades=num_closed,
            open_trades=num_open,
            final_balance_usd=balance,
            realized_pnl_usd=realized_pnl,
            max_drawdown_pct=max_drawdown * 100,
            win_rate=win_rate,
            avg_pnl_per_trade_usd=avg_pnl,
            stats={
                "steps_processed": steps_processed,
                "total_snapshots": len(snapshots),
                "winning_trades": winning_trades,
                "losing_trades": num_closed - winning_trades,
            },
        )
