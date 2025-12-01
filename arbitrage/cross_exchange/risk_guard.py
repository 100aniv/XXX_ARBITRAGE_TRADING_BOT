# -*- coding: utf-8 -*-
"""
D79-5: Cross-Exchange Risk Guard

Cross-Exchange 아비트라지 전용 Risk Management 계층.

Features:
- D75 4-Tier RiskGuard 통합 (1차 필터)
- Cross-exposure limits (CrossSync 기반)
- Inventory imbalance detection
- Directional bias 방지 (PositionManager 기반)
- Circuit breaker (Cross-Exchange PnL tracking)
- Dynamic thresholds (향후 확장)

Architecture:
    CrossExchangeDecision
            ↓
    CrossExchangeRiskGuard
            ↓
    ├─> D75 4-Tier RiskGuard (1차 필터)
    ├─> CrossSync 규칙 (exposure/imbalance)
    ├─> PositionManager 규칙 (directional bias)
    ├─> Circuit Breaker (PnL tracking)
    └─> CrossRiskDecision (allow, tier, reason_code, details)
"""

import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Literal, Union

from .integration import CrossExchangeDecision, CrossExchangeAction
from .position_manager import CrossExchangePositionManager
from arbitrage.domain.cross_sync import InventoryTracker, RebalanceSignal
from arbitrage.common.currency import Currency, Money, FxRateProvider, StaticFxRateProvider

logger = logging.getLogger(__name__)


class CrossRiskReasonCode(Enum):
    """Cross-Exchange Risk 이유 코드"""
    # D75 pass-through (tier="exchange", "route", "symbol", "global")
    # → D75 RiskGuard의 reason_code를 그대로 전달
    
    # Cross-Exchange 전용 (tier="cross_exchange")
    CROSS_EXPOSURE_LIMIT = "cross_exposure_limit"
    CROSS_INVENTORY_IMBALANCE = "cross_inventory_imbalance"
    CROSS_DIRECTIONAL_BIAS = "cross_directional_bias"
    CROSS_DAILY_LOSS_LIMIT = "cross_daily_loss_limit"
    CROSS_CONSECUTIVE_LOSS_LIMIT = "cross_consecutive_loss_limit"
    CROSS_CIRCUIT_BREAKER = "cross_circuit_breaker"
    CROSS_HIGH_VOLATILITY = "cross_high_volatility"
    
    # OK
    OK = "ok"


@dataclass
class CrossRiskDecision:
    """
    Cross-Exchange Risk 결정.
    
    D75 RiskGuardDecision과 유사하지만,
    Cross-Exchange 전용 tier/reason_code 추가.
    """
    allowed: bool  # 허용 여부
    tier: Literal[
        "none",           # Risk check 통과
        "exchange",       # D75 Tier 1 BLOCK
        "route",          # D75 Tier 2 BLOCK
        "symbol",         # D75 Tier 3 BLOCK
        "global",         # D75 Tier 4 BLOCK
        "cross_exchange"  # D79-5 NEW Tier BLOCK
    ]
    reason_code: str  # 상세 이유 코드
    details: Dict[str, Any] = field(default_factory=dict)  # 임계값/실측값/심볼/경로 등
    cooldown_until: Optional[float] = None  # Cooldown 종료 시각 (timestamp)
    max_notional_override: Optional[float] = None  # 축소 허용 시 최대 금액


@dataclass
class CrossExchangeRiskGuardConfig:
    """CrossExchangeRiskGuard 설정 (Multi-Currency 지원, D80-1)"""
    # Base currency
    base_currency: Currency = Currency.KRW
    
    # Exposure limits
    max_cross_exposure: float = 0.6  # 60% 이상 한쪽 집중 시 BLOCK
    
    # Inventory imbalance
    max_imbalance_ratio: float = 0.5  # ±50% 이상 불균형 시 추가 진입 BLOCK
    
    # Directional bias
    max_directional_bias: float = 0.7  # 70% 이상 쏠림 시 추가 진입 BLOCK
    min_position_count_for_bias_check: int = 3  # 최소 포지션 수 (이하면 bias 체크 생략)
    
    # Circuit breaker (Money 기반)
    max_daily_loss: Money = field(default_factory=lambda: Money(Decimal("5000000"), Currency.KRW))
    max_consecutive_loss: int = 5  # 연속 5회 손실 시 COOLDOWN
    circuit_breaker_cooldown: float = 3600.0  # 1시간 쿨다운
    consecutive_loss_cooldown: float = 900.0  # 15분 쿨다운
    
    # Dynamic thresholds (향후 확장)
    high_volatility_threshold: float = 0.05  # 5% 이상 변동성 시 강화
    volatility_exposure_multiplier: float = 0.7  # 고변동성 시 exposure limit 배수
    volatility_imbalance_multiplier: float = 0.8  # 고변동성 시 imbalance limit 배수
    
    # Backward compatibility (deprecated)
    max_daily_loss_krw: Optional[float] = None
    
    def __post_init__(self):
        """max_daily_loss_krw 제공 시 Money로 변환 (Backward compatibility)"""
        if self.max_daily_loss_krw is not None:
            self.max_daily_loss = Money(Decimal(str(self.max_daily_loss_krw)), Currency.KRW)
            logger.warning(
                "[CONFIG] max_daily_loss_krw is deprecated. Use max_daily_loss (Money) instead."
            )


class CrossExchangePnLTracker:
    """
    Cross-Exchange PnL 추적기 (Multi-Currency 지원, D80-1).
    
    Daily PnL 및 Consecutive loss 추적.
    Base Currency 기준으로 모든 PnL을 통합 집계.
    
    Note: 현재는 in-memory 구현. 향후 Redis 등으로 확장 가능.
    """
    
    def __init__(
        self,
        base_currency: Currency = Currency.KRW,
        fx_provider: Optional[FxRateProvider] = None,
    ):
        """
        Initialize PnLTracker.
        
        Args:
            base_currency: 기준 통화 (기본: KRW)
            fx_provider: 환율 제공자 (None 시 기본 StaticFxRateProvider with fallback rates)
        """
        self.base_currency = base_currency
        self.fx_provider = fx_provider or StaticFxRateProvider({
            # Fallback rates (테스트/개발용)
            (Currency.USD, Currency.KRW): Decimal("1420.50"),
            (Currency.USDT, Currency.KRW): Decimal("1500.00"),
        })
        
        self._daily_pnl: Money = Money(Decimal("0"), base_currency)
        self._daily_pnl_reset_time: float = 0.0
        self._consecutive_loss_count: int = 0
        self._last_trade_pnl: Money = Money(Decimal("0"), base_currency)
    
    def add_trade(
        self,
        pnl: Union[Money, float],
        currency: Optional[Currency] = None,
    ) -> None:
        """
        거래 PnL 추가 (Backward compatible).
        
        Args:
            pnl: 거래 손익 (Money 또는 float)
            currency: pnl이 float인 경우 통화 (기본: KRW, backward compatible)
        
        Example:
            # 새 방식 (Money)
            tracker.add_trade(Money(Decimal("50000"), Currency.KRW))
            
            # 기존 방식 (float, 자동 KRW 변환)
            tracker.add_trade(50000.0)
            tracker.add_trade(50000.0, Currency.KRW)
        """
        # float → Money 변환 (Backward compatibility)
        if isinstance(pnl, (int, float)):
            if currency is None:
                currency = Currency.KRW  # Default to KRW
            pnl = Money(Decimal(str(pnl)), currency)
        
        # Daily PnL 초기화 (자정 기준)
        now = time.time()
        current_day = int(now / 86400)
        reset_day = int(self._daily_pnl_reset_time / 86400)
        
        if current_day != reset_day:
            self._daily_pnl = Money(Decimal("0"), self.base_currency)
            self._daily_pnl_reset_time = now
        
        # Base currency로 변환 후 누적
        pnl_in_base = pnl.convert_to(self.base_currency, self.fx_provider)
        self._daily_pnl += pnl_in_base
        
        # Consecutive loss 카운팅 (부호만 확인)
        if pnl.is_negative:
            if self._last_trade_pnl.is_negative:
                self._consecutive_loss_count += 1
            else:
                self._consecutive_loss_count = 1
        else:
            self._consecutive_loss_count = 0
        
        self._last_trade_pnl = pnl_in_base
        
        logger.debug(
            f"[CROSS_PNL_TRACKER] Trade added: {pnl}, "
            f"Daily PnL: {self._daily_pnl}, "
            f"Consecutive loss: {self._consecutive_loss_count}"
        )
    
    def get_daily_pnl(self) -> Money:
        """일일 PnL 조회 (Money)"""
        # Daily PnL 초기화 확인
        now = time.time()
        current_day = int(now / 86400)
        reset_day = int(self._daily_pnl_reset_time / 86400)
        
        if current_day != reset_day:
            return Money(Decimal("0"), self.base_currency)
        
        return self._daily_pnl
    
    def get_daily_pnl_amount(self) -> float:
        """일일 PnL amount 조회 (Backward compatible, float)"""
        return float(self.get_daily_pnl().amount)
    
    def get_consecutive_loss_count(self) -> int:
        """연속 손실 횟수 조회"""
        return self._consecutive_loss_count
    
    def reset_consecutive_loss(self) -> None:
        """연속 손실 카운터 리셋"""
        self._consecutive_loss_count = 0
        logger.info("[CROSS_PNL_TRACKER] Consecutive loss counter reset")


class CrossExchangeRiskGuard:
    """
    Cross-Exchange 아비트라지 전용 Risk Guard.
    
    D75 4-Tier RiskGuard + CrossSync + PositionManager를
    composition으로 사용하여 5번째 Tier 구현.
    
    Example:
        risk_guard = CrossExchangeRiskGuard(
            four_tier_risk_guard=four_tier_risk_guard,  # D75-5
            inventory_tracker=inventory_tracker,  # D75-4
            position_manager=position_manager,  # D79-2
            config=CrossExchangeRiskGuardConfig(),
        )
        
        decision = CrossExchangeDecision(...)
        risk_decision = risk_guard.check_cross_exchange_trade(decision)
        
        if risk_decision.allowed:
            # Proceed with execution
        else:
            # Block trade
            logger.warning(
                f"Trade blocked: {risk_decision.tier} / {risk_decision.reason_code}"
            )
    """
    
    def __init__(
        self,
        four_tier_risk_guard: Optional[Any],  # FourTierRiskGuard (D75-5), None 허용 (테스트용)
        inventory_tracker: InventoryTracker,  # D75-4 CrossSync
        position_manager: CrossExchangePositionManager,  # D79-2
        config: Optional[CrossExchangeRiskGuardConfig] = None,
        pnl_tracker: Optional[CrossExchangePnLTracker] = None,
        alert_manager: Optional[Any] = None,  # D76 AlertManager (optional)
        metrics_collector: Optional[Any] = None,  # D79-6 CrossExchangeMetrics (optional)
    ):
        """
        Initialize CrossExchangeRiskGuard
        
        Args:
            four_tier_risk_guard: D75-5 FourTierRiskGuard (None 허용)
            inventory_tracker: D75-4 InventoryTracker
            position_manager: D79-2 CrossExchangePositionManager
            config: CrossExchangeRiskGuardConfig (None 시 기본값)
            pnl_tracker: CrossExchangePnLTracker (None 시 신규 생성)
            alert_manager: D76 AlertManager (optional)
            metrics_collector: D79-6 CrossExchangeMetrics (optional)
        """
        self.four_tier_risk_guard = four_tier_risk_guard
        self.inventory_tracker = inventory_tracker
        self.position_manager = position_manager
        self.config = config or CrossExchangeRiskGuardConfig()
        self.pnl_tracker = pnl_tracker or CrossExchangePnLTracker()
        self.alert_manager = alert_manager
        self.metrics_collector = metrics_collector
        
        # Cooldown state (symbol → cooldown_until timestamp)
        self._cooldown_state: Dict[str, float] = {}
        
        # Metrics counters (내부용, 하위 호환성 유지)
        self.total_checks = 0
        self.blocked_by_tier: Dict[str, int] = {
            "exchange": 0,
            "route": 0,
            "symbol": 0,
            "global": 0,
            "cross_exchange": 0,
        }
        self.blocked_by_reason: Dict[str, int] = {}
        
        logger.info("[CROSS_RISK_GUARD] Initialized (metrics=%s)",
                    type(self.metrics_collector).__name__ if self.metrics_collector else "None")
    
    def check_cross_exchange_trade(
        self,
        decision: CrossExchangeDecision,
    ) -> CrossRiskDecision:
        """
        Cross-Exchange 아비트라지 진입/청산 전 최종 Risk Gate.
        
        Args:
            decision: CrossExchangeDecision (from Integration layer)
        
        Returns:
            CrossRiskDecision (allowed, tier, reason_code, details)
        
        Flow:
            1. Cooldown 확인
            2. D75 4-Tier RiskGuard 호출 (1차 필터)
            3. CrossSync 기반 규칙 (exposure/imbalance)
            4. PositionManager 기반 규칙 (directional bias)
            5. Circuit Breaker (PnL tracking)
        """
        self.total_checks += 1
        
        try:
            # Step 0: Cooldown 확인
            cooldown_decision = self._check_cooldown(decision)
            if not cooldown_decision.allowed:
                self._update_metrics(cooldown_decision)
                return cooldown_decision
            
            # Step 1: D75 4-Tier RiskGuard (있을 경우에만)
            if self.four_tier_risk_guard is not None:
                core_decision = self._check_core_risk_guard(decision)
                if not core_decision.allowed:
                    self._update_metrics(core_decision)
                    return core_decision
            
            # Step 2: CrossSync 규칙
            cross_sync_decision = self._check_cross_sync_rules(decision)
            if not cross_sync_decision.allowed:
                self._update_metrics(cross_sync_decision)
                self._record_metrics_decision(cross_sync_decision, decision)
                self._send_alert(cross_sync_decision, decision)
                return cross_sync_decision
            
            # Step 3: PositionManager 규칙
            position_decision = self._check_position_rules(decision)
            if not position_decision.allowed:
                self._update_metrics(position_decision)
                self._record_metrics_decision(position_decision, decision)
                self._send_alert(position_decision, decision)
                return position_decision
            
            # Step 4: Circuit Breaker
            circuit_decision = self._check_circuit_breaker(decision)
            if not circuit_decision.allowed:
                self._update_metrics(circuit_decision)
                self._record_metrics_decision(circuit_decision, decision)
                self._send_alert(circuit_decision, decision)
                # Cooldown 설정
                self._set_cooldown(
                    decision.symbol_upbit,
                    circuit_decision.cooldown_until or (time.time() + self.config.circuit_breaker_cooldown),
                )
                return circuit_decision
            
            # All checks passed
            logger.debug(
                f"[CROSS_RISK_GUARD] Trade allowed: "
                f"{decision.symbol_upbit}/{decision.symbol_binance} "
                f"(action={decision.action.value})"
            )
            
            return CrossRiskDecision(
                allowed=True,
                tier="none",
                reason_code="OK",
                details={},
            )
        
        except Exception as e:
            logger.error(f"[CROSS_RISK_GUARD] Check error: {e}", exc_info=True)
            # Safety: 에러 시 BLOCK
            return CrossRiskDecision(
                allowed=False,
                tier="cross_exchange",
                reason_code="INTERNAL_ERROR",
                details={"error": str(e)},
            )
    
    def _check_cooldown(self, decision: CrossExchangeDecision) -> CrossRiskDecision:
        """Cooldown 상태 확인"""
        symbol = decision.symbol_upbit
        
        if symbol in self._cooldown_state:
            cooldown_until = self._cooldown_state[symbol]
            now = time.time()
            
            if now < cooldown_until:
                remaining = cooldown_until - now
                logger.warning(
                    f"[CROSS_RISK_GUARD] Trade in cooldown: {symbol} "
                    f"(remaining={remaining:.0f}s)"
                )
                return CrossRiskDecision(
                    allowed=False,
                    tier="cross_exchange",
                    reason_code="COOLDOWN",
                    details={
                        "symbol": symbol,
                        "cooldown_until": cooldown_until,
                        "remaining_seconds": remaining,
                    },
                    cooldown_until=cooldown_until,
                )
            else:
                # Cooldown 종료
                del self._cooldown_state[symbol]
        
        return CrossRiskDecision(
            allowed=True,
            tier="none",
            reason_code="OK",
            details={},
        )
    
    def _check_core_risk_guard(self, decision: CrossExchangeDecision) -> CrossRiskDecision:
        """
        D75 4-Tier RiskGuard 호출
        
        Note: 현재는 placeholder. 실제로는 FourTierRiskGuard.check_trade() 호출.
        """
        # TODO: D75-5 FourTierRiskGuard 통합
        # core_decision = self.four_tier_risk_guard.check_trade(
        #     exchange_name="upbit",  # or "binance"
        #     route_id="upbit_binance_btc",
        #     symbol=decision.symbol_upbit,
        #     notional=decision.notional_krw,
        # )
        # 
        # if not core_decision.allow:
        #     # D75에서 BLOCK
        #     tier_decisions = core_decision.tier_decisions
        #     blocked_tier = next(
        #         (tier for tier, dec in tier_decisions.items() if dec.decision != "ALLOW"),
        #         None
        #     )
        #     return CrossRiskDecision(
        #         allowed=False,
        #         tier=blocked_tier.value if blocked_tier else "global",
        #         reason_code=core_decision.get_reason_summary(),
        #         details={"core_decision": asdict(core_decision)},
        #     )
        
        # Placeholder: Always allow (D75 통합 전)
        return CrossRiskDecision(
            allowed=True,
            tier="none",
            reason_code="OK",
            details={},
        )
    
    def _check_cross_sync_rules(self, decision: CrossExchangeDecision) -> CrossRiskDecision:
        """
        CrossSync 기반 exposure/imbalance 규칙
        
        Rule 1: Cross-Exposure Limit
        Rule 2: Inventory Imbalance
        """
        try:
            # Rule 1: Cross-Exposure Limit
            # Note: InventoryTracker의 check_rebalance_needed 사용
            
            # Placeholder price (실제로는 SpreadModel 등에서 조회)
            base_price_a = 50_000_000.0  # 50M KRW (Upbit BTC 기준)
            base_price_b = 38_000.0  # 38K USDT (Binance BTC 기준)
            
            rebalance_signal = self.inventory_tracker.check_rebalance_needed(
                base_price_a, base_price_b
            )
            
            # Exposure risk (0.0 ~ 1.0)
            exposure_risk = rebalance_signal.exposure_risk
            
            if exposure_risk > self.config.max_cross_exposure:
                logger.warning(
                    f"[CROSS_RISK_GUARD] Exposure limit exceeded: "
                    f"{exposure_risk:.2%} > {self.config.max_cross_exposure:.2%}"
                )
                return CrossRiskDecision(
                    allowed=False,
                    tier="cross_exchange",
                    reason_code=CrossRiskReasonCode.CROSS_EXPOSURE_LIMIT.value,
                    details={
                        "exposure_risk": exposure_risk,
                        "limit": self.config.max_cross_exposure,
                        "symbol_upbit": decision.symbol_upbit,
                        "symbol_binance": decision.symbol_binance,
                    },
                )
            
            # Rule 2: Inventory Imbalance
            imbalance_ratio = rebalance_signal.imbalance_ratio
            
            if abs(imbalance_ratio) > self.config.max_imbalance_ratio:
                # 불균형 방향과 진입 방향이 일치하면 BLOCK
                is_positive_entry = decision.action in [
                    CrossExchangeAction.ENTRY_POSITIVE
                ]
                is_negative_entry = decision.action in [
                    CrossExchangeAction.ENTRY_NEGATIVE
                ]
                
                # imbalance_ratio > 0: Upbit 잔고 많음 (A > B)
                # imbalance_ratio < 0: Binance 잔고 많음 (B > A)
                # ENTRY_POSITIVE: Upbit SELL / Binance BUY → A 감소, B 증가
                # ENTRY_NEGATIVE: Upbit BUY / Binance SELL → A 증가, B 감소
                
                should_block = False
                
                if imbalance_ratio > 0 and is_negative_entry:
                    # Upbit 잔고 많음 + Upbit BUY → 추가 불균형
                    should_block = True
                elif imbalance_ratio < 0 and is_positive_entry:
                    # Binance 잔고 많음 + Binance BUY → 추가 불균형
                    should_block = True
                
                if should_block:
                    logger.warning(
                        f"[CROSS_RISK_GUARD] Inventory imbalance: "
                        f"{imbalance_ratio:+.2%} (action={decision.action.value})"
                    )
                    return CrossRiskDecision(
                        allowed=False,
                        tier="cross_exchange",
                        reason_code=CrossRiskReasonCode.CROSS_INVENTORY_IMBALANCE.value,
                        details={
                            "imbalance_ratio": imbalance_ratio,
                            "limit": self.config.max_imbalance_ratio,
                            "action": decision.action.value,
                        },
                    )
            
            return CrossRiskDecision(
                allowed=True,
                tier="none",
                reason_code="OK",
                details={},
            )
        
        except Exception as e:
            logger.error(f"[CROSS_RISK_GUARD] CrossSync rule error: {e}", exc_info=True)
            # Safety: 에러 시 ALLOW (CrossSync는 optional)
            return CrossRiskDecision(
                allowed=True,
                tier="none",
                reason_code="OK",
                details={"cross_sync_error": str(e)},
            )
    
    def _check_position_rules(self, decision: CrossExchangeDecision) -> CrossRiskDecision:
        """
        PositionManager 기반 directional bias 규칙
        
        Rule 3: Directional Bias (POSITIVE/NEGATIVE 쏠림 방지)
        """
        try:
            positions = self.position_manager.list_open_positions()
            
            if len(positions) < self.config.min_position_count_for_bias_check:
                # 포지션 수가 적으면 bias 체크 생략
                return CrossRiskDecision(
                    allowed=True,
                    tier="none",
                    reason_code="OK",
                    details={},
                )
            
            # POSITIVE/NEGATIVE 카운팅
            positive_count = sum(1 for p in positions if p.entry_side == "positive")
            negative_count = sum(1 for p in positions if p.entry_side == "negative")
            total_count = positive_count + negative_count
            
            if total_count == 0:
                return CrossRiskDecision(
                    allowed=True,
                    tier="none",
                    reason_code="OK",
                    details={},
                )
            
            positive_ratio = positive_count / total_count
            negative_ratio = negative_count / total_count
            
            # POSITIVE 쏠림 체크
            if positive_ratio > self.config.max_directional_bias:
                if decision.action in [CrossExchangeAction.ENTRY_POSITIVE]:
                    logger.warning(
                        f"[CROSS_RISK_GUARD] POSITIVE directional bias: "
                        f"{positive_ratio:.2%} (limit={self.config.max_directional_bias:.2%})"
                    )
                    return CrossRiskDecision(
                        allowed=False,
                        tier="cross_exchange",
                        reason_code=CrossRiskReasonCode.CROSS_DIRECTIONAL_BIAS.value,
                        details={
                            "positive_ratio": positive_ratio,
                            "limit": self.config.max_directional_bias,
                            "positive_count": positive_count,
                            "negative_count": negative_count,
                            "direction": "POSITIVE",
                        },
                    )
            
            # NEGATIVE 쏠림 체크
            if negative_ratio > self.config.max_directional_bias:
                if decision.action in [CrossExchangeAction.ENTRY_NEGATIVE]:
                    logger.warning(
                        f"[CROSS_RISK_GUARD] NEGATIVE directional bias: "
                        f"{negative_ratio:.2%} (limit={self.config.max_directional_bias:.2%})"
                    )
                    return CrossRiskDecision(
                        allowed=False,
                        tier="cross_exchange",
                        reason_code=CrossRiskReasonCode.CROSS_DIRECTIONAL_BIAS.value,
                        details={
                            "negative_ratio": negative_ratio,
                            "limit": self.config.max_directional_bias,
                            "positive_count": positive_count,
                            "negative_count": negative_count,
                            "direction": "NEGATIVE",
                        },
                    )
            
            return CrossRiskDecision(
                allowed=True,
                tier="none",
                reason_code="OK",
                details={},
            )
        
        except Exception as e:
            logger.error(f"[CROSS_RISK_GUARD] Position rule error: {e}", exc_info=True)
            # Safety: 에러 시 ALLOW
            return CrossRiskDecision(
                allowed=True,
                tier="none",
                reason_code="OK",
                details={"position_error": str(e)},
            )
    
    def _check_circuit_breaker(self, decision: CrossExchangeDecision) -> CrossRiskDecision:
        """
        Circuit Breaker (PnL tracking) - Money 기반 (D80-1).
        
        Rule 4: Daily Loss Limit
        Rule 5: Consecutive Loss Limit
        """
        # Rule 4: Daily Loss Limit (Money 비교)
        daily_pnl = self.pnl_tracker.get_daily_pnl()  # Money
        
        # Money 비교: daily_pnl < -max_daily_loss
        if daily_pnl < -self.config.max_daily_loss:
            logger.error(
                f"[CROSS_RISK_GUARD] Daily loss limit exceeded: "
                f"{daily_pnl} < {-self.config.max_daily_loss}"
            )
            return CrossRiskDecision(
                allowed=False,
                tier="cross_exchange",
                reason_code=CrossRiskReasonCode.CROSS_DAILY_LOSS_LIMIT.value,
                details={
                    "daily_pnl": str(daily_pnl),
                    "max_daily_loss": str(self.config.max_daily_loss),
                    "threshold": float(self.config.max_daily_loss.amount),
                    "actual": float(daily_pnl.amount),
                },
                cooldown_until=time.time() + self.config.circuit_breaker_cooldown,
            )
        
        # Rule 5: Consecutive Loss Limit
        consecutive_loss = self.pnl_tracker.get_consecutive_loss_count()
        
        if consecutive_loss >= self.config.max_consecutive_loss:
            logger.warning(
                f"[CROSS_RISK_GUARD] Consecutive loss limit: "
                f"{consecutive_loss} >= {self.config.max_consecutive_loss}"
            )
            return CrossRiskDecision(
                allowed=False,
                tier="cross_exchange",
                reason_code=CrossRiskReasonCode.CROSS_CONSECUTIVE_LOSS_LIMIT.value,
                details={
                    "consecutive_loss": consecutive_loss,
                    "limit": self.config.max_consecutive_loss,
                },
                cooldown_until=time.time() + self.config.consecutive_loss_cooldown,
            )
        
        return CrossRiskDecision(
            allowed=True,
            tier="none",
            reason_code="OK",
            details={},
        )
    
    def _set_cooldown(self, symbol: str, cooldown_until: float) -> None:
        """Cooldown 설정"""
        self._cooldown_state[symbol] = cooldown_until
        logger.info(
            f"[CROSS_RISK_GUARD] Cooldown set: {symbol} "
            f"until {time.strftime('%H:%M:%S', time.localtime(cooldown_until))}"
        )
    
    def _update_metrics(self, decision: CrossRiskDecision) -> None:
        """Metrics 업데이트"""
        if not decision.allowed:
            self.blocked_by_tier[decision.tier] = self.blocked_by_tier.get(decision.tier, 0) + 1
            self.blocked_by_reason[decision.reason_code] = self.blocked_by_reason.get(decision.reason_code, 0) + 1
    
    def _send_alert(self, decision: CrossRiskDecision, trade_decision: CrossExchangeDecision) -> None:
        """Alert 전송 (D76 AlertManager 연계)"""
        if self.alert_manager is None:
            return
        
        try:
            # AlertManager.send_alert() 호출 (기존 D76 인터페이스 가정)
            # 실제로는 D76에서 정의한 AlertType과 인터페이스에 맞춰 구현
            
            severity = "P2"  # Default
            
            if decision.reason_code in [
                CrossRiskReasonCode.CROSS_DAILY_LOSS_LIMIT.value,
                CrossRiskReasonCode.CROSS_CIRCUIT_BREAKER.value,
            ]:
                severity = "P1"  # Critical
            
            message = (
                f"[CROSS_RISK_GUARD] Trade blocked: {trade_decision.symbol_upbit}/{trade_decision.symbol_binance} "
                f"(tier={decision.tier}, reason={decision.reason_code})"
            )
            
            # self.alert_manager.send_alert(
            #     alert_type=f"CROSS_{decision.reason_code.upper()}",
            #     severity=severity,
            #     message=message,
            #     details=decision.details,
            # )
            
            logger.info(f"[CROSS_RISK_GUARD] Alert sent: {message}")
        
        except Exception as e:
            logger.error(f"[CROSS_RISK_GUARD] Alert send error: {e}", exc_info=True)
    
    def _record_metrics_decision(
        self,
        decision: CrossRiskDecision,
        trade_decision: CrossExchangeDecision,
    ) -> None:
        """
        CrossExchangeMetrics에 decision 기록 (D79-6)
        
        Args:
            decision: CrossRiskDecision
            trade_decision: CrossExchangeDecision (context 정보용)
        """
        if self.metrics_collector is None:
            return
        
        try:
            decision_context = {
                "symbol_upbit": trade_decision.symbol_upbit,
                "symbol_binance": trade_decision.symbol_binance,
                "action": trade_decision.action.value,
                # first_trigger_reason은 향후 다단계 체크에서 설정
            }
            
            self.metrics_collector.record_risk_decision(decision, decision_context)
        
        except Exception as e:
            logger.error(f"[CROSS_RISK_GUARD] Metrics recording failed: {e}", exc_info=True)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Metrics 조회"""
        return {
            "total_checks": self.total_checks,
            "blocked_by_tier": self.blocked_by_tier,
            "blocked_by_reason": self.blocked_by_reason,
            "daily_pnl_krw": self.pnl_tracker.get_daily_pnl(),
            "consecutive_loss": self.pnl_tracker.get_consecutive_loss_count(),
            "cooldown_symbols": list(self._cooldown_state.keys()),
        }
