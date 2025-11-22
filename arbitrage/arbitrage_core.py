"""
D37 Arbitrage Strategy MVP – Core Engine

Pure Python arbitrage detection and trade management.
No external API calls, no network I/O.
Deterministic and fully testable.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

logger = logging.getLogger(__name__)

Side = Literal["LONG_A_SHORT_B", "LONG_B_SHORT_A"]


@dataclass
class ArbitrageConfig:
    """Arbitrage strategy configuration."""

    min_spread_bps: float  # 최소 스프레드 (basis points)
    taker_fee_a_bps: float  # Exchange A 테이커 수수료 (bps)
    taker_fee_b_bps: float  # Exchange B 테이커 수수료 (bps)
    slippage_bps: float  # 슬리피지 (bps) - 양쪽 다리 합계
    max_position_usd: float  # 최대 포지션 크기 (USD)
    max_open_trades: int = 1  # 최대 동시 거래 수
    close_on_spread_reversal: bool = True  # 스프레드 역전 시 종료
    # D45: 환율 정규화 및 호가 스프레드 설정
    exchange_a_to_b_rate: float = 2.5  # 1 A_unit = N B_unit (예: 1 BTC = 2.5 * 40000 USDT)
    bid_ask_spread_bps: float = 100.0  # bid/ask 스프레드 (bps)


@dataclass
class OrderBookSnapshot:
    """주문서 스냅샷 (두 거래소)."""

    timestamp: str  # ISO 8601 형식
    best_bid_a: float  # Exchange A 최고 매수가
    best_ask_a: float  # Exchange A 최저 매도가
    best_bid_b: float  # Exchange B 최고 매수가
    best_ask_b: float  # Exchange B 최저 매도가


@dataclass
class ArbitrageOpportunity:
    """차익거래 기회."""

    timestamp: str
    side: Side  # LONG_A_SHORT_B 또는 LONG_B_SHORT_A
    spread_bps: float  # 총 스프레드 (bps)
    gross_edge_bps: float  # 수수료 차감 전 엣지 (bps)
    net_edge_bps: float  # 수수료 + 슬리피지 차감 후 엣지 (bps)
    notional_usd: float  # 거래 규모 (USD)


@dataclass
class ArbitrageTrade:
    """차익거래 거래."""

    open_timestamp: str
    close_timestamp: Optional[str] = None
    side: Side = "LONG_A_SHORT_B"
    entry_spread_bps: float = 0.0
    exit_spread_bps: Optional[float] = None
    notional_usd: float = 0.0
    pnl_usd: Optional[float] = None
    pnl_bps: Optional[float] = None
    is_open: bool = True
    meta: Dict[str, str] = field(default_factory=dict)
    # D65: Exit 이유 추적
    exit_reason: Optional[str] = None  # "spread_reversal", "take_profit", "stop_loss", etc.

    def close(
        self,
        close_timestamp: str,
        exit_spread_bps: float,
        taker_fee_a_bps: float,
        taker_fee_b_bps: float,
        slippage_bps: float,
    ) -> None:
        """거래 종료 및 PnL 계산."""
        self.close_timestamp = close_timestamp
        self.exit_spread_bps = exit_spread_bps
        self.is_open = False

        # PnL 계산: (진입 스프레드 - 종료 스프레드 - 수수료 - 슬리피지) * 명목가
        # 수수료와 슬리피지는 이미 스프레드에 반영되어 있으므로 추가 차감
        total_cost_bps = taker_fee_a_bps + taker_fee_b_bps + slippage_bps
        net_pnl_bps = self.entry_spread_bps - exit_spread_bps - total_cost_bps

        self.pnl_bps = net_pnl_bps
        self.pnl_usd = (net_pnl_bps / 10_000.0) * self.notional_usd
    
    def to_dict(self) -> Dict[str, Any]:
        """D70: JSON 직렬화를 위한 dict 변환"""
        return {
            'open_timestamp': self.open_timestamp,
            'close_timestamp': self.close_timestamp,
            'side': self.side,
            'entry_spread_bps': self.entry_spread_bps,
            'exit_spread_bps': self.exit_spread_bps,
            'notional_usd': self.notional_usd,
            'pnl_usd': self.pnl_usd,
            'pnl_bps': self.pnl_bps,
            'is_open': self.is_open,
            'meta': dict(self.meta),
            'exit_reason': self.exit_reason
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ArbitrageTrade':
        """D70: dict에서 ArbitrageTrade 객체 복원"""
        return cls(
            open_timestamp=data['open_timestamp'],
            close_timestamp=data.get('close_timestamp'),
            side=data.get('side', 'LONG_A_SHORT_B'),
            entry_spread_bps=data.get('entry_spread_bps', 0.0),
            exit_spread_bps=data.get('exit_spread_bps'),
            notional_usd=data.get('notional_usd', 0.0),
            pnl_usd=data.get('pnl_usd'),
            pnl_bps=data.get('pnl_bps'),
            is_open=data.get('is_open', True),
            meta=data.get('meta', {}),
            exit_reason=data.get('exit_reason')
        )


class ArbitrageEngine:
    """차익거래 엔진."""

    def __init__(self, config: ArbitrageConfig):
        """엔진 초기화."""
        self.config = config
        self._open_trades: List[ArbitrageTrade] = []
        self._last_snapshot: Optional[OrderBookSnapshot] = None
        
        # D75-2: Pre-calculated values (Phase 2 최적화)
        self._total_cost_bps = (
            self.config.taker_fee_a_bps
            + self.config.taker_fee_b_bps
            + self.config.slippage_bps
        )
        self._exchange_a_to_b_rate = self.config.exchange_a_to_b_rate

    def detect_opportunity(
        self, snapshot: OrderBookSnapshot
    ) -> Optional[ArbitrageOpportunity]:
        """
        주문서 스냅샷에서 차익거래 기회 감지.

        D45 개선사항:
        - 환율 정규화: bid_b_normalized = bid_b * exchange_a_to_b_rate
        - bid/ask 스프레드 확장: bid = mid * (1 - spread/2), ask = mid * (1 + spread/2)
        - 더 현실적인 스프레드 계산

        두 방향 스프레드 계산:
        - LONG_A_SHORT_B: A에서 매수(ask_a), B에서 매도(bid_b_normalized)
          spread = (bid_b_normalized - ask_a) / ask_a * 10_000 (bps)
        - LONG_B_SHORT_A: B에서 매수(ask_b_normalized), A에서 매도(bid_a)
          spread = (bid_a - ask_b_normalized) / ask_b_normalized * 10_000 (bps)
        """
        # 기본 검증
        if (
            snapshot.best_bid_a <= 0
            or snapshot.best_ask_a <= 0
            or snapshot.best_bid_b <= 0
            or snapshot.best_ask_b <= 0
        ):
            return None

        # bid < ask는 정상 (bid는 매수 호가, ask는 매도 호가)
        if snapshot.best_bid_a >= snapshot.best_ask_a:
            return None
        if snapshot.best_bid_b >= snapshot.best_ask_b:
            return None

        # D45: 환율 정규화 (D75-2: cached exchange rate 사용)
        # bid_b와 ask_b를 A의 통화 단위로 정규화
        bid_b_normalized = snapshot.best_bid_b * self._exchange_a_to_b_rate
        ask_b_normalized = snapshot.best_ask_b * self._exchange_a_to_b_rate

        # LONG_A_SHORT_B 스프레드: A에서 매수(ask_a), B에서 매도(bid_b_normalized)
        # 수익 = bid_b_normalized - ask_a (절대값)
        # 수익률 = (bid_b_normalized - ask_a) / ask_a
        spread_a_to_b = (bid_b_normalized - snapshot.best_ask_a) / snapshot.best_ask_a * 10_000.0

        # LONG_B_SHORT_A 스프레드: B에서 매수(ask_b_normalized), A에서 매도(bid_a)
        # 수익 = bid_a - ask_b_normalized (절대값)
        # 수익률 = (bid_a - ask_b_normalized) / ask_b_normalized
        spread_b_to_a = (snapshot.best_bid_a - ask_b_normalized) / ask_b_normalized * 10_000.0

        # D75-2: Pre-calculated total cost (Phase 2 최적화)
        total_cost_bps = self._total_cost_bps

        # 최적 방향 선택
        best_spread = max(spread_a_to_b, spread_b_to_a)
        net_edge = best_spread - total_cost_bps

        # D45: 최소 스프레드 완화 (20 bps → 0 bps, 즉 양수이면 신호 생성)
        # 이전: if net_edge < self.config.min_spread_bps
        # 현재: if net_edge <= 0 (손실이 아니면 거래 신호)
        if net_edge < 0:
            return None

        # D75-2: 최대 거래 수 확인 (len() 1회만 호출)
        open_trade_count = len(self._open_trades)
        if open_trade_count >= self.config.max_open_trades:
            return None

        # 최적 방향 결정
        if spread_a_to_b >= spread_b_to_a:
            side = "LONG_A_SHORT_B"
            gross_edge = spread_a_to_b
        else:
            side = "LONG_B_SHORT_A"
            gross_edge = spread_b_to_a

        return ArbitrageOpportunity(
            timestamp=snapshot.timestamp,
            side=side,
            spread_bps=best_spread,
            gross_edge_bps=gross_edge,
            net_edge_bps=net_edge,
            notional_usd=self.config.max_position_usd,
        )

    def on_snapshot(self, snapshot: OrderBookSnapshot) -> List[ArbitrageTrade]:
        """
        스냅샷 처리: 거래 개설/종료.
        
        D65: Exit 이유 추적 (spread_reversal, take_profit, stop_loss)
        D75-2: 환율 정규화 1회 계산 후 재사용 (Phase 2 최적화)

        반환: 이 스냅샷에서 개설/종료된 거래 목록
        """
        self._last_snapshot = snapshot
        trades_changed: List[ArbitrageTrade] = []

        # D75-2: 환율 정규화 값을 1회만 계산 (Phase 2 최적화)
        bid_b_normalized = snapshot.best_bid_b * self._exchange_a_to_b_rate
        ask_b_normalized = snapshot.best_ask_b * self._exchange_a_to_b_rate

        # 기존 거래 종료 확인
        if self.config.close_on_spread_reversal:
            trades_to_close = []
            for trade in self._open_trades:
                # D75-2: 미리 계산된 normalized 값 재사용
                
                # 스프레드 역전 또는 음수 확인
                if trade.side == "LONG_A_SHORT_B":
                    current_spread = (
                        (bid_b_normalized - snapshot.best_ask_a)
                        / snapshot.best_ask_a
                        * 10_000.0
                    )
                else:
                    current_spread = (
                        (snapshot.best_bid_a - ask_b_normalized)
                        / ask_b_normalized
                        * 10_000.0
                    )

                # 스프레드가 음수가 되면 종료 (D65: exit_reason 설정)
                if current_spread < 0:
                    trades_to_close.append((trade, "spread_reversal"))

            for trade, exit_reason in trades_to_close:
                trade.close(
                    close_timestamp=snapshot.timestamp,
                    exit_spread_bps=0.0,
                    taker_fee_a_bps=self.config.taker_fee_a_bps,
                    taker_fee_b_bps=self.config.taker_fee_b_bps,
                    slippage_bps=self.config.slippage_bps,
                )
                trade.exit_reason = exit_reason  # D65: Exit 이유 설정
                self._open_trades.remove(trade)
                trades_changed.append(trade)

        # 새로운 기회 감지 및 거래 개설
        opportunity = self.detect_opportunity(snapshot)
        if opportunity:
            new_trade = ArbitrageTrade(
                open_timestamp=snapshot.timestamp,
                side=opportunity.side,
                entry_spread_bps=opportunity.spread_bps,
                notional_usd=opportunity.notional_usd,
                is_open=True,
            )
            self._open_trades.append(new_trade)
            trades_changed.append(new_trade)
            logger.debug(
                f"Opened trade: {opportunity.side} at {opportunity.spread_bps:.2f} bps"
            )

        return trades_changed

    def get_open_trades(self) -> List[ArbitrageTrade]:
        """현재 개설된 거래 목록 반환."""
        return list(self._open_trades)

    def get_last_snapshot(self) -> Optional[OrderBookSnapshot]:
        """마지막 스냅샷 반환."""
        return self._last_snapshot
