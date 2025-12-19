# -*- coding: utf-8 -*-
"""
D61: Multi-Symbol Paper Execution — Executor Base Classes

거래 실행 엔진의 추상 클래스 및 Paper Executor 구현.
D98-3: LiveExecutor ReadOnlyGuard 추가
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from arbitrage.types import (
    Order,
    OrderSide,
    OrderStatus,
    Position,
    PortfolioState,
)
from arbitrage.live_runner import RiskGuard
from arbitrage.execution.fill_model import (
    FillContext,
    FillResult,
    BaseFillModel,
    create_default_fill_model,
)
from arbitrage.config.readonly_guard import get_readonly_guard, ReadOnlyError

if TYPE_CHECKING:
    from arbitrage.arbitrage_core import ArbitrageTrade

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """거래 실행 결과"""
    symbol: str
    trade_id: str
    status: str  # "success", "failed", "partial"
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None
    buy_price: float = 0.0
    sell_price: float = 0.0
    quantity: float = 0.0
    pnl: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # D80-4: Fill Model 정보 (선택적)
    buy_slippage_bps: float = 0.0
    sell_slippage_bps: float = 0.0
    buy_fill_ratio: float = 1.0
    sell_fill_ratio: float = 1.0


class BaseExecutor(ABC):
    """
    D61: 거래 실행 엔진 추상 클래스
    
    책임:
    - 거래 실행 (매수/매도)
    - 포지션 관리
    - PnL 계산
    """
    
    def __init__(
        self,
        symbol: str,
        portfolio_state: PortfolioState,
        risk_guard: RiskGuard,
    ):
        """
        Args:
            symbol: 거래 심볼
            portfolio_state: 포트폴리오 상태
            risk_guard: 리스크 가드
        """
        self.symbol = symbol
        self.portfolio_state = portfolio_state
        self.risk_guard = risk_guard
        self.execution_count = 0
        self.total_pnl = 0.0
        
        logger.info(f"[D61_EXECUTOR] Initialized for {symbol}")
    
    @abstractmethod
    def execute_trades(self, trades: List) -> List[ExecutionResult]:
        """
        거래 실행
        
        Args:
            trades: 실행할 거래 목록 (ArbitrageTrade)
        
        Returns:
            실행 결과 목록
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """
        심볼별 포지션 조회
        
        Returns:
            포지션 딕셔너리
        """
        pass
    
    @abstractmethod
    def get_pnl(self) -> float:
        """
        심볼별 PnL 조회
        
        Returns:
            PnL (USD)
        """
        pass
    
    @abstractmethod
    def close_position(self, position_id: str) -> Optional[ExecutionResult]:
        """
        포지션 청산
        
        Args:
            position_id: 포지션 ID
        
        Returns:
            실행 결과 또는 None
        """
        pass


class PaperExecutor(BaseExecutor):
    """
    D61: Paper Executor (가상 거래)
    
    실제 주문 없이 가상으로 거래를 시뮬레이션한다.
    """
    
    def __init__(
        self,
        symbol: str,
        portfolio_state: PortfolioState,
        risk_guard: RiskGuard,
        enable_fill_model: bool = False,
        fill_model: Optional[BaseFillModel] = None,
        default_available_volume_factor: float = 2.0,
        market_data_provider = None,
        fill_event_collector = None,
    ):
        """
        Args:
            symbol: 거래 심볼
            portfolio_state: 포트폴리오 상태
            risk_guard: 리스크 가드
            enable_fill_model: Fill Model 활성화 여부 (D80-4)
            fill_model: 사용할 Fill Model 인스턴스 (None이면 기본 생성)
            default_available_volume_factor: 호가 잔량 추정 계수 (order_qty * factor)
            market_data_provider: L2 Orderbook Provider (D83-0, Optional)
            fill_event_collector: Fill Event Collector (D83-0.5, Optional)
        """
        super().__init__(symbol, portfolio_state, risk_guard)
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.pnl_history: List[Tuple[datetime, float]] = []
        
        # D80-4: Fill Model
        self.enable_fill_model = enable_fill_model
        self.default_available_volume_factor = default_available_volume_factor
        if enable_fill_model and fill_model is None:
            self.fill_model = create_default_fill_model()
        else:
            self.fill_model = fill_model
        
        # D83-0: L2 Orderbook Provider
        self.market_data_provider = market_data_provider
        
        # D83-0.5: Fill Event Collector
        self.fill_event_collector = fill_event_collector
        
        logger.info(
            f"[D61_PAPER_EXECUTOR] Initialized for {symbol} "
            f"(fill_model={enable_fill_model}, l2_provider={market_data_provider is not None}, "
            f"event_collector={fill_event_collector is not None})"
        )
    
    def execute_trades(self, trades: List) -> List[ExecutionResult]:
        """
        D61: 거래 실행 (Paper Mode)
        
        Args:
            trades: 실행할 거래 목록 (ArbitrageTrade)
        
        Returns:
            실행 결과 목록
        """
        results = []
        
        for trade in trades:
            # 1. 리스크 체크
            if not self.risk_guard.check_symbol_capital_limit(
                self.symbol, trade.notional_usd
            ):
                logger.warning(
                    f"[D61_PAPER_EXECUTOR] Trade rejected for {self.symbol}: "
                    f"capital limit exceeded"
                )
                results.append(
                    ExecutionResult(
                        symbol=self.symbol,
                        trade_id=trade.trade_id,
                        status="failed",
                    )
                )
                continue
            
            if not self.risk_guard.check_symbol_position_limit(self.symbol):
                logger.warning(
                    f"[D61_PAPER_EXECUTOR] Trade rejected for {self.symbol}: "
                    f"position limit exceeded"
                )
                results.append(
                    ExecutionResult(
                        symbol=self.symbol,
                        trade_id=trade.trade_id,
                        status="failed",
                    )
                )
                continue
            
            # 2. 거래 실행
            result = self._execute_single_trade(trade)
            results.append(result)
            
            # 3. 상태 업데이트
            if result.status == "success":
                self.execution_count += 1
                self.total_pnl += result.pnl
                
                # 포트폴리오 상태 업데이트
                self.portfolio_state.update_symbol_capital_used(
                    self.symbol,
                    self.portfolio_state.get_symbol_capital_used(self.symbol) + result.quantity * result.buy_price,
                )
                self.portfolio_state.update_symbol_position_count(
                    self.symbol,
                    len(self.positions),
                )
        
        return results
    
    def _execute_single_trade(self, trade) -> ExecutionResult:
        """
        단일 거래 실행
        
        D80-4: Fill Model 통합
        - enable_fill_model=False: 기존 동작 (100% 전량 체결, 슬리피지 0)
        - enable_fill_model=True: Partial Fill + Slippage 반영
        
        Args:
            trade: 거래 정보 (ArbitrageTrade)
        
        Returns:
            실행 결과
        """
        try:
            # D80-4: Fill Model 경로 분기
            if self.enable_fill_model and self.fill_model:
                return self._execute_single_trade_with_fill_model(trade)
            else:
                return self._execute_single_trade_legacy(trade)
        
        except Exception as e:
            logger.error(f"[D61_PAPER_EXECUTOR] Trade execution failed: {e}")
            return ExecutionResult(
                symbol=self.symbol,
                trade_id=trade.trade_id,
                status="failed",
            )
    
    def _execute_single_trade_legacy(self, trade) -> ExecutionResult:
        """
        기존 거래 실행 로직 (Fill Model 없음)
        
        D80-4 이전 동작 유지: 100% 전량 체결, 슬리피지 0
        """
        # 1. 매수 주문 생성
        buy_order_id = f"BUY_{self.symbol}_{self.execution_count}"
        buy_order = Order(
            order_id=buy_order_id,
            exchange=trade.buy_exchange,
            symbol=self.symbol,
            side=OrderSide.BUY,
            quantity=trade.quantity,
            price=trade.buy_price,
            status=OrderStatus.FILLED,
            filled_quantity=trade.quantity,
        )
        self.orders[buy_order_id] = buy_order
        
        # 2. 매도 주문 생성
        sell_order_id = f"SELL_{self.symbol}_{self.execution_count}"
        sell_order = Order(
            order_id=sell_order_id,
            exchange=trade.sell_exchange,
            symbol=self.symbol,
            side=OrderSide.SELL,
            quantity=trade.quantity,
            price=trade.sell_price,
            status=OrderStatus.FILLED,
            filled_quantity=trade.quantity,
        )
        self.orders[sell_order_id] = sell_order
        
        # 3. 포지션 생성
        position_id = f"POS_{self.symbol}_{self.execution_count}"
        position = Position(
            symbol=self.symbol,
            quantity=trade.quantity,
            entry_price=trade.buy_price,
            current_price=trade.sell_price,
            side=OrderSide.BUY,
            timestamp=datetime.utcnow(),
        )
        self.positions[position_id] = position
        
        # 4. PnL 계산
        pnl = (trade.sell_price - trade.buy_price) * trade.quantity
        
        # 5. 결과 반환
        result = ExecutionResult(
            symbol=self.symbol,
            trade_id=trade.trade_id,
            status="success",
            buy_order_id=buy_order_id,
            sell_order_id=sell_order_id,
            buy_price=trade.buy_price,
            sell_price=trade.sell_price,
            quantity=trade.quantity,
            pnl=pnl,
        )
        
        logger.info(
            f"[D61_PAPER_EXECUTOR] Trade executed for {self.symbol}: "
            f"qty={trade.quantity}, buy={trade.buy_price}, sell={trade.sell_price}, pnl={pnl:.2f}"
        )
        
        return result
    
    def _extract_volume_from_single_l2(
        self,
        snapshot,
        symbol: str,
        side: OrderSide,
        fallback_quantity: float,
    ) -> float:
        """
        D85-0: Single L2 Snapshot (OrderBookSnapshot)에서 available_volume 추출
        
        Args:
            snapshot: OrderBookSnapshot (.bids, .asks 속성 존재)
            symbol: 거래 심볼
            side: BUY or SELL
            fallback_quantity: Fallback 수량
        
        Returns:
            available_volume (best level volume)
        """
        # L2 Orderbook에서 available_volume 계산
        if side == OrderSide.BUY:
            # BUY: asks 사용 (매도 호가)
            levels = snapshot.asks
        else:
            # SELL: bids 사용 (매수 호가)
            levels = snapshot.bids
        
        if not levels:
            logger.warning(f"[D85-0_SINGLE_L2] Empty {side.value} levels for {symbol}, using fallback")
            return fallback_quantity * self.default_available_volume_factor
        
        # Best Level의 volume 반환
        best_price, best_volume = levels[0]
        
        logger.debug(
            f"[D85-0_SINGLE_L2] {symbol} {side.value} available_volume={best_volume:.6f} "
            f"(best_price={best_price:.2f})"
        )
        
        return best_volume
    
    def _extract_volume_from_multi_l2(
        self,
        snapshot,
        symbol: str,
        side: OrderSide,
        fallback_quantity: float,
    ) -> float:
        """
        D85-0: Multi L2 Snapshot (MultiExchangeL2Snapshot)에서 available_volume 추출
        
        v0 구현: Best exchange 1개 선택 → OrderBookSnapshot 추출 → volume 반환
        
        Args:
            snapshot: MultiExchangeL2Snapshot (.per_exchange, .best_bid_exchange, .best_ask_exchange)
            symbol: 거래 심볼
            side: BUY or SELL
            fallback_quantity: Fallback 수량
        
        Returns:
            available_volume (best exchange의 best level volume)
        """
        # Best exchange 선택
        if side == OrderSide.BUY:
            # BUY: 가장 낮은 ask를 제공하는 exchange
            best_exchange_id = snapshot.best_ask_exchange
        else:
            # SELL: 가장 높은 bid를 제공하는 exchange
            best_exchange_id = snapshot.best_bid_exchange
        
        if best_exchange_id is None:
            logger.warning(f"[D85-0_MULTI_L2] No best exchange for {symbol} {side.value}, using fallback")
            return fallback_quantity * self.default_available_volume_factor
        
        # Best exchange의 OrderBookSnapshot 추출
        exchange_snapshot = snapshot.per_exchange.get(best_exchange_id)
        if exchange_snapshot is None:
            logger.warning(
                f"[D85-0_MULTI_L2] No snapshot for best exchange {best_exchange_id.value}, using fallback"
            )
            return fallback_quantity * self.default_available_volume_factor
        
        # OrderBookSnapshot에서 volume 추출 (재사용)
        volume = self._extract_volume_from_single_l2(
            exchange_snapshot, symbol, side, fallback_quantity
        )
        
        logger.info(
            f"[D85-0_MULTI_L2] {symbol} {side.value} using {best_exchange_id.value} "
            f"available_volume={volume:.6f}"
        )
        
        return volume
    
    def _get_available_volume_from_orderbook(
        self,
        symbol: str,
        side: OrderSide,
        target_price: float,
        fallback_quantity: float,
    ) -> float:
        """
        D85-0: L2 Orderbook에서 available_volume 계산 (Multi L2 지원)
        
        L2 Orderbook의 Best Level (첫 번째 호가) volume을 반환한다.
        MultiExchangeL2Snapshot 및 OrderBookSnapshot 모두 지원.
        Orderbook이 없거나 Provider가 없으면 기존 fallback 로직 사용.
        
        Args:
            symbol: 거래 심볼
            side: BUY or SELL
            target_price: 목표 가격 (현재 미사용, D85-1+에서 활용)
            fallback_quantity: Orderbook 없을 시 fallback (기존 로직)
        
        Returns:
            available_volume (실제 L2 기반 값 또는 fallback)
        
        Notes:
            - D83-0: Single L2 (OrderBookSnapshot) 지원
            - D85-0: Multi L2 (MultiExchangeL2Snapshot) 지원 추가
            - D85-1+: Multi-level aggregation, cross-exchange order routing
        """
        # Provider 없으면 기존 fallback 로직
        if self.market_data_provider is None:
            return fallback_quantity * self.default_available_volume_factor
        
        # Orderbook snapshot 가져오기
        snapshot = self.market_data_provider.get_latest_snapshot(symbol)
        if snapshot is None:
            logger.warning(f"[D85-0_L2] No snapshot for {symbol}, using fallback")
            return fallback_quantity * self.default_available_volume_factor
        
        # D85-0: Type 체크 순서 중요 (Multi L2 우선 체크)
        # Type 1: MultiExchangeL2Snapshot (Multi L2: Upbit + Binance)
        if hasattr(snapshot, 'per_exchange'):
            logger.info(f"[D85-0_L2] Detected MultiExchangeL2Snapshot for {symbol}")
            return self._extract_volume_from_multi_l2(
                snapshot, symbol, side, fallback_quantity
            )
        
        # Type 2: OrderBookSnapshot (Single L2: Upbit/Binance)
        elif hasattr(snapshot, 'bids') and hasattr(snapshot, 'asks'):
            logger.debug(f"[D85-0_L2] Detected OrderBookSnapshot for {symbol}")
            return self._extract_volume_from_single_l2(
                snapshot, symbol, side, fallback_quantity
            )
        
        # Fallback: 알 수 없는 타입
        else:
            logger.warning(
                f"[D85-0_L2] Unknown snapshot type for {symbol}, using fallback. "
                f"Snapshot type: {type(snapshot).__name__}"
            )
            return fallback_quantity * self.default_available_volume_factor
    
    def _execute_single_trade_with_fill_model(self, trade) -> ExecutionResult:
        """
        D80-4: Fill Model 적용 거래 실행
        
        Partial Fill + Slippage 반영
        
        Args:
            trade: 거래 정보
        
        Returns:
            Fill Model 결과가 반영된 ExecutionResult
        """
        # D83-0: L2 Orderbook 기반 available_volume 계산
        buy_available_volume = self._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.BUY,
            target_price=trade.buy_price,
            fallback_quantity=trade.quantity,
        )
        
        sell_available_volume = self._get_available_volume_from_orderbook(
            symbol=self.symbol,
            side=OrderSide.SELL,
            target_price=trade.sell_price,
            fallback_quantity=trade.quantity,
        )
        
        # 1. 매수 Fill Model 실행
        buy_context = FillContext(
            symbol=self.symbol,
            side=OrderSide.BUY,
            order_quantity=trade.quantity,
            target_price=trade.buy_price,
            available_volume=buy_available_volume,
        )
        buy_fill_result = self.fill_model.execute(buy_context)
        
        # 2. 매도 Fill Model 실행 (매수 체결량만큼만)
        sell_context = FillContext(
            symbol=self.symbol,
            side=OrderSide.SELL,
            order_quantity=buy_fill_result.filled_quantity,
            target_price=trade.sell_price,
            available_volume=sell_available_volume,
        )
        sell_fill_result = self.fill_model.execute(sell_context)
        
        # 3. 실제 체결 수량 (매수/매도 중 작은 값)
        final_filled_qty = min(
            buy_fill_result.filled_quantity,
            sell_fill_result.filled_quantity,
        )
        
        # 4. 매수 주문 생성
        buy_order_id = f"BUY_{self.symbol}_{self.execution_count}"
        buy_order = Order(
            order_id=buy_order_id,
            exchange=trade.buy_exchange,
            symbol=self.symbol,
            side=OrderSide.BUY,
            quantity=trade.quantity,
            price=buy_fill_result.effective_price,
            status=(
                OrderStatus.FILLED if buy_fill_result.status == "filled"
                else OrderStatus.PARTIALLY_FILLED
            ),
            filled_quantity=buy_fill_result.filled_quantity,
        )
        self.orders[buy_order_id] = buy_order
        
        # 5. 매도 주문 생성
        sell_order_id = f"SELL_{self.symbol}_{self.execution_count}"
        sell_order = Order(
            order_id=sell_order_id,
            exchange=trade.sell_exchange,
            symbol=self.symbol,
            side=OrderSide.SELL,
            quantity=buy_fill_result.filled_quantity,
            price=sell_fill_result.effective_price,
            status=(
                OrderStatus.FILLED if sell_fill_result.status == "filled"
                else OrderStatus.PARTIALLY_FILLED
            ),
            filled_quantity=sell_fill_result.filled_quantity,
        )
        self.orders[sell_order_id] = sell_order
        
        # 6. 포지션 생성 (체결된 수량만)
        if final_filled_qty > 0:
            position_id = f"POS_{self.symbol}_{self.execution_count}"
            position = Position(
                symbol=self.symbol,
                quantity=final_filled_qty,
                entry_price=buy_fill_result.effective_price,
                current_price=sell_fill_result.effective_price,
                side=OrderSide.BUY,
                timestamp=datetime.utcnow(),
            )
            self.positions[position_id] = position
        
        # 7. PnL 계산 (Fill Model 기준)
        pnl = (
            sell_fill_result.effective_price - buy_fill_result.effective_price
        ) * final_filled_qty
        
        # 8. 상태 결정
        if final_filled_qty == 0:
            exec_status = "failed"
        elif final_filled_qty < trade.quantity:
            exec_status = "partial"
        else:
            exec_status = "success"
        
        # 9. 결과 반환
        result = ExecutionResult(
            symbol=self.symbol,
            trade_id=trade.trade_id,
            status=exec_status,
            buy_order_id=buy_order_id,
            sell_order_id=sell_order_id,
            buy_price=buy_fill_result.effective_price,
            sell_price=sell_fill_result.effective_price,
            quantity=final_filled_qty,
            pnl=pnl,
            buy_slippage_bps=buy_fill_result.slippage_bps,
            sell_slippage_bps=sell_fill_result.slippage_bps,
            buy_fill_ratio=buy_fill_result.fill_ratio,
            sell_fill_ratio=sell_fill_result.fill_ratio,
        )
        
        logger.info(
            f"[D80-4_FILL_MODEL] Trade executed for {self.symbol}: "
            f"order_qty={trade.quantity:.4f}, filled_qty={final_filled_qty:.4f}, "
            f"buy_price={trade.buy_price:.2f}→{buy_fill_result.effective_price:.2f} "
            f"(slippage={buy_fill_result.slippage_bps:.2f}bps), "
            f"sell_price={trade.sell_price:.2f}→{sell_fill_result.effective_price:.2f} "
            f"(slippage={sell_fill_result.slippage_bps:.2f}bps), "
            f"pnl={pnl:.2f}, status={exec_status}"
        )
        
        # D83-0.5: Fill Event 기록 (BUY + SELL)
        if self.fill_event_collector is not None:
            # D86: CalibratedFillModel에서 entry_bps/tp_bps 가져오기
            entry_bps = getattr(self.fill_model, 'entry_bps', 0.0)
            tp_bps = getattr(self.fill_model, 'tp_bps', 0.0)
            
            # BUY Event
            self.fill_event_collector.record_fill_event(
                symbol=self.symbol,
                side=OrderSide.BUY,
                entry_bps=entry_bps,
                tp_bps=tp_bps,
                order_quantity=trade.quantity,
                filled_quantity=buy_fill_result.filled_quantity,
                fill_ratio=buy_fill_result.fill_ratio,
                slippage_bps=buy_fill_result.slippage_bps,
                available_volume=buy_available_volume,
                spread_bps=0.0,  # TODO: 실제 Spread 계산
                exit_reason="unknown",
                latency_ms=None,
            )
            # SELL Event
            self.fill_event_collector.record_fill_event(
                symbol=self.symbol,
                side=OrderSide.SELL,
                entry_bps=entry_bps,
                tp_bps=tp_bps,
                order_quantity=buy_fill_result.filled_quantity,
                filled_quantity=sell_fill_result.filled_quantity,
                fill_ratio=sell_fill_result.fill_ratio,
                slippage_bps=sell_fill_result.slippage_bps,
                available_volume=sell_available_volume,
                spread_bps=0.0,
                exit_reason="unknown",
                latency_ms=None,
            )
        
        return result
    
    def get_positions(self) -> Dict[str, Position]:
        """
        포지션 조회
        
        Returns:
            포지션 딕셔너리
        """
        return self.positions.copy()
    
    def get_pnl(self) -> float:
        """
        PnL 조회
        
        Returns:
            PnL (USD)
        """
        return self.total_pnl
    
    def close_position(self, position_id: str) -> Optional[ExecutionResult]:
        """
        포지션 청산
        
        Args:
            position_id: 포지션 ID
        
        Returns:
            실행 결과 또는 None
        """
        if position_id not in self.positions:
            logger.warning(f"[D61_PAPER_EXECUTOR] Position not found: {position_id}")
            return None
        
        position = self.positions[position_id]
        
        # 청산 주문 생성
        close_order_id = f"CLOSE_{self.symbol}_{self.execution_count}"
        close_order = Order(
            order_id=close_order_id,
            exchange=position.side.value,
            symbol=self.symbol,
            side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
            quantity=position.quantity,
            price=position.current_price,
            status=OrderStatus.FILLED,
            filled_quantity=position.quantity,
        )
        self.orders[close_order_id] = close_order
        
        # PnL 계산
        pnl = position.pnl
        
        # 포지션 제거
        del self.positions[position_id]
        
        # 결과 반환
        result = ExecutionResult(
            symbol=self.symbol,
            trade_id=position_id,
            status="success",
            sell_order_id=close_order_id,
            sell_price=position.current_price,
            quantity=position.quantity,
            pnl=pnl,
        )
        
        logger.info(
            f"[D61_PAPER_EXECUTOR] Position closed for {self.symbol}: "
            f"pnl={pnl:.2f}"
        )
        
        return result


class LiveExecutor(BaseExecutor):
    """
    D64: Live Executor (실제 거래)
    
    Upbit/Binance API를 통해 실제 주문을 실행한다.
    dry_run=True 시 로그만 출력하고 실제 주문은 하지 않는다.
    """
    
    def __init__(
        self,
        symbol: str,
        portfolio_state: PortfolioState,
        risk_guard: RiskGuard,
        upbit_api=None,
        binance_api=None,
        dry_run: bool = True,
    ):
        """
        Args:
            symbol: 거래 심볼
            portfolio_state: 포트폴리오 상태
            risk_guard: 리스크 가드
            upbit_api: Upbit API 클라이언트
            binance_api: Binance API 클라이언트
            dry_run: 드라이런 모드 (True면 실제 주문 안 함)
        """
        super().__init__(symbol, portfolio_state, risk_guard)
        self.upbit_api = upbit_api
        self.binance_api = binance_api
        self.dry_run = dry_run
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.pnl_history: List[Tuple[datetime, float]] = []
        
        logger.info(
            f"[D64_LIVE_EXECUTOR] Initialized for {symbol} "
            f"(dry_run={dry_run})"
        )
    
    def execute_trades(self, trades: List) -> List[ExecutionResult]:
        """
        D64: 거래 실행 (Live Mode)
        D98-3: ReadOnlyGuard 추가 (Executor 레벨 차단)
        
        Args:
            trades: 실행할 거래 목록 (ArbitrageTrade)
        
        Returns:
            실행 결과 목록
        
        Raises:
            ReadOnlyError: READ_ONLY_ENFORCED=true 시 발생
        """
        # D98-3: 중앙 차단 게이트 (Defense-in-depth Layer 2)
        guard = get_readonly_guard()
        if guard.is_read_only:
            logger.error(
                "[D98-3_EXECUTOR_GUARD] Live order execution blocked in READ_ONLY mode. "
                f"Attempted to execute {len(trades)} trades for {self.symbol}."
            )
            raise ReadOnlyError(
                "[D98-3_EXECUTOR_GUARD] Cannot execute live trades when READ_ONLY_ENFORCED=true. "
                "Set READ_ONLY_ENFORCED=false to enable live trading (use with extreme caution)."
            )
        
        results = []
        
        for trade in trades:
            # 1. 리스크 체크
            if not self.risk_guard.check_symbol_capital_limit(
                self.symbol, trade.notional_usd
            ):
                logger.warning(
                    f"[D64_LIVE_EXECUTOR] Trade rejected for {self.symbol}: "
                    f"capital limit exceeded"
                )
                results.append(
                    ExecutionResult(
                        symbol=self.symbol,
                        trade_id=trade.trade_id,
                        status="failed",
                    )
                )
                continue
            
            if not self.risk_guard.check_symbol_position_limit(self.symbol):
                logger.warning(
                    f"[D64_LIVE_EXECUTOR] Trade rejected for {self.symbol}: "
                    f"position limit exceeded"
                )
                results.append(
                    ExecutionResult(
                        symbol=self.symbol,
                        trade_id=trade.trade_id,
                        status="failed",
                    )
                )
                continue
            
            # 2. 거래 실행
            result = self._execute_single_trade(trade)
            results.append(result)
            
            # 3. 상태 업데이트
            if result.status == "success":
                self.execution_count += 1
                self.total_pnl += result.pnl
                
                # 포트폴리오 상태 업데이트
                self.portfolio_state.update_symbol_capital_used(
                    self.symbol,
                    self.portfolio_state.get_symbol_capital_used(self.symbol) + result.quantity * result.buy_price,
                )
                self.portfolio_state.update_symbol_position_count(
                    self.symbol,
                    len(self.positions),
                )
        
        return results
    
    def _execute_single_trade(self, trade) -> ExecutionResult:
        """
        단일 거래 실행 (실제 API 호출)
        
        Args:
            trade: 거래 정보 (ArbitrageTrade)
        
        Returns:
            실행 결과
        """
        try:
            # 1. 매수 주문 (Exchange A)
            buy_order_id = None
            if self.dry_run:
                buy_order_id = f"DRY_BUY_{self.symbol}_{self.execution_count}"
                logger.info(
                    f"[D64_LIVE_EXECUTOR] DRY-RUN: Buy order on {trade.buy_exchange}: "
                    f"qty={trade.quantity}, price={trade.buy_price}"
                )
            else:
                if trade.buy_exchange == "upbit" and self.upbit_api:
                    try:
                        order = self.upbit_api.create_order(
                            market=f"KRW-{trade.symbol.split('-')[1]}",
                            side="bid",
                            ord_type="limit",
                            volume=trade.quantity,
                            price=trade.buy_price,
                        )
                        buy_order_id = order.get("uuid")
                        logger.info(
                            f"[D64_LIVE_EXECUTOR] Buy order placed on Upbit: "
                            f"order_id={buy_order_id}, qty={trade.quantity}, price={trade.buy_price}"
                        )
                    except Exception as e:
                        logger.error(f"[D64_LIVE_EXECUTOR] Upbit buy order failed: {e}")
                        return ExecutionResult(
                            symbol=self.symbol,
                            trade_id=trade.trade_id,
                            status="failed",
                        )
                elif trade.buy_exchange == "binance" and self.binance_api:
                    try:
                        order = self.binance_api.create_order(
                            symbol=f"{trade.symbol.split('-')[1]}USDT",
                            side="BUY",
                            type="LIMIT",
                            quantity=trade.quantity,
                            price=trade.buy_price,
                        )
                        buy_order_id = order.get("orderId")
                        logger.info(
                            f"[D64_LIVE_EXECUTOR] Buy order placed on Binance: "
                            f"order_id={buy_order_id}, qty={trade.quantity}, price={trade.buy_price}"
                        )
                    except Exception as e:
                        logger.error(f"[D64_LIVE_EXECUTOR] Binance buy order failed: {e}")
                        return ExecutionResult(
                            symbol=self.symbol,
                            trade_id=trade.trade_id,
                            status="failed",
                        )
            
            # 2. 매도 주문 (Exchange B)
            sell_order_id = None
            if self.dry_run:
                sell_order_id = f"DRY_SELL_{self.symbol}_{self.execution_count}"
                logger.info(
                    f"[D64_LIVE_EXECUTOR] DRY-RUN: Sell order on {trade.sell_exchange}: "
                    f"qty={trade.quantity}, price={trade.sell_price}"
                )
            else:
                if trade.sell_exchange == "upbit" and self.upbit_api:
                    try:
                        order = self.upbit_api.create_order(
                            market=f"KRW-{trade.symbol.split('-')[1]}",
                            side="ask",
                            ord_type="limit",
                            volume=trade.quantity,
                            price=trade.sell_price,
                        )
                        sell_order_id = order.get("uuid")
                        logger.info(
                            f"[D64_LIVE_EXECUTOR] Sell order placed on Upbit: "
                            f"order_id={sell_order_id}, qty={trade.quantity}, price={trade.sell_price}"
                        )
                    except Exception as e:
                        logger.error(f"[D64_LIVE_EXECUTOR] Upbit sell order failed: {e}")
                        # 매수 주문 취소 시도
                        if buy_order_id and self.upbit_api:
                            try:
                                self.upbit_api.cancel_order(buy_order_id)
                            except:
                                pass
                        return ExecutionResult(
                            symbol=self.symbol,
                            trade_id=trade.trade_id,
                            status="failed",
                        )
                elif trade.sell_exchange == "binance" and self.binance_api:
                    try:
                        order = self.binance_api.create_order(
                            symbol=f"{trade.symbol.split('-')[1]}USDT",
                            side="SELL",
                            type="LIMIT",
                            quantity=trade.quantity,
                            price=trade.sell_price,
                        )
                        sell_order_id = order.get("orderId")
                        logger.info(
                            f"[D64_LIVE_EXECUTOR] Sell order placed on Binance: "
                            f"order_id={sell_order_id}, qty={trade.quantity}, price={trade.sell_price}"
                        )
                    except Exception as e:
                        logger.error(f"[D64_LIVE_EXECUTOR] Binance sell order failed: {e}")
                        # 매수 주문 취소 시도
                        if buy_order_id and self.binance_api:
                            try:
                                self.binance_api.cancel_order(buy_order_id)
                            except:
                                pass
                        return ExecutionResult(
                            symbol=self.symbol,
                            trade_id=trade.trade_id,
                            status="failed",
                        )
            
            # 3. 포지션 생성
            position_id = f"POS_{self.symbol}_{self.execution_count}"
            position = Position(
                symbol=self.symbol,
                quantity=trade.quantity,
                entry_price=trade.buy_price,
                current_price=trade.sell_price,
                side=OrderSide.BUY,
                timestamp=datetime.utcnow(),
            )
            self.positions[position_id] = position
            
            # 4. PnL 계산
            pnl = (trade.sell_price - trade.buy_price) * trade.quantity
            
            # 5. 결과 반환
            result = ExecutionResult(
                symbol=self.symbol,
                trade_id=trade.trade_id,
                status="success",
                buy_order_id=buy_order_id,
                sell_order_id=sell_order_id,
                buy_price=trade.buy_price,
                sell_price=trade.sell_price,
                quantity=trade.quantity,
                pnl=pnl,
            )
            
            logger.info(
                f"[D64_LIVE_EXECUTOR] Trade executed for {self.symbol}: "
                f"qty={trade.quantity}, buy={trade.buy_price}, sell={trade.sell_price}, pnl={pnl:.2f}"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"[D64_LIVE_EXECUTOR] Trade execution failed: {e}")
            return ExecutionResult(
                symbol=self.symbol,
                trade_id=trade.trade_id,
                status="failed",
            )
    
    def get_positions(self) -> Dict[str, Position]:
        """
        포지션 조회
        
        Returns:
            포지션 딕셔너리
        """
        return self.positions.copy()
    
    def get_pnl(self) -> float:
        """
        PnL 조회
        
        Returns:
            PnL (USD)
        """
        return self.total_pnl
    
    def close_position(self, position_id: str) -> Optional[ExecutionResult]:
        """
        포지션 청산
        
        Args:
            position_id: 포지션 ID
        
        Returns:
            실행 결과 또는 None
        """
        if position_id not in self.positions:
            logger.warning(f"[D64_LIVE_EXECUTOR] Position not found: {position_id}")
            return None
        
        position = self.positions[position_id]
        
        # 청산 주문 생성
        close_order_id = f"CLOSE_{self.symbol}_{self.execution_count}"
        close_order = Order(
            order_id=close_order_id,
            exchange=position.side.value,
            symbol=self.symbol,
            side=OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY,
            quantity=position.quantity,
            price=position.current_price,
            status=OrderStatus.FILLED,
            filled_quantity=position.quantity,
        )
        self.orders[close_order_id] = close_order
        
        # PnL 계산
        pnl = position.pnl
        
        # 포지션 제거
        del self.positions[position_id]
        
        # 결과 반환
        result = ExecutionResult(
            symbol=self.symbol,
            trade_id=position_id,
            status="success",
            sell_order_id=close_order_id,
            sell_price=position.current_price,
            quantity=position.quantity,
            pnl=pnl,
        )
        
        logger.info(
            f"[D64_LIVE_EXECUTOR] Position closed for {self.symbol}: "
            f"pnl={pnl:.2f}"
        )
        
        return result
