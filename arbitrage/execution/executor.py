# -*- coding: utf-8 -*-
"""
D61: Multi-Symbol Paper Execution — Executor Base Classes

거래 실행 엔진의 추상 클래스 및 Paper Executor 구현.
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
    ):
        """
        Args:
            symbol: 거래 심볼
            portfolio_state: 포트폴리오 상태
            risk_guard: 리스크 가드
        """
        super().__init__(symbol, portfolio_state, risk_guard)
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.pnl_history: List[Tuple[datetime, float]] = []
        
        logger.info(f"[D61_PAPER_EXECUTOR] Initialized for {symbol}")
    
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
        
        Args:
            trade: 거래 정보 (ArbitrageTrade)
        
        Returns:
            실행 결과
        """
        try:
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
        
        except Exception as e:
            logger.error(f"[D61_PAPER_EXECUTOR] Trade execution failed: {e}")
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
