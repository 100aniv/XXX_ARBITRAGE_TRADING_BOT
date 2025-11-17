# -*- coding: utf-8 -*-
"""
D44 Arbitrage Live Runner with RiskGuard

ArbitrageEngine + Exchange Adapter를 연결하는 실시간 루프.
Paper 모드 우선 구현 + RiskGuard 하드닝.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from arbitrage.arbitrage_core import (
    ArbitrageEngine,
    ArbitrageConfig,
    OrderBookSnapshot,
    ArbitrageTrade,
)
from arbitrage.exchanges.base import (
    BaseExchange,
    OrderSide,
    OrderType,
)

logger = logging.getLogger(__name__)


class RiskGuardDecision(Enum):
    """RiskGuard 판정 결과"""
    OK = "OK"
    TRADE_REJECTED = "TRADE_REJECTED"
    SESSION_STOP = "SESSION_STOP"


class RiskGuard:
    """
    리스크 가드: 거래 실행 전 리스크 체크.
    
    책임:
    - 거래당 최대 명목가 확인
    - 일일 최대 손실 확인
    - 최대 동시 거래 수 확인
    - 세션 종료 조건 판정
    """
    
    def __init__(self, risk_limits: "RiskLimits"):
        """
        Args:
            risk_limits: RiskLimits 설정
        """
        self.risk_limits = risk_limits
        self.session_start_time = time.time()
        self.daily_loss_usd = 0.0
        
        logger.info(
            f"[D44_RISKGUARD] Initialized: "
            f"max_notional={risk_limits.max_notional_per_trade}, "
            f"max_daily_loss={risk_limits.max_daily_loss}, "
            f"max_open_trades={risk_limits.max_open_trades}"
        )
    
    def check_trade_allowed(
        self,
        trade: ArbitrageTrade,
        num_active_orders: int,
    ) -> RiskGuardDecision:
        """
        거래 실행 가능 여부 판정.
        
        Args:
            trade: 거래 정보
            num_active_orders: 현재 활성 주문 수
        
        Returns:
            RiskGuardDecision
        """
        # 1. 거래당 최대 명목가 확인
        if trade.notional_usd > self.risk_limits.max_notional_per_trade:
            logger.warning(
                f"[D44_RISKGUARD] Trade rejected: "
                f"notional={trade.notional_usd} > max={self.risk_limits.max_notional_per_trade}"
            )
            return RiskGuardDecision.TRADE_REJECTED
        
        # 2. 최대 동시 거래 수 확인
        if num_active_orders >= self.risk_limits.max_open_trades:
            logger.warning(
                f"[D44_RISKGUARD] Trade rejected: "
                f"active_orders={num_active_orders} >= max={self.risk_limits.max_open_trades}"
            )
            return RiskGuardDecision.TRADE_REJECTED
        
        # 3. 일일 최대 손실 확인
        if self.daily_loss_usd >= self.risk_limits.max_daily_loss:
            logger.error(
                f"[D44_RISKGUARD] Session stop: "
                f"daily_loss={self.daily_loss_usd} >= max={self.risk_limits.max_daily_loss}"
            )
            return RiskGuardDecision.SESSION_STOP
        
        return RiskGuardDecision.OK
    
    def update_daily_loss(self, pnl_usd: float) -> None:
        """
        일일 손실 업데이트.
        
        Args:
            pnl_usd: 거래 손익 (음수면 손실)
        """
        if pnl_usd < 0:
            self.daily_loss_usd += abs(pnl_usd)
            logger.debug(
                f"[D44_RISKGUARD] Daily loss updated: {self.daily_loss_usd:.2f} USD"
            )


@dataclass
class RiskLimits:
    """리스크 제한 설정"""
    max_notional_per_trade: float = 10000.0  # 거래당 최대 명목가 (USD)
    max_daily_loss: float = 1000.0  # 일일 최대 손실 (USD)
    max_open_trades: int = 1  # 최대 동시 거래 수


@dataclass
class LiveTradingConfig:
    """D47: 실거래 모드 설정"""
    enabled: bool = False  # 실거래 활성화 (기본: False)
    dry_run_scale: float = 0.01  # 주문 수량 축소 비율 (0.0~1.0, 기본: 1%)
    allowed_symbols: List[str] = field(default_factory=list)  # 허용 심볼 목록
    min_account_balance: float = 50.0  # 최소 계좌 잔고 (USD)
    max_daily_loss: float = 20.0  # 최대 일일 손실 (USD)
    max_notional_per_trade: float = 50.0  # 거래당 최대 명목가 (USD)


@dataclass
class ArbitrageLiveConfig:
    """Live Runner 설정"""
    
    # 거래 쌍
    symbol_a: str  # 예: "KRW-BTC"
    symbol_b: str  # 예: "BTCUSDT"
    
    # 엔진 설정
    min_spread_bps: float = 30.0
    taker_fee_a_bps: float = 5.0
    taker_fee_b_bps: float = 5.0
    slippage_bps: float = 5.0
    max_position_usd: float = 1000.0
    
    # 루프 설정
    poll_interval_seconds: float = 1.0
    max_concurrent_trades: int = 1
    mode: str = "paper"  # "paper" | "live_readonly" | "live_trading" (D46-D47)
    log_level: str = "INFO"
    max_runtime_seconds: Optional[int] = None  # None이면 무제한
    
    # 리스크 제한
    risk_limits: RiskLimits = field(default_factory=RiskLimits)
    
    # Paper 모드 시뮬레이션 설정 (D44)
    paper_simulation_enabled: bool = False  # Paper 호가 변동 시뮬레이션 활성화
    paper_volatility_range_bps: float = 100.0  # ±100 bps 변동 범위
    paper_spread_injection_interval: int = 5  # 5초마다 스프레드 주입
    
    # D47: 실거래 모드 설정
    live_trading: LiveTradingConfig = field(default_factory=LiveTradingConfig)
    
    # D50.5: 데이터 소스 선택 (rest | ws)
    data_source: str = "rest"  # 기본값: rest (안전)


class ArbitrageLiveRunner:
    """
    Arbitrage Live Runner.
    
    두 거래소의 호가를 받아서 엔진에 전달하고,
    신호에 따라 주문을 실행하는 루프.
    """
    
    def __init__(
        self,
        engine: ArbitrageEngine,
        exchange_a: BaseExchange,
        exchange_b: BaseExchange,
        config: ArbitrageLiveConfig,
        market_data_provider: Optional["MarketDataProvider"] = None,
        metrics_collector: Optional["MetricsCollector"] = None,
    ):
        """
        Args:
            engine: ArbitrageEngine 인스턴스
            exchange_a: 거래소 A (Upbit 역할)
            exchange_b: 거래소 B (Binance 역할)
            config: ArbitrageLiveConfig
            market_data_provider: MarketDataProvider (D50.5, 선택사항)
            metrics_collector: MetricsCollector (D50.5, 선택사항)
        """
        self.engine = engine
        self.exchange_a = exchange_a
        self.exchange_b = exchange_b
        self.config = config
        self.market_data_provider = market_data_provider
        self.metrics_collector = metrics_collector
        
        # RiskGuard 초기화 (D44)
        self._risk_guard = RiskGuard(config.risk_limits)
        self._session_stop_requested = False
        
        # 상태 추적
        self._start_time = time.time()
        self._loop_count = 0
        self._total_trades_opened = 0
        self._total_trades_closed = 0
        self._total_pnl_usd = 0.0
        self._active_orders: Dict[str, Dict[str, Any]] = {}
        
        # Paper 시뮬레이션 상태 (D44)
        self._last_price_injection_time = time.time()
        
        # D50.5: 메트릭 추적
        self._last_spread_bps = 0.0
        self._last_loop_time_ms = 0.0
        
        logger.info(
            f"[D43_LIVE] ArbitrageLiveRunner initialized: "
            f"{config.symbol_a} vs {config.symbol_b}, mode={config.mode}, "
            f"data_source={config.data_source}"
        )
    
    def build_snapshot(self) -> Optional[OrderBookSnapshot]:
        """
        두 거래소에서 호가를 가져와 OrderBookSnapshot 생성.
        D50.5: MarketDataProvider 지원 추가.
        Paper 시뮬레이션 호가 변동 포함 (D44).
        
        Returns:
            OrderBookSnapshot 또는 None (오류 발생 시)
        """
        try:
            # D50.5: MarketDataProvider 사용 (data_source 기반)
            if self.market_data_provider is not None:
                # WebSocket 또는 REST 제공자 사용
                snapshot_a = self.market_data_provider.get_latest_snapshot(self.config.symbol_a)
                snapshot_b = self.market_data_provider.get_latest_snapshot(self.config.symbol_b)
                
                if snapshot_a is None or snapshot_b is None:
                    logger.warning(
                        f"[D50_LIVE] MarketDataProvider returned None snapshot: "
                        f"A={snapshot_a is not None}, B={snapshot_b is not None}"
                    )
                    return None
                
                # OrderBookSnapshot 생성 (D37 형식)
                best_bid_a = snapshot_a.bids[0][0] if snapshot_a.bids else None
                best_ask_a = snapshot_a.asks[0][0] if snapshot_a.asks else None
                best_bid_b = snapshot_b.bids[0][0] if snapshot_b.bids else None
                best_ask_b = snapshot_b.asks[0][0] if snapshot_b.asks else None
                
                if not all([best_bid_a, best_ask_a, best_bid_b, best_ask_b]):
                    logger.warning("[D50_LIVE] Invalid snapshot data from MarketDataProvider")
                    return None
                
                snapshot = OrderBookSnapshot(
                    timestamp=datetime.utcnow().isoformat(),
                    best_bid_a=best_bid_a,
                    best_ask_a=best_ask_a,
                    best_bid_b=best_bid_b,
                    best_ask_b=best_ask_b,
                )
                
                logger.debug(
                    f"[D50_LIVE] Snapshot from {self.config.data_source}: "
                    f"A(bid={best_bid_a}, ask={best_ask_a}), "
                    f"B(bid={best_bid_b}, ask={best_ask_b})"
                )
                
                return snapshot
            
            # 기존 REST 기반 로직 (data_source="rest" 또는 provider 없음)
            # Paper 시뮬레이션 호가 변동 (D44)
            if self.config.paper_simulation_enabled:
                self._inject_paper_prices()
            
            # Exchange A 호가
            orderbook_a = self.exchange_a.get_orderbook(self.config.symbol_a)
            if not orderbook_a.bids or not orderbook_a.asks:
                logger.warning(f"[D43_LIVE] Empty orderbook for {self.config.symbol_a}")
                return None
            
            best_bid_a = orderbook_a.best_bid()
            best_ask_a = orderbook_a.best_ask()
            
            # Exchange B 호가
            orderbook_b = self.exchange_b.get_orderbook(self.config.symbol_b)
            if not orderbook_b.bids or not orderbook_b.asks:
                logger.warning(f"[D43_LIVE] Empty orderbook for {self.config.symbol_b}")
                return None
            
            best_bid_b = orderbook_b.best_bid()
            best_ask_b = orderbook_b.best_ask()
            
            # OrderBookSnapshot 생성 (D37 형식)
            snapshot = OrderBookSnapshot(
                timestamp=datetime.utcnow().isoformat(),
                best_bid_a=best_bid_a,
                best_ask_a=best_ask_a,
                best_bid_b=best_bid_b,
                best_ask_b=best_ask_b,
            )
            
            logger.debug(
                f"[D44_DEBUG] Snapshot created: "
                f"bid_a={best_bid_a}, ask_a={best_ask_a}, "
                f"bid_b={best_bid_b}, ask_b={best_ask_b}"
            )
            
            logger.debug(
                f"[D43_LIVE] Snapshot: A(bid={best_bid_a}, ask={best_ask_a}), "
                f"B(bid={best_bid_b}, ask={best_ask_b})"
            )
            
            return snapshot
        
        except Exception as e:
            logger.error(f"[D43_LIVE] Error building snapshot: {e}")
            return None
    
    def _inject_paper_prices(self) -> None:
        """
        Paper 모드 호가 변동 시뮬레이션 (D45 개선).
        
        5초마다 스프레드를 주입하여 거래 신호 생성.
        
        D45 개선사항:
        - 환율 정규화 반영 (1 BTC = 100,000 KRW = 40,000 USDT)
        - bid/ask 스프레드 추가 (현실적 호가)
        - LONG_A_SHORT_B 신호 생성 최적화
        """
        current_time = time.time()
        if current_time - self._last_price_injection_time < self.config.paper_spread_injection_interval:
            return
        
        self._last_price_injection_time = current_time
        
        # D45: 환율 정규화 및 bid/ask 스프레드 추가
        # 기본 환율: 1 BTC = 100,000 KRW = 40,000 USDT
        # exchange_a_to_b_rate = 2.5 (100,000 / 40,000)
        
        # 기본 중가 (mid price)
        mid_a = 100000.0  # A (KRW)
        mid_b = 40000.0   # B (USDT)
        
        # bid/ask 스프레드 (1% = 100 bps)
        # bid = mid * (1 - spread_bps / 20000)
        # ask = mid * (1 + spread_bps / 20000)
        spread_bps = 100.0  # 1% 스프레드
        spread_ratio = spread_bps / 20000.0  # 0.005
        
        # A 호가 (저가)
        bid_a = mid_a * (1 - spread_ratio)  # 99,500
        ask_a = mid_a * (1 + spread_ratio)  # 100,500
        
        # B 호가 (고가)
        bid_b = mid_b * (1 + spread_ratio)  # 40,200
        ask_b = mid_b * (1 + spread_ratio)  # 40,200
        
        # D45: 스프레드 계산 검증
        # bid_b_normalized = 40,200 * 2.5 = 100,500
        # spread = (100,500 - 100,500) / 100,500 * 10000 = 0 bps (경계선)
        # 더 큰 스프레드를 위해 B를 더 높게 설정
        bid_b = mid_b * (1 + spread_ratio * 2)  # 40,400
        ask_b = mid_b * (1 + spread_ratio * 2)  # 40,400
        
        # 재검증:
        # bid_b_normalized = 40,400 * 2.5 = 101,000
        # spread = (101,000 - 100,500) / 100,500 * 10000 = 50 bps ✓
        
        # 호가 주입 (PaperExchange.set_orderbook 사용)
        from arbitrage.exchanges.base import OrderBookSnapshot as BaseOrderBookSnapshot
        
        snapshot_a = BaseOrderBookSnapshot(
            symbol=self.config.symbol_a,
            timestamp=time.time(),
            bids=[(bid_a, 1.0)],
            asks=[(ask_a, 1.0)],
        )
        self.exchange_a.set_orderbook(self.config.symbol_a, snapshot_a)
        
        snapshot_b = BaseOrderBookSnapshot(
            symbol=self.config.symbol_b,
            timestamp=time.time(),
            bids=[(bid_b, 1.0)],
            asks=[(ask_b, 1.0)],
        )
        self.exchange_b.set_orderbook(self.config.symbol_b, snapshot_b)
        
        logger.info(
            f"[D44_PAPER] Injected prices: "
            f"A(bid={bid_a}, ask={ask_a}), B(bid={bid_b}, ask={ask_b})"
        )
    
    def process_snapshot(self, snapshot: OrderBookSnapshot) -> List[ArbitrageTrade]:
        """
        스냅샷을 엔진에 전달하고 신규/종료 거래 반환.
        
        Args:
            snapshot: OrderBookSnapshot
        
        Returns:
            이 스냅샷에서 개설/종료된 거래 목록
        """
        try:
            trades = self.engine.on_snapshot(snapshot)
            logger.debug(f"[D43_LIVE] Engine returned {len(trades)} trades")
            return trades
        
        except Exception as e:
            logger.error(f"[D43_LIVE] Error processing snapshot: {e}")
            return []
    
    def execute_trades(self, trades: List[ArbitrageTrade]) -> None:
        """
        거래 목록을 실제 주문으로 변환하여 실행.
        RiskGuard 체크 포함 (D44).
        
        Args:
            trades: ArbitrageTrade 목록
        """
        for trade in trades:
            try:
                if trade.is_open:
                    # RiskGuard 체크 (D44)
                    decision = self._risk_guard.check_trade_allowed(
                        trade,
                        len(self._active_orders)
                    )
                    
                    if decision == RiskGuardDecision.SESSION_STOP:
                        logger.error("[D44_RISKGUARD] Session stop requested")
                        self._session_stop_requested = True
                        break
                    
                    if decision == RiskGuardDecision.TRADE_REJECTED:
                        logger.warning(f"[D44_RISKGUARD] Trade rejected: {trade.side}")
                        continue
                    
                    # 신규 거래 개설
                    self._execute_open_trade(trade)
                    self._total_trades_opened += 1
                else:
                    # 거래 종료
                    self._execute_close_trade(trade)
                    self._total_trades_closed += 1
                    
                    # PnL 누적 및 RiskGuard 업데이트 (D44)
                    if trade.pnl_usd is not None:
                        self._total_pnl_usd += trade.pnl_usd
                        self._risk_guard.update_daily_loss(trade.pnl_usd)
            
            except Exception as e:
                logger.error(f"[D43_LIVE] Error executing trade: {e}")
    
    def _execute_open_trade(self, trade: ArbitrageTrade) -> None:
        """
        신규 거래 개설: 양쪽 거래소에 주문 생성.
        
        D45 개선: 현실적인 주문 수량 계산
        
        Args:
            trade: ArbitrageTrade
        """
        logger.info(
            f"[D43_LIVE] Opening trade: {trade.side}, "
            f"notional={trade.notional_usd}, spread={trade.entry_spread_bps}bps"
        )
        
        # D45: 현실적인 주문 수량 계산
        # 마지막 스냅샷에서 현재가 조회
        snapshot = self.build_snapshot()
        if not snapshot:
            logger.error("[D45_QUANTITY] Failed to get snapshot for quantity calculation")
            return
        
        # 기준가: Exchange A의 ask 가격 사용
        # notional_usd를 환율로 변환하여 수량 계산
        # qty = notional_usd / (ask_a * exchange_a_to_b_rate)
        # 예: notional_usd=5000, ask_a=100500, rate=2.5
        # qty = 5000 / (100500 * 2.5) = 5000 / 251250 = 0.0199 BTC
        
        exchange_rate = self.engine.config.exchange_a_to_b_rate
        ask_a = snapshot.best_ask_a
        
        # 수량 계산 (USD 기준)
        qty = trade.notional_usd / (ask_a * exchange_rate)
        
        logger.debug(
            f"[D45_QUANTITY] Calculated qty={qty:.6f} BTC "
            f"(notional={trade.notional_usd}, ask_a={ask_a}, rate={exchange_rate})"
        )
        
        try:
            if trade.side == "LONG_A_SHORT_B":
                # A에서 매수, B에서 매도
                order_a = self.exchange_a.create_order(
                    symbol=self.config.symbol_a,
                    side=OrderSide.BUY,
                    qty=qty,
                    price=None,  # Market order
                    order_type=OrderType.MARKET,
                )
                
                order_b = self.exchange_b.create_order(
                    symbol=self.config.symbol_b,
                    side=OrderSide.SELL,
                    qty=qty,
                    price=None,  # Market order
                    order_type=OrderType.MARKET,
                )
                
                # 주문 추적
                self._active_orders[trade.open_timestamp] = {
                    "trade": trade,
                    "order_a": order_a,
                    "order_b": order_b,
                }
                self._total_trades_opened += 1
            
            elif trade.side == "LONG_B_SHORT_A":
                # B에서 매수, A에서 매도
                order_b = self.exchange_b.create_order(
                    symbol=self.config.symbol_b,
                    side=OrderSide.BUY,
                    qty=qty,
                    price=None,  # Market order
                    order_type=OrderType.MARKET,
                )
                
                order_a = self.exchange_a.create_order(
                    symbol=self.config.symbol_a,
                    side=OrderSide.SELL,
                    qty=qty,
                    price=None,  # Market order
                    order_type=OrderType.MARKET,
                )
                
                # 주문 추적
                self._active_orders[trade.open_timestamp] = {
                    "trade": trade,
                    "order_a": order_a,
                    "order_b": order_b,
                }
                self._total_trades_opened += 1
        
        except Exception as e:
            logger.error(f"[D43_LIVE] Failed to execute trade: {e}")
    
    def _execute_close_trade(self, trade: ArbitrageTrade) -> None:
        """
        거래 종료: 양쪽 거래소의 포지션 정리.
        
        Args:
            trade: ArbitrageTrade
        """
        logger.info(
            f"[D43_LIVE] Closing trade: {trade.side}, "
            f"pnl={trade.pnl_usd}USD ({trade.pnl_bps}bps)"
        )
        
        # 주문 추적에서 제거
        if trade.open_timestamp in self._active_orders:
            del self._active_orders[trade.open_timestamp]
    
    def run_once(self) -> bool:
        """
        1회 루프 실행: snapshot → engine → trades → orders.
        D50.5: 메트릭 수집 추가.
        D53: 성능 최적화 - dict 할당 제거, getattr 최소화.
        
        Returns:
            성공 여부
        """
        loop_start = time.time()
        self._loop_count += 1
        
        # 스냅샷 생성
        snapshot = self.build_snapshot()
        if snapshot is None:
            logger.warning("[D43_LIVE] Failed to build snapshot")
            return False
        
        # 엔진 처리
        trades = self.process_snapshot(snapshot)
        
        # 주문 실행 (D53: list comprehension 최소화)
        trades_opened_delta = sum(1 for t in trades if t.is_open)
        self.execute_trades(trades)
        
        # D50.5/D53: 메트릭 수집 (최적화)
        loop_end = time.time()
        loop_time_ms = (loop_end - loop_start) * 1000.0
        self._last_loop_time_ms = loop_time_ms
        
        # D53: 스프레드 캐싱 (hasattr 대신 직접 접근)
        last_spread_bps = getattr(self.engine, 'last_spread_bps', self._last_spread_bps)
        self._last_spread_bps = last_spread_bps
        
        # D53: MetricsCollector 업데이트 (조건부 dict 생성 제거)
        if self.metrics_collector is not None:
            # WS 상태는 provider가 있을 때만 조회
            if self.market_data_provider is not None:
                ws_connected = getattr(self.market_data_provider, 'ws_connected', False)
                ws_reconnects = getattr(self.market_data_provider, 'ws_reconnects', 0)
            else:
                ws_connected = False
                ws_reconnects = 0
            
            self.metrics_collector.update_loop_metrics(
                loop_time_ms=loop_time_ms,
                trades_opened=trades_opened_delta,
                spread_bps=last_spread_bps,
                data_source=self.config.data_source,
                ws_connected=ws_connected,
                ws_reconnects=ws_reconnects,
            )
        
        logger.debug(
            f"[D43_LIVE] Loop {self._loop_count}: "
            f"trades={len(trades)}, active_orders={len(self._active_orders)}, "
            f"loop_time={loop_time_ms:.2f}ms"
        )
        
        return True
    
    def run_forever(self) -> None:
        """
        무한 루프 실행 (또는 max_runtime_seconds 조건).
        RiskGuard session_stop 체크 포함 (D44).
        """
        logger.info(
            f"[D43_LIVE] Starting live loop: "
            f"interval={self.config.poll_interval_seconds}s, "
            f"max_runtime={self.config.max_runtime_seconds}s"
        )
        
        while True:
            # RiskGuard session_stop 확인 (D44)
            if self._session_stop_requested:
                logger.info("[D44_RISKGUARD] Session stopped by RiskGuard")
                break
            
            # 런타임 제한 확인
            if self.config.max_runtime_seconds is not None:
                elapsed = time.time() - self._start_time
                if elapsed > self.config.max_runtime_seconds:
                    logger.info(
                        f"[D43_LIVE] Max runtime exceeded: {elapsed:.1f}s > "
                        f"{self.config.max_runtime_seconds}s"
                    )
                    break
            
            # 1회 루프 실행
            self.run_once()
            
            # 대기
            time.sleep(self.config.poll_interval_seconds)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        현재 통계 반환.
        
        Returns:
            통계 dict
        """
        elapsed = time.time() - self._start_time
        
        return {
            "elapsed_seconds": elapsed,
            "loop_count": self._loop_count,
            "total_trades_opened": self._total_trades_opened,
            "total_trades_closed": self._total_trades_closed,
            "total_pnl_usd": self._total_pnl_usd,
            "active_orders": len(self._active_orders),
            "avg_loop_time_ms": (elapsed / self._loop_count * 1000) if self._loop_count > 0 else 0,
        }
