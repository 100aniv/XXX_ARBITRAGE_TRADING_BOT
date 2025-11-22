"""
D75-4/D75-5: Arbitrage Domain Layer

ArbRoute, ArbUniverse, CrossSync, RiskGuard 등
아비트라지 비즈니스 로직 계층
"""

from arbitrage.domain.market_spec import MarketSpec, ExchangeSpec
from arbitrage.domain.fee_model import FeeModel, FeeStructure
from arbitrage.domain.arb_route import (
    ArbRoute,
    ArbRouteDecision,
    RouteDirection,
    RouteScore,
)
from arbitrage.domain.arb_universe import (
    UniverseMode,
    UniverseProvider,
    UniverseDecision,
)
from arbitrage.domain.cross_sync import (
    Inventory,
    InventoryTracker,
    RebalanceSignal,
)
from arbitrage.domain.risk_guard import (
    FourTierRiskGuard,
    RiskGuardDecision,
    TierDecision,
    GuardTier,
    GuardDecisionType,
    GuardReasonCode,
    FourTierRiskGuardConfig,
    ExchangeGuardConfig,
    RouteGuardConfig,
    SymbolGuardConfig,
    GlobalGuardConfig,
    ExchangeState,
    RouteState,
    SymbolState,
    GlobalState,
)

__all__ = [
    "MarketSpec",
    "ExchangeSpec",
    "FeeModel",
    "FeeStructure",
    "ArbRoute",
    "ArbRouteDecision",
    "RouteDirection",
    "RouteScore",
    "UniverseMode",
    "UniverseProvider",
    "UniverseDecision",
    "Inventory",
    "InventoryTracker",
    "RebalanceSignal",
    "FourTierRiskGuard",
    "RiskGuardDecision",
    "TierDecision",
    "GuardTier",
    "GuardDecisionType",
    "GuardReasonCode",
    "FourTierRiskGuardConfig",
    "ExchangeGuardConfig",
    "RouteGuardConfig",
    "SymbolGuardConfig",
    "GlobalGuardConfig",
    "ExchangeState",
    "RouteState",
    "SymbolState",
    "GlobalState",
]
