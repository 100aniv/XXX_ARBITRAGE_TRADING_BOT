"""
D76: Alerting Infrastructure + D80-7: Cross-Exchange Alert Layer

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
- FX_LAYER (D80-7)
- EXECUTOR (D80-7)
- WS_CLIENT (D80-7)
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

# D80-7: Cross-Exchange Alert Layer
from .alert_types import (
    AlertCategory,
    AlertRuleDefinition,
    ALERT_RULES,
    get_alert_rule,
    format_alert,
)
from .throttler import AlertThrottler
from .aggregator import AlertAggregator, AggregatedAlert
from .queue import AlertQueue
from .config import (
    AlertConfig,
    TelegramConfig,
    SlackConfig,
    ThrottlerConfig,
    AggregatorConfig,
    QueueConfig,
    get_alert_config,
    reload_alert_config,
)

# D80-7-INT: Alert Integration Helpers
from .helpers import (
    emit_rule_based_alert,
    emit_fx_source_down_alert,
    emit_fx_all_sources_down_alert,
    emit_fx_median_deviation_alert,
    emit_fx_staleness_alert,
    emit_executor_order_error_alert,
    emit_executor_rollback_alert,
    emit_circuit_breaker_alert,
    emit_risk_limit_alert,
    emit_ws_staleness_alert,
    emit_ws_reconnect_failed_alert,
)

__all__ = [
    # D76
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
    # D80-7
    "AlertCategory",
    "AlertRuleDefinition",
    "ALERT_RULES",
    "get_alert_rule",
    "format_alert",
    "AlertThrottler",
    "AlertAggregator",
    "AggregatedAlert",
    "AlertQueue",
    "AlertConfig",
    "TelegramConfig",
    "SlackConfig",
    "ThrottlerConfig",
    "AggregatorConfig",
    "QueueConfig",
    "get_alert_config",
    "reload_alert_config",
    # D80-7-INT
    "emit_rule_based_alert",
    "emit_fx_source_down_alert",
    "emit_fx_all_sources_down_alert",
    "emit_fx_median_deviation_alert",
    "emit_fx_staleness_alert",
    "emit_executor_order_error_alert",
    "emit_executor_rollback_alert",
    "emit_circuit_breaker_alert",
    "emit_risk_limit_alert",
    "emit_ws_staleness_alert",
    "emit_ws_reconnect_failed_alert",
]
