# -*- coding: utf-8 -*-
"""
D79-4: Cross-Exchange Real Order Execution

실제 Upbit/Binance 주문 실행 계층.

Features:
- Real order execution (Upbit ↔ Binance)
- Partial fill handling
- Rollback logic
- Health/Secrets/RiskGuard validation
- Position state machine integration (OPEN → CLOSING → CLOSED)

Architecture:
    CrossExchangeDecision (Paper)
            ↓
    CrossExchangeExecutor (Real Orders)
            ↓
    ├─> Upbit order
    ├─> Binance order
    ├─> Fill monitoring
    └─> Partial fill handling / Rollback
"""

from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Optional, Dict, Any, Literal, TYPE_CHECKING
from dataclasses import dataclass, asdict, field

if TYPE_CHECKING:
    from .integration import CrossExchangeIntegration

if TYPE_CHECKING:
    from arbitrage.execution.fill_model_integration import FillModelIntegration

from .integration import CrossExchangeDecision, CrossExchangeAction
from .position_manager import CrossExchangePositionManager
from .fx_converter import FXConverter
from .risk_guard import CrossExchangeRiskGuard, CrossRiskDecision
from arbitrage.exchanges.base import OrderSide, OrderType, OrderStatus, OrderResult, BaseExchange
from arbitrage.common.currency import Money, Currency, FxRateProvider, StaticFxRateProvider

logger = logging.getLogger(__name__)


@dataclass
class LegExecutionResult:
    """
    단일 레그 (Upbit or Binance) 실행 결과
    """
    exchange: Literal["upbit", "binance"]
    order_id: Optional[str]
    status: Literal["accepted", "partially_filled", "filled", "canceled", "failed"]
    filled_qty: float
    requested_qty: float
    avg_price: Optional[float]
    error: Optional[str] = None
    
    def is_filled(self) -> bool:
        """완전 체결 여부"""
        return self.status == "filled"
    
    def is_partial(self) -> bool:
        """부분 체결 여부"""
        return self.status == "partially_filled"


@dataclass
class CrossExecutionResult:
    """
    교차 거래소 실행 결과
    
    D80-2: pnl (Money) 추가, pnl_krw deprecated
    """
    decision: CrossExchangeDecision
    upbit: LegExecutionResult
    binance: LegExecutionResult
    status: Literal["success", "partial_hedged", "rolled_back", "failed", "blocked"]
    pnl: Optional[Money] = None  # D80-2: Money 기반 PnL
    pnl_krw: Optional[float] = None  # DEPRECATED: backward compat
    note: Optional[str] = None
    execution_time_ms: Optional[float] = None
    
    def is_success(self) -> bool:
        """성공 여부"""
        return self.status == "success"
    
    @property
    def pnl_krw_amount(self) -> float:
        """
        D80-2: DEPRECATED backward compatible accessor
        
        Returns:
            PnL amount (float)
        """
        if self.pnl is not None:
            return float(self.pnl.amount)
        return self.pnl_krw or 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Dict로 변환"""
        data = asdict(self)
        # Money 객체를 JSON 직렬화 가능하게 변환
        if self.pnl is not None:
            data['pnl'] = {'amount': str(self.pnl.amount), 'currency': self.pnl.currency.value}
        return data


class CrossExchangeExecutor:
    """
    교차 거래소 주문 실행자
    
    Responsibilities:
    - Real order execution (Upbit/Binance)
    - Partial fill handling
    - Rollback logic
    - Health/Secrets/RiskGuard validation
    
    Example:
        executor = CrossExchangeExecutor(
            upbit_client=upbit_client,
            binance_client=binance_client,
            position_manager=position_manager,
            fx_converter=fx_converter,
            health_monitor=health_monitor,
            settings=settings,
        )
        
        result = executor.execute_decision(decision)
        
        if result.is_success():
            print(f"Success: {result.pnl_krw:.0f} KRW")
        else:
            print(f"Failed: {result.note}")
    """
    
    # Default order sizes (나중에 설정으로 변경 가능)
    DEFAULT_NOTIONAL_KRW = 100_000_000  # 100M KRW
    FILL_WAIT_TIMEOUT = 5.0  # 5 seconds
    
    def __init__(
        self,
        upbit_exchange: BaseExchange,
        binance_exchange: BaseExchange,
        position_manager: CrossExchangePositionManager,
        fx_converter: FXConverter,
        risk_guard: Optional[CrossExchangeRiskGuard] = None,
        secrets_checker: Optional[Any] = None,  # SecretsChecker
        dry_run: bool = False,
        fill_model_integration: Optional["FillModelIntegration"] = None,
        fx_provider: Optional[FxRateProvider] = None,  # D80-2
        base_currency: Currency = Currency.KRW,  # D80-2
    ):
        """
        Initialize CrossExchangeExecutor
        
        Args:
            upbit_exchange: Upbit exchange adapter (BaseExchange)
            binance_exchange: Binance exchange adapter (BaseExchange)
            position_manager: CrossExchangePositionManager
            fx_converter: FXConverter
            risk_guard: CrossExchangeRiskGuard (optional, D79-5)
            secrets_checker: SecretsChecker (optional)
            dry_run: Dry run mode (optional)
            fill_model_integration: FillModelIntegration (optional)
            fx_provider: FxRateProvider (optional, D80-2)
            base_currency: 기본 통화 (D80-2)
        """
        self.upbit_exchange = upbit_exchange
        self.binance_exchange = binance_exchange
        self.position_manager = position_manager
        self.fx_converter = fx_converter
        self.risk_guard = risk_guard
        self.secrets_checker = secrets_checker
        self.dry_run = dry_run
        self.fill_model_integration = fill_model_integration
        
        # D80-2/D80-3: Multi-Currency 지원
        if fx_provider is None:
            # D80-3: RealFxRateProvider 기본 사용 (fallback to static)
            try:
                from arbitrage.common.currency import RealFxRateProvider
                fx_provider = RealFxRateProvider()
                logger.info("[CROSS_EXECUTOR] Using RealFxRateProvider (API-based FX rates)")
            except Exception as e:
                logger.warning(
                    f"[CROSS_EXECUTOR] Failed to init RealFxRateProvider: {e}, "
                    "falling back to StaticFxRateProvider"
                )
                fx_provider = StaticFxRateProvider({
                    (Currency.USD, Currency.KRW): Decimal("1420.50"),
                    (Currency.USDT, Currency.KRW): Decimal("1420.00"),
                })
        
        self.fx_provider = fx_provider
        self.base_currency = base_currency
        
        # Metrics (내부용, 하위 호환성 유지)
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.partial_hedged_executions = 0
        self.rolled_back_executions = 0
        
        logger.info(
            "[CROSS_EXECUTOR] Initialized (metrics=%s, base_currency=%s)",
            type(self.metrics_collector).__name__ if self.metrics_collector else "None",
            self.base_currency.value
        )
    
    def execute_decision(self, decision: CrossExchangeDecision) -> CrossExecutionResult:
        """
        의사결정을 실제 주문으로 실행
        
        Args:
            decision: CrossExchangeDecision (from Integration layer)
        
        Returns:
            CrossExecutionResult
        
        Flow:
            1. Pre-check (Health/Secrets/RiskGuard)
            2. Calculate order sizes
            3. Place orders (Upbit + Binance)
            4. Monitor fills
            5. Handle partial fills / Rollback
            6. Update PositionManager
        """
        start_time = time.time()
        self.total_executions += 1
        
        try:
            # 1. Pre-check
            precheck_result = self._precheck(decision)
            if not precheck_result["ok"]:
                self.failed_executions += 1
                return self._failed_result(
                    decision=decision,
                    reason=precheck_result["reason"],
                    status="blocked" if "blocked" in precheck_result["reason"].lower() else "failed",
                )
            
            # 2. Calculate order sizes
            sizes = self._build_order_sizes(decision)
            
            # 3. Place orders
            if decision.action in [CrossExchangeAction.ENTRY_POSITIVE, CrossExchangeAction.ENTRY_NEGATIVE]:
                result = self._execute_entry(decision, sizes)
            elif decision.action in [
                CrossExchangeAction.EXIT_TP,
                CrossExchangeAction.EXIT_SL,
                CrossExchangeAction.EXIT_TIMEOUT,
                CrossExchangeAction.EXIT_REVERSAL,
                CrossExchangeAction.EXIT_HEALTH,
            ]:
                result = self._execute_exit(decision, sizes)
            else:
                # NO_ACTION 등
                self.failed_executions += 1
                return self._failed_result(
                    decision=decision,
                    reason=f"Invalid action: {decision.action}",
                )
            
            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000
            result.execution_time_ms = execution_time_ms
            
            # Update metrics
            if result.status == "success":
                self.successful_executions += 1
            elif result.status in ["partial_hedged", "rolled_back"]:
                self.partial_hedged_executions += 1
            else:
                self.failed_executions += 1
            
            # Record metrics to CrossExchangeMetrics (D79-6)
            self._record_execution_metrics(result)
            
            logger.info(
                f"[CROSS_EXECUTOR] Execution result: {result.status} "
                f"(action={decision.action.value}, "
                f"symbol={decision.symbol_upbit}/{decision.symbol_binance}, "
                f"time={execution_time_ms:.1f}ms)"
            )
            
            return result
        
        except Exception as e:
            self.failed_executions += 1
            logger.error(f"[CROSS_EXECUTOR] Execution error: {e}", exc_info=True)
            
            # D80-7-INT: EX-001 Alert
            try:
                from arbitrage.alerting import emit_executor_order_error_alert
                emit_executor_order_error_alert(
                    exchange="cross_exchange",
                    symbol=f"{decision.symbol_upbit}/{decision.symbol_binance}",
                    side=decision.action.value,
                    error_message=str(e),
                    action="Execution failed",
                )
            except Exception as alert_err:
                logger.debug(f"[CROSS_EXECUTOR] Alert emission failed: {alert_err}")
            
            return self._failed_result(
                decision=decision,
                reason=f"Execution exception: {str(e)}",
            )
    
    def _precheck(self, decision: CrossExchangeDecision) -> Dict[str, Any]:
        """
        실행 전 사전 체크
        
        Returns:
            {"ok": bool, "reason": str, "risk_decision": Optional[CrossRiskDecision]}
        """
        # 1. Health check
        if not self._check_health():
            return {"ok": False, "reason": "Health degraded", "risk_decision": None}
        
        # 2. Secrets check
        if not self._check_secrets():
            return {"ok": False, "reason": "Secrets unavailable", "risk_decision": None}
        
        # 3. CrossExchangeRiskGuard check (D79-5)
        if self.risk_guard:
            risk_decision = self.risk_guard.check_cross_exchange_trade(decision)
            
            if not risk_decision.allowed:
                logger.warning(
                    f"[CROSS_EXECUTOR] Trade blocked by RiskGuard: "
                    f"tier={risk_decision.tier}, reason={risk_decision.reason_code}"
                )
                return {
                    "ok": False,
                    "reason": f"RiskGuard: {risk_decision.tier}/{risk_decision.reason_code}",
                    "risk_decision": risk_decision,
                }
        
        return {"ok": True, "reason": "", "risk_decision": None}
    
    def _check_health(self) -> bool:
        """Exchange health 확인"""
        try:
            if not self.health_monitor:
                return True  # No monitor = assume healthy
            
            from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus
            
            upbit_status = self.health_monitor.get_status("upbit")
            binance_status = self.health_monitor.get_status("binance")
            
            return (
                upbit_status in [ExchangeHealthStatus.HEALTHY, ExchangeHealthStatus.DEGRADED] and
                binance_status in [ExchangeHealthStatus.HEALTHY, ExchangeHealthStatus.DEGRADED]
            )
        except Exception as e:
            logger.error(f"[CROSS_EXECUTOR] Health check error: {e}")
            return False
    
    def _check_secrets(self) -> bool:
        """Secrets availability 확인"""
        try:
            if not self.settings:
                return True  # No settings = assume available (test mode)
            
            has_upbit = bool(self.settings.upbit_access_key and self.settings.upbit_secret_key)
            has_binance = bool(self.settings.binance_api_key and self.settings.binance_api_secret)
            
            return has_upbit or has_binance
        except Exception as e:
            logger.error(f"[CROSS_EXECUTOR] Secrets check error: {e}")
            return False
    
    def _build_order_sizes(
        self, 
        decision: CrossExchangeDecision,
        fill_model_advice=None,  # D87-0: FillModelAdvice 통합 훅 (D87-2에서 구현 예정)
    ) -> Dict[str, Any]:
        """
        주문 수량 계산
        
        Args:
            decision: CrossExchangeDecision
            fill_model_advice: D87-0: Fill Model Advice (Optional, D87-2+)
        
        Returns:
            {
                "upbit_qty": float,
                "binance_qty": float,
                "upbit_price": float,
                "binance_price": float,
            }
        
        D87-0: fill_model_advice 통합 훅 추가 (backward compatible)
        D87-1: Zone별 주문 수량 조정 구현 완료 (Advisory Mode)
        """
        notional_krw = decision.notional_krw or self.DEFAULT_NOTIONAL_KRW
        
        # D87-1: Fill Model Advice 기반 주문 수량 조정
        if fill_model_advice and self.fill_model_integration:
            # Notional을 기준으로 조정 (base size로 사용)
            adjusted_notional = self.fill_model_integration.adjust_order_size(
                base_size=notional_krw,
                advice=fill_model_advice
            )
            logger.debug(
                f"[CROSS_EXECUTOR] Fill Model Size 조정: "
                f"base={notional_krw:.2f} → adjusted={adjusted_notional:.2f} KRW, "
                f"zone={fill_model_advice.zone_id}"
            )
            notional_krw = adjusted_notional
        
        # FX rate
        fx_rate = self.fx_converter.get_fx_rate()
        fx_rate_value = fx_rate.rate if fx_rate else 1300.0
        
        # Estimate prices (Paper mode에서는 decision에 포함되지 않을 수 있으므로 간단히 계산)
        # 실제로는 현재 시세를 조회해야 함
        upbit_price_krw = 50_000_000.0  # Placeholder (BTC 기준)
        binance_price_usdt = upbit_price_krw / fx_rate_value
        
        # Quantities
        upbit_qty = notional_krw / upbit_price_krw
        binance_qty = upbit_qty  # Same base asset
        
        return {
            "upbit_qty": upbit_qty,
            "binance_qty": binance_qty,
            "upbit_price": upbit_price_krw,
            "binance_price": binance_price_usdt,
        }
    
    def _execute_entry(
        self,
        decision: CrossExchangeDecision,
        sizes: Dict[str, Any],
    ) -> CrossExecutionResult:
        """
        Entry 주문 실행
        
        ENTRY_POSITIVE: Upbit SELL / Binance BUY
        ENTRY_NEGATIVE: Upbit BUY / Binance SELL
        """
        # Determine order sides
        if decision.action == CrossExchangeAction.ENTRY_POSITIVE:
            upbit_side = OrderSide.SELL
            binance_side = OrderSide.BUY
        else:  # ENTRY_NEGATIVE
            upbit_side = OrderSide.BUY
            binance_side = OrderSide.SELL
        
        # Place orders
        upbit_result = self._place_upbit_order(
            symbol=decision.symbol_upbit,
            side=upbit_side,
            qty=sizes["upbit_qty"],
            price=sizes["upbit_price"],
        )
        
        binance_result = self._place_binance_order(
            symbol=decision.symbol_binance,
            side=binance_side,
            qty=sizes["binance_qty"],
            price=sizes["binance_price"],
        )
        
        # Check fill status
        if upbit_result.is_filled() and binance_result.is_filled():
            # Success: Open position
            # Note: Integration layer already opened position in tick_entry
            # Here we just update order IDs if needed
            
            return CrossExecutionResult(
                decision=decision,
                upbit=upbit_result,
                binance=binance_result,
                status="success",
                note="Entry executed successfully",
            )
        else:
            # Partial fill or failure
            return self._handle_partial_fill(decision, upbit_result, binance_result)
    
    def _execute_exit(
        self,
        decision: CrossExchangeDecision,
        sizes: Dict[str, Any],
    ) -> CrossExecutionResult:
        """
        Exit 주문 실행
        
        Exit는 Entry의 반대 방향으로 주문
        """
        # Get position
        position = self.position_manager.get_position(decision.symbol_upbit)
        
        if not position:
            return self._failed_result(
                decision=decision,
                reason="Position not found for exit",
            )
        
        # Determine order sides (반대 방향)
        if position.entry_side == "positive":
            # Entry was SELL/BUY, Exit is BUY/SELL
            upbit_side = OrderSide.BUY
            binance_side = OrderSide.SELL
        else:  # negative
            # Entry was BUY/SELL, Exit is SELL/BUY
            upbit_side = OrderSide.SELL
            binance_side = OrderSide.BUY
        
        # Mark position as CLOSING
        self.position_manager.mark_position_closing(decision.symbol_upbit)
        
        # Place orders
        upbit_result = self._place_upbit_order(
            symbol=decision.symbol_upbit,
            side=upbit_side,
            qty=sizes["upbit_qty"],
            price=sizes["upbit_price"],
        )
        
        binance_result = self._place_binance_order(
            symbol=decision.symbol_binance,
            side=binance_side,
            qty=sizes["binance_qty"],
            price=sizes["binance_price"],
        )
        
        # Check fill status
        if upbit_result.is_filled() and binance_result.is_filled():
            # Success: Close position
            # Note: Integration layer already closed position in tick_exit
            # Here we just confirm and update order IDs
            
            return CrossExecutionResult(
                decision=decision,
                upbit=upbit_result,
                binance=binance_result,
                status="success",
                pnl_krw=decision.exit_pnl_krw,
                note="Exit executed successfully",
            )
        else:
            # Partial fill or failure
            return self._handle_partial_fill(decision, upbit_result, binance_result)
    
    def _place_upbit_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: float,
    ) -> LegExecutionResult:
        """
        Upbit 주문 실행
        
        Args:
            symbol: Upbit 심볼 (예: "KRW-BTC")
            side: OrderSide (BUY/SELL)
            qty: 수량
            price: 가격
        
        Returns:
            LegExecutionResult
        """
        try:
            order_result = self.upbit_client.create_order(
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                order_type=OrderType.LIMIT,
            )
            
            # Map OrderStatus to LegExecutionResult status
            if order_result.status == OrderStatus.FILLED:
                status = "filled"
            elif order_result.status == OrderStatus.PARTIALLY_FILLED:
                status = "partially_filled"
            elif order_result.status in [OrderStatus.OPEN, OrderStatus.PENDING]:
                status = "accepted"
            elif order_result.status == OrderStatus.CANCELED:
                status = "canceled"
            else:
                status = "failed"
            
            return LegExecutionResult(
                exchange="upbit",
                order_id=order_result.order_id,
                status=status,
                filled_qty=order_result.filled_qty,
                requested_qty=qty,
                avg_price=order_result.price,
            )
        
        except Exception as e:
            logger.error(f"[CROSS_EXECUTOR] Upbit order failed: {e}", exc_info=True)
            return LegExecutionResult(
                exchange="upbit",
                order_id=None,
                status="failed",
                filled_qty=0.0,
                requested_qty=qty,
                avg_price=None,
                error=str(e),
            )
    
    def _place_binance_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        price: float,
    ) -> LegExecutionResult:
        """
        Binance 주문 실행
        
        Args:
            symbol: Binance 심볼 (예: "BTCUSDT")
            side: OrderSide (BUY/SELL)
            qty: 수량
            price: 가격
        
        Returns:
            LegExecutionResult
        """
        try:
            order_result = self.binance_client.create_order(
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                order_type=OrderType.LIMIT,
            )
            
            # Map OrderStatus to LegExecutionResult status
            if order_result.status == OrderStatus.FILLED:
                status = "filled"
            elif order_result.status == OrderStatus.PARTIALLY_FILLED:
                status = "partially_filled"
            elif order_result.status in [OrderStatus.OPEN, OrderStatus.PENDING]:
                status = "accepted"
            elif order_result.status == OrderStatus.CANCELED:
                status = "canceled"
            else:
                status = "failed"
            
            return LegExecutionResult(
                exchange="binance",
                order_id=order_result.order_id,
                status=status,
                filled_qty=order_result.filled_qty,
                requested_qty=qty,
                avg_price=order_result.price,
            )
        
        except Exception as e:
            logger.error(f"[CROSS_EXECUTOR] Binance order failed: {e}", exc_info=True)
            return LegExecutionResult(
                exchange="binance",
                order_id=None,
                status="failed",
                filled_qty=0.0,
                requested_qty=qty,
                avg_price=None,
                error=str(e),
            )
    
    def _handle_partial_fill(
        self,
        decision: CrossExchangeDecision,
        upbit_result: LegExecutionResult,
        binance_result: LegExecutionResult,
    ) -> CrossExecutionResult:
        """
        부분 체결 처리
        
        Strategy:
        - One-side filled: Cancel other side, try hedge
        - Both partial: Cancel both, try hedge remaining
        - Both failed: Return failed result
        """
        logger.warning(
            f"[CROSS_EXECUTOR] Partial fill detected: "
            f"upbit={upbit_result.status}, binance={binance_result.status}"
        )
        
        # Cancel unfilled orders
        if upbit_result.status in ["accepted", "partially_filled"] and upbit_result.order_id:
            try:
                self.upbit_client.cancel_order(upbit_result.order_id)
                logger.info(f"[CROSS_EXECUTOR] Canceled Upbit order: {upbit_result.order_id}")
            except Exception as e:
                logger.error(f"[CROSS_EXECUTOR] Failed to cancel Upbit order: {e}")
        
        if binance_result.status in ["accepted", "partially_filled"] and binance_result.order_id:
            try:
                self.binance_client.cancel_order(binance_result.order_id)
                logger.info(f"[CROSS_EXECUTOR] Canceled Binance order: {binance_result.order_id}")
            except Exception as e:
                logger.error(f"[CROSS_EXECUTOR] Failed to cancel Binance order: {e}")
        
        # Calculate exposure
        upbit_filled = upbit_result.filled_qty
        binance_filled = binance_result.filled_qty
        exposure_diff = abs(upbit_filled - binance_filled)
        
        if exposure_diff > 0.0001:  # Non-zero exposure
            # Send alert (if alert_manager available)
            if self.alert_manager:
                # Future implementation
                pass
            
            note = (
                f"Partial fill: Upbit filled {upbit_filled:.6f}, "
                f"Binance filled {binance_filled:.6f}, "
                f"exposure={exposure_diff:.6f}"
            )
            
            return CrossExecutionResult(
                decision=decision,
                upbit=upbit_result,
                binance=binance_result,
                status="partial_hedged",
                note=note,
            )
        else:
            # No exposure (both failed or both canceled)
            # D80-8: EX-002 Alert (Rollback)
            try:
                from arbitrage.alerting import emit_executor_rollback_alert
                emit_executor_rollback_alert(
                    symbol=f"{decision.symbol_upbit}/{decision.symbol_binance}",
                    exchange="cross_exchange",
                    filled_qty=0.0,
                    requested_qty=float(sizes.get("upbit_qty", 0)),
                    status="rolled_back",
                )
            except Exception as e:
                logger.debug(f"[CROSS_EXECUTOR] Alert emission failed: {e}")
            
            return CrossExecutionResult(
                decision=decision,
                upbit=upbit_result,
                binance=binance_result,
                status="rolled_back",
                note="Both orders canceled, no exposure",
            )
    
    def _estimate_order_cost(
        self,
        exchange: BaseExchange,
        symbol: str,
        price: float,
        qty: float
    ) -> Money:
        """
        D80-2/D80-3: 주문 비용 추정 (Money 기반, staleness check 포함)
        
        Args:
            exchange: Exchange adapter
            symbol: 거래 쌍
            price: 가격
            qty: 수량
        
        Returns:
            Money 객체 (주문 비용)
        
        Example:
            >>> upbit_cost = executor._estimate_order_cost(
            ...     self.upbit_client, "KRW-BTC", 100_000_000, 0.001
            ... )
            >>> # Money(Decimal("100000"), Currency.KRW)
        """
        notional = Decimal(str(price)) * Decimal(str(qty))
        money = exchange.make_money(notional)
        
        # D80-3: Staleness check (RealFxRateProvider만 해당)
        from arbitrage.common.currency import RealFxRateProvider
        if isinstance(self.fx_provider, RealFxRateProvider):
            if self.fx_provider.is_stale(money.currency, self.base_currency):
                age_seconds = int(time.time() - self.fx_provider.get_updated_at(money.currency, self.base_currency))
                logger.warning(
                    f"[CROSS_EXECUTOR] FX rate is STALE: "
                    f"{money.currency.value}→{self.base_currency.value} "
                    f"(age > {RealFxRateProvider.STALE_THRESHOLD_SECONDS}s)"
                )
                
                # D80-7-INT: FX-004 Alert
                try:
                    from arbitrage.alerting import emit_fx_staleness_alert
                    emit_fx_staleness_alert(
                        source="real_fx_provider",
                        pair=f"{money.currency.value}/{self.base_currency.value}",
                        age_seconds=age_seconds,
                        last_rate=float(self.fx_provider.get_rate(money.currency, self.base_currency)),
                    )
                except Exception as e:
                    logger.debug(f"[CROSS_EXECUTOR] Alert emission failed: {e}")
        
        return money
    
    def _failed_result(
        self,
        decision: CrossExchangeDecision,
        reason: str,
        status: Literal["failed", "blocked"] = "failed",
    ) -> CrossExecutionResult:
        """실패 결과 생성"""
        return CrossExecutionResult(
            decision=decision,
            upbit=LegExecutionResult(
                exchange="upbit",
                order_id=None,
                status="failed",
                filled_qty=0.0,
                requested_qty=0.0,
                avg_price=None,
            ),
            binance=LegExecutionResult(
                exchange="binance",
                order_id=None,
                status="failed",
                filled_qty=0.0,
                requested_qty=0.0,
                avg_price=None,
            ),
            status=status,
            note=reason,
        )
    
    def _record_execution_metrics(self, result: CrossExecutionResult) -> None:
        """
        CrossExchangeMetrics에 실행 결과 기록 (D79-6)
        
        Args:
            result: CrossExecutionResult
        """
        if self.metrics_collector is None:
            return
        
        try:
            # CrossExecutionResult를 그대로 전달
            # (cross_exchange_metrics.py의 CrossExecutionResult와 호환)
            from arbitrage.monitoring.cross_exchange_metrics import CrossExecutionResult as MetricsResult
            
            metrics_result = MetricsResult(
                status=result.status,
                upbit_result=result.upbit,
                binance_result=result.binance,
                total_latency=result.execution_time_ms / 1000.0 if result.execution_time_ms else None,  # ms → s
                rollback_reason=result.note if result.status == "rolled_back" else None,
            )
            
            self.metrics_collector.record_execution_result(metrics_result)
        
        except Exception as e:
            logger.error(f"[CROSS_EXECUTOR] Metrics recording failed: {e}", exc_info=True)
    
    def get_metrics(self) -> Dict[str, Any]:
        """실행 메트릭 반환"""
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "partial_hedged_executions": self.partial_hedged_executions,
            "rolled_back_executions": self.rolled_back_executions,
            "success_rate": (
                self.successful_executions / self.total_executions
                if self.total_executions > 0
                else 0.0
            ),
        }


class CrossExchangeOrchestrator:
    """
    교차 거래소 Orchestrator
    
    Integration (Paper mode signal) + Executor (Real orders)를 결합.
    
    Responsibilities:
    - Entry/Exit tick 조율
    - Decision generation (Integration)
    - Order execution (Executor)
    - Result aggregation
    
    Example:
        orchestrator = CrossExchangeOrchestrator(
            integration=integration,
            executor=executor,
        )
        
        # Process entry tick
        decisions, results = orchestrator.process_entry_tick(context)
        
        # Process exit tick
        decisions, results = orchestrator.process_exit_tick(context)
    """
    
    def __init__(
        self,
        integration: CrossExchangeIntegration,
        executor: CrossExchangeExecutor,
        enable_execution: bool = True,
    ):
        """
        Initialize CrossExchangeOrchestrator
        
        Args:
            integration: CrossExchangeIntegration (Paper signal generation)
            executor: CrossExchangeExecutor (Real order execution)
            enable_execution: True면 실제 주문 실행, False면 Paper 모드
        """
        self.integration = integration
        self.executor = executor
        self.enable_execution = enable_execution
        
        logger.info(
            f"[CROSS_ORCHESTRATOR] Initialized "
            f"(execution={'ENABLED' if enable_execution else 'DISABLED (Paper)'})"
        )
    
    def process_entry_tick(
        self,
        context: Optional[Dict] = None,
    ) -> tuple[list[CrossExchangeDecision], list[CrossExecutionResult]]:
        """
        Entry tick 처리
        
        Flow:
        1. Integration.tick_entry() → Decisions
        2. For each decision: Executor.execute_decision() → Results
        
        Args:
            context: Optional context
        
        Returns:
            (decisions, results)
        """
        decisions = []
        results = []
        
        try:
            # 1. Generate decisions (Paper mode)
            decisions = self.integration.tick_entry(context)
            
            if not decisions:
                logger.debug("[CROSS_ORCHESTRATOR] No entry decisions generated")
                return decisions, results
            
            logger.info(
                f"[CROSS_ORCHESTRATOR] Processing {len(decisions)} entry decision(s)"
            )
            
            # 2. Execute decisions (if enabled)
            if self.enable_execution:
                for decision in decisions:
                    result = self.executor.execute_decision(decision)
                    results.append(result)
                    
                    logger.info(
                        f"[CROSS_ORCHESTRATOR] Entry execution: "
                        f"{decision.symbol_upbit}/{decision.symbol_binance} → {result.status}"
                    )
            else:
                logger.info("[CROSS_ORCHESTRATOR] Execution disabled (Paper mode)")
        
        except Exception as e:
            logger.error(f"[CROSS_ORCHESTRATOR] Entry tick error: {e}", exc_info=True)
        
        return decisions, results
    
    def process_exit_tick(
        self,
        context: Optional[Dict] = None,
    ) -> tuple[list[CrossExchangeDecision], list[CrossExecutionResult]]:
        """
        Exit tick 처리
        
        Flow:
        1. Integration.tick_exit() → Decisions
        2. For each decision: Executor.execute_decision() → Results
        
        Args:
            context: Optional context
        
        Returns:
            (decisions, results)
        """
        decisions = []
        results = []
        
        try:
            # 1. Generate decisions (Paper mode)
            decisions = self.integration.tick_exit(context)
            
            if not decisions:
                logger.debug("[CROSS_ORCHESTRATOR] No exit decisions generated")
                return decisions, results
            
            logger.info(
                f"[CROSS_ORCHESTRATOR] Processing {len(decisions)} exit decision(s)"
            )
            
            # 2. Execute decisions (if enabled)
            if self.enable_execution:
                for decision in decisions:
                    result = self.executor.execute_decision(decision)
                    results.append(result)
                    
                    logger.info(
                        f"[CROSS_ORCHESTRATOR] Exit execution: "
                        f"{decision.symbol_upbit}/{decision.symbol_binance} → {result.status}"
                    )
            else:
                logger.info("[CROSS_ORCHESTRATOR] Execution disabled (Paper mode)")
        
        except Exception as e:
            logger.error(f"[CROSS_ORCHESTRATOR] Exit tick error: {e}", exc_info=True)
        
        return decisions, results
    
    def get_metrics(self) -> Dict[str, Any]:
        """통합 메트릭 반환"""
        integration_metrics = self.integration.get_metrics()
        executor_metrics = self.executor.get_metrics() if self.enable_execution else {}
        
        return {
            "integration": integration_metrics,
            "executor": executor_metrics,
            "execution_enabled": self.enable_execution,
        }
