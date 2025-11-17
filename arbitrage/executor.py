#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Executor Module
===============
거래소 주문 실행 인터페이스

책임:
- 업비트/바이낸스 주문 실행
- 주문 상태 추적
- Paper 모드 지원 (가상 체결)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple, TYPE_CHECKING
from uuid import uuid4
from urllib.parse import urlencode

import httpx
import jwt

if TYPE_CHECKING:  # pragma: no cover - type checking helper
    from rich.console import Console

from .models import Position, TradeSignal, SpreadOpportunity, OrderLeg
from .storage import SimpleStorage
from .risk import can_open_new_position, compute_position_size_krw, should_close_position, calculate_pnl


logger = logging.getLogger(__name__)


class LiveTradingError(Exception):
    """Raised when live trading API calls fail."""



class BaseExecutor:
    """
    주문 실행 인터페이스 (추상 클래스)
    
    Paper/Live 모드를 통합하는 인터페이스를 정의합니다.
    """
    
    def execute_entry(self, signal: TradeSignal, size: float, config: Dict) -> Optional[Position]:
        """
        진입 주문 실행
        
        Args:
            signal: 진입 시그널
            size: 주문 수량
            config: 설정 딕셔너리
        
        Returns:
            생성된 Position 객체 (실패 시 None)
        
        TODO (PHASE A-3 이후):
        ─────────────────────────────────────────────────────────────────
        하위 클래스(PaperExecutor, LiveExecutor)에서 구현합니다.
        ─────────────────────────────────────────────────────────────────
        """
        raise NotImplementedError("Subclass must implement execute_entry")
    
    def execute_exit(self, position: Position, signal: TradeSignal, config: Dict) -> bool:
        """
        청산 주문 실행
        
        Args:
            position: 청산할 포지션
            signal: 청산 시그널
            config: 설정 딕셔너리
        
        Returns:
            True: 청산 성공, False: 청산 실패
        
        TODO (PHASE A-3 이후):
        ─────────────────────────────────────────────────────────────────
        하위 클래스(PaperExecutor, LiveExecutor)에서 구현합니다.
        ─────────────────────────────────────────────────────────────────
        """
        raise NotImplementedError("Subclass must implement execute_exit")


class PaperExecutor(BaseExecutor):
    """
    Paper Trading (가상 체결) Executor
    
    실제 주문 없이 가상으로 포지션을 생성/청산합니다.
    
    TODO (PHASE A-3):
    ─────────────────────────────────────────────────────────────────────
    [구현 계획]
    
    1. **execute_entry**:
       ```python
       def execute_entry(self, signal, size, config):
           # 가상 포지션 생성
           position = Position(
               symbol=signal.symbol,
               direction=signal.direction,
               size=size,
               entry_upbit_price=signal.spread_opportunity.upbit_price,
               entry_binance_price=signal.spread_opportunity.binance_price,
               entry_spread_pct=signal.spread_opportunity.spread_pct,
               timestamp_open=signal.timestamp
           )
           return position
       ```
    
    2. **execute_exit**:
       ```python
       def execute_exit(self, position, signal, config):
           from .risk import calculate_pnl
           
           # 손익 계산
           usdkrw = config["fx"]["usdkrw"]
           pnl_krw, pnl_pct = calculate_pnl(
               position,
               signal.spread_opportunity.upbit_price,
               signal.spread_opportunity.binance_price,
               usdkrw
           )
           
           # 포지션 청산
           position.close(
               exit_upbit_price=signal.spread_opportunity.upbit_price,
               exit_binance_price=signal.spread_opportunity.binance_price,
               exit_spread_pct=signal.spread_opportunity.spread_pct,
               pnl_krw=pnl_krw,
               pnl_pct=pnl_pct,
               timestamp_close=signal.timestamp
           )
           return True
       ```
    ─────────────────────────────────────────────────────────────────────
    """
    def __init__(
        self,
        config: Dict,
        storage: SimpleStorage,
        *,
        console: Optional["Console"] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.config = config
        self.storage = storage
        self.console = console
        self.logger = logger or logging.getLogger("arbitrage.paper")
        self.positions: List[Position] = []  # 모든 포지션 (심볼 구분은 Position.symbol로)
        self.force_entry_used = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _print_console(self, message: str, style: Optional[str] = None) -> None:
        if not self.console:
            return
        if style:
            self.console.print(message, style=style)
        else:
            self.console.print(message)

    def _log(self, level: str, message: str, *args) -> None:
        logger = self.logger or logging.getLogger("arbitrage.paper")
        log_fn = getattr(logger, level, logger.info)
        log_fn(message, *args)

    def _get_slippage_bps(self, venue: str) -> float:
        """거래소별 슬리피지 조회 (bps 단위)
        
        Args:
            venue: "upbit" | "binance_futures"
        
        Returns:
            float: 슬리피지 (bps, 예: 10 = 0.10%)
        """
        slippage_cfg = self.config.get("slippage", {})
        venue_cfg = slippage_cfg.get(venue, {})
        base_bps = float(venue_cfg.get("base_bps", 0.0))
        volatility_factor = float(venue_cfg.get("volatility_factor", 1.0))
        return base_bps * volatility_factor

    def _apply_slippage(self, price: float, venue: str, side: str) -> Tuple[float, float]:
        """슬리피지 적용 (Order Routing & Slippage Model)
        
        Args:
            price: 이론 체결가
            venue: "upbit" | "binance_futures"
            side: "buy" | "sell" | "long" | "short"
        
        Returns:
            Tuple[float, float]: (실제 체결가, 적용된 슬리피지_bps)
        """
        slippage_bps = self._get_slippage_bps(venue)
        
        # Buy/Long: 가격 상승 (불리함)
        # Sell/Short: 가격 하락 (불리함)
        if side in ("buy", "long"):
            price_effective = price * (1 + slippage_bps / 10000)
        else:  # sell, short
            price_effective = price * (1 - slippage_bps / 10000)
        
        return price_effective, slippage_bps

    def _create_order_legs(self, position: Position, signal: TradeSignal, is_entry: bool) -> List[OrderLeg]:
        """포지션으로부터 OrderLeg 2개 생성 (Order Routing)
        
        Args:
            position: Position 객체
            signal: TradeSignal 객체
            is_entry: True면 진입 주문, False면 청산 주문
        
        Returns:
            List[OrderLeg]: 2개의 OrderLeg (Upbit + Binance)
        """
        now = datetime.now(timezone.utc)
        pos_id = str(abs(hash(position.timestamp_open.isoformat())) % 10000)
        
        legs = []
        
        # Direction 파싱: "upbit_short_binance_long" 등
        direction = position.direction
        is_upbit_short = "upbit_short" in direction
        is_binance_long = "binance_long" in direction
        
        if is_entry:
            # ENTRY 주문
            upbit_side = "sell" if is_upbit_short else "buy"
            binance_side = "long" if is_binance_long else "short"
            upbit_price = signal.spread_opportunity.upbit_price
            binance_price = signal.spread_opportunity.binance_price_krw
        else:
            # EXIT 주문
            upbit_side = "buy" if is_upbit_short else "sell"
            binance_side = "short" if is_binance_long else "long"
            upbit_price = signal.spread_opportunity.upbit_price
            binance_price = signal.spread_opportunity.binance_price_krw
        
        # Upbit leg
        upbit_price_eff, upbit_slippage = self._apply_slippage(upbit_price, "upbit", upbit_side)
        upbit_leg = OrderLeg(
            symbol=position.symbol,
            venue="upbit",
            side=upbit_side,
            qty=position.size,
            price_theoretical=upbit_price,
            price_effective=upbit_price_eff,
            slippage_bps=upbit_slippage,
            timestamp=now,
            leg_id=f"pos_{pos_id}_leg_0",
            order_id=None,
        )
        legs.append(upbit_leg)
        
        # Binance leg
        binance_price_eff, binance_slippage = self._apply_slippage(binance_price, "binance_futures", binance_side)
        binance_leg = OrderLeg(
            symbol=position.symbol,
            venue="binance_futures",
            side=binance_side,
            qty=position.size,
            price_theoretical=binance_price,
            price_effective=binance_price_eff,
            slippage_bps=binance_slippage,
            timestamp=now,
            leg_id=f"pos_{pos_id}_leg_1",
            order_id=None,
        )
        legs.append(binance_leg)
        
        return legs

    def execute_entry(self, signal: TradeSignal, size: float, config: Dict) -> Optional[Position]:
        now = datetime.now(timezone.utc)
        position = Position(
            symbol=signal.symbol,
            direction=signal.direction or "upbit_long_binance_short",
            size=size,
            entry_upbit_price=signal.spread_opportunity.upbit_price,
            entry_binance_price=signal.spread_opportunity.binance_price,
            entry_spread_pct=signal.spread_opportunity.spread_pct,
            timestamp_open=now,
        )
        self.positions.append(position)
        self.storage.log_position_open(position)
        
        # Order Routing & Slippage: OrderLeg 생성 및 기록
        order_legs = self._create_order_legs(position, signal, is_entry=True)
        for leg in order_legs:
            self.storage.log_order(leg)
            self._log(
                "debug",
                "order_leg_created symbol=%s venue=%s side=%s qty=%.6f "
                "price_theo=%.0f price_eff=%.0f slippage=%.1fbps leg_id=%s",
                leg.symbol,
                leg.venue,
                leg.side,
                leg.qty,
                leg.price_theoretical,
                leg.price_effective,
                leg.slippage_bps,
                leg.leg_id,
            )
        
        self._log(
            "info",
            "position_open symbol=%s direction=%s size=%.6f spread=%.4f reason=%s",
            signal.symbol,
            position.direction,
            position.size,
            signal.spread_opportunity.spread_pct if signal.spread_opportunity else 0.0,
            signal.reason,
        )
        self._print_console(
            (
                f"[OPEN] {signal.symbol} {position.direction} size={position.size:.6f} "
                f"spread={signal.spread_opportunity.spread_pct:+.2f}% reason={signal.reason}"
            ),
            style="bold green",
        )
        return position

    def execute_exit(self, position: Position, signal: TradeSignal, config: Dict) -> bool:
        now = datetime.now(timezone.utc)
        usdkrw = config.get("fx", {}).get("usdkrw", 1350.0)
        pnl_krw, pnl_pct = calculate_pnl(
            position,
            signal.spread_opportunity.upbit_price,
            signal.spread_opportunity.binance_price,
            usdkrw,
        )
        position.close(
            exit_upbit_price=signal.spread_opportunity.upbit_price,
            exit_binance_price=signal.spread_opportunity.binance_price,
            exit_spread_pct=signal.spread_opportunity.spread_pct,
            pnl_krw=pnl_krw,
            pnl_pct=pnl_pct,
            timestamp_close=now,
        )
        self.storage.log_position_close(position)
        self.storage.log_position_open(position)
        
        # Order Routing & Slippage: OrderLeg 생성 및 기록
        order_legs = self._create_order_legs(position, signal, is_entry=False)
        for leg in order_legs:
            self.storage.log_order(leg)
            self._log(
                "debug",
                "order_leg_created symbol=%s venue=%s side=%s qty=%.6f "
                "price_theo=%.0f price_eff=%.0f slippage=%.1fbps leg_id=%s",
                leg.symbol,
                leg.venue,
                leg.side,
                leg.qty,
                leg.price_theoretical,
                leg.price_effective,
                leg.slippage_bps,
                leg.leg_id,
            )
        
        self._log(
            "info",
            "position_close symbol=%s direction=%s size=%.6f pnl_krw=%.2f pnl_pct=%.2f reason=%s",
            position.symbol,
            position.direction,
            position.size,
            pnl_krw,
            pnl_pct,
            signal.reason,
        )
        self._print_console(
            (
                f"[CLOSE] {position.symbol} size={position.size:.6f} "
                f"pnl={pnl_krw:+.0f} KRW ({pnl_pct:+.2f}%) reason={signal.reason}"
            ),
            style="bold cyan",
        )
        return True

    def on_opportunity(self, opp: SpreadOpportunity, now: datetime, symbol: str = None) -> List[TradeSignal]:
        """스프레드 기회 처리 (심볼별 진입/청산)
        
        Args:
            opp: 스프레드 기회
            now: 현재 시간
            symbol: 심볼명 (기본값: opp.symbol)
        """
        symbol = symbol or opp.symbol
        signals: List[TradeSignal] = []

        # [1] CLOSE 시그널 처리: 기존 OPEN 포지션 청산 (해당 심볼만)
        closed_positions = []
        for position in [p for p in self.positions if p.status == "OPEN" and p.symbol == symbol]:
            close_ok, reason = should_close_position(self.config, position, opp, now)
            if close_ok:
                signal = TradeSignal(
                    symbol=position.symbol,
                    action="CLOSE",
                    direction=position.direction,
                    spread_opportunity=opp,
                    reason=reason,
                    timestamp=now,
                )
                self.execute_exit(position, signal, self.config)
                signals.append(signal)
                closed_positions.append(position)
        
        # CLOSED 포지션을 리스트에서 제거
        for pos in closed_positions:
            self.positions.remove(pos)

        # [2] OPEN 시그널 처리: 새 포지션 진입 (중복 진입 방지)
        can_open, reason = can_open_new_position(self.config, self.positions, opp, symbol=symbol)

        debug_cfg = self.config.get("debug", {})
        force_entry = bool(debug_cfg.get("force_first_entry"))
        force_min_size = float(debug_cfg.get("force_entry_min_size", 0.0))
        has_open_position = any(p.status == "OPEN" for p in self.positions)

        if not can_open and force_entry and not has_open_position and not self.force_entry_used:
            can_open = True
            reason = "FORCED_DEBUG_ENTRY"
            self.force_entry_used = True
            self._print_console("[DEBUG] force_first_entry 플래그로 인해 강제 진입", style="bold yellow")
            self._log(
                "warning",
                "force_first_entry triggered symbol=%s spread=%.4f net=%.4f",
                opp.symbol,
                opp.spread_pct,
                opp.net_spread_pct,
            )

        if can_open:
            # 중복 진입 방지: 같은 symbol+direction의 OPEN 포지션이 이미 있으면 무시
            existing = next(
                (p for p in self.positions if p.status == "OPEN" and p.symbol == opp.symbol),
                None,
            )
            if existing:
                self._log(
                    "warning",
                    "skip duplicate entry symbol=%s direction=%s (already open)",
                    opp.symbol,
                    existing.direction,
                )
                return signals

            threshold_price = (opp.upbit_price + opp.binance_price_krw) / 2 or opp.upbit_price
            size = compute_position_size_krw(self.config, threshold_price)
            if size <= 0 and reason == "FORCED_DEBUG_ENTRY":
                size = force_min_size or 0.001
            if size <= 0:
                self._log(
                    "warning",
                    "skip entry symbol=%s reason=%s size<=0 threshold_price=%.2f",
                    opp.symbol,
                    reason,
                    threshold_price,
                )
                return signals

            direction = (
                "upbit_long_binance_short"
                if opp.upbit_price <= opp.binance_price_krw
                else "upbit_short_binance_long"
            )
            signal = TradeSignal(
                symbol=opp.symbol,
                action="OPEN",
                direction=direction,
                spread_opportunity=opp,
                reason=reason,
                timestamp=now,
            )
            position = self.execute_entry(signal, size, self.config)
            if position:
                signals.append(signal)

        return signals


class LiveExecutor(BaseExecutor):
    """Live trading executor that places orders on Upbit/Binance."""

    def __init__(
        self,
        config: Dict,
        secrets: Dict,
        storage: SimpleStorage,
        dry_run: bool = False,
    ) -> None:
        self.config = config
        self.storage = storage
        self.dry_run = dry_run
        self.positions: List[Position] = []
        self.http = httpx.Client(timeout=10.0)
        exchanges = (secrets.get("exchanges") if secrets else {}) or {}
        self.upbit_keys = exchanges.get("upbit", {})
        self.binance_keys = exchanges.get("binance_futures", {})
        self.upbit_base = self.config["exchanges"]["upbit"]["base_url"].rstrip("/")
        self.binance_base = self.config["exchanges"]["binance_futures"]["base_url"].rstrip("/")

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def _format_decimal(self, value: float, precision: int = 8) -> str:
        fmt = f"{value:.{precision}f}"
        return fmt.rstrip("0").rstrip(".") or "0"

    def _upbit_market(self, symbol: str) -> str:
        return f"KRW-{symbol}"

    def _binance_symbol(self, symbol: str) -> str:
        return f"{symbol}USDT"

    def _place_upbit_order(
        self,
        market: str,
        side: str,
        ord_type: str,
        *,
        volume: Optional[float] = None,
        price: Optional[float] = None,
    ) -> dict:
        payload = {"market": market, "side": side, "ord_type": ord_type}
        if volume is not None:
            payload["volume"] = self._format_decimal(volume, 8)
        if price is not None:
            payload["price"] = self._format_decimal(price, 0)

        if self.dry_run:
            logger.info("[DRY-RUN] Upbit order %s", payload)
            return {"uuid": f"dry-upbit-{uuid4()}"}

        if not self.upbit_keys.get("access_key"):
            raise LiveTradingError("Upbit API key missing")

        query_string = urlencode(payload)
        query_hash = hashlib.sha512(query_string.encode()).hexdigest()
        jwt_payload = {
            "access_key": self.upbit_keys["access_key"],
            "nonce": str(uuid4()),
            "query_hash": query_hash,
            "query_hash_alg": "SHA512",
        }
        token = jwt.encode(jwt_payload, self.upbit_keys["secret_key"], algorithm="HS256")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{self.upbit_base}/v1/orders"
        try:
            response = self.http.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise LiveTradingError(f"Upbit order failed: {exc}") from exc

    def _place_binance_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        *,
        reduce_only: bool = False,
    ) -> dict:
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": self._format_decimal(quantity, 6),
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000,
        }
        if reduce_only:
            params["reduceOnly"] = "true"

        if self.dry_run:
            logger.info("[DRY-RUN] Binance order %s", params)
            return {"orderId": f"dry-binance-{uuid4()}"}

        if not self.binance_keys.get("api_key"):
            raise LiveTradingError("Binance Futures API key missing")

        query = urlencode(params)
        signature = hmac.new(
            self.binance_keys["secret_key"].encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        headers = {"X-MBX-APIKEY": self.binance_keys["api_key"]}
        url = f"{self.binance_base}/fapi/v1/order"
        try:
            response = self.http.post(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise LiveTradingError(f"Binance order failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Trading workflow
    # ------------------------------------------------------------------
    def _entry_plans(self, direction: str, size: float, opp: SpreadOpportunity):
        market = self._upbit_market(opp.symbol)
        symbol = self._binance_symbol(opp.symbol)
        notional = size * opp.upbit_price
        if direction == "upbit_long_binance_short":
            upbit_plan = {"side": "bid", "ord_type": "price", "price": notional}
            binance_plan = {"side": "SELL", "quantity": size, "reduce_only": False}
        else:
            upbit_plan = {"side": "ask", "ord_type": "market", "volume": size}
            binance_plan = {"side": "BUY", "quantity": size, "reduce_only": False}
        return market, symbol, upbit_plan, binance_plan

    def _exit_plans(self, direction: str, size: float, opp: SpreadOpportunity):
        market = self._upbit_market(opp.symbol)
        symbol = self._binance_symbol(opp.symbol)
        notional = size * opp.upbit_price
        if direction == "upbit_long_binance_short":
            upbit_plan = {"side": "ask", "ord_type": "market", "volume": size}
            binance_plan = {"side": "BUY", "quantity": size, "reduce_only": True}
        else:
            upbit_plan = {"side": "bid", "ord_type": "price", "price": notional}
            binance_plan = {"side": "SELL", "quantity": size, "reduce_only": True}
        return market, symbol, upbit_plan, binance_plan

    def _rollback_entry(
        self,
        direction: str,
        size: float,
        opp: SpreadOpportunity,
        executed_legs: List[str],
    ) -> None:
        if self.dry_run:
            return
        market = self._upbit_market(opp.symbol)
        symbol = self._binance_symbol(opp.symbol)
        if "upbit" in executed_legs:
            rollback_plan = {"side": "ask", "ord_type": "market", "volume": size}
            if direction == "upbit_short_binance_long":
                rollback_plan = {"side": "bid", "ord_type": "price", "price": size * opp.upbit_price}
            try:
                self._place_upbit_order(market, **rollback_plan)
            except LiveTradingError as exc:
                self.storage.log_error(f"Upbit rollback failed: {exc}")
        if "binance" in executed_legs:
            rollback_side = "BUY" if direction == "upbit_long_binance_short" else "SELL"
            try:
                self._place_binance_order(symbol, rollback_side, size, reduce_only=True)
            except LiveTradingError as exc:
                self.storage.log_error(f"Binance rollback failed: {exc}")

    def execute_entry(self, signal: TradeSignal, size: float, config: Dict) -> Optional[Position]:
        market, symbol, upbit_plan, binance_plan = self._entry_plans(signal.direction, size, signal.spread_opportunity)
        executed: List[str] = []
        try:
            if size <= 0:
                raise LiveTradingError("Position size must be greater than zero")
            self._place_upbit_order(market, **upbit_plan)
            executed.append("upbit")
            self._place_binance_order(symbol, **binance_plan)
            executed.append("binance")
        except LiveTradingError as exc:
            self._rollback_entry(signal.direction, size, signal.spread_opportunity, executed)
            raise

        position = Position(
            symbol=signal.symbol,
            direction=signal.direction or "upbit_long_binance_short",
            size=size,
            entry_upbit_price=signal.spread_opportunity.upbit_price,
            entry_binance_price=signal.spread_opportunity.binance_price,
            entry_spread_pct=signal.spread_opportunity.spread_pct,
            timestamp_open=datetime.now(timezone.utc),
        )
        self.positions.append(position)
        self.storage.log_position_open(position)
        return position

    def execute_exit(self, position: Position, signal: TradeSignal, config: Dict) -> bool:
        market, symbol, upbit_plan, binance_plan = self._exit_plans(position.direction, position.size, signal.spread_opportunity)
        executed: List[str] = []
        try:
            self._place_upbit_order(market, **upbit_plan)
            executed.append("upbit")
            self._place_binance_order(symbol, **binance_plan)
            executed.append("binance")
        except LiveTradingError as exc:
            self._rollback_entry(position.direction, position.size, signal.spread_opportunity, executed)
            raise

        usdkrw = config.get("fx", {}).get("usdkrw", 1350.0)
        pnl_krw, pnl_pct = calculate_pnl(
            position,
            signal.spread_opportunity.upbit_price,
            signal.spread_opportunity.binance_price,
            usdkrw,
        )
        position.close(
            exit_upbit_price=signal.spread_opportunity.upbit_price,
            exit_binance_price=signal.spread_opportunity.binance_price,
            exit_spread_pct=signal.spread_opportunity.spread_pct,
            pnl_krw=pnl_krw,
            pnl_pct=pnl_pct,
            timestamp_close=datetime.now(timezone.utc),
        )
        self.storage.log_position_close(position)
        return True

    def on_opportunity(self, opp: SpreadOpportunity, now: datetime) -> List[TradeSignal]:
        signals: List[TradeSignal] = []

        for position in [p for p in self.positions if p.status == "OPEN"]:
            should_close, reason = should_close_position(self.config, position, opp, now)
            if should_close:
                signal = TradeSignal(
                    symbol=position.symbol,
                    action="CLOSE",
                    direction=position.direction,
                    spread_opportunity=opp,
                    reason=reason,
                    timestamp=now,
                )
                try:
                    self.execute_exit(position, signal, self.config)
                    signals.append(signal)
                except LiveTradingError as exc:
                    error_msg = f"Close failed ({position.symbol}): {exc}"
                    logger.error(error_msg)
                    self.storage.log_error(error_msg)

        can_open, reason = can_open_new_position(self.config, self.positions, opp)
        if can_open:
            mid_price = (opp.upbit_price + opp.binance_price_krw) / 2 or opp.upbit_price
            size = compute_position_size_krw(self.config, mid_price)
            if size > 0:
                direction = (
                    "upbit_long_binance_short"
                    if opp.upbit_price <= opp.binance_price_krw
                    else "upbit_short_binance_long"
                )
                signal = TradeSignal(
                    symbol=opp.symbol,
                    action="OPEN",
                    direction=direction,
                    spread_opportunity=opp,
                    reason=reason,
                    timestamp=now,
                )
                try:
                    position = self.execute_entry(signal, size, self.config)
                    if position:
                        signals.append(signal)
                except LiveTradingError as exc:
                    error_msg = f"Entry failed ({opp.symbol}): {exc}"
                    logger.error(error_msg)
                    self.storage.log_error(error_msg)
        return signals
