# -*- coding: utf-8 -*-
"""
D42 Exchange Adapter Layer - Paper (Mock) Exchange

실제 API 호출 없이 메모리 상에서 주문/체결/포지션을 시뮬레이션.

D98-1: Read-only Guard 적용 (실주문 0건 강제)
"""

import logging
import time
import uuid
from typing import Dict, List, Optional, Any

from arbitrage.exchanges.base import (
    BaseExchange,
    OrderSide,
    OrderType,
    TimeInForce,
    OrderStatus,
    OrderResult,
    Balance,
    Position,
    PositionSide,
    OrderBookSnapshot,
)
from arbitrage.common.currency import Currency
from arbitrage.exchanges.exceptions import (
    InsufficientBalanceError,
    OrderNotFoundError,
    InvalidOrderError,
)
from arbitrage.config.readonly_guard import enforce_readonly

logger = logging.getLogger(__name__)


class PaperExchange(BaseExchange):
    """
    모의 거래소 (Paper Trading Mode).
    
    실제 API 호출 없이 메모리 상에서 동작.
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        initial_balance: Optional[Dict[str, float]] = None,
    ):
        """
        Args:
            config: 설정 dict
            initial_balance: 초기 잔고 (예: {"KRW": 1000000, "BTC": 0.1})
        """
        super().__init__("paper", config)
        
        # 초기 잔고 설정
        self._balance: Dict[str, Balance] = {}
        if initial_balance:
            for asset, amount in initial_balance.items():
                self._balance[asset] = Balance(asset=asset, free=amount, locked=0.0)
        else:
            # 기본값: KRW 1,000,000
            self._balance["KRW"] = Balance(asset="KRW", free=1000000.0, locked=0.0)
        
        # 주문 저장소
        self._orders: Dict[str, OrderResult] = {}
        
        # 포지션 저장소
        self._positions: Dict[str, Position] = {}
        
        # 호가 캐시 (테스트용)
        self._orderbook_cache: Dict[str, OrderBookSnapshot] = {}
        
        logger.info(f"[D42_PAPER] PaperExchange initialized with balance: {self._balance}, base_currency={self.base_currency.value}")
    
    def _infer_base_currency(self) -> Currency:
        """
        D80-2: PaperExchange 기본 통화 (기본값: KRW, config로 변경 가능)
        
        Returns:
            Currency (기본값: KRW)
        """
        return self.config.get("base_currency", Currency.KRW)
    
    def set_orderbook(self, symbol: str, snapshot: OrderBookSnapshot) -> None:
        """
        호가 정보 설정 (테스트용).
        
        Args:
            symbol: 거래 쌍
            snapshot: OrderBookSnapshot
        """
        self._orderbook_cache[symbol] = snapshot
        logger.debug(f"[D42_PAPER] Orderbook set for {symbol}")
    
    def get_orderbook(self, symbol: str) -> OrderBookSnapshot:
        """호가 정보 조회"""
        if symbol not in self._orderbook_cache:
            # 기본값 반환
            return OrderBookSnapshot(
                symbol=symbol,
                timestamp=time.time(),
                bids=[(100000.0, 1.0)],
                asks=[(101000.0, 1.0)],
            )
        return self._orderbook_cache[symbol]
    
    def get_balance(self) -> Dict[str, Balance]:
        """자산 잔고 조회"""
        return dict(self._balance)
    
    @enforce_readonly
    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: Optional[float] = None,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> OrderResult:
        """
        주문 생성.
        
        D98-1: @enforce_readonly 데코레이터 적용
        READ_ONLY_ENFORCED=true 시 차단됨
        """
        if qty <= 0:
            raise InvalidOrderError(f"Invalid quantity: {qty}")
        
        # 호가에서 가격 결정
        if price is None:
            orderbook = self.get_orderbook(symbol)
            if order_type == OrderType.MARKET:
                price = orderbook.best_ask() if side == OrderSide.BUY else orderbook.best_bid()
            else:
                price = orderbook.best_bid() if side == OrderSide.BUY else orderbook.best_ask()
        
        if price is None:
            raise InvalidOrderError(f"Cannot determine price for {symbol}")
        
        # Symbol 파싱하여 기본 자산 결정
        if "-" in symbol:
            # Upbit 형식: "KRW-BTC" -> 기본 자산은 "KRW"
            base_asset = symbol.split("-")[0]
        else:
            # Binance 형식: "BTCUSDT" -> 기본 자산은 "USDT"
            if symbol.endswith("USDT"):
                base_asset = "USDT"
            else:
                base_asset = symbol[3:]  # 기타 경우
        
        # 잔고 확인 (매수 시)
        if side == OrderSide.BUY:
            required_amount = qty * price
            if base_asset not in self._balance or self._balance[base_asset].free < required_amount:
                raise InsufficientBalanceError(
                    f"Insufficient {base_asset}: required={required_amount}, available={self._balance.get(base_asset, Balance(base_asset, 0, 0)).free}"
                )
        
        # 주문 생성
        order_id = str(uuid.uuid4())[:12]
        order = OrderResult(
            order_id=order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            order_type=order_type,
            status=OrderStatus.OPEN,
            filled_qty=0.0,
        )
        
        self._orders[order_id] = order
        
        # 즉시 체결 (Paper 모드에서는 시뮬레이션)
        self._fill_order(order_id)
        
        logger.info(f"[D42_PAPER] Order created: {order_id} {side} {qty} {symbol} @ {price}")
        return self._orders[order_id]
    
    def _fill_order(self, order_id: str) -> None:
        """주문 체결 시뮬레이션"""
        if order_id not in self._orders:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        order = self._orders[order_id]
        
        # 체결 수량 = 주문 수량 (Paper 모드에서는 항상 체결)
        order.filled_qty = order.qty
        order.status = OrderStatus.FILLED
        
        # Symbol 파싱 (Upbit: "KRW-BTC", Binance: "BTCUSDT")
        if "-" in order.symbol:
            # Upbit 형식: "KRW-BTC" -> 거래 자산은 "BTC"
            parts = order.symbol.split("-")
            base_asset = parts[0]  # "KRW"
            trade_asset = parts[1]  # "BTC"
        else:
            # Binance 형식: "BTCUSDT" -> 거래 자산은 "BTC", 기본 자산은 "USDT"
            # 간단화: 마지막 4자리를 기본 자산으로 간주
            if order.symbol.endswith("USDT"):
                trade_asset = order.symbol[:-4]  # "BTCUSDT" -> "BTC"
                base_asset = "USDT"
            else:
                # 기타 경우: 첫 3자리를 거래 자산으로
                trade_asset = order.symbol[:3]
                base_asset = order.symbol[3:]
        
        # 잔고 업데이트
        if order.side == OrderSide.BUY:
            # 기본 자산 차감, 거래 자산 추가
            cost = order.qty * order.price
            
            if base_asset not in self._balance:
                self._balance[base_asset] = Balance(asset=base_asset, free=0.0, locked=0.0)
            
            self._balance[base_asset].free -= cost
            
            if trade_asset not in self._balance:
                self._balance[trade_asset] = Balance(asset=trade_asset, free=0.0, locked=0.0)
            self._balance[trade_asset].free += order.qty
        
        elif order.side == OrderSide.SELL:
            # 거래 자산 차감, 기본 자산 추가
            revenue = order.qty * order.price
            
            if trade_asset in self._balance:
                self._balance[trade_asset].free -= order.qty
            
            if base_asset not in self._balance:
                self._balance[base_asset] = Balance(asset=base_asset, free=0.0, locked=0.0)
            
            self._balance[base_asset].free += revenue
        
        logger.debug(f"[D42_PAPER] Order filled: {order_id}")
    
    @enforce_readonly
    def cancel_order(self, order_id: str) -> bool:
        """
        주문 취소.
        
        D98-1: @enforce_readonly 데코레이터 적용
        READ_ONLY_ENFORCED=true 시 차단됨
        """
        if order_id not in self._orders:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        order = self._orders[order_id]
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED]:
            return False  # 이미 체결되거나 취소됨
        
        order.status = OrderStatus.CANCELED
        logger.info(f"[D42_PAPER] Order canceled: {order_id}")
        return True
    
    def get_open_positions(self) -> List[Position]:
        """미결제 포지션 조회"""
        return list(self._positions.values())
    
    def get_order_status(self, order_id: str) -> OrderResult:
        """주문 상태 조회"""
        if order_id not in self._orders:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        return self._orders[order_id]
    
    def get_all_orders(self) -> Dict[str, OrderResult]:
        """모든 주문 조회 (테스트용)"""
        return dict(self._orders)
