"""
D76: Alerting Infrastructure

Alert severity classification:
- P0 (Critical): Service down, global risk limit breached
- P1 (High): Performance degradation, high error rate
- P2 (Medium): Component failure, resource exhaustion
- P3 (Low): Warnings, informational

Event sources:
- RateLimiter
- ExchangeHealth
- ArbRoute/ArbUniverse
- CrossSync
- 4-Tier RiskGuard
"""

from .models import AlertSeverity, AlertSource, AlertRecord
from .manager import AlertManager
from .rule_engine import (
    RuleEngine,
    RuleRegistry,
    AlertRule,
    AlertDispatchPlan,
    AlertChannel,
    Environment,
)

__all__ = [
    "AlertSeverity",
    "AlertSource",
    "AlertRecord",
    "AlertManager",
    "RuleEngine",
    "RuleRegistry",
    "AlertRule",
    "AlertDispatchPlan",
    "AlertChannel",
    "Environment",
]
