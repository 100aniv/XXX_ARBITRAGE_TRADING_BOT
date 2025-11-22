"""
D75-5: 4-Tier RiskGuard

4개 계층 리스크 관리:
- Tier 1: ExchangeGuard (거래소 레벨)
- Tier 2: RouteGuard (Route 레벨)
- Tier 3: SymbolGuard (Symbol 레벨)
- Tier 4: GlobalGuard (Portfolio 레벨)

각 Tier는 독립적으로 평가하고, 최종 결정은 가장 보수적인 Tier를 따름.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from arbitrage.domain.arb_route import RouteScore
from arbitrage.infrastructure.exchange_health import ExchangeHealthStatus, HealthMetrics


class GuardTier(Enum):
    """Guard Tier"""
    EXCHANGE = "exchange"
    ROUTE = "route"
    SYMBOL = "symbol"
    GLOBAL = "global"


class GuardDecisionType(Enum):
    """Guard decision 유형"""
    ALLOW = "allow"  # 허용
    BLOCK = "block"  # 차단
    DEGRADE = "degrade"  # 축소 허용
    COOLDOWN_ONLY = "cooldown_only"  # Cooldown 중 (일시 차단)


class GuardReasonCode(Enum):
    """Guard decision 이유 코드"""
    # Exchange reasons
    EXCHANGE_HEALTH_DOWN = "exchange_health_down"
    EXCHANGE_HEALTH_FROZEN = "exchange_health_frozen"
    EXCHANGE_HEALTH_DEGRADED = "exchange_health_degraded"
    EXCHANGE_DAILY_LOSS_LIMIT = "exchange_daily_loss_limit"
    EXCHANGE_RATE_LIMIT_EXHAUSTED = "exchange_rate_limit_exhausted"
    
    # Route reasons
    ROUTE_SCORE_LOW = "route_score_low"
    ROUTE_STREAK_LOSS = "route_streak_loss"
    ROUTE_SPREAD_ABNORMAL = "route_spread_abnormal"
    ROUTE_INVENTORY_PENALTY = "route_inventory_penalty"
    
    # Symbol reasons
    SYMBOL_EXPOSURE_HIGH = "symbol_exposure_high"
    SYMBOL_DD_HIGH = "symbol_dd_high"
    SYMBOL_VOLATILITY_HIGH = "symbol_volatility_high"
    
    # Global reasons
    GLOBAL_DD_LIMIT = "global_dd_limit"
    GLOBAL_EXPOSURE_LIMIT = "global_exposure_limit"
    GLOBAL_IMBALANCE_HIGH = "global_imbalance_high"
    
    # OK
    OK = "ok"


@dataclass
class TierDecision:
    """각 Tier의 결정"""
    tier: GuardTier
    decision: GuardDecisionType
    max_notional: Optional[float] = None  # 최대 거래 금액 (degraded 시)
    cooldown_seconds: float = 0.0  # Cooldown 시간
    reasons: List[GuardReasonCode] = field(default_factory=list)
    details: str = ""


@dataclass
class RiskGuardDecision:
    """
    4-Tier RiskGuard 최종 결정.
    
    모든 Tier 중 가장 보수적인 결정을 따름.
    """
    allow: bool
    degraded: bool  # 축소 허용 여부
    cooldown_seconds: float  # Cooldown 시간
    max_notional: Optional[float]  # 최대 거래 금액
    tier_decisions: Dict[GuardTier, TierDecision] = field(default_factory=dict)
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def get_reason_summary(self) -> str:
        """전체 이유 요약"""
        if self.allow and not self.degraded:
            return "ALL_TIERS_OK"
        
        blocked_tiers = [
            f"{tier.value}:{','.join(r.value for r in dec.reasons)}"
            for tier, dec in self.tier_decisions.items()
            if dec.decision in (GuardDecisionType.BLOCK, GuardDecisionType.COOLDOWN_ONLY, GuardDecisionType.DEGRADE)
        ]
        return "; ".join(blocked_tiers)


# ============================================================================
# Configuration Classes
# ============================================================================

@dataclass
class ExchangeGuardConfig:
    """Exchange Guard 설정"""
    max_daily_loss_usd: float = 10000.0  # 일일 최대 손실 (USD)
    rate_limit_buffer_pct: float = 0.2  # Rate limit 여유분 (20%)
    health_status_block_on_down: bool = True  # DOWN 상태 시 차단
    health_status_degrade_on_degraded: bool = True  # DEGRADED 상태 시 축소
    degrade_notional_multiplier: float = 0.5  # DEGRADED 시 거래 금액 배수


@dataclass
class RouteGuardConfig:
    """Route Guard 설정"""
    min_route_score: float = 50.0  # 최소 route score
    max_streak_loss: int = 3  # 최대 연속 손실 횟수
    abnormal_spread_threshold_bps: float = 500.0  # 비정상 스프레드 (500 bps = 5%)
    cooldown_after_streak_loss: float = 300.0  # Streak loss 후 cooldown (5분)


@dataclass
class SymbolGuardConfig:
    """Symbol Guard 설정"""
    max_exposure_ratio: float = 0.5  # 최대 exposure 비율 (50%)
    max_dd_ratio: float = 0.2  # 최대 drawdown 비율 (20%)
    high_volatility_threshold: float = 0.1  # 고변동성 기준 (10%)


@dataclass
class GlobalGuardConfig:
    """Global Guard 설정"""
    max_global_daily_loss_usd: float = 50000.0  # 전역 일일 최대 손실
    max_total_exposure_usd: float = 100000.0  # 전역 최대 exposure
    max_imbalance_ratio: float = 0.5  # 최대 cross-exchange imbalance (50%)
    max_exposure_risk: float = 0.8  # 최대 exposure risk (80%)


@dataclass
class FourTierRiskGuardConfig:
    """4-Tier RiskGuard 전체 설정"""
    exchange: ExchangeGuardConfig = field(default_factory=ExchangeGuardConfig)
    route: RouteGuardConfig = field(default_factory=RouteGuardConfig)
    symbol: SymbolGuardConfig = field(default_factory=SymbolGuardConfig)
    global_guard: GlobalGuardConfig = field(default_factory=GlobalGuardConfig)


# ============================================================================
# State/Snapshot Classes
# ============================================================================

@dataclass
class ExchangeState:
    """거래소 레벨 상태"""
    exchange_name: str
    health_status: ExchangeHealthStatus
    health_metrics: HealthMetrics
    rate_limit_remaining_pct: float  # 0.0 ~ 1.0
    daily_loss_usd: float  # 오늘 누적 손실 (USD)
    open_trade_count: int = 0


@dataclass
class RouteState:
    """Route 레벨 상태"""
    symbol_a: str
    symbol_b: str
    route_score: Optional[RouteScore] = None
    gross_spread_bps: float = 0.0
    recent_trades: List[float] = field(default_factory=list)  # 최근 PnL 리스트
    last_trade_timestamp: float = 0.0
    
    def get_streak_loss_count(self) -> int:
        """연속 손실 횟수 계산"""
        if not self.recent_trades:
            return 0
        
        streak = 0
        for pnl in reversed(self.recent_trades):
            if pnl < 0:
                streak += 1
            else:
                break
        return streak


@dataclass
class SymbolState:
    """Symbol 레벨 상태"""
    symbol: str  # Unified symbol (e.g., "BTC")
    total_exposure_usd: float  # 총 exposure (USD)
    total_notional_usd: float  # 총 notional (USD)
    unrealized_pnl_usd: float  # 미실현 손익
    intraday_pnl_usd: float  # 당일 손익
    intraday_peak_usd: float  # 당일 최고점
    volatility_proxy: float = 0.0  # 변동성 proxy (간단히 가격 변화율)
    
    def get_drawdown_ratio(self) -> float:
        """Drawdown 비율 계산"""
        if self.intraday_peak_usd <= 0:
            return 0.0
        return max(0.0, (self.intraday_peak_usd - self.intraday_pnl_usd) / self.intraday_peak_usd)
    
    def get_exposure_ratio(self, total_portfolio_value: float) -> float:
        """Exposure 비율 계산"""
        if total_portfolio_value <= 0:
            return 0.0
        return self.total_exposure_usd / total_portfolio_value


@dataclass
class GlobalState:
    """Global 레벨 상태"""
    total_portfolio_value_usd: float  # 총 포트폴리오 가치
    total_exposure_usd: float  # 총 exposure
    total_margin_used_usd: float  # 총 증거금 사용량
    global_daily_loss_usd: float  # 전역 일일 손실
    global_cumulative_loss_usd: float  # 전역 누적 손실
    cross_exchange_imbalance_ratio: float  # Cross-exchange imbalance (-1.0 ~ 1.0)
    cross_exchange_exposure_risk: float  # Cross-exchange exposure risk (0.0 ~ 1.0)


# ============================================================================
# Core RiskGuard Class
# ============================================================================

class FourTierRiskGuard:
    """
    4-Tier RiskGuard.
    
    각 Tier를 독립적으로 평가하고, 가장 보수적인 결정을 최종 결정으로 사용.
    """
    
    def __init__(self, config: FourTierRiskGuardConfig):
        """
        Args:
            config: 4-Tier RiskGuard 설정
        """
        self.config = config
        
        # Tier별 cooldown 추적
        self._route_cooldown_until: Dict[Tuple[str, str], float] = {}  # (symbol_a, symbol_b) -> cooldown_until
    
    def evaluate(
        self,
        exchange_states: Dict[str, ExchangeState],  # exchange_name -> ExchangeState
        route_state: RouteState,
        symbol_states: Dict[str, SymbolState],  # symbol -> SymbolState
        global_state: GlobalState,
    ) -> RiskGuardDecision:
        """
        4-Tier RiskGuard 평가.
        
        Args:
            exchange_states: 거래소별 상태
            route_state: Route 상태
            symbol_states: Symbol별 상태
            global_state: Global 상태
        
        Returns:
            RiskGuardDecision
        """
        tier_decisions = {}
        
        # Tier 1: Exchange Guard
        tier_decisions[GuardTier.EXCHANGE] = self._evaluate_exchange(exchange_states)
        
        # Tier 2: Route Guard
        tier_decisions[GuardTier.ROUTE] = self._evaluate_route(route_state)
        
        # Tier 3: Symbol Guard
        tier_decisions[GuardTier.SYMBOL] = self._evaluate_symbol(
            symbol_states, global_state.total_portfolio_value_usd
        )
        
        # Tier 4: Global Guard
        tier_decisions[GuardTier.GLOBAL] = self._evaluate_global(global_state)
        
        # Aggregate: 가장 보수적인 결정 선택
        return self._aggregate_decisions(tier_decisions)
    
    def _evaluate_exchange(
        self,
        exchange_states: Dict[str, ExchangeState],
    ) -> TierDecision:
        """Tier 1: Exchange Guard 평가"""
        config = self.config.exchange
        reasons = []
        decision_type = GuardDecisionType.ALLOW
        max_notional = None
        cooldown_seconds = 0.0
        
        for exchange_name, state in exchange_states.items():
            # Health status check
            if state.health_status == ExchangeHealthStatus.DOWN and config.health_status_block_on_down:
                reasons.append(GuardReasonCode.EXCHANGE_HEALTH_DOWN)
                decision_type = GuardDecisionType.BLOCK
            elif state.health_status == ExchangeHealthStatus.FROZEN:
                reasons.append(GuardReasonCode.EXCHANGE_HEALTH_FROZEN)
                decision_type = GuardDecisionType.BLOCK
            elif state.health_status == ExchangeHealthStatus.DEGRADED and config.health_status_degrade_on_degraded:
                reasons.append(GuardReasonCode.EXCHANGE_HEALTH_DEGRADED)
                if decision_type == GuardDecisionType.ALLOW:
                    decision_type = GuardDecisionType.DEGRADE
            
            # Daily loss limit check
            if state.daily_loss_usd > config.max_daily_loss_usd:
                reasons.append(GuardReasonCode.EXCHANGE_DAILY_LOSS_LIMIT)
                decision_type = GuardDecisionType.BLOCK
            
            # Rate limit check
            if state.rate_limit_remaining_pct < config.rate_limit_buffer_pct:
                reasons.append(GuardReasonCode.EXCHANGE_RATE_LIMIT_EXHAUSTED)
                if decision_type == GuardDecisionType.ALLOW:
                    decision_type = GuardDecisionType.DEGRADE
        
        # Degrade 시 notional 축소
        if decision_type == GuardDecisionType.DEGRADE:
            max_notional = None  # Caller가 현재 notional * multiplier 적용
        
        if not reasons:
            reasons.append(GuardReasonCode.OK)
        
        return TierDecision(
            tier=GuardTier.EXCHANGE,
            decision=decision_type,
            max_notional=max_notional,
            cooldown_seconds=cooldown_seconds,
            reasons=reasons,
            details=f"Exchanges: {', '.join(exchange_states.keys())}"
        )
    
    def _evaluate_route(
        self,
        route_state: RouteState,
    ) -> TierDecision:
        """Tier 2: Route Guard 평가"""
        config = self.config.route
        reasons = []
        decision_type = GuardDecisionType.ALLOW
        cooldown_seconds = 0.0
        
        # Cooldown check
        route_key = (route_state.symbol_a, route_state.symbol_b)
        if route_key in self._route_cooldown_until:
            if time.time() < self._route_cooldown_until[route_key]:
                remaining = self._route_cooldown_until[route_key] - time.time()
                return TierDecision(
                    tier=GuardTier.ROUTE,
                    decision=GuardDecisionType.COOLDOWN_ONLY,
                    cooldown_seconds=remaining,
                    reasons=[GuardReasonCode.ROUTE_STREAK_LOSS],
                    details=f"Cooldown until {self._route_cooldown_until[route_key]:.0f}"
                )
            else:
                # Cooldown 만료
                del self._route_cooldown_until[route_key]
        
        # Route score check
        if route_state.route_score:
            total_score = route_state.route_score.total_score()
            if total_score < config.min_route_score:
                reasons.append(GuardReasonCode.ROUTE_SCORE_LOW)
                decision_type = GuardDecisionType.BLOCK
        
        # Streak loss check
        streak_loss = route_state.get_streak_loss_count()
        if streak_loss >= config.max_streak_loss:
            reasons.append(GuardReasonCode.ROUTE_STREAK_LOSS)
            decision_type = GuardDecisionType.BLOCK
            cooldown_seconds = config.cooldown_after_streak_loss
            # Set cooldown
            self._route_cooldown_until[route_key] = time.time() + cooldown_seconds
        
        # Abnormal spread check
        if route_state.gross_spread_bps > config.abnormal_spread_threshold_bps:
            reasons.append(GuardReasonCode.ROUTE_SPREAD_ABNORMAL)
            decision_type = GuardDecisionType.DEGRADE  # 의심스러운 spread → 사이즈 축소
        
        # Inventory penalty check (from RouteScore)
        if route_state.route_score and route_state.route_score.inventory_penalty < 50.0:
            reasons.append(GuardReasonCode.ROUTE_INVENTORY_PENALTY)
            if decision_type == GuardDecisionType.ALLOW:
                decision_type = GuardDecisionType.DEGRADE
        
        if not reasons:
            reasons.append(GuardReasonCode.OK)
        
        return TierDecision(
            tier=GuardTier.ROUTE,
            decision=decision_type,
            cooldown_seconds=cooldown_seconds,
            reasons=reasons,
            details=f"Route: {route_state.symbol_a}-{route_state.symbol_b}, Streak: {streak_loss}"
        )
    
    def _evaluate_symbol(
        self,
        symbol_states: Dict[str, SymbolState],
        total_portfolio_value: float,
    ) -> TierDecision:
        """Tier 3: Symbol Guard 평가"""
        config = self.config.symbol
        reasons = []
        decision_type = GuardDecisionType.ALLOW
        
        for symbol, state in symbol_states.items():
            # Exposure ratio check
            exposure_ratio = state.get_exposure_ratio(total_portfolio_value)
            if exposure_ratio > config.max_exposure_ratio:
                reasons.append(GuardReasonCode.SYMBOL_EXPOSURE_HIGH)
                decision_type = GuardDecisionType.DEGRADE
            
            # Drawdown check
            dd_ratio = state.get_drawdown_ratio()
            if dd_ratio > config.max_dd_ratio:
                reasons.append(GuardReasonCode.SYMBOL_DD_HIGH)
                if decision_type == GuardDecisionType.ALLOW:
                    decision_type = GuardDecisionType.BLOCK
            
            # Volatility check
            if state.volatility_proxy > config.high_volatility_threshold:
                reasons.append(GuardReasonCode.SYMBOL_VOLATILITY_HIGH)
                if decision_type == GuardDecisionType.ALLOW:
                    decision_type = GuardDecisionType.DEGRADE
        
        if not reasons:
            reasons.append(GuardReasonCode.OK)
        
        return TierDecision(
            tier=GuardTier.SYMBOL,
            decision=decision_type,
            reasons=reasons,
            details=f"Symbols: {', '.join(symbol_states.keys())}"
        )
    
    def _evaluate_global(
        self,
        global_state: GlobalState,
    ) -> TierDecision:
        """Tier 4: Global Guard 평가"""
        config = self.config.global_guard
        reasons = []
        decision_type = GuardDecisionType.ALLOW
        
        # Global daily loss check
        if global_state.global_daily_loss_usd > config.max_global_daily_loss_usd:
            reasons.append(GuardReasonCode.GLOBAL_DD_LIMIT)
            decision_type = GuardDecisionType.BLOCK
        
        # Total exposure check
        if global_state.total_exposure_usd > config.max_total_exposure_usd:
            reasons.append(GuardReasonCode.GLOBAL_EXPOSURE_LIMIT)
            decision_type = GuardDecisionType.BLOCK
        
        # Cross-exchange imbalance check
        if abs(global_state.cross_exchange_imbalance_ratio) > config.max_imbalance_ratio:
            reasons.append(GuardReasonCode.GLOBAL_IMBALANCE_HIGH)
            decision_type = GuardDecisionType.BLOCK  # Rebalance 우선
        
        # Cross-exchange exposure risk check
        if global_state.cross_exchange_exposure_risk > config.max_exposure_risk:
            reasons.append(GuardReasonCode.GLOBAL_IMBALANCE_HIGH)
            if decision_type == GuardDecisionType.ALLOW:
                decision_type = GuardDecisionType.DEGRADE
        
        if not reasons:
            reasons.append(GuardReasonCode.OK)
        
        return TierDecision(
            tier=GuardTier.GLOBAL,
            decision=decision_type,
            reasons=reasons,
            details=f"Global exposure: {global_state.total_exposure_usd:.0f} USD"
        )
    
    def _aggregate_decisions(
        self,
        tier_decisions: Dict[GuardTier, TierDecision],
    ) -> RiskGuardDecision:
        """
        Tier별 결정을 aggregation (가장 보수적인 결정 선택).
        
        우선순위:
        1. BLOCK > COOLDOWN_ONLY > DEGRADE > ALLOW
        2. Cooldown: 최대값 선택
        3. Max notional: 최소값 선택
        """
        # Decision priority
        decision_priority = {
            GuardDecisionType.BLOCK: 4,
            GuardDecisionType.COOLDOWN_ONLY: 3,
            GuardDecisionType.DEGRADE: 2,
            GuardDecisionType.ALLOW: 1,
        }
        
        # Find strictest decision
        strictest_decision = GuardDecisionType.ALLOW
        for tier, tier_dec in tier_decisions.items():
            if decision_priority[tier_dec.decision] > decision_priority[strictest_decision]:
                strictest_decision = tier_dec.decision
        
        # Aggregate cooldown (max)
        max_cooldown = max(
            (tier_dec.cooldown_seconds for tier_dec in tier_decisions.values()),
            default=0.0
        )
        
        # Aggregate max_notional (min, if DEGRADE)
        max_notional = None
        if strictest_decision == GuardDecisionType.DEGRADE:
            notionals = [
                tier_dec.max_notional
                for tier_dec in tier_decisions.values()
                if tier_dec.max_notional is not None
            ]
            if notionals:
                max_notional = min(notionals)
        
        # Final decision
        allow = strictest_decision == GuardDecisionType.ALLOW
        degraded = strictest_decision == GuardDecisionType.DEGRADE
        
        # COOLDOWN_ONLY는 allow=False
        if strictest_decision == GuardDecisionType.COOLDOWN_ONLY:
            allow = False
            degraded = False
        
        # BLOCK은 allow=False
        if strictest_decision == GuardDecisionType.BLOCK:
            allow = False
            degraded = False
        
        return RiskGuardDecision(
            allow=allow,
            degraded=degraded,
            cooldown_seconds=max_cooldown,
            max_notional=max_notional,
            tier_decisions=tier_decisions,
        )
