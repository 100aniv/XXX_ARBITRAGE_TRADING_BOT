# -*- coding: utf-8 -*-
"""
D44 Arbitrage Live Runner with RiskGuard

ArbitrageEngine + Exchange Adapter를 연결하는 실시간 루프.
Paper 모드 우선 구현 + RiskGuard 하드닝.

D54: Async wrapper 추가 (멀티심볼 v2.0 기반)
D55: Complete async execution flow (완전 비동기 전환)
D56: Multi-Symbol Engine Phase 1 (구조 기반 마련)
"""

import asyncio
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
    
    D58: Multi-Symbol Integration
    - symbol-aware state tracking 준비
    - per-symbol loss tracking (future-proofing)
    
    D60: Multi-Symbol Capital & Position Limits
    - Per-symbol capital limits
    - Per-symbol position limits
    - Per-symbol concurrent trade limits
    """
    
    def __init__(self, risk_limits: "RiskLimits"):
        """
        Args:
            risk_limits: RiskLimits 설정
        """
        self.risk_limits = risk_limits
        self.session_start_time = time.time()
        self.daily_loss_usd = 0.0
        
        # D58: Multi-Symbol state tracking
        self.per_symbol_loss: Dict[str, float] = {}  # {symbol: loss_usd}
        self.per_symbol_trades_rejected: Dict[str, int] = {}  # {symbol: count}
        self.per_symbol_trades_allowed: Dict[str, int] = {}  # {symbol: count}
        
        # D60: Multi-Symbol Capital & Position Limits
        self.per_symbol_limits: Dict[str, "SymbolRiskLimits"] = {}  # {symbol: SymbolRiskLimits}
        self.per_symbol_capital_used: Dict[str, float] = {}  # {symbol: used_capital}
        self.per_symbol_position_count: Dict[str, int] = {}  # {symbol: position_count}
        
        logger.info(
            f"[D60_RISKGUARD] Initialized: "
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
    
    def check_trade_allowed_for_symbol(
        self,
        symbol: str,
        trade: ArbitrageTrade,
        num_active_orders: int,
    ) -> RiskGuardDecision:
        """
        D58: Symbol-aware trade allowed check.
        
        특정 심볼에 대한 거래 실행 가능 여부 판정.
        기존 check_trade_allowed와 동일한 로직이지만,
        symbol을 추적하여 per-symbol 상태를 업데이트한다.
        
        Args:
            symbol: 거래 심볼
            trade: 거래 정보
            num_active_orders: 현재 활성 주문 수
        
        Returns:
            RiskGuardDecision
        """
        # 1. 거래당 최대 명목가 확인
        if trade.notional_usd > self.risk_limits.max_notional_per_trade:
            logger.warning(
                f"[D58_RISKGUARD] Trade rejected for {symbol}: "
                f"notional={trade.notional_usd} > max={self.risk_limits.max_notional_per_trade}"
            )
            self.per_symbol_trades_rejected[symbol] = self.per_symbol_trades_rejected.get(symbol, 0) + 1
            return RiskGuardDecision.TRADE_REJECTED
        
        # 2. 최대 동시 거래 수 확인
        if num_active_orders >= self.risk_limits.max_open_trades:
            logger.warning(
                f"[D58_RISKGUARD] Trade rejected for {symbol}: "
                f"active_orders={num_active_orders} >= max={self.risk_limits.max_open_trades}"
            )
            self.per_symbol_trades_rejected[symbol] = self.per_symbol_trades_rejected.get(symbol, 0) + 1
            return RiskGuardDecision.TRADE_REJECTED
        
        # 3. 일일 최대 손실 확인
        if self.daily_loss_usd >= self.risk_limits.max_daily_loss:
            logger.error(
                f"[D58_RISKGUARD] Session stop for {symbol}: "
                f"daily_loss={self.daily_loss_usd} >= max={self.risk_limits.max_daily_loss}"
            )
            return RiskGuardDecision.SESSION_STOP
        
        # 거래 허용
        self.per_symbol_trades_allowed[symbol] = self.per_symbol_trades_allowed.get(symbol, 0) + 1
        return RiskGuardDecision.OK
    
    def update_symbol_loss(self, symbol: str, pnl_usd: float) -> None:
        """
        D58: Symbol-aware loss update.
        
        특정 심볼의 손실을 업데이트한다.
        
        Args:
            symbol: 거래 심볼
            pnl_usd: 거래 손익 (음수면 손실)
        """
        if pnl_usd < 0:
            loss = abs(pnl_usd)
            self.per_symbol_loss[symbol] = self.per_symbol_loss.get(symbol, 0.0) + loss
            self.daily_loss_usd += loss
            logger.debug(
                f"[D58_RISKGUARD] Symbol {symbol} loss updated: "
                f"symbol_loss={self.per_symbol_loss[symbol]:.2f}, "
                f"total_loss={self.daily_loss_usd:.2f} USD"
            )
    
    def get_symbol_stats(self, symbol: str) -> Dict[str, Any]:
        """
        D58: Get per-symbol risk statistics.
        
        특정 심볼의 리스크 통계를 반환한다.
        
        Args:
            symbol: 거래 심볼
        
        Returns:
            {
                'loss': float,
                'trades_rejected': int,
                'trades_allowed': int,
            }
        """
        return {
            'loss': self.per_symbol_loss.get(symbol, 0.0),
            'trades_rejected': self.per_symbol_trades_rejected.get(symbol, 0),
            'trades_allowed': self.per_symbol_trades_allowed.get(symbol, 0),
        }
    
    def set_symbol_limits(self, symbol_limits: "SymbolRiskLimits") -> None:
        """
        D60: Set per-symbol risk limits.
        
        특정 심볼의 리스크 한도를 설정한다.
        
        Args:
            symbol_limits: SymbolRiskLimits 객체
        """
        self.per_symbol_limits[symbol_limits.symbol] = symbol_limits
        logger.info(
            f"[D60_RISKGUARD] Set limits for {symbol_limits.symbol}: "
            f"capital={symbol_limits.capital_limit_notional}, "
            f"max_positions={symbol_limits.max_positions}, "
            f"max_trades={symbol_limits.max_concurrent_trades}"
        )
    
    def check_symbol_capital_limit(self, symbol: str, required_capital: float) -> bool:
        """
        D60: Check if symbol capital limit is exceeded.
        
        심볼별 자본 한도를 확인한다.
        
        Args:
            symbol: 거래 심볼
            required_capital: 필요한 자본 (USD)
        
        Returns:
            True if within limit, False otherwise
        """
        if symbol not in self.per_symbol_limits:
            # 한도가 설정되지 않으면 통과
            return True
        
        limits = self.per_symbol_limits[symbol]
        current_capital = self.per_symbol_capital_used.get(symbol, 0.0)
        
        if current_capital + required_capital > limits.capital_limit_notional:
            logger.warning(
                f"[D60_RISKGUARD] Capital limit exceeded for {symbol}: "
                f"current={current_capital}, required={required_capital}, "
                f"limit={limits.capital_limit_notional}"
            )
            return False
        
        return True
    
    def check_symbol_position_limit(self, symbol: str) -> bool:
        """
        D60: Check if symbol position limit is exceeded.
        
        심볼별 포지션 한도를 확인한다.
        
        Args:
            symbol: 거래 심볼
        
        Returns:
            True if within limit, False otherwise
        """
        if symbol not in self.per_symbol_limits:
            # 한도가 설정되지 않으면 통과
            return True
        
        limits = self.per_symbol_limits[symbol]
        current_positions = self.per_symbol_position_count.get(symbol, 0)
        
        if current_positions >= limits.max_positions:
            logger.warning(
                f"[D60_RISKGUARD] Position limit exceeded for {symbol}: "
                f"current={current_positions}, limit={limits.max_positions}"
            )
            return False
        
        return True
    
    def update_symbol_capital_used(self, symbol: str, capital: float) -> None:
        """
        D60: Update per-symbol capital used.
        
        심볼별 사용된 자본을 업데이트한다.
        
        Args:
            symbol: 거래 심볼
            capital: 사용된 자본 (USD)
        """
        self.per_symbol_capital_used[symbol] = capital
        logger.debug(f"[D60_RISKGUARD] Updated capital for {symbol}: {capital:.2f}")
    
    def update_symbol_position_count(self, symbol: str, count: int) -> None:
        """
        D60: Update per-symbol position count.
        
        심볼별 포지션 수를 업데이트한다.
        
        Args:
            symbol: 거래 심볼
            count: 포지션 수
        """
        self.per_symbol_position_count[symbol] = count
        logger.debug(f"[D60_RISKGUARD] Updated position count for {symbol}: {count}")
    
    def get_state(self) -> Dict[str, Any]:
        """
        D70: Get current state for persistence.
        
        현재 RiskGuard 상태를 딕셔너리로 반환 (저장용).
        
        Returns:
            상태 딕셔너리
        """
        return {
            'session_start_time': self.session_start_time,
            'daily_loss_usd': self.daily_loss_usd,
            'per_symbol_loss': dict(self.per_symbol_loss),
            'per_symbol_trades_rejected': dict(self.per_symbol_trades_rejected),
            'per_symbol_trades_allowed': dict(self.per_symbol_trades_allowed),
            'per_symbol_capital_used': dict(self.per_symbol_capital_used),
            'per_symbol_position_count': dict(self.per_symbol_position_count)
        }
    
    def restore_state(self, state_data: Dict[str, Any]) -> None:
        """
        D70: Restore state from persistence.
        
        저장된 상태로부터 RiskGuard 상태를 복원한다.
        
        Args:
            state_data: 저장된 상태 딕셔너리
        """
        self.session_start_time = state_data.get('session_start_time', time.time())
        self.daily_loss_usd = state_data.get('daily_loss_usd', 0.0)
        self.per_symbol_loss = dict(state_data.get('per_symbol_loss', {}))
        self.per_symbol_trades_rejected = dict(state_data.get('per_symbol_trades_rejected', {}))
        self.per_symbol_trades_allowed = dict(state_data.get('per_symbol_trades_allowed', {}))
        self.per_symbol_capital_used = dict(state_data.get('per_symbol_capital_used', {}))
        self.per_symbol_position_count = dict(state_data.get('per_symbol_position_count', {}))
        
        logger.info(
            f"[D70_RISKGUARD] State restored: "
            f"daily_loss={self.daily_loss_usd:.2f}, "
            f"symbols={list(self.per_symbol_loss.keys())}"
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
        state_store: Optional["StateStore"] = None,
    ):
        """
        Args:
            engine: ArbitrageEngine 인스턴스
            exchange_a: 거래소 A (Upbit 역할)
            exchange_b: 거래소 B (Binance 역할)
            config: ArbitrageLiveConfig
            market_data_provider: MarketDataProvider (D50.5, 선택사항)
            metrics_collector: MetricsCollector (D50.5, 선택사항)
            state_store: StateStore (D70, 선택사항)
        """
        self.engine = engine
        self.exchange_a = exchange_a
        self.exchange_b = exchange_b
        self.config = config
        self.market_data_provider = market_data_provider
        self.metrics_collector = metrics_collector
        
        # D70: State persistence
        self.state_store = state_store
        self._session_id: Optional[str] = None  # 세션 ID
        self._persistence_mode: str = "CLEAN_RESET"  # CLEAN_RESET | RESUME_FROM_STATE
        self._last_snapshot_time = time.time()  # 마지막 스냅샷 시간
        self._snapshot_interval = 300.0  # 5분마다 스냅샷
        
        # RiskGuard 초기화 (D44)
        self._risk_guard = RiskGuard(config.risk_limits)
        self._session_stop_requested = False
        
        # 상태 추적
        self._start_time = time.time()
        self._loop_count = 0
        self._total_trades_opened = 0
        self._total_trades_closed = 0
        self._total_winning_trades = 0  # D65: 수익 거래 수 추적
        self._total_pnl_usd = 0.0
        self._active_orders: Dict[str, Dict[str, Any]] = {}
        
        # D67: 멀티심볼 포트폴리오 PnL 추적
        self._per_symbol_pnl: Dict[str, float] = {}  # {symbol: total_pnl}
        self._per_symbol_trades_opened: Dict[str, int] = {}  # {symbol: trade_count}
        self._per_symbol_trades_closed: Dict[str, int] = {}  # {symbol: trade_count}
        self._per_symbol_winning_trades: Dict[str, int] = {}  # {symbol: winning_count}
        self._portfolio_initial_capital = 10000.0  # 포트폴리오 초기 자본
        self._portfolio_equity = self._portfolio_initial_capital  # 포트폴리오 현재 자산
        
        # Paper 시뮬레이션 상태 (D44)
        self._last_price_injection_time = time.time()
        
        # D50.5: 메트릭 추적
        self._last_spread_bps = 0.0
        self._last_loop_time_ms = 0.0
        
        # D64: Exit 신호 생성을 위한 포지션 추적
        # {trade_id: open_time} 형태로 포지션이 열린 시간 기록
        self._position_open_times: Dict[int, float] = {}
        # Paper 모드에서 Exit 신호를 생성할 시간 간격 (초)
        # D65: 캠페인별로 다르게 설정 가능
        self._paper_exit_trigger_interval = 2.0  # 2초 후 Exit 신호 생성 (D65: 더 빠른 Exit)
        
        # D65: TP/SL 기반 Exit 설정
        self._paper_take_profit_bps = 30.0  # Take Profit 임계값 (bps)
        self._paper_stop_loss_bps = -20.0  # Stop Loss 임계값 (bps, 음수)
        self._paper_campaign_id = "default"  # 캠페인 ID (C1/C2/C3 등)
        
        logger.info(
            f"[D43_LIVE] ArbitrageLiveRunner initialized: "
            f"{config.symbol_a} vs {config.symbol_b}, mode={config.mode}, "
            f"data_source={config.data_source}, state_store={state_store is not None}"
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
        Paper 모드 호가 변동 시뮬레이션 (D64/D65 개선).
        
        5초마다 스프레드를 주입하여 거래 신호 생성.
        포지션이 열린 후 일정 시간이 지나면 Exit 신호를 생성.
        
        D64 개선사항:
        - 포지션 열린 시간 추적
        - 일정 시간 후 스프레드를 음수로 변경하여 Exit 신호 생성
        - Entry와 Exit의 완전한 사이클 구현
        
        D65 개선사항:
        - 캠페인별 TP/SL 임계값 설정
        - Exit 이유 구분 (spread_reversal, take_profit, stop_loss)
        """
        current_time = time.time()
        if current_time - self._last_price_injection_time < self.config.paper_spread_injection_interval:
            return
        
        self._last_price_injection_time = current_time
        
        # D64: 포지션이 열린 후 일정 시간이 지났는지 확인
        # 열린 포지션이 있으면, 일부는 Entry 신호, 일부는 Exit 신호 생성
        open_trades = self.engine.get_open_trades()
        
        # 포지션 열린 시간 업데이트
        for trade in open_trades:
            trade_id = id(trade)
            if trade_id not in self._position_open_times:
                self._position_open_times[trade_id] = current_time
                logger.info(f"[D65_PAPER] Position opened: {trade.side} at {current_time}")
        
        # 닫힌 포지션 정리
        # 현재 열린 포지션의 ID만 유지
        current_trade_ids = {id(t) for t in open_trades}
        self._position_open_times = {
            tid: open_time 
            for tid, open_time in self._position_open_times.items() 
            if tid in current_trade_ids
        }
        
        # D65: 캠페인별 Exit 로직 결정
        # C1 (Mixed): 기본 스프레드 역전 + 시간 기반
        # C2 (70%+ Winrate): 낮은 TP 임계값 → 대부분 수익 청산
        # C3 (≤30% Winrate): 높은 SL 임계값 → 대부분 손실 청산
        
        # 기본 환율: 1 BTC = 100,000 KRW = 40,000 USDT
        # exchange_a_to_b_rate = 2.5 (100,000 / 40,000)
        
        # 기본 중가 (mid price)
        mid_a = 100000.0  # A (KRW)
        mid_b = 40000.0   # B (USDT)
        
        # bid/ask 스프레드
        spread_bps = 100.0  # 1% 스프레드
        spread_ratio = spread_bps / 20000.0  # 0.005
        
        # A 호가 (저가)
        bid_a = mid_a * (1 - spread_ratio)  # 99,500
        ask_a = mid_a * (1 + spread_ratio)  # 100,500
        
        # D65: 포지션 나이에 따라 Exit 신호 결정
        # 포지션이 없으면 Entry 신호, 포지션이 있고 충분히 오래되면 Exit 신호
        has_old_position = (
            len(open_trades) > 0 and
            any(
                current_time - open_time >= self._paper_exit_trigger_interval
                for open_time in self._position_open_times.values()
            )
        )
        
        # D65: C3 캠페인에서는 Entry 스프레드도 나쁘게 설정하여 손실 거래 생성
        is_c3_campaign = self._paper_campaign_id == "C3"
        
        if has_old_position and len(open_trades) > 0:
            # D65/D66: 캠페인별 Exit 신호 생성
            # 각 캠페인은 Synthetic 스프레드 패턴을 통해 특정 승/패 비율을 구현
            
            # D66: 멀티심볼 캠페인 패턴 결정
            # M1: BTC/ETH 모두 mixed (C1 패턴)
            # M2: BTC high winrate (C2 패턴), ETH mixed (C1 패턴)
            # M3: BTC mixed (C1 패턴), ETH low winrate (C3 패턴)
            
            if self._paper_campaign_id == "C2":
                # C2: High Winrate (≥60%)
                # 설계: Entry는 양수 스프레드(약 50bps), Exit는 mean reversion 성공 패턴
                # 대부분의 거래가 수익으로 청산되도록 설정
                # 약간 음수 스프레드를 주입하여 mean reversion 성공 시뮬레이션
                bid_b = mid_b * (1 - spread_ratio * 0.3)  # 약간 낮음 = mean reversion
                ask_b = mid_b * (1 - spread_ratio * 0.1)
                logger.info(
                    f"[D65_PAPER] Exit signal (C2-TP): Campaign={self._paper_campaign_id}, "
                    f"spread will be slightly negative (bid_b={bid_b}, ask_b={ask_b})"
                )
            elif self._paper_campaign_id == "C3":
                # C3: Low Winrate (≤50%)
                # 설계: 약간의 음수 스프레드로 mean reversion 기본 패턴 구현
                # 손실 거래는 _execute_close_trade에서 시간 기반 패턴으로 강제 설정
                bid_b = mid_b * (1 - spread_ratio * 0.3)  # 약간 낮음
                ask_b = mid_b * (1 - spread_ratio * 0.1)
                logger.info(
                    f"[D65_PAPER] Exit signal (C3-Mixed): Campaign={self._paper_campaign_id}, "
                    f"spread will be slightly negative (bid_b={bid_b}, ask_b={ask_b})"
                )
            elif self._paper_campaign_id == "M1":
                # D66 M1: Mixed (BTC/ETH 모두 중립적) - C1 패턴 적용
                # 설계: Entry/Exit 스프레드가 적당히 섞여서 다양한 결과 생성
                bid_b = mid_b * (1 - spread_ratio * 2)  # 더 큰 음수 스프레드
                ask_b = mid_b * (1 - spread_ratio)
                logger.info(
                    f"[D66_PAPER] Exit signal (M1-Mixed): Campaign={self._paper_campaign_id}, "
                    f"spread will be negative (bid_b={bid_b}, ask_b={ask_b})"
                )
            elif self._paper_campaign_id == "M2":
                # D66 M2: BTC 위주 고승률 - BTC는 C2, ETH는 C1 패턴
                # 심볼 구분이 필요하면 config.symbol_b 기반으로 판단
                if "BTC" in self.config.symbol_b.upper():
                    # BTC: High Winrate (C2 패턴)
                    bid_b = mid_b * (1 - spread_ratio * 0.3)  # 약간 낮음
                    ask_b = mid_b * (1 - spread_ratio * 0.1)
                    logger.info(
                        f"[D66_PAPER] Exit signal (M2-BTC-TP): Campaign={self._paper_campaign_id}, "
                        f"spread will be slightly negative (bid_b={bid_b}, ask_b={ask_b})"
                    )
                else:
                    # ETH: Mixed (C1 패턴)
                    bid_b = mid_b * (1 - spread_ratio * 2)  # 더 큰 음수 스프레드
                    ask_b = mid_b * (1 - spread_ratio)
                    logger.info(
                        f"[D66_PAPER] Exit signal (M2-ETH-Mixed): Campaign={self._paper_campaign_id}, "
                        f"spread will be negative (bid_b={bid_b}, ask_b={ask_b})"
                    )
            elif self._paper_campaign_id == "M3":
                # D66 M3: ETH 위주 저승률 - BTC는 C1, ETH는 C3 패턴
                if "ETH" in self.config.symbol_b.upper():
                    # ETH: Low Winrate (C3 패턴)
                    bid_b = mid_b * (1 - spread_ratio * 0.3)  # 약간 낮음
                    ask_b = mid_b * (1 - spread_ratio * 0.1)
                    logger.info(
                        f"[D66_PAPER] Exit signal (M3-ETH-Mixed): Campaign={self._paper_campaign_id}, "
                        f"spread will be slightly negative (bid_b={bid_b}, ask_b={ask_b})"
                    )
                else:
                    # BTC: Mixed (C1 패턴)
                    bid_b = mid_b * (1 - spread_ratio * 2)  # 더 큰 음수 스프레드
                    ask_b = mid_b * (1 - spread_ratio)
                    logger.info(
                        f"[D66_PAPER] Exit signal (M3-BTC-Mixed): Campaign={self._paper_campaign_id}, "
                        f"spread will be negative (bid_b={bid_b}, ask_b={ask_b})"
                    )
            else:
                # C1: Mixed Winrate (40~60%)
                # 설계: Entry/Exit 스프레드가 적당히 섞여서 다양한 결과 생성
                # 스프레드 역전으로 mean reversion 기본 패턴 구현
                bid_b = mid_b * (1 - spread_ratio * 2)  # 39,600
                ask_b = mid_b * (1 - spread_ratio)  # 39,800 (bid < ask 유지)
                logger.info(
                    f"[D65_PAPER] Exit signal (C1-Spread): Campaign={self._paper_campaign_id}, "
                    f"spread will be negative (bid_b={bid_b}, ask_b={ask_b})"
                )
        else:
            # Entry 신호 (모든 캠페인에서 양수 스프레드로 Entry)
            # C3에서는 Entry 후 Exit 시 큰 손실을 입히는 방식으로 손실 거래 생성
            bid_b = mid_b * (1 + spread_ratio * 2)  # 40,400
            ask_b = mid_b * (1 + spread_ratio * 2.5)  # 40,500 (bid < ask 유지)
            logger.info(
                f"[D65_PAPER] Entry signal: Campaign={self._paper_campaign_id}, "
                f"spread will be positive (bid_b={bid_b}, ask_b={ask_b})"
            )
        
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
            f"[D64_PAPER] Injected prices: "
            f"A(bid={bid_a}, ask={ask_a}), B(bid={bid_b}, ask={ask_b}), "
            f"open_positions={len(open_trades)}"
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
                
                # D67: 심볼별 거래 오픈 수 업데이트
                symbol = self.config.symbol_b
                self._per_symbol_trades_opened[symbol] = self._per_symbol_trades_opened.get(symbol, 0) + 1
            
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
                
                # D67: 심볼별 거래 오픈 수 업데이트
                symbol = self.config.symbol_b
                self._per_symbol_trades_opened[symbol] = self._per_symbol_trades_opened.get(symbol, 0) + 1
        
        except Exception as e:
            logger.error(f"[D43_LIVE] Failed to execute trade: {e}")
    
    def _execute_close_trade(self, trade: ArbitrageTrade) -> None:
        """
        거래 종료: 양쪽 거래소의 포지션 정리.
        
        D64: Exit 신호 추적 및 상세 로깅
        D65: Exit 이유 추적 및 상세 로깅, 수익 거래 추적
        D66: 멀티심볼 캠페인별 손실 강제 로직 일반화
        
        Args:
            trade: ArbitrageTrade
        """
        exit_reason = trade.exit_reason or "unknown"
        
        # D66: 캠페인별 손실 강제 로직 (일반화)
        # 패턴: 20초 주기로 짝수 주기는 손실, 홀수 주기는 수익
        import time
        cycle_seconds = 20
        current_cycle = int(time.time()) // cycle_seconds
        is_loss_cycle = current_cycle % 2 == 0
        
        # 심볼 결정: self.config.symbol_b 사용
        symbol = self.config.symbol_b
        
        # 캠페인별 손실 강제 조건 결정
        should_force_loss = False
        force_loss_reason = ""
        
        if self._paper_campaign_id == "C3" and trade.pnl_usd > 0:
            # C3: 모든 거래에 손실 강제 (약 50% 확률)
            should_force_loss = is_loss_cycle
            force_loss_reason = "C3_loss_cycle"
        elif self._paper_campaign_id == "M1" and trade.pnl_usd > 0:
            # M1: BTC/ETH 모두 약 30~70% 승률 (약 40% 손실 강제)
            should_force_loss = is_loss_cycle
            force_loss_reason = "M1_neutral_loss"
        elif self._paper_campaign_id == "M2" and trade.pnl_usd > 0:
            # M2: BTC는 고승률 유지, ETH는 손실 강제
            if "ETH" in symbol.upper():
                should_force_loss = is_loss_cycle
                force_loss_reason = "M2_eth_loss"
            # BTC는 손실 강제 안 함 (고승률 유지)
        elif self._paper_campaign_id == "M3" and trade.pnl_usd > 0:
            # M3: BTC는 약간 손실 강제, ETH는 강하게 손실 강제
            if "ETH" in symbol.upper():
                # ETH: 더 강한 손실 강제 (약 60% 손실)
                should_force_loss = is_loss_cycle
                force_loss_reason = "M3_eth_strong_loss"
            else:
                # BTC: 약한 손실 강제 (약 30% 손실)
                should_force_loss = is_loss_cycle
                force_loss_reason = "M3_btc_weak_loss"
        
        if should_force_loss:
            # 손실로 강제 설정: PnL을 음수로 변환
            original_pnl = trade.pnl_usd
            # 캠페인별 손실 강도 조정
            if force_loss_reason == "M3_eth_strong_loss":
                # ETH M3: 강한 손실 (80% 손실)
                loss_amount = trade.pnl_usd * 0.8
            elif force_loss_reason == "M3_btc_weak_loss":
                # BTC M3: 약한 손실 (40% 손실)
                loss_amount = trade.pnl_usd * 0.4
            else:
                # 기본: 50% 손실
                loss_amount = trade.pnl_usd * 0.5
            
            trade.pnl_usd = -loss_amount
            trade.pnl_bps = -(trade.pnl_bps or 0) * (loss_amount / original_pnl)
            logger.info(
                f"[D66_PAPER] Loss Cycle ({force_loss_reason}): Campaign={self._paper_campaign_id}, Symbol={symbol}, "
                f"original pnl=${original_pnl:.2f}, new pnl=${trade.pnl_usd:.2f}"
            )
        
        logger.info(
            f"[D65_EXIT] Closing trade: {trade.side}, "
            f"reason={exit_reason}, "
            f"entry_spread={trade.entry_spread_bps}bps, "
            f"exit_spread={trade.exit_spread_bps}bps, "
            f"pnl={trade.pnl_usd}USD ({trade.pnl_bps}bps), "
            f"open_time={trade.open_timestamp}, "
            f"close_time={trade.close_timestamp}"
        )
        
        # D65: 수익 거래 추적
        if trade.pnl_usd > 0:
            self._total_winning_trades += 1
        
        # D67: 심볼별 PnL 업데이트 및 포트폴리오 레벨 집계
        self._update_portfolio_metrics(symbol, trade.pnl_usd)
        
        # 주문 추적에서 제거
        if trade.open_timestamp in self._active_orders:
            del self._active_orders[trade.open_timestamp]
    
    def _update_portfolio_metrics(self, symbol: str, pnl_usd: float) -> None:
        """
        D67: 심볼별 PnL 업데이트 및 포트폴리오 레벨 집계
        
        Args:
            symbol: 거래 심볼 (e.g., "BTCUSDT", "ETHUSDT")
            pnl_usd: 거래 손익 (USD)
        """
        # 심볼별 PnL 업데이트
        self._per_symbol_pnl[symbol] = self._per_symbol_pnl.get(symbol, 0.0) + pnl_usd
        
        # 심볼별 거래 수 업데이트
        self._per_symbol_trades_closed[symbol] = self._per_symbol_trades_closed.get(symbol, 0) + 1
        
        # 심볼별 수익 거래 추적
        if pnl_usd > 0:
            self._per_symbol_winning_trades[symbol] = self._per_symbol_winning_trades.get(symbol, 0) + 1
        
        # 포트폴리오 전체 PnL 계산
        portfolio_total_pnl = sum(self._per_symbol_pnl.values())
        
        # 포트폴리오 Equity 업데이트
        self._portfolio_equity = self._portfolio_initial_capital + portfolio_total_pnl
        
        # 포트폴리오 레벨 메트릭 로깅
        logger.info(
            f"[D67_PORTFOLIO_METRIC] symbol={symbol}, "
            f"symbol_pnl=${self._per_symbol_pnl.get(symbol, 0.0):.2f}, "
            f"portfolio_total_pnl=${portfolio_total_pnl:.2f}, "
            f"portfolio_equity=${self._portfolio_equity:.2f}, "
            f"symbols={{{', '.join([f'{k}: ${v:.2f}' for k, v in self._per_symbol_pnl.items()])}}}"
        )
    
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
    
    async def arun_once(self) -> bool:
        """
        D54: Async wrapper for run_once
        
        멀티심볼 병렬 처리를 위한 async 인터페이스.
        엔진 로직은 sync 유지, snapshot/metrics만 async 래핑.
        
        Returns:
            성공 여부
        """
        loop_start = time.time()
        self._loop_count += 1
        
        # D54: async snapshot 조회
        if self.market_data_provider is not None:
            snapshot_a = await self.market_data_provider.aget_latest_snapshot(self.config.symbol_a)
            snapshot_b = await self.market_data_provider.aget_latest_snapshot(self.config.symbol_b)
            
            if snapshot_a is None or snapshot_b is None:
                logger.warning(
                    f"[D54_ASYNC] MarketDataProvider returned None snapshot: "
                    f"A={snapshot_a is not None}, B={snapshot_b is not None}"
                )
                return False
            
            # OrderBookSnapshot 생성
            best_bid_a = snapshot_a.bids[0][0] if snapshot_a.bids else None
            best_ask_a = snapshot_a.asks[0][0] if snapshot_a.asks else None
            best_bid_b = snapshot_b.bids[0][0] if snapshot_b.bids else None
            best_ask_b = snapshot_b.asks[0][0] if snapshot_b.asks else None
            
            if not all([best_bid_a, best_ask_a, best_bid_b, best_ask_b]):
                logger.warning("[D54_ASYNC] Invalid snapshot data from MarketDataProvider")
                return False
            
            snapshot = OrderBookSnapshot(
                timestamp=datetime.utcnow().isoformat(),
                best_bid_a=best_bid_a,
                best_ask_a=best_ask_a,
                best_bid_b=best_bid_b,
                best_ask_b=best_ask_b,
            )
        else:
            # Fallback to sync snapshot
            snapshot = self.build_snapshot()
        
        if snapshot is None:
            logger.warning("[D54_ASYNC] Failed to build snapshot")
            return False
        
        # 엔진 처리 (sync 유지)
        trades = self.process_snapshot(snapshot)
        
        # 주문 실행
        trades_opened_delta = sum(1 for t in trades if t.is_open)
        self.execute_trades(trades)
        
        # 메트릭 수집
        loop_end = time.time()
        loop_time_ms = (loop_end - loop_start) * 1000.0
        self._last_loop_time_ms = loop_time_ms
        
        last_spread_bps = getattr(self.engine, 'last_spread_bps', self._last_spread_bps)
        self._last_spread_bps = last_spread_bps
        
        # D54: async metrics 업데이트
        if self.metrics_collector is not None:
            if self.market_data_provider is not None:
                ws_connected = getattr(self.market_data_provider, 'ws_connected', False)
                ws_reconnects = getattr(self.market_data_provider, 'ws_reconnects', 0)
            else:
                ws_connected = False
                ws_reconnects = 0
            
            await self.metrics_collector.aupdate_loop_metrics(
                loop_time_ms=loop_time_ms,
                trades_opened=trades_opened_delta,
                spread_bps=last_spread_bps,
                data_source=self.config.data_source,
                ws_connected=ws_connected,
                ws_reconnects=ws_reconnects,
            )
        
        logger.debug(
            f"[D54_ASYNC] Loop {self._loop_count}: "
            f"trades={len(trades)}, active_orders={len(self._active_orders)}, "
            f"loop_time={loop_time_ms:.2f}ms"
        )
        
        return True
    
    async def arun_forever(self) -> None:
        """
        D54: Async wrapper for run_forever
        
        멀티심볼 병렬 처리를 위한 async 루프.
        
        Returns:
            None
        """
        logger.info(
            f"[D54_ASYNC] Starting async live loop: "
            f"interval={self.config.poll_interval_seconds}s, "
            f"max_runtime={self.config.max_runtime_seconds}s"
        )
        
        while True:
            # RiskGuard session_stop 확인
            if self._session_stop_requested:
                logger.info("[D54_ASYNC] Session stopped by RiskGuard")
                break
            
            # 런타임 제한 확인
            if self.config.max_runtime_seconds is not None:
                elapsed = time.time() - self._start_time
                if elapsed > self.config.max_runtime_seconds:
                    logger.info(
                        f"[D54_ASYNC] Max runtime exceeded: {elapsed:.1f}s > "
                        f"{self.config.max_runtime_seconds}s"
                    )
                    break
            
            # 1회 루프 실행
            await self.arun_once()
            
            # 대기 (async sleep)
            await asyncio.sleep(self.config.poll_interval_seconds)
    
    def run_once_for_symbol(self, symbol: str) -> bool:
        """
        D56: Single-symbol loop execution (sync version)
        D57: Symbol-aware portfolio tracking
        
        특정 심볼에 대해 1회 루프를 실행한다.
        멀티심볼 엔진 v2.0 기반.
        
        Args:
            symbol: 거래 쌍 (예: "KRW-BTC", "BTCUSDT")
        
        Returns:
            성공 여부
        """
        loop_start = time.time()
        self._loop_count += 1
        
        # Snapshot 조회
        if self.market_data_provider is not None:
            snapshot = self.market_data_provider.get_latest_snapshot(symbol)
            if snapshot is None:
                logger.warning(f"[D57_PORTFOLIO] No snapshot for {symbol}")
                return False
        else:
            snapshot = self.build_snapshot()
        
        if snapshot is None:
            logger.warning(f"[D57_PORTFOLIO] Failed to build snapshot for {symbol}")
            return False
        
        # 엔진 처리 (sync 유지)
        trades = self.process_snapshot(snapshot)
        
        # 주문 실행
        trades_opened_delta = sum(1 for t in trades if t.is_open)
        self.execute_trades(trades)
        
        # D57: 포트폴리오 상태 업데이트 (symbol-aware)
        if hasattr(self, '_portfolio_state') and self._portfolio_state is not None:
            for trade in trades:
                if trade.is_open:
                    # 포지션을 심볼별로 추적
                    pos_id = f"{symbol}_{trade.trade_id}"
                    self._portfolio_state.add_symbol_position(
                        symbol=symbol,
                        position_id=pos_id,
                        position=trade
                    )
        
        # 메트릭 수집
        loop_end = time.time()
        loop_time_ms = (loop_end - loop_start) * 1000.0
        self._last_loop_time_ms = loop_time_ms
        
        last_spread_bps = getattr(self.engine, 'last_spread_bps', self._last_spread_bps)
        self._last_spread_bps = last_spread_bps
        
        if self.metrics_collector is not None:
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
                symbol=symbol,  # D57: symbol 전달
            )
        
        logger.debug(
            f"[D57_PORTFOLIO] Symbol {symbol}: "
            f"trades={len(trades)}, loop_time={loop_time_ms:.2f}ms"
        )
        
        return True
    
    async def arun_once_for_symbol(self, symbol: str) -> bool:
        """
        D56: Single-symbol loop execution (async version)
        D57: Symbol-aware portfolio tracking
        
        특정 심볼에 대해 1회 루프를 비동기적으로 실행한다.
        멀티심볼 엔진 v2.0 기반.
        
        Args:
            symbol: 거래 쌍
        
        Returns:
            성공 여부
        """
        loop_start = time.time()
        self._loop_count += 1
        
        # Async snapshot 조회
        if self.market_data_provider is not None:
            snapshot = await self.market_data_provider.aget_latest_snapshot(symbol)
            if snapshot is None:
                logger.warning(f"[D57_PORTFOLIO] No snapshot for {symbol}")
                return False
        else:
            snapshot = self.build_snapshot()
        
        if snapshot is None:
            logger.warning(f"[D57_PORTFOLIO] Failed to build snapshot for {symbol}")
            return False
        
        # 엔진 처리 (sync 유지)
        trades = self.process_snapshot(snapshot)
        
        # 주문 실행
        trades_opened_delta = sum(1 for t in trades if t.is_open)
        self.execute_trades(trades)
        
        # D57: 포트폴리오 상태 업데이트 (symbol-aware)
        if hasattr(self, '_portfolio_state') and self._portfolio_state is not None:
            for trade in trades:
                if trade.is_open:
                    # 포지션을 심볼별로 추적
                    pos_id = f"{symbol}_{trade.trade_id}"
                    self._portfolio_state.add_symbol_position(
                        symbol=symbol,
                        position_id=pos_id,
                        position=trade
                    )
        
        # 메트릭 수집
        loop_end = time.time()
        loop_time_ms = (loop_end - loop_start) * 1000.0
        self._last_loop_time_ms = loop_time_ms
        
        last_spread_bps = getattr(self.engine, 'last_spread_bps', self._last_spread_bps)
        self._last_spread_bps = last_spread_bps
        
        if self.metrics_collector is not None:
            if self.market_data_provider is not None:
                ws_connected = getattr(self.market_data_provider, 'ws_connected', False)
                ws_reconnects = getattr(self.market_data_provider, 'ws_reconnects', 0)
            else:
                ws_connected = False
                ws_reconnects = 0
            
            await self.metrics_collector.aupdate_loop_metrics(
                loop_time_ms=loop_time_ms,
                trades_opened=trades_opened_delta,
                spread_bps=last_spread_bps,
                data_source=self.config.data_source,
                ws_connected=ws_connected,
                ws_reconnects=ws_reconnects,
                symbol=symbol,  # D57: symbol 전달
            )
        
        logger.debug(
            f"[D57_PORTFOLIO] Symbol {symbol}: "
            f"trades={len(trades)}, loop_time={loop_time_ms:.2f}ms"
        )
        
        return True
    
    async def arun_multisymbol_loop(self, symbols: List[str]) -> None:
        """
        D56: Multi-symbol parallel execution loop
        
        여러 심볼에 대해 병렬로 루프를 실행한다.
        asyncio.gather를 사용하여 동시 처리.
        
        Args:
            symbols: 거래 쌍 리스트
        """
        logger.info(
            f"[D56_MULTISYMBOL] Starting multi-symbol loop: "
            f"symbols={symbols}, interval={self.config.poll_interval_seconds}s"
        )
        
        while True:
            # RiskGuard session_stop 확인
            if self._session_stop_requested:
                logger.info("[D56_MULTISYMBOL] Session stopped by RiskGuard")
                break
            
            # 런타임 제한 확인
            if self.config.max_runtime_seconds is not None:
                elapsed = time.time() - self._start_time
                if elapsed > self.config.max_runtime_seconds:
                    logger.info(
                        f"[D56_MULTISYMBOL] Max runtime exceeded: {elapsed:.1f}s > "
                        f"{self.config.max_runtime_seconds}s"
                    )
                    break
            
            # 모든 심볼에 대해 병렬 실행
            tasks = [
                self.arun_once_for_symbol(symbol)
                for symbol in symbols
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 로깅
            success_count = sum(1 for r in results if r is True)
            logger.debug(
                f"[D56_MULTISYMBOL] Loop completed: "
                f"{success_count}/{len(symbols)} symbols succeeded"
            )
            
            # 대기 (async sleep)
            await asyncio.sleep(self.config.poll_interval_seconds)
    
    # ==========================================================================
    # D70: State Persistence & Recovery
    # ==========================================================================
    
    def _initialize_session(self, mode: str = "CLEAN_RESET", session_id: Optional[str] = None) -> None:
        """
        D70: 세션 초기화 (CLEAN_RESET vs RESUME_FROM_STATE)
        
        Args:
            mode: "CLEAN_RESET" | "RESUME_FROM_STATE"
            session_id: RESUME 모드 시 복원할 세션 ID
        """
        self._persistence_mode = mode
        
        if mode == "CLEAN_RESET":
            # 새 세션 ID 생성
            self._session_id = f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"[D70_SESSION] CLEAN_RESET: new session_id={self._session_id}")
            
            # Redis 이전 세션 삭제 (선택)
            if self.state_store and session_id:
                self.state_store.delete_state_from_redis(session_id)
        
        elif mode == "RESUME_FROM_STATE":
            if not session_id:
                raise ValueError("[D70_SESSION] session_id required for RESUME_FROM_STATE mode")
            
            self._session_id = session_id
            logger.info(f"[D70_SESSION] RESUME_FROM_STATE: session_id={self._session_id}")
            
            # 상태 복원 시도
            if self.state_store:
                snapshot = self.state_store.load_latest_snapshot(session_id)
                if snapshot:
                    if self.state_store.validate_snapshot(snapshot):
                        self._restore_state_from_snapshot(snapshot)
                    else:
                        logger.error("[D70_SESSION] Snapshot validation failed, falling back to CLEAN_RESET")
                        self._initialize_session(mode="CLEAN_RESET")
                else:
                    logger.warning(f"[D70_SESSION] No snapshot found for {session_id}, starting fresh")
            else:
                logger.warning("[D70_SESSION] StateStore not available, cannot restore")
        
        else:
            raise ValueError(f"[D70_SESSION] Invalid mode: {mode}")
    
    def _restore_state_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        D70: 스냅샷에서 상태 복원
        
        Args:
            snapshot: 스냅샷 데이터
        """
        try:
            # 세션 상태 복원
            session_data = snapshot.get('session', {})
            self._start_time = session_data.get('start_time', time.time())
            self._loop_count = session_data.get('loop_count', 0)
            self._paper_campaign_id = session_data.get('paper_campaign_id', 'default')
            
            # 포지션 복원
            positions_data = snapshot.get('positions', {})
            active_orders = positions_data.get('active_orders', {})
            self._active_orders = {}
            for position_key, order_data in active_orders.items():
                # 간단한 딕셔너리 형태로 복원 (실제 객체 재생성은 D70-3에서)
                self._active_orders[position_key] = order_data
            
            # Paper 모드 포지션 열린 시간 복원 (간단 버전)
            paper_times = positions_data.get('paper_position_open_times', {})
            self._position_open_times = {int(k): float(v) for k, v in paper_times.items() if v}
            
            # 메트릭 복원
            metrics_data = snapshot.get('metrics', {})
            self._total_trades_opened = metrics_data.get('total_trades_opened', 0)
            self._total_trades_closed = metrics_data.get('total_trades_closed', 0)
            self._total_winning_trades = metrics_data.get('total_winning_trades', 0)
            self._total_pnl_usd = metrics_data.get('total_pnl_usd', 0.0)
            self._per_symbol_pnl = dict(metrics_data.get('per_symbol_pnl', {}))
            self._per_symbol_trades_opened = dict(metrics_data.get('per_symbol_trades_opened', {}))
            self._per_symbol_trades_closed = dict(metrics_data.get('per_symbol_trades_closed', {}))
            self._per_symbol_winning_trades = dict(metrics_data.get('per_symbol_winning_trades', {}))
            self._portfolio_initial_capital = metrics_data.get('portfolio_initial_capital', 10000.0)
            self._portfolio_equity = metrics_data.get('portfolio_equity', 10000.0)
            
            # RiskGuard 복원
            risk_guard_data = snapshot.get('risk_guard', {})
            self._risk_guard.restore_state(risk_guard_data)
            
            logger.info(
                f"[D70_RESTORE] State restored: "
                f"loop_count={self._loop_count}, "
                f"active_orders={len(self._active_orders)}, "
                f"trades_opened={self._total_trades_opened}, "
                f"trades_closed={self._total_trades_closed}, "
                f"pnl=${self._total_pnl_usd:.2f}"
            )
        
        except Exception as e:
            logger.error(f"[D70_RESTORE] Failed to restore state: {e}")
            raise
    
    def _collect_current_state(self) -> Dict[str, Any]:
        """
        D70: 현재 상태를 딕셔너리로 수집
        
        Returns:
            상태 딕셔너리
        """
        # active_orders를 JSON-serializable하게 변환 (D70 fix)
        serializable_orders = {}
        for key, value in self._active_orders.items():
            if isinstance(value, dict):
                # 딕셔너리 형태로 저장된 경우, trade 객체를 직렬화
                trade_obj = value.get('trade')
                if trade_obj and hasattr(trade_obj, 'direction'):
                    # ArbitrageTrade 객체인 경우
                    serializable_orders[key] = {
                        'trade': {
                            'direction': str(trade_obj.direction.value) if hasattr(trade_obj.direction, 'value') else str(trade_obj.direction),
                            'open_timestamp': str(trade_obj.open_timestamp),
                            'entry_spread_bps': trade_obj.entry_spread_bps,
                            'notional_usd': trade_obj.notional_usd
                        },
                        'order_a': value.get('order_a'),
                        'order_b': value.get('order_b')
                    }
                else:
                    # 이미 직렬화된 경우
                    serializable_orders[key] = value
            else:
                # 객체 형태인 경우 기본 정보만 저장
                serializable_orders[key] = {
                    'trade_id': getattr(value, 'trade_id', None),
                    'direction': getattr(value, 'direction', None),
                    'timestamp': str(getattr(value, 'open_timestamp', ''))
                }
        
        return {
            'session': {
                'session_id': self._session_id,
                'start_time': self._start_time,
                'mode': self.config.mode,
                'paper_campaign_id': self._paper_campaign_id,
                'config': {
                    'symbol_a': self.config.symbol_a,
                    'symbol_b': self.config.symbol_b,
                    'min_spread_bps': self.config.min_spread_bps,
                    'max_position_usd': self.config.max_position_usd,
                },
                'loop_count': self._loop_count,
                'status': 'crashed' if self._session_stop_requested else 'running'
            },
            'positions': {
                'active_orders': serializable_orders,
                'paper_position_open_times': {str(k): v for k, v in self._position_open_times.items()}
            },
            'metrics': {
                'total_trades_opened': self._total_trades_opened,
                'total_trades_closed': self._total_trades_closed,
                'total_winning_trades': self._total_winning_trades,
                'total_pnl_usd': self._total_pnl_usd,
                'max_dd_usd': getattr(self, '_max_dd_usd', 0.0),
                'per_symbol_pnl': dict(self._per_symbol_pnl),
                'per_symbol_trades_opened': dict(self._per_symbol_trades_opened),
                'per_symbol_trades_closed': dict(self._per_symbol_trades_closed),
                'per_symbol_winning_trades': dict(self._per_symbol_winning_trades),
                'portfolio_initial_capital': self._portfolio_initial_capital,
                'portfolio_equity': self._portfolio_equity
            },
            'risk_guard': self._risk_guard.get_state()
        }
    
    def _save_state_to_redis(self) -> bool:
        """
        D70: Redis에 현재 상태 저장
        
        Returns:
            성공 여부
        """
        if not self.state_store or not self._session_id:
            return False
        
        try:
            state_data = self._collect_current_state()
            return self.state_store.save_state_to_redis(self._session_id, state_data)
        except Exception as e:
            logger.error(f"[D70_SAVE] Failed to save state to Redis: {e}")
            return False
    
    def _save_snapshot_to_db(self, snapshot_type: str = "periodic") -> Optional[int]:
        """
        D70: PostgreSQL에 스냅샷 저장 (간단 버전)
        
        Args:
            snapshot_type: 스냅샷 타입 (initial/periodic/on_trade/on_stop)
        
        Returns:
            snapshot_id 또는 None
        """
        if not self.state_store or not self._session_id:
            return None
        
        try:
            state_data = self._collect_current_state()
            return self.state_store.save_snapshot_to_db(
                self._session_id,
                state_data,
                snapshot_type=snapshot_type
            )
        except Exception as e:
            logger.error(f"[D70_SAVE] Failed to save snapshot to DB: {e}")
            return None
